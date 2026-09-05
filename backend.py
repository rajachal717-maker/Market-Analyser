import os
import asyncio
import psycopg2
import yfinance as yf
from fastapi import FastAPI

app = FastAPI(title="jarvis. Execution Engine")

DB_URI = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DB_URI)

def get_live_price(ticker):
    try:
        return yf.Ticker(ticker).fast_info.get('lastPrice')
    except Exception:
        return None

async def market_scanner_loop():
    print("⚡ jarvis. Background Engine Online.")
    while True:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT id, user_id, ticker, target_price FROM price_alerts")
            active_alerts = c.fetchall()
            
            for alert_id, user_id, ticker, target_price in active_alerts:
                current_price = get_live_price(ticker)
                
                if current_price and (target_price * 0.995) <= current_price <= (target_price * 1.005):
                    print(f"🎯 TARGET HIT: User {user_id} | {ticker} at ₹{current_price}")
                    c.execute("DELETE FROM price_alerts WHERE id = %s", (alert_id,))
                    conn.commit()
            
            conn.close()
        except Exception as e:
            print(f"Scanner Error: {e}")
            
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(market_scanner_loop())

@app.get("/health")
def health_check():
    return {"status": "Engine Online", "scanner": "Active"}
