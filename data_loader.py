import yfinance as yf
import pandas as pd
import streamlit as st

# For API server - NO caching, always fresh data
def fetch_stock_data_live(tickers, start_date, end_date):
    """Fetch live data without caching - used by FastAPI"""
    data = {}
    for ticker in tickers:
        symbol = f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df = df.xs('Close', level=0, axis=1)
            else:
                df = df[['Close']]
            data[ticker] = df.squeeze()
    
    if data:
        return pd.DataFrame(data).dropna()
    return pd.DataFrame()


# For Streamlit app - WITH caching for performance
@st.cache_data(ttl=300)
def fetch_stock_data(tickers, start_date, end_date):
    """Fetch cached data - used by Streamlit UI"""
    return fetch_stock_data_live(tickers, start_date, end_date)
