import numpy as np
import pandas as pd


def check_portfolio_risk(
    df_prices, weights_dict, max_drawdown_limit=-0.15, vol_target=0.20
):
  """Evaluates portfolio drawdown and applies risk circuit breakers.

  Returns safe adjusted weights and warning flags.
  """
  if df_prices.empty or not weights_dict:
    return weights_dict, "Normal", 0.0

  returns = df_prices[list(weights_dict.keys())].pct_change().dropna()
  weight_array = np.array(list(weights_dict.values()))

  # Calculate portfolio historical daily returns
  portfolio_returns = returns.dot(weight_array)

  # Calculate Cumulative Returns & Drawdown
  cum_returns = (1 + portfolio_returns).cumprod()
  rolling_max = cum_returns.cummax()
  drawdown = (cum_returns - rolling_max) / rolling_max
  current_drawdown = drawdown.iloc[-1]

  # Calculate Annualized Volatility
  annual_vol = portfolio_returns.std() * np.sqrt(252)

  status = "Normal"
  adjusted_weights = weights_dict.copy()

  # Circuit Breaker Trigger
  if current_drawdown <= max_drawdown_limit:
    status = (
        "🔴 CIRCUIT BREAKER TRIGGERED: Max Drawdown Limit Exceeded!"
        f" ({current_drawdown*100:.2f}%)"
    )
    # Reallocate to defensive stance (e.g., zero out or flatten risk)
    adjusted_weights = {k: 0.0 for k in weights_dict.keys()}
  elif annual_vol > vol_target:
    status = (
        "🟡 WARNING: High Portfolio Volatility Detected"
        f" ({annual_vol*100:.2f}%). Scaling risk."
    )
    scale_factor = vol_target / annual_vol
    adjusted_weights = {k: round(v * scale_factor, 4) for k, v in weights_dict.items()}

  return adjusted_weights, status, float(current_drawdown)