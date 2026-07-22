import numpy as np
import pandas as pd


def run_backtest(df_prices, weights_dict, risk_free_rate=0.03):
  """Performs historical backtest given price data and asset weights."""
  if df_prices.empty or not weights_dict:
    return {}, pd.Series(dtype=float)

  valid_tickers = [t for t in weights_dict.keys() if t in df_prices.columns]
  if not valid_tickers:
    return {}, pd.Series(dtype=float)

  returns = df_prices[valid_tickers].pct_change().dropna()
  w_vec = np.array([weights_dict[t] for t in valid_tickers])

  # Portfolio daily returns series
  portfolio_returns = returns.dot(w_vec)
  cumulative_curve = (1 + portfolio_returns).cumprod()

  # Performance Metrics
  total_days = len(portfolio_returns)
  years = total_days / 252.0 if total_days > 0 else 1.0

  cagr = (
      (cumulative_curve.iloc[-1] ** (1 / years)) - 1
      if years > 0 and cumulative_curve.iloc[-1] > 0
      else 0.0
  )
  annualized_vol = portfolio_returns.std() * np.sqrt(252)

  sharpe_ratio = (
      (cagr - risk_free_rate) / annualized_vol
      if annualized_vol > 0
      else 0.0
  )

  rolling_max = cumulative_curve.cummax()
  max_drawdown = ((cumulative_curve - rolling_max) / rolling_max).min()

  metrics = {
      "CAGR": round(cagr * 100, 2),
      "Annualized Volatility": round(annualized_vol * 100, 2),
      "Sharpe Ratio": round(sharpe_ratio, 2),
      "Maximum Drawdown": round(max_drawdown * 100, 2),
  }

  return metrics, cumulative_curve