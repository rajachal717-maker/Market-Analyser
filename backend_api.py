from fastapi import FastAPI, HTTPException
import pandas as pd
import yfinance as yf

app = FastAPI(title="Institutional Quant Backend", version="1.0")

@app.get("/api/historical/{ticker}")
def get_historical_prices(ticker: str, start: str, end: str):
    try:
        symbol = f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker
        df = yf.download(symbol, start=start, end=end, progress=False)
        if df.empty:
            raise HTTPException(status_code=404, detail="Ticker data not found")
        
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs('Close', level=0, axis=1)
        else:
            df = df[['Close']]
            
        return df.reset_index().to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))