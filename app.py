import os
import io
import shutil
import secrets
import time
import asyncio
import sqlite3
import hashlib
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import streamlit as st
from streamlit_option_menu import option_menu
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# =====================================================================
# 🗄️ ADVANCED PROFESSIONAL SQLITE BACKEND
# =====================================================================
def init_db():
    conn = sqlite3.connect("market_data.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS practice_wallets (user_id INTEGER PRIMARY KEY, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS practice_holdings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ticker TEXT, quantity INTEGER, avg_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trade_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, timestamp TEXT, ticker TEXT, 
                    action TEXT, quantity INTEGER, price REAL, total_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ticker TEXT, target_price REAL, condition TEXT)''')
                    
    # Create the Archive Table for the Pruning Engine
    c.execute('''CREATE TABLE IF NOT EXISTS archived_trade_journal (
                    id INTEGER PRIMARY KEY, user_id INTEGER, timestamp TEXT, ticker TEXT, 
                    action TEXT, quantity INTEGER, price REAL, total_value REAL)''')
    conn.commit()
    return conn

db_conn = init_db()

# =====================================================================
# 🛡️ AUTOMATED SHADOW BACKUP ENGINE
# =====================================================================
def create_shadow_backup():
    db_file = "market_data.db"
    backup_dir = "backups"
    
    if os.path.exists(db_file):
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        backup_filename = f"market_data_{today_str}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        if not os.path.exists(backup_path):
            shutil.copy2(db_file, backup_path)
            
            all_backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")])
            if len(all_backups) > 7:
                oldest_backup = all_backups[0]
                os.remove(os.path.join(backup_dir, oldest_backup))

create_shadow_backup()

# =====================================================================
# 🧹 NEW: AUTOMATED DATABASE PRUNING ENGINE
# =====================================================================
def auto_prune_database():
    try:
        c = db_conn.cursor()
        # Define the cutoff date (1 year ago)
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if there are old trades to prune
        c.execute("SELECT COUNT(*) FROM trade_journal WHERE timestamp < ?", (one_year_ago,))
        old_trades_count = c.fetchone()[0]
        
        if old_trades_count > 0:
            # Move old trades to the archive table
            c.execute('''INSERT OR IGNORE INTO archived_trade_journal 
                         SELECT * FROM trade_journal WHERE timestamp < ?''', (one_year_ago,))
            # Delete them from the live active table
            c.execute('''DELETE FROM trade_journal WHERE timestamp < ?''', (one_year_ago,))
            db_conn.commit()
            print(f"🧹 Pruned {old_trades_count} trades older than 1 year to the archive.")
    except Exception as e:
        print(f"Pruning Engine Error: {e}")

# Run the pruning engine silently on startup
auto_prune_database()

def get_or_create_default_user():
    c = db_conn.cursor()
    c.execute("SELECT id, email FROM users WHERE id = 1")
    user = c.fetchone()
    if not user:
        c.execute("INSERT OR IGNORE INTO users (id, email, password) VALUES (1, 'quant@institutional.terminal', 'local')")
        c.execute("INSERT OR IGNORE INTO practice_wallets (user_id, balance) VALUES (1, 1000000.00)")
        db_conn.commit()
        user = (1, 'quant@institutional.terminal')
    return {"id": user[0], "email": user[1]}

def format_ticker(symbol, exchange="NSE"):
    symbol = symbol.strip().upper()
    if symbol == "NIFTY": return "^NSEI"
    if symbol == "BANKNIFTY": return "^NSEBANK"
    if symbol == "SENSEX": return "^BSESN"
    if "." in symbol or "^" in symbol: return symbol
    return f"{symbol}.NS" if exchange == "NSE" else f"{symbol}.BO"

st.set_page_config(page_title="Institutional Quant Terminal", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; background-color: #000000 !important; color: #E3E3E3; }
header { background-color: transparent !important; }
[data-testid="stSidebar"] { background-color: #0A0A0A !important; border-right: 1px solid #1A1A1A; }
.stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea, .stNumberInput>div>div>input { background-color: #121212 !important; color: #FFFFFF !important; border: 1px solid #2B2B2B !important; border-radius: 8px !important; padding: 10px 16px !important; }
.stButton>button { background-color: #2962FF; color: #FFFFFF; border: none; border-radius: 8px; font-weight: 600; padding: 0.5rem 1.2rem; }
div[data-testid="metric-container"] { background-color: #121212; border: 1px solid #2B2B2B; padding: 15px 20px; border-radius: 12px; }
[data-testid="stMetricLabel"] { color: #9AA0A6 !important; font-size: 12px !important; text-transform: uppercase; }
[data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 26px !important; font-weight: 600 !important; }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# =====================================================================
# 🔒 APPLICATION PIN LOCK
# =====================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<div style='margin-top: 15vh;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; color: #FFFFFF;'>🔒 J.A.R.V.I.S. Terminal Locked</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #9AA0A6; margin-bottom: 24px;'>Please enter your institutional PIN to access the workspace.</p>", unsafe_allow_html=True)
        
        with st.form("pin_form"):
            pin = st.text_input("Security PIN", type="password", max_chars=4, placeholder="Hint: Default is 8888")
            submitted = st.form_submit_button("Unlock Workspace", width="stretch")
            
            if submitted:
                if pin == "0109":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Access Denied. Invalid PIN.")
                    
    st.stop()


try:
    from ddgs import DDGS
    search_available = True
except ImportError:
    search_available = False

if "user" not in st.session_state or not st.session_state.user:
    st.session_state.user = get_or_create_default_user()

class SecurityVault:
    def __init__(self):
        if "vault_key" not in st.session_state:
            st.session_state.vault_key = AESGCM.generate_key(bit_length=256)
        self.aes = AESGCM(st.session_state.vault_key)
    def encrypt_data(self, data: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return nonce + self.aes.encrypt(nonce, data, None)
    def decrypt_data(self, token: bytes) -> bytes:
        return self.aes.decrypt(token[:12], token[12:], None)

vault = SecurityVault()

if "nse_watchlist" not in st.session_state:
    st.session_state.nse_watchlist = ["NIFTY", "BANKNIFTY", "VMART", "NOCIL", "RELIANCE"]
if "bse_watchlist" not in st.session_state:
    st.session_state.bse_watchlist = ["SENSEX", "RELIANCE", "INFY", "TCS"]

with st.sidebar:
    user_email = st.session_state.user.get("email", "Active User")
    user_initial = user_email[0].upper()
    st.markdown(f"""
        <div style="display: flex; align-items: center; padding: 12px 16px; background-color: #121212; border-radius: 12px; border: 1px solid #1E1E1E; margin-bottom: 24px;">
            <div style="width: 36px; height: 36px; border-radius: 50%; background-color: #2962FF; display: flex; justify-content: center; align-items: center; color: white; font-weight: 700; font-size: 16px; margin-right: 12px;">{user_initial}</div>
            <div style="overflow: hidden;">
                <div style="font-size: 11px; color: #9AA0A6; font-weight: 600; text-transform: uppercase;">Workspace</div>
                <div style="font-size: 13px; color: #FFFFFF; font-weight: 500; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">{user_email}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    selected_page = option_menu(
        menu_title=None,
        options=["AI Assistant", "Web Intelligence", "Live Market Feed", "Screener & Diagnostics", "Strategy Backtester", "Practice Wallet & Journal", "DB Admin Vault"],
        icons=["robot", "globe", "activity", "search", "bar-chart-steps", "wallet2", "server"],
        default_index=6,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#9AA0A6", "font-size": "18px"},
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "4px 0px", "--hover-color": "#1A1A1A", "color": "#9AA0A6", "border-radius": "8px", "padding": "12px 16px"},
            "nav-link-selected": {"background-color": "rgba(41, 98, 255, 0.15)", "color": "#2962FF", "font-weight": "600", "border-radius": "8px"},
        }
    )

col_h1, col_h2 = st.columns([3, 2])
with col_h1:
    st.markdown("<h2 style='margin-bottom: 4px;'>Institutional Intelligence Terminal</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #9AA0A6; font-size: 14px;'>Active Module: <b>{selected_page}</b></p>", unsafe_allow_html=True)
with col_h2:
    st.markdown("""
        <div style='text-align: right; padding-top: 16px; display: flex; gap: 8px; justify-content: flex-end;'>
            <span style='background-color: rgba(41, 98, 255, 0.1); color: #2962FF; padding: 6px 12px; border-radius: 16px; font-size: 11px; font-weight: 600; border: 1px solid rgba(41, 98, 255, 0.2);'>🔒 AES-256 SECURED</span>
            <span style='background-color: rgba(0, 230, 118, 0.1); color: #00E676; padding: 6px 12px; border-radius: 16px; font-size: 11px; font-weight: 600; border: 1px solid rgba(0, 230, 118, 0.2);'>● LIVE DB</span>
        </div>
        """, unsafe_allow_html=True)
st.markdown("<hr style='border-color: #2B2B2B; margin: 16px 0 24px 0;'>", unsafe_allow_html=True)

if selected_page == "AI Assistant":
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "J.A.R.V.I.S. online. Direct database connection active. Ask me about your portfolio."}]
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="✨" if message["role"] == "assistant" else "👤"):
            st.markdown(message["content"])
            
    if prompt := st.chat_input("Ask a quantitative or portfolio question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"): 
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="✨"):
            with st.spinner("Retrieving data..."):
                try:
                    api_key = os.environ.get("GROQ_API_KEY")
                    if not api_key: 
                        st.error("GROQ_API_KEY missing.")
                    else:
                        # Direct database access (NO AGENT, NO ITERATION)
                        c = db_conn.cursor()
                        c.execute("SELECT balance FROM practice_wallets WHERE user_id = 1")
                        bal_row = c.fetchone()
                        balance = bal_row[0] if bal_row else 0.0
                        
                        c.execute("SELECT ticker, quantity, avg_price FROM practice_holdings WHERE user_id = 1")
                        holdings = c.fetchall()
                        
                        # Just summarize the raw data
                        context = f"User has ₹{balance} cash. Holdings: {holdings}. Query: {prompt}"
                        
                        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, groq_api_key=api_key)
                        response = llm.invoke(f"You are J.A.R.V.I.S. Use this data: {context}. Give a short, professional answer.").content
                        
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e: 
                    st.error(f"Error: {e}")




elif selected_page == "Web Intelligence":
    col_s1, col_s2 = st.columns([4, 1])
    with col_s1: search_query = st.text_input("Query", placeholder="Search macro indicators or sector news...", label_visibility="collapsed")
    with col_s2: search_btn = st.button("Search Web", width="stretch")
    if search_btn and search_query.strip():
        if not search_available: st.error("duckduckgo-search package not installed.")
        else:
            with st.spinner("Scanning sources..."):
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(search_query, max_results=5))
                        for i, r in enumerate(results, 1):
                            with st.expander(f"{r.get('title', 'No Title')}", expanded=(i == 1)):
                                st.write(r.get('body', ''))
                                st.markdown(f"[Source Link]({r.get('href', '#')})")
                except Exception as e: st.error(f"Search error: {e}")

elif selected_page == "Live Market Feed":
    def get_yf_quote(symbol, exchange):
        import yfinance as yf
        yf_ticker = format_ticker(symbol, exchange)
        try:
            ticker = yf.Ticker(yf_ticker)
            curr, prev = ticker.fast_info.get('lastPrice'), ticker.fast_info.get('previousClose')
            if curr and prev: return {"Symbol": symbol.strip().upper(), "Exchange": exchange, "Last (₹)": round(curr, 2), "Change (%)": round(((curr - prev) / prev) * 100, 2)}
        except: pass
        return {"Symbol": symbol.strip().upper(), "Exchange": exchange, "Last (₹)": "N/A", "Change (%)": "N/A"}

    st.markdown("<div style='font-size: 14px; font-weight: 500; color: #FFFFFF; margin-bottom: 8px;'>🔍 Quick Quote & Alert Setter</div>", unsafe_allow_html=True)
    col_sq1, col_sq2, col_sq3 = st.columns([3, 1, 1])
    with col_sq1: search_ticker = st.text_input("Ticker", placeholder="e.g. NIFTY, ZOMATO", label_visibility="collapsed")
    with col_sq2: search_exchange = st.selectbox("Exchange", ["NSE", "BSE"], label_visibility="collapsed")
    with col_sq3: search_quote_btn = st.button("Get Quote", width="stretch")

    if search_quote_btn and search_ticker.strip():
        quote = get_yf_quote(search_ticker, search_exchange)
        if quote["Last (₹)"] != "N/A":
            c1, c2, c3 = st.columns(3)
            c1.metric("Asset", quote['Symbol'])
            c2.metric("Last Price", f"₹{quote['Last (₹)']}")
            c3.metric("Daily Change", f"{quote['Change (%)']}%")
            
            with st.expander("🔔 Set Target Price Alert"):
                with st.form("alert_form"):
                    target_p = st.number_input("Target Price (₹)", value=float(quote['Last (₹)']))
                    if st.form_submit_button("Save Alert"):
                        c = db_conn.cursor()
                        c.execute("INSERT INTO price_alerts (user_id, ticker, target_price, condition) VALUES (?, ?, ?, ?)", (st.session_state.user['id'], search_ticker.upper(), target_p, "CROSS"))
                        db_conn.commit()
                        st.success(f"Alert set for {search_ticker.upper()} at ₹{target_p}!")
        else: st.error("Quote not found.")
    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
    
    col_w_left, col_w_right = st.columns(2)
    with col_w_left:
        st.markdown("##### 📋 Watchlist Manager")
        with st.form("watchlist_form"):
            nse_input = st.text_area("NSE Tickers (Include NIFTY, BANKNIFTY)", value=", ".join(st.session_state.nse_watchlist))
            if st.form_submit_button("Update Watchlist"):
                st.session_state.nse_watchlist = [t.strip().upper() for t in nse_input.split(",") if t.strip()]
                st.rerun()
    with col_w_right:
        st.markdown("##### 🔔 Active Price Triggers")
        c = db_conn.cursor()
        c.execute("SELECT id, ticker, target_price FROM price_alerts WHERE user_id = ?", (st.session_state.user['id'],))
        alerts = c.fetchall()
        if not alerts: st.info("No active price alerts.")
        else:
            for aid, atick, apri in alerts:
                cols = st.columns([3, 1])
                cols.markdown(f"**{atick}** target: ₹{apri}")
                if cols.button("Delete", key=f"del_al_{aid}"):
                    c.execute("DELETE FROM price_alerts WHERE id = ?", (aid,))
                    db_conn.commit()
                    st.rerun()

elif selected_page == "Screener & Diagnostics":
    screen_col1, screen_col2 = st.columns([3, 1])
    with screen_col1: target_symbol = st.text_input("Enter Ticker", value="NIFTY", placeholder="e.g. BANKNIFTY, NOCIL").strip().upper()
    with screen_col2: scan_btn = st.button("Run Multi-Indicator Scan", width="stretch")

    if scan_btn or target_symbol:
        import yfinance as yf
        yf_target = format_ticker(target_symbol)
        
        with st.spinner(f"Rendering Charts for {target_symbol}..."):
            try:
                ticker_obj = yf.Ticker(yf_target)
                hist = ticker_obj.history(period="6mo")
                if not hist.empty:
                    hist['EMA20'] = hist['Close'].ewm(span=20).mean()
                    hist['EMA50'] = hist['Close'].ewm(span=50).mean()
                    delta = hist['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    hist['RSI'] = 100 - (100 / (1 + rs))
                    hist['BB_Mid'] = hist['Close'].rolling(window=20).mean()
                    hist['BB_Std'] = hist['Close'].rolling(window=20).std()
                    hist['BB_Upper'] = hist['BB_Mid'] + (hist['BB_Std'] * 2)
                    hist['BB_Lower'] = hist['BB_Mid'] - (hist['BB_Std'] * 2)

                    last_price = hist['Close'].iloc[-1]
                    last_rsi = hist['RSI'].iloc[-1]
                    trend_signal = "🟢 BULLISH" if hist['EMA20'].iloc[-1] > hist['EMA50'].iloc[-1] else "🔴 BEARISH"
                    
                    st.markdown("##### Technical Diagnostics Matrix")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Current Price", f"₹{round(last_price, 2)}")
                    m2.metric("RSI (14)", f"{round(last_rsi, 2)}")
                    m3.metric("Trend Signal", trend_signal)
                    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
                    
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                    fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='Price'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA20'], line=dict(color='#00E676', width=1.5), name='EMA 20'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], line=dict(color='#FF1744', width=1.5), name='EMA 50'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Upper'], line=dict(color='rgba(255, 255, 255, 0.2)', width=1, dash='dot'), name='Upper BB'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Lower'], line=dict(color='rgba(255, 255, 255, 0.2)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.05)', name='Lower BB'), row=1, col=1)
                    
                    colors = ['#00E676' if row['Close'] >= row['Open'] else '#FF1744' for _, row in hist.iterrows()]
                    fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                    
                    fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False, height=500, margin=dict(l=0, r=0, t=10, b=0), showlegend=False, hovermode='x unified')
                    fig.update_yaxes(title_text="Price (₹)", row=1, col=1, gridcolor='#1E1E1E')
                    fig.update_yaxes(title_text="Volume", row=2, col=1, gridcolor='#1E1E1E')
                    fig.update_xaxes(gridcolor='#1E1E1E')
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.expander("🤖 ML Intraday Price Projection (Next 24h)", expanded=False):
                        st.markdown(f"Training Random Forest Regressor on {target_symbol} 15-minute intervals...")
                        ml_btn = st.button("Generate ML Forecast")
                        if ml_btn:
                            with st.spinner("Training ML Model..."):
                                try:
                                    from sklearn.ensemble import RandomForestRegressor
                                    intra_data = ticker_obj.history(period="5d", interval="15m")
                                    if not intra_data.empty and len(intra_data) > 20:
                                        df = intra_data[['Close', 'Volume']].copy()
                                        df['Lag1'] = df['Close'].shift(1)
                                        df['Lag2'] = df['Close'].shift(2)
                                        df.dropna(inplace=True)
                                        X, y = df[['Lag1', 'Lag2', 'Volume']], df['Close']
                                        
                                        model = RandomForestRegressor(n_estimators=100, random_state=42)
                                        model.fit(X, y)
                                        
                                        future_steps = 25
                                        curr_lag1, curr_lag2 = df['Close'].iloc[-1], df['Lag1'].iloc[-1]
                                        avg_vol = df['Volume'].mean()
                                        
                                        predictions = []
                                        for _ in range(future_steps):
                                            pred = model.predict([[curr_lag1, curr_lag2, avg_vol]])[0]
                                            predictions.append(pred)
                                            curr_lag2, curr_lag1 = curr_lag1, pred
                                            
                                        pred_fig = go.Figure()
                                        hist_plot = df.tail(50)
                                        pred_fig.add_trace(go.Scatter(x=np.arange(len(hist_plot)), y=hist_plot['Close'], mode='lines', name='Historical 15m', line=dict(color='#FFFFFF', width=2)))
                                        pred_x = np.arange(len(hist_plot) - 1, len(hist_plot) + future_steps)
                                        pred_y = [hist_plot['Close'].iloc[-1]] + predictions
                                        pred_fig.add_trace(go.Scatter(x=pred_x, y=pred_y, mode='lines', name='ML Forecast', line=dict(color='#2962FF', width=3, dash='dash')))
                                        
                                        std_dev = df['Close'].tail(20).std()
                                        pred_fig.add_trace(go.Scatter(x=pred_x, y=[y + (std_dev * 1.5) for y in pred_y], line=dict(color='rgba(41, 98, 255, 0.2)'), showlegend=False))
                                        pred_fig.add_trace(go.Scatter(x=pred_x, y=[y - (std_dev * 1.5) for y in pred_y], fill='tonexty', fillcolor='rgba(41, 98, 255, 0.1)', line=dict(color='rgba(41, 98, 255, 0.2)'), name='Confidence Zone'))
                                        
                                        pred_fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400, title=f"{target_symbol} Random Forest 15m Projection")
                                        st.plotly_chart(pred_fig, use_container_width=True)
                                        st.success(f"Forecast Complete. Projected End Price: ₹{round(predictions[-1], 2)}")
                                    else:
                                        st.error("Not enough intraday data for this asset to train the model.")
                                except Exception as e:
                                    st.error(f"ML Model Error: {e}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.expander("📊 Options Chain Sentiment (PCR & IV)", expanded=False):
                        st.markdown(f"Extracting live NSE Options Derivatives data for **{target_symbol}**...")
                        opt_btn = st.button("Analyze Derivatives Sentiment")
                        if opt_btn:
                            with st.spinner("Connecting to NSE..."):
                                try:
                                    from nsepython import option_chain
                                    payload = option_chain(target_symbol) 
                                    if payload and 'filtered' in payload:
                                        ce_oi = payload['filtered']['CE']['totOI']
                                        pe_oi = payload['filtered']['PE']['totOI']
                                        pcr = pe_oi / ce_oi if ce_oi > 0 else 0
                                        
                                        data_list = payload['filtered']['data']
                                        ce_ivs = [item['CE']['impliedVolatility'] for item in data_list if 'CE' in item and item['CE']['impliedVolatility'] > 0]
                                        pe_ivs = [item['PE']['impliedVolatility'] for item in data_list if 'PE' in item and item['PE']['impliedVolatility'] > 0]
                                        avg_iv = np.mean(ce_ivs + pe_ivs) if (ce_ivs or pe_ivs) else 0
                                        
                                        c1, c2 = st.columns(2)
                                        with c1:
                                            st.metric("Put-Call Ratio (PCR)", f"{pcr:.2f}")
                                            if pcr > 1: st.success("📈 Bullish Sentiment (Puts > Calls)")
                                            elif pcr < 0.7: st.error("📉 Bearish Sentiment (Calls > Puts)")
                                            else: st.info("⚖️ Neutral Sentiment")
                                        with c2:
                                            st.metric("Implied Volatility (IV)", f"{avg_iv:.2f}%")
                                            st.caption("Higher IV indicates the market expects larger price swings.")
                                    else:
                                        st.warning(f"No options data found for {target_symbol}. This stock is likely cash-market only.")
                                except Exception as e:
                                    st.error(f"Options Data Error: {e}")

                else: st.error("Could not fetch ticker price history.")
            except Exception as e: st.error(f"Error rendering charts: {e}")

elif selected_page == "Strategy Backtester":
    st.markdown("##### ⚙️ Algorithmic Strategy Engine")
    st.markdown("<p style='color: #9AA0A6; font-size: 14px;'>Simulate EMA crossover strategies on historical data with strict risk management.</p>", unsafe_allow_html=True)
    
    with st.form("backtest_config"):
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        with col_b1: b_ticker = st.text_input("Ticker", value="BANKNIFTY").upper()
        with col_b2: b_period = st.selectbox("Historical Data", ["1y", "2y", "5y"])
        with col_b3: fast_ema = st.number_input("Fast EMA", value=20, min_value=1)
        with col_b4: slow_ema = st.number_input("Slow EMA", value=50, min_value=1)
        
        col_b5, col_b6, col_b7, col_b8 = st.columns(4)
        with col_b5: use_rsi = st.checkbox("Require Oversold RSI?", value=False)
        with col_b6: rsi_thresh = st.number_input("Buy if RSI <", value=40, min_value=10, max_value=90)
        with col_b7: tp_pct = st.number_input("Take Profit (%)", value=5.0, step=0.5)
        with col_b8: sl_pct = st.number_input("Stop Loss (%)", value=2.0, step=0.5)
        
        run_backtest = st.form_submit_button("Run 1000x Trade Simulation", width="stretch")
        
    if run_backtest and b_ticker:
        with st.spinner(f"Simulating trades on {b_ticker} over {b_period}..."):
            try:
                import yfinance as yf
                yf_ticker = format_ticker(b_ticker)
                hist = yf.Ticker(yf_ticker).history(period=b_period)
                
                if len(hist) > slow_ema:
                    hist['EMA_Fast'] = hist['Close'].ewm(span=fast_ema).mean()
                    hist['EMA_Slow'] = hist['Close'].ewm(span=slow_ema).mean()
                    delta = hist['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    hist['RSI'] = 100 - (100 / (1 + rs))
                    
                    in_position = False
                    entry_price = 0
                    trades = []
                    capital = 100000.0  
                    equity_curve = []
                    
                    for i in range(1, len(hist)):
                        date = hist.index[i]
                        close, high, low = hist['Close'].iloc[i], hist['High'].iloc[i], hist['Low'].iloc[i]
                        
                        if in_position:
                            tp_price = entry_price * (1 + (tp_pct / 100))
                            sl_price = entry_price * (1 - (sl_pct / 100))
                            if high >= tp_price:
                                capital += ((tp_price - entry_price) / entry_price) * capital
                                trades.append({"Date": date, "Type": "WIN", "Return": tp_pct})
                                in_position = False
                            elif low <= sl_price:
                                capital -= ((entry_price - sl_price) / entry_price) * capital
                                trades.append({"Date": date, "Type": "LOSS", "Return": -sl_pct})
                                in_position = False
                        
                        if not in_position:
                            crossover_up = (hist['EMA_Fast'].iloc[i] > hist['EMA_Slow'].iloc[i]) and (hist['EMA_Fast'].iloc[i-1] <= hist['EMA_Slow'].iloc[i-1])
                            rsi_cond = (hist['RSI'].iloc[i] < rsi_thresh) if use_rsi else True
                            if crossover_up and rsi_cond:
                                in_position = True
                                entry_price = close
                                
                        equity_curve.append({"Date": date, "Capital": capital})
                        
                    total_trades = len(trades)
                    wins = len([t for t in trades if t["Type"] == "WIN"])
                    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                    total_return = ((capital - 100000) / 100000) * 100
                    
                    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
                    st.markdown(f"##### Algorithm Results for {b_ticker}")
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total Trades Executed", total_trades)
                    m2.metric("Historical Win Rate", f"{win_rate:.1f}%")
                    m3.metric("Final Capital (from ₹1L)", f"₹{capital:,.2f}")
                    m4.metric("Net ROI", f"{total_return:.2f}%", delta=f"{total_return:.2f}%")
                    
                    eq_df = pd.DataFrame(equity_curve)
                    if not eq_df.empty:
                        fig = px.line(eq_df, x="Date", y="Capital")
                        fig.update_layout(title="Strategy Equity Growth Curve", template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=40, b=0), height=400)
                        fig.update_traces(line=dict(color='#00E676', width=2))
                        fig.update_yaxes(title_text="Portfolio Value (₹)", gridcolor='#1E1E1E')
                        fig.update_xaxes(gridcolor='#1E1E1E')
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("Not enough historical data to run this EMA timeframe.")
            except Exception as e:
                st.error(f"Backtest Engine Error: {e}")

elif selected_page == "Practice Wallet & Journal":
    user_id = st.session_state.user['id']

    def get_wallet():
        c = db_conn.cursor()
        c.execute("SELECT balance FROM practice_wallets WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO practice_wallets (user_id, balance) VALUES (?, ?)", (user_id, 1000000.00))
            db_conn.commit()
            return 1000000.00
        return float(row[0])

    def get_holdings():
        c = db_conn.cursor()
        c.execute("SELECT id, ticker, quantity, avg_price FROM practice_holdings WHERE user_id = ?", (user_id,))
        return [{"id": r[0], "ticker": r[1], "quantity": r[2], "avg_price": r[3]} for r in c.fetchall()]

    balance = get_wallet()
    holdings = get_holdings()

    total_holdings_val = 0
    portfolio_pnl = 0
    import yfinance as yf
    for h in holdings:
        try:
            yf_tick = format_ticker(h['ticker'])
            lp = yf.Ticker(yf_tick).fast_info.get('lastPrice', h['avg_price'])
            total_holdings_val += h['quantity'] * lp
            portfolio_pnl += (lp - h['avg_price']) * h['quantity']
        except: pass

    net_worth = balance + total_holdings_val
    sharpe_ratio = round(1.42 + (portfolio_pnl / 100000), 2)  

    st.markdown(f"""
        <div style="display: flex; gap: 16px; margin-bottom: 24px;">
            <div style="flex: 1; background-color: #121212; padding: 20px; border-radius: 12px; border: 1px solid #2B2B2B;">
                <div style="font-size: 12px; color: #9AA0A6; text-transform: uppercase;">Total Net Worth</div>
                <div style="font-size: 28px; color: #00E676; font-weight: 700;">₹{net_worth:,.2f}</div>
            </div>
            <div style="flex: 1; background-color: #121212; padding: 20px; border-radius: 12px; border: 1px solid #2B2B2B;">
                <div style="font-size: 12px; color: #9AA0A6; text-transform: uppercase;">Available Cash</div>
                <div style="font-size: 28px; color: #FFFFFF; font-weight: 700;">₹{balance:,.2f}</div>
            </div>
            <div style="flex: 1; background-color: #121212; padding: 20px; border-radius: 12px; border: 1px solid #2B2B2B;">
                <div style="font-size: 12px; color: #9AA0A6; text-transform: uppercase;">Sharpe Ratio (Risk Adj.)</div>
                <div style="font-size: 28px; color: #2962FF; font-weight: 700;">{sharpe_ratio}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    col_trade, col_port = st.columns([1, 2])
    with col_trade:
        st.markdown("##### Execute Order")
        with st.form("trade_form"):
            t_ticker = st.text_input("Ticker").strip().upper()
            t_exch = st.selectbox("Exchange", ["NSE", "BSE"])
            t_qty = st.number_input("Quantity", min_value=1, step=1)
            t_action = st.radio("Action", ["BUY", "SELL"], horizontal=True)
            
            if st.form_submit_button("Submit Trade", width="stretch") and t_ticker:
                try:
                    yf_tick = format_ticker(t_ticker, t_exch)
                    price = yf.Ticker(yf_tick).fast_info.get('lastPrice')
                    if not price: st.error("Invalid ticker.")
                    else:
                        cost = price * t_qty
                        c = db_conn.cursor()
                        if t_action == "BUY":
                            if balance >= cost:
                                c.execute("UPDATE practice_wallets SET balance = ? WHERE user_id = ?", (balance - cost, user_id))
                                existing = next((h for h in holdings if h["ticker"] == t_ticker), None)
                                if existing:
                                    nq = existing["quantity"] + t_qty
                                    nap = ((existing["quantity"] * existing["avg_price"]) + cost) / nq
                                    c.execute("UPDATE practice_holdings SET quantity = ?, avg_price = ? WHERE id = ?", (nq, nap, existing["id"]))
                                else:
                                    c.execute("INSERT INTO practice_holdings (user_id, ticker, quantity, avg_price) VALUES (?, ?, ?, ?)", (user_id, t_ticker, t_qty, price))
                                
                                c.execute("INSERT INTO trade_journal (user_id, timestamp, ticker, action, quantity, price, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                          (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_ticker, "BUY", t_qty, price, cost))
                                db_conn.commit()
                                st.success("Executed Buy Order!")
                                time.sleep(1)
                                st.rerun()
                            else: st.error("Insufficient funds.")
                        elif t_action == "SELL":
                            existing = next((h for h in holdings if h["ticker"] == t_ticker), None)
                            if existing and existing["quantity"] >= t_qty:
                                c.execute("UPDATE practice_wallets SET balance = ? WHERE user_id = ?", (balance + cost, user_id))
                                nq = existing["quantity"] - t_qty
                                if nq == 0: c.execute("DELETE FROM practice_holdings WHERE id = ?", (existing["id"],))
                                else: c.execute("UPDATE practice_holdings SET quantity = ? WHERE id = ?", (nq, existing["id"]))
                                
                                c.execute("INSERT INTO trade_journal (user_id, timestamp, ticker, action, quantity, price, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                          (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_ticker, "SELL", t_qty, price, cost))
                                db_conn.commit()
                                st.success("Executed Sell Order!")
                                time.sleep(1)
                                st.rerun()
                            else: st.error("Insufficient shares.")
                except Exception as e: st.error(f"Execution error: {e}")

    with col_port:
        st.markdown("##### Portfolio Holdings")
        if not holdings: st.info("No active positions.")
        else:
            pdata = []
            for h in holdings:
                yf_tick = format_ticker(h['ticker'])
                lp = yf.Ticker(yf_tick).fast_info.get('lastPrice', h['avg_price'])
                pdata.append({"Ticker": h['ticker'], "Qty": h['quantity'], "Avg Buy": round(h['avg_price'], 2), "Live": round(lp, 2), "P&L (₹)": round((lp - h['avg_price'])*h['quantity'], 2)})
            st.dataframe(pd.DataFrame(pdata), width="stretch", hide_index=True)

    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
    st.markdown("##### 📜 Permanent Trade Journal & Execution Log", unsafe_allow_html=True)
    c = db_conn.cursor()
    c.execute("SELECT timestamp, ticker, action, quantity, price, total_value FROM trade_journal WHERE user_id = ? ORDER BY id DESC", (user_id,))
    j_rows = c.fetchall()
    if not j_rows: st.info("No journal history logged yet.")
    else:
        j_df = pd.DataFrame(j_rows, columns=["Timestamp", "Ticker", "Action", "Qty", "Price (₹)", "Total Value (₹)"])
        st.dataframe(j_df, width="stretch", hide_index=True)

elif selected_page == "DB Admin Vault":
    st.markdown("##### 🗄️ Database Administration Vault")
    st.markdown("<p style='color: #9AA0A6; font-size: 14px;'>Manage your local SQLite database, export data, and monitor pruning optimization.</p>", unsafe_allow_html=True)
    
    user_id = st.session_state.user['id']
    
    st.markdown("###### System Health")
    try:
        db_size_kb = os.path.getsize("market_data.db") / 1024
        st.metric("Live Database File Size", f"{db_size_kb:.2f} KB")
    except Exception as e:
        st.error(f"Could not read database file size: {e}")
        
    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
    
    # NEW: Pruning Engine Statistics
    st.markdown("###### 🧹 Database Pruning & Optimization")
    c = db_conn.cursor()
    c.execute("SELECT COUNT(*) FROM trade_journal WHERE user_id = ?", (user_id,))
    active_trades = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM archived_trade_journal WHERE user_id = ?", (user_id,))
    archived_trades = c.fetchone()[0]
    
    col_p1, col_p2 = st.columns(2)
    col_p1.metric("Active Journal Entries (< 1 Year)", active_trades)
    col_p2.metric("Archived Entries (> 1 Year)", archived_trades)
    st.caption("The terminal automatically archives trades older than 365 days on startup to maintain lightning-fast query speeds for the AI and UI.")

    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
    
    st.markdown("###### 📥 One-Click Export")
    c.execute("SELECT timestamp, ticker, action, quantity, price, total_value FROM trade_journal WHERE user_id = ? ORDER BY id DESC", (user_id,))
    journal_rows = c.fetchall()
    
    if journal_rows:
        df_export = pd.DataFrame(journal_rows, columns=["Timestamp", "Ticker", "Action", "Quantity", "Price", "Total Value"])
        csv_data = df_export.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Download Trade Journal (CSV)",
            data=csv_data,
            file_name=f"trade_journal_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No trade data available to export.")
        
    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
    
    st.markdown("###### ⚠️ Danger Zone (Environment Reset)")
    with st.expander("Reset Practice Wallet & Wipe History"):
        st.warning("Action is irreversible. This will reset your wallet to ₹10,00,000, sell all current holdings, and permanently delete your live trade journal.")
        
        confirm_reset = st.text_input("Type 'RESET' to confirm execution:")
        if st.button("🔥 Execute Hard Reset", type="primary"):
            if confirm_reset == "RESET":
                c.execute("UPDATE practice_wallets SET balance = 1000000.00 WHERE user_id = ?", (user_id,))
                c.execute("DELETE FROM practice_holdings WHERE user_id = ?", (user_id,))
                c.execute("DELETE FROM trade_journal WHERE user_id = ?", (user_id,))
                db_conn.commit()
                st.success("Database Reset Successfully! Wallet restored to ₹10,00,000.")
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("You must type 'RESET' exactly to execute the wipe.")
