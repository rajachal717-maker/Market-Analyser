import numpy as np
import pandas as pd


def check_portfolio_risk(df_prices: pd.DataFrame, target_weights: dict, max_drawdown_limit: float = -0.15):
    """
    Institutional Risk Diagnostic & Dynamic Portfolio De-risking Engine.
    
    Returns:
        (safe_weights, risk_status_string, current_drawdown_float)
    """
    if df_prices.empty or not target_weights:
        return target_weights, "Status: Nominal (No Data)", 0.0

    # Ensure tickers match price DataFrame columns
    valid_tickers = [t for t in target_weights.keys() if t in df_prices.columns]
    if not valid_tickers:
        return target_weights, "Status: Nominal", 0.0

    # Extract weights vector
    weights = np.array([target_weights[t] for t in valid_tickers])
    weights = weights / np.sum(weights)  # Renormalize

    # Compute Portfolio Historical Returns
    returns = df_prices[valid_tickers].pct_change().dropna()
    portfolio_daily_returns = (returns * weights).sum(axis=1)

    # 1. Compute Peak-to-Trough Drawdown
    cumulative_returns = (1 + portfolio_daily_returns).cumprod()
    running_max = cumulative_returns.cummax()
    drawdown_series = (cumulative_returns - running_max) / running_max
    current_drawdown = float(drawdown_series.iloc[-1]) if not drawdown_series.empty else 0.0

    # 2. Risk Metrics: Value-at-Risk (95% VaR) & Conditional VaR (99% Expected Shortfall)
    var_95 = np.percentile(portfolio_daily_returns, 5)
    cvar_95 = portfolio_daily_returns[portfolio_daily_returns <= var_95].mean() if len(portfolio_daily_returns) > 0 else 0.0

    # 3. Concentration Index (Herfindahl-Hirschman Index - HHI)
    hhi = np.sum(weights ** 2)

    # 4. Dynamic De-Risking & Circuit Breaker Logic
    safe_weights = target_weights.copy()
    
    # Standardize threshold sign (make negative for comparison)
    limit = -abs(max_drawdown_limit)

    if current_drawdown < limit:
        # CRITICAL CIRCUIT BREAKER: Scale down exposure to prevent further capital destruction
        de_risk_factor = max(0.2, 1.0 - (abs(current_drawdown) - abs(limit)) / abs(limit))
        safe_weights = {t: round(w * de_risk_factor, 4) for t, w in target_weights.items()}
        
        status = (
            f"🚨 CIRCUIT BREAKER ACTIVATED: Max Drawdown breached ({current_drawdown*100:.2f}% < {limit*100:.2f}%). "
            f"Exposure de-risked by {(1-de_risk_factor)*100:.1f}%. | VaR(95): {var_95*100:.2f}%"
        )
    elif current_drawdown < (limit * 0.5):
        # WARNING ZONE
        status = (
            f"⚠️ WARNING: Portfolio approaching drawdown threshold ({current_drawdown*100:.2f}%). "
            f"VaR(95): {var_95*100:.2f}% | CVaR(95): {cvar_95*100:.2f}% | HHI: {hhi:.2f}"
        )
    else:
        # NOMINAL HEALTH
        status = (
            f"Status: Nominal | Drawdown: {current_drawdown*100:.2f}% | "
            f"Daily VaR(95): {var_95*100:.2f}% | Portfolio Concentration HHI: {hhi:.2f}"
        )

    return safe_weights, status, current_drawdown
