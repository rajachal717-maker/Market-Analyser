import streamlit as st
import yfinance as yf
import pandas as pd

@st.cache_data(ttl=300)  # Cache historical prices for 5 minutes
def fetch_stock_data(tickers, start_date, end_date):
    data = {}
    for ticker in tickers:
        symbol = f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if not df.empty:
            # Handle multi-index columns if present in newer yfinance versions
            if isinstance(df.columns, pd.MultiIndex):
                df = df.xs('Close', level=0, axis=1)
            else:
                df = df[['Close']]
            data[ticker] = df.squeeze()
    
    if data:
        return pd.DataFrame(data).dropna()
    return pd.DataFrame()
