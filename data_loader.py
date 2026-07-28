import yfinance as yf
import pandas as pd
import streamlit as st

@st.cache_data(ttl=3600)
def fetch_stock_data(tickers, start_date, end_date):
    formatted_tickers = []
    
    # 1. Format tickers for Yahoo Finance (force .NS for Indian stocks)
    for t in tickers:
        t_clean = t.strip().upper()
        
        # Handle accidental hyphens (e.g., if you type V-MART instead of VMART)
        if t_clean == "V-MART":
            t_clean = "VMART"
            
        # If it doesn't already have an exchange suffix, force .NS
        if "." not in t_clean:
            t_clean = f"{t_clean}.NS"
            
        formatted_tickers.append(t_clean)
        
    if not formatted_tickers:
        return pd.DataFrame()

    # 2. Fetch the historical data
    data = yf.download(formatted_tickers, start=start_date, end=end_date, progress=False)
    
    if data is None or data.empty:
        return pd.DataFrame()

    # 3. Clean up the multi-index columns returned by newer yfinance versions
    if isinstance(data.columns, pd.MultiIndex):
        if 'Adj Close' in data.columns.levels[0]:
            df = data['Adj Close']
        elif 'Close' in data.columns.levels[0]:
            df = data['Close']
        else:
            df = data.iloc[:, 0]
    else:
        if 'Adj Close' in data.columns:
            df = data['Adj Close']
        elif 'Close' in data.columns:
            df = data['Close']
        else:
            df = data

    # 4. If it's a single series (one ticker), convert it back to a DataFrame
    if isinstance(df, pd.Series):
        df = df.to_frame(name=formatted_tickers[0])
    elif isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)

    # 5. STRIP the .NS suffix from the final columns so your strategy.py and backtester.py can read them!
    df.columns = [str(col).replace(".NS", "").replace(".BO", "") for col in df.columns]

    return df.dropna(how="all")
