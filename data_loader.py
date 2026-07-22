from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf


def fetch_stock_data(tickers, period="6m", start_date=None, end_date=None):
  """Fetches historical adjusted close prices using individual Ticker history

  with built-in error handling and fallback controls.
  """
  if isinstance(tickers, str):
    tickers = [t.strip().upper() for t in tickers.split(",")]
  else:
    tickers = [t.strip().upper() for t in tickers]

  if not end_date:
    end_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

  price_data = {}

  for ticker in tickers:
    try:
      print(f"Fetching data for: {ticker}...")
      t_obj = yf.Ticker(ticker)
      if start_date:
        df = t_obj.history(
            start=start_date, end=end_date, auto_adjust=True, timeout=10
        )
      else:
        df = t_obj.history(period=period, auto_adjust=True, timeout=10)

      if not df.empty and "Close" in df.columns:
        price_data[ticker] = df["Close"]
      else:
        print(f"Warning: No valid price data found for {ticker}")
    except Exception as e:
      print(f"Error fetching {ticker}: {e}")

  if not price_data:
    return pd.DataFrame()

  combined_df = pd.DataFrame(price_data)
  combined_df = combined_df.dropna(how="all")
  return combined_df
