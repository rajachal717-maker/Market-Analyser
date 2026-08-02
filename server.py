from fastapi import FastAPI
from data_loader import fetch_stock_data
import pandas as pd

app = FastAPI()

@app.get("/api/historical/{symbol}")
async def get_historical(symbol: str, start: str, end: str):
    """
    Get historical stock data for a symbol
    Example: /api/historical/VMART?start=2026-02-03&end=2026-08-02
    """
    try:
        # Fetch data for a single ticker
        data = fetch_stock_data([symbol], start_date=start, end_date=end)
        
        if data.empty:
            return {"error": f"No data found for {symbol}"}
        
        # Convert to dictionary format for JSON response
        return {
            "symbol": symbol,
            "start": start,
            "end": end,
            "data": data.to_dict('index')
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    return {"status": "ok"}