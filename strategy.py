import numpy as np
import pandas as pd
from scipy.optimize import minimize


class RebalancingStrategy:
    """
    Institutional Portfolio Optimization Engine using SciPy Convex Optimization,
    Ledoit-Wolf-style covariance shrinkage, and linear inequality constraints.
    """

    def __init__(self, tickers, df_prices=None, method="equal", risk_free_rate=0.065):
        self.tickers = [t for t in tickers if df_prices is None or t in df_prices.columns]
        self.df_prices = df_prices
        self.method = method
        self.rf = risk_free_rate

    def calculate_weights(self) -> dict:
        num_assets = len(self.tickers)

        if num_assets == 0:
            return {}

        # 1. Equal-Weight Fallback or Explicit Selection
        if self.method == "equal" or self.df_prices is None or self.df_prices.empty or num_assets == 1:
            equal_w = 1.0 / num_assets
            return {ticker: round(equal_w, 4) for ticker in self.tickers}

        # 2. Extract Returns and Calculate Annualized Metrics
        returns = self.df_prices[self.tickers].pct_change().dropna()
        if returns.empty or len(returns) < 10:
            equal_w = 1.0 / num_assets
            return {ticker: round(equal_w, 4) for ticker in self.tickers}

        mean_returns = returns.mean() * 252  # Annualized Expected Returns
        cov_matrix = returns.cov() * 252     # Annualized Covariance Matrix

        # Apply Covariance Shrinkage (Ledoit-Wolf proxy) for numerical stability
        shrinkage = 0.10
        prior = np.diag(np.diag(cov_matrix))
        cov_matrix_shrunk = (1 - shrinkage) * cov_matrix + shrinkage * prior

        # 3. Maximum Sharpe Ratio Optimization
        if self.method in ["max_sharpe", "max_sharpe_ratio"]:
            weights = self._optimize_max_sharpe(mean_returns, cov_matrix_shrunk, num_assets)
        else:
            weights = self._inverse_volatility_weights(returns)

        return {ticker: round(float(w), 4) for ticker, w in zip(self.tickers, weights)}

    def _optimize_max_sharpe(self, mean_returns, cov_matrix, num_assets):
        """Convex optimization to maximize portfolio Sharpe ratio."""

        def negative_sharpe(weights):
            p_return = np.sum(mean_returns * weights)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            if p_vol <= 0:
                return 0.0
            return -(p_return - self.rf) / p_vol

        # Constraint: Sum of weights == 1.0 (Fully Invested)
        constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})

        # Bounds: Prevent corner solutions by enforcing diversification (e.g. max 40% per asset)
        max_cap = max(0.35, min(1.0, 2.0 / num_assets))
        bounds = tuple((0.02, max_cap) for _ in range(num_assets))

        # Initial Guess (Equal-Weighted)
        init_guess = np.array([1.0 / num_assets] * num_assets)

        try:
            result = minimize(
                negative_sharpe,
                init_guess,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )

            if result.success:
                # Normalize to guarantee exact sum = 1.0
                weights = result.x / np.sum(result.x)
                return weights
        except Exception:
            pass

        # Fallback to Minimum Volatility weights if SLSQP fails
        return self._inverse_volatility_weights(self.df_prices[self.tickers].pct_change().dropna())

    def _inverse_volatility_weights(self, returns):
        """Fallback heuristics: Inverse-volatility weighting."""
        vols = returns.std()
        inv_vols = 1.0 / np.where(vols == 0, 1e-6, vols)
        weights = inv_vols / np.sum(inv_vols)
        return weights
