from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy.optimize import minimize

try:
    from data_loader import fetch_stock_data
except ImportError:
    pass


def calculate_portfolio_weights(
    tickers, method="max_sharpe", risk_free_rate=0.03
):
    if isinstance(tickers, str):
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
    else:
        ticker_list = [t.strip().upper() for t in tickers]

    if not ticker_list:
        return {}

    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    df = fetch_stock_data(ticker_list, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return {ticker: 0.0 for ticker in ticker_list}

    valid_tickers = [t for t in ticker_list if t in df.columns]
    if not valid_tickers:
        return {}

    n = len(valid_tickers)
    returns = df[valid_tickers].pct_change().dropna()

    if method.lower() == "equal" or n == 1:
        weight = round(1.0 / n, 4)
        return {ticker: weight for ticker in valid_tickers}

    elif method.lower() == "max_sharpe":
        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252

        def neg_sharpe(weights):
            p_return = np.sum(mean_returns * weights)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            if p_vol == 0:
                return 0
            return -(p_return - risk_free_rate) / p_vol

        constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
        bounds = tuple((0.0, 1.0) for _ in range(n))
        init_guess = n * [1.0 / n]

        opt_results = minimize(
            neg_sharpe,
            init_guess,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        if opt_results.success:
            opt_weights = [round(w, 4) for w in opt_results.x]
            return dict(zip(valid_tickers, opt_weights))
        else:
            weight = round(1.0 / n, 4)
            return {ticker: weight for ticker in valid_tickers}

    else:
        raise ValueError(f"Unknown optimization method: {method}")


class RebalancingStrategy:
    """Evaluates portfolio drift and determines when asset rebalancing is required."""

    def __init__(self, tickers, method="max_sharpe", threshold=0.05):
        self.tickers = tickers
        self.method = method
        self.threshold = threshold

    def calculate_weights(self):
        """Wrapper method matching the dashboard's expected call signature."""
        return calculate_portfolio_weights(self.tickers, method=self.method)

    def check_rebalance_needed(self, current_portfolio_values):
        total_value = sum(current_portfolio_values.values())
        if total_value == 0:
            return True, self.calculate_weights()

        current_weights = {
            t: val / total_value for t, val in current_portfolio_values.items()
        }
        target_weights = self.calculate_weights()

        rebalance_triggered = False
        for ticker, target_w in target_weights.items():
            current_w = current_weights.get(ticker, 0.0)
            if abs(current_w - target_w) > self.threshold:
                rebalance_triggered = True
                break

        return rebalance_triggered, target_weights
