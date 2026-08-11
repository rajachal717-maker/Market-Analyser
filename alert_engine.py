import time
import sqlite3
import pyttsx3
import yfinance as yf
from plyer import notification

# --- 1. INITIALIZE VOICE ENGINE ---
engine = pyttsx3.init()
# Adjust speech speed (lower is slower)
engine.setProperty('rate', 160) 
# Set to a clear, professional voice
voices = engine.getProperty('voices')
if len(voices) > 1:
    engine.setProperty('voice', voices[1].id) # Usually a female voice on Windows

DB_PATH = "market_data.db"

def check_alerts():
    # Connect to your local database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Fetch all active alerts
    c.execute("SELECT id, ticker, target_price FROM price_alerts")
    alerts = c.fetchall()
    
    for alert in alerts:
        alert_id, ticker, target_price = alert
        
        # Append .NS for NSE stocks
        yf_ticker = ticker if "." in ticker else f"{ticker}.NS"
        
        try:
            # Fetch live price quietly
            ticker_obj = yf.Ticker(yf_ticker)
            current_price = ticker_obj.fast_info.get('lastPrice')
            
            if current_price:
                # Proximity Trigger: If the current price is within 0.5% of your target, trigger it.
                # This ensures we catch it if it crosses quickly between checks.
                diff = abs(current_price - target_price)
                if (diff / target_price) <= 0.005: 
                    trigger_alert(alert_id, ticker, current_price, target_price, conn)
                    
        except Exception as e:
            pass # Fail silently so the loop doesn't break
            
    conn.close()

def trigger_alert(alert_id, ticker, current_price, target_price, conn):
    message = f"{ticker} is trading at ₹{round(current_price, 2)}, hitting your target zone of ₹{target_price}!"
    
    # 1. Fire Native Windows Desktop Notification
    notification.notify(
        title="🔔 J.A.R.V.I.S. Price Alert",
        message=message,
        app_name="Institutional Quant Terminal",
        timeout=10 # Notification stays on screen for 10 seconds
    )
    
    # 2. Speak out loud
    print(f"[ALERT TRIGGERED] {message}")
    engine.say(f"Sir, price alert triggered. {ticker} has reached the target zone.")
    engine.runAndWait()
    
    # 3. Delete the alert from the database so it doesn't spam you every 60 seconds
    c = conn.cursor()
    c.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
    conn.commit()

print("✨ J.A.R.V.I.S. Background Alert Engine Started...")
print("Scanning local database for active price targets every 60 seconds. You can minimize this window.")

# --- 2. MAIN LOOP ---
while True:
    try:
        check_alerts()
    except Exception as e:
        print(f"System Error: {e}")
    
    # Wait 60 seconds before checking again
    time.sleep(60)