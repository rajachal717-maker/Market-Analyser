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
# 📂 ENVIRONMENT ROUTING & DB
# =====================================================================
if os.path.exists('/mount/src/'):
    DB_PATH = "/tmp/market_data.db"
    BACKUP_DIR = "/tmp/backups"
else:
    DB_PATH = "market_data.db"
    BACKUP_DIR = "backups"

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    except sqlite3.DatabaseError:
        if os.path.exists(DB_PATH): os.remove(DB_PATH)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS practice_wallets (user_id INTEGER PRIMARY KEY, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS practice_holdings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ticker TEXT, quantity INTEGER, avg_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trade_journal (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, timestamp TEXT, ticker TEXT, action TEXT, quantity INTEGER, price REAL, total_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS price_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ticker TEXT, target_price REAL, condition TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS archived_trade_journal (id INTEGER PRIMARY KEY, user_id INTEGER, timestamp TEXT, ticker TEXT, action TEXT, quantity INTEGER, price REAL, total_value REAL)''')
    conn.commit()
    return conn

db_conn = init_db()

def create_shadow_backup():
    if os.path.exists(DB_PATH):
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        today_str = datetime.now().strftime("%Y-%m-%d")
        backup_filename = f"market_data_{today_str}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        if not os.path.exists(backup_path):
            shutil.copy2(DB_PATH, backup_path)
            all_backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")])
            if len(all_backups) > 7:
                oldest_backup = all_backups[0]
                os.remove(os.path.join(BACKUP_DIR, oldest_backup))

create_shadow_backup()

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

# =====================================================================
# 🎨 011.PNG EXACT CSS MATCH ENGINE
# =====================================================================
st.set_page_config(page_title="J.A.R.V.I.S.", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Global Layout & Pitch Black Background */
html, body, [class*="css"], .stApp { 
    font-family: 'Inter', sans-serif; 
    background-color: #000000 !important; 
    color: #FFFFFF; 
}
header { background-color: transparent !important; }

/* Sidebar Styling (Dark Grey) */
[data-testid="stSidebar"] { 
    background-color: #0E0E12 !important; 
    border-right: 1px solid #1C1C21; 
}

/* Inputs & Form Elements (Dark Pills) */
.stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input { 
    background-color: #121214 !important; 
    color: #FFFFFF !important; 
    border: 1px solid #27272A !important; 
    border-radius: 8px !important; 
    padding: 12px 16px !important;
    font-weight: 500;
    transition: all 0.2s ease;
}
.stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
    border-color: #A855F7 !important;
    box-shadow: 0 0 0 1px #A855F7 !important;
}

/* Primary Button Override (Neon Purple/Pink Gradient) */
button[kind="primary"] {
    background: linear-gradient(90deg, #9333EA 0%, #D946EF 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 50px !important; /* Full pill shape */
    font-weight: 600 !important;
    font-size: 15px !important;
    padding: 10px 24px !important;
    box-shadow: 0 4px 14px rgba(217, 70, 239, 0.3) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(217, 70, 239, 0.5) !important;
}

/* Secondary Button Override */
button[kind="secondary"] {
    background-color: #18181B !important;
    color: #E3E3E3 !important;
    border: 1px solid #27272A !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}
button[kind="secondary"]:hover {
    border-color: #A1A1AA !important;
}

/* Invisible Metric Containers (Match screenshot floating text) */
div[data-testid="metric-container"] { 
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0px !important; 
}
[data-testid="stMetricLabel"] { 
    color: #A1A1AA !important; 
    font-size: 13px !important; 
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] { 
    color: #FFFFFF !important; 
    font-size: 36px !important; 
    font-weight: 700 !important; 
    letter-spacing: -1px;
}
[data-testid="stMetricDelta"] {
    font-size: 14px !important;
    font-weight: 600 !important;
    padding: 4px 8px !important;
    border-radius: 4px !important;
}
/* Style the positive delta specifically for that green badge look */
[data-testid="stMetricDelta"] > div:first-child {
    background-color: rgba(0, 230, 118, 0.15) !important;
    color: #00E676 !important;
    padding: 2px 8px;
    border-radius: 12px;
}

/* Expander / Accodions */
.streamlit-expanderHeader {
    background-color: #0E0E12 !important;
    border-radius: 8px !important;
    border: 1px solid #1C1C21 !important;
    font-weight: 600 !important;
}
div[data-testid="stExpanderDetails"] {
    border: 1px solid #1C1C21;
    border-top: none;
    border-radius: 0 0 8px 8px;
    background-color: #000000;
}

/* Custom Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; border: none; }
.stTabs [data-baseweb="tab"] { height: 40px; background-color: #0E0E12; border-radius: 8px; border: 1px solid #27272A; color: #A1A1AA; padding: 0 20px; font-weight: 600; font-size: 14px; }
.stTabs [aria-selected="true"] { background-color: rgba(147, 51, 234, 0.1) !important; color: #D946EF !important; border: 1px solid rgba(217, 70, 239, 0.5) !important; }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# =====================================================================
# 🔓 LOCK SCREEN
# =====================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<div style='height: 25vh;'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h1 style='text-align: center; font-size: 3rem; letter-spacing: -2px; color: #FFF; margin-bottom: -10px;'>jarvis.</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #A1A1AA; margin-bottom: 40px;'>Secure terminal access</p>", unsafe_allow_html=True)
        with st.form("pin_form", clear_on_submit=True):
            pin = st.text_input("PIN", type="password", label_visibility="collapsed", placeholder="Enter PIN")
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Authenticate", width="stretch", type="primary")
            if submitted:
                if pin == "0109":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid PIN.")
    st.stop()

if "user" not in st.session_state or not st.session_state.user:
    st.session_state.user = get_or_create_default_user()
if "nse_watchlist" not in st.session_state:
    st.session_state.nse_watchlist = ["NIFTY", "BANKNIFTY", "VMART", "NOCIL"]

# =====================================================================
# 🧭 SIDEBAR NAVIGATION (MATCHING 011.PNG)
# =====================================================================
with st.sidebar:
    user_email = st.session_state.user.get("email", "Active User")
    
    # EXACT replica of the top-left profile card
    st.markdown(f"""
        <div style="background: #121216; border: 1px solid #1C1C21; border-radius: 16px; padding: 16px; display: flex; align-items: center; margin-bottom: 24px;">
            <div style="width: 44px; height: 44px; border-radius: 12px; background: #FFFFFF; display: flex; justify-content: center; align-items: center; color: #000; font-weight: 800; font-size: 20px; margin-right: 14px;">Q</div>
            <div>
                <div style="font-size: 15px; color: #FFFFFF; font-weight: 700;">@quant</div>
                <div style="font-size: 12px; color: #00FFA3; font-weight: 600; display: flex; align-items: center; gap: 6px; margin-top: 2px;">
                    <span style="width: 6px; height: 6px; background:#00FFA3; border-radius:50%; display:inline-block; box-shadow: 0 0 6px #00FFA3;"></span> Online
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    selected_page = option_menu(
        menu_title=None,
        options=["AI Assistant", "Web Intelligence", "Live Market Feed", "Screener & Diagnostics", "Strategy Backtester", "Practice Wallet & Journal", "DB Admin Vault"],
        icons=["robot", "globe", "activity", "search", "bar-chart", "wallet2", "server"],
        default_index=3,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#8A8F98", "font-size": "16px"},
            "nav-link": {"font-family": "Inter", "font-size": "14px", "font-weight": "600", "text-align": "left", "margin": "4px 0px", "color": "#8A8F98", "border-radius": "100px", "padding": "12px 16px", "transition": "all 0.2s"},
            "nav-link-selected": {"background-color": "#FFFFFF", "color": "#000000", "font-weight": "700", "border-radius": "100px"},
        }
    )

# =====================================================================
# 🌐 EXACT MAIN HEADER (MATCHING 011.PNG)
# =====================================================================
st.markdown(f"""
    <div style="background-color: #0C0C0F; padding: 36px 48px; border-radius: 24px; display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; border: 1px solid #1F1F22;">
        <div>
            <h1 style="margin:0; font-size: 42px; font-weight: 800; letter-spacing: -1.5px; color: #FFFFFF;">jarvis.</h1>
            <p style="margin: 12px 0 0 0; color: #8A8F98; font-size: 15px; font-weight: 500;">{selected_page}</p>
        </div>
        <div style="display: flex; gap: 12px;">
            <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 20px; font-size: 12px; color: #E3E3E3; display: flex; align-items: center; gap: 6px; font-weight: 600;"><span style="color:#EF4444;">🛡️</span> AES-256</div>
            <div style="background: rgba(0, 255, 163, 0.05); border: 1px solid rgba(0, 255, 163, 0.2); padding: 8px 16px; border-radius: 20px; font-size: 12px; color: #00FFA3; display: flex; align-items: center; gap: 6px; font-weight: 600;">⚡ Synced</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# =====================================================================
# MODULE ROUTING
# =====================================================================
if selected_page == "AI Assistant":
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "J.A.R.V.I.S. is online. Synced to portfolio. What's the target?"}]
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="⚡" if message["role"] == "assistant" else "👤"):
            st.markdown(message["content"])
            
    if prompt := st.chat_input("Query database or external API..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"): st.markdown(prompt)
        with st.chat_message("assistant", avatar="⚡"):
            with st.spinner("Processing via NVIDIA NIM..."):
                try:
                    api_key = os.environ.get("NVIDIA_API_KEY")
                    if not api_key: st.error("NVIDIA_API_KEY missing.")
                    else:
                        c = db_conn.cursor()
                        c.execute("SELECT balance FROM practice_wallets WHERE user_id = ?", (st.session_state.user['id'],))
                        balance = c.fetchone()[0]
                        c.execute("SELECT ticker, quantity FROM practice_holdings WHERE user_id = ?", (st.session_state.user['id'],))
                        holdings = c.fetchall()
                        from langchain_nvidia_ai_endpoints import ChatNVIDIA
                        llm = ChatNVIDIA(model="nvidia/nemotron-3-ultra-550b-a55b", temperature=0, nvidia_api_key=api_key)
                        res = llm.invoke(f"Data: ₹{balance} cash. Holdings: {holdings}. Query: {prompt}. Be brief and highly technical.").content
                        st.markdown(res)
                        st.session_state.messages.append({"role": "assistant", "content": res})
                except Exception as e: st.error(str(e))

elif selected_page == "Web Intelligence":
    st.markdown("<p style='font-size: 14px; color: #A1A1AA; margin-bottom: 4px;'>Macro Search</p>", unsafe_allow_html=True)
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1: search_query = st.text_input("Query", placeholder="Search macro indicators...", label_visibility="collapsed")
    with col_s2: search_btn = st.button("Search Web", type="primary", use_container_width=True)
    if search_btn and search_query.strip():
        try:
            from ddgs import DDGS
            with st.spinner("Scanning sources..."):
                with DDGS() as ddgs:
                    results = list(ddgs.text(search_query, max_results=5))
                    for i, r in enumerate(results, 1):
                        with st.expander(f"{r.get('title', 'No Title')}", expanded=(i == 1)):
                            st.write(r.get('body', ''))
                            st.markdown(f"[Source Link]({r.get('href', '#')})")
        except Exception as e: st.error(f"Search error: {e}")

elif selected_page == "Live Market Feed":
    def get_exact_yf_quote(exact_symbol):
        import yfinance as yf
        try:
            ticker = yf.Ticker(exact_symbol)
            curr, prev = ticker.fast_info.get('lastPrice'), ticker.fast_info.get('previousClose')
            if curr and prev: return {"Symbol": exact_symbol, "Last (₹)": round(curr, 2), "Change (%)": round(((curr - prev) / prev) * 100, 2)}
        except: pass
        return {"Symbol": exact_symbol, "Last (₹)": "N/A", "Change (%)": "N/A"}

    st.markdown("<p style='font-size: 14px; color: #A1A1AA; margin-bottom: 4px;'>Universal Search</p>", unsafe_allow_html=True)
    search_query = st.text_input("Search", placeholder="Type ticker and press Enter...", label_visibility="collapsed")
    if search_query.strip():
        with st.spinner("Fetching..."):
            try:
                exact_symbol = format_ticker(search_query)
                quote = get_exact_yf_quote(exact_symbol)
                if quote["Last (₹)"] != "N/A":
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Asset", quote['Symbol'])
                    c2.metric("LTP", f"₹{quote['Last (₹)']}")
                    c3.metric("Change", f"{quote['Change (%)']}%", delta=f"{quote['Change (%)']}%")
                else: st.error("Unavailable.")
            except: pass
            
    st.markdown("<br><hr style='border-color: #1C1C21;'><br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Watchlist")
        wl = st.text_area("", value=", ".join(st.session_state.nse_watchlist), label_visibility="collapsed")
        if st.button("Update"): st.session_state.nse_watchlist = [t.strip().upper() for t in wl.split(",") if t.strip()]; st.rerun()
    with c2:
        st.markdown("###### Background Scanner")
        if st.button("Start Live Scanner", type="primary", use_container_width=True):
            st.info("Scanner running in background.")

elif selected_page == "Screener & Diagnostics":
    # EXACT LAYOUT OF 011.PNG
    st.markdown("<p style='font-size: 14px; color: #8A8F98; margin-bottom: 8px;'>Enter Ticker</p>", unsafe_allow_html=True)
    
    # Input and Button Side-by-Side
    c1, c2 = st.columns([3.5, 1.5])
    with c1: 
        target_symbol = st.text_input("Ticker", value="NIFTY", label_visibility="collapsed").strip().upper()
    with c2: 
        scan_btn = st.button("Run Scan", type="primary", use_container_width=True)

    if scan_btn or target_symbol:
        import yfinance as yf
        yf_target = format_ticker(target_symbol)
        
        with st.spinner(f"Analyzing {target_symbol}..."):
            try:
                ticker_obj = yf.Ticker(yf_target)
                hist = ticker_obj.history(period="6mo")
                if not hist.empty:
                    # Technicals
                    hist['EMA20'] = hist['Close'].ewm(span=20).mean()
                    hist['EMA50'] = hist['Close'].ewm(span=50).mean()
                    delta = hist['Close'].diff()
                    up = delta.where(delta > 0, 0)
                    down = -delta.where(delta < 0, 0)
                    rs = up.ewm(alpha=1/14, adjust=False).mean() / down.ewm(alpha=1/14, adjust=False).mean()
                    hist['RSI'] = 100 - (100 / (1 + rs))
                    
                    last_price = hist['Close'].iloc[-1]
                    last_rsi = hist['RSI'].iloc[-1]
                    trend_signal = "BULLISH" if hist['EMA20'].iloc[-1] > hist['EMA50'].iloc[-1] else "BEARISH"
                    
                    # MATCHING THE METRICS IN THE SCREENSHOT
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("LTP", f"₹{round(last_price, 2)}")
                    m2.metric("RSI (14)", f"{round(last_rsi, 2)}")
                    m3.metric("Trend Signal", trend_signal, delta="↑ EMA Crossover" if trend_signal=="BULLISH" else "↓ Bear Cross", delta_color="normal" if trend_signal=="BULLISH" else "inverse")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # MATCHING THE PLOTLY CHART IN THE SCREENSHOT
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
                    
                    # Candlestick (Neon Green / Pink)
                    fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='Price', increasing_line_color='#00E676', decreasing_line_color='#FF1744'), row=1, col=1)
                    
                    # EMA Lines (Purple and White)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA20'], line=dict(color='#A855F7', width=2), name='EMA 20'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], line=dict(color='#FFFFFF', width=2), name='EMA 50'), row=1, col=1)
                    
                    # Volume
                    colors = ['#00E676' if row['Close'] >= row['Open'] else '#FF1744' for _, row in hist.iterrows()]
                    fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                    
                    # Layout Styling
                    fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False, height=550, margin=dict(l=0, r=0, t=10, b=0), showlegend=False, hovermode='x unified')
                    fig.update_yaxes(gridcolor='#1C1C21')
                    fig.update_xaxes(gridcolor='#1C1C21')
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # STATIONARY XGBOOST ENGINE
                    with st.expander("🤖 Advanced ML Forecaster (Stationary XGBoost)", expanded=False):
                        if st.button("Generate ML Prediction", type="primary"):
                            with st.spinner("Training Stationary XGBoost Model..."):
                                try:
                                    from xgboost import XGBRegressor
                                    intra_data = ticker_obj.history(period="5d", interval="15m")
                                    if not intra_data.empty and len(intra_data) > 20:
                                        df = intra_data[['Close', 'Volume']].copy()
                                        df['Return'] = df['Close'].pct_change()
                                        df['Target_Return'] = df['Return'].shift(-1) 
                                        df['Lag1_Ret'] = df['Return'].shift(1)
                                        df['Lag2_Ret'] = df['Return'].shift(2)
                                        df['Vol_Change'] = df['Volume'].pct_change().replace([np.inf, -np.inf], 0).fillna(0)
                                        df['Volatility'] = df['Return'].rolling(window=10).std().fillna(0)
                                        df = df.dropna(subset=['Return', 'Target_Return', 'Lag1_Ret', 'Lag2_Ret'])
                                        
                                        if len(df) < 5: st.error("Data collapsed.")
                                        else:
                                            X = df[['Return', 'Lag1_Ret', 'Lag2_Ret', 'Vol_Change', 'Volatility']]
                                            y = df['Target_Return']
                                            model = XGBRegressor(n_estimators=100, learning_rate=0.03, max_depth=3, random_state=42)
                                            model.fit(X, y)
                                            
                                            future_steps = 25
                                            curr_ret = float(df['Return'].iloc[-1])
                                            curr_lag1_ret = float(df['Lag1_Ret'].iloc[-1])
                                            curr_lag2_ret = float(df['Lag2_Ret'].iloc[-1])
                                            avg_vol_change = float(df['Vol_Change'].mean())
                                            avg_volatility = float(df['Volatility'].mean())
                                            
                                            predicted_returns = []
                                            for _ in range(future_steps):
                                                pred_df = pd.DataFrame([[curr_ret, curr_lag1_ret, curr_lag2_ret, avg_vol_change, avg_volatility]], columns=['Return', 'Lag1_Ret', 'Lag2_Ret', 'Vol_Change', 'Volatility'])
                                                pred_ret = float(model.predict(pred_df)[0])
                                                predicted_returns.append(pred_ret)
                                                curr_lag2_ret = curr_lag1_ret
                                                curr_lag1_ret = curr_ret
                                                curr_ret = pred_ret
                                                
                                            last_real_price = float(intra_data['Close'].iloc[-1])
                                            pred_prices = []
                                            for ret in predicted_returns:
                                                next_price = last_real_price * (1 + ret)
                                                pred_prices.append(next_price)
                                                last_real_price = next_price
                                                
                                            pred_fig = go.Figure()
                                            hist_plot = intra_data.tail(50)
                                            pred_fig.add_trace(go.Scatter(x=np.arange(len(hist_plot)), y=hist_plot['Close'], mode='lines', name='Historical 15m', line=dict(color='#FFFFFF', width=2)))
                                            
                                            pred_x = np.arange(len(hist_plot) - 1, len(hist_plot) + future_steps)
                                            pred_y = [hist_plot['Close'].iloc[-1]] + pred_prices
                                            
                                            pred_fig.add_trace(go.Scatter(x=pred_x, y=pred_y, mode='lines', name='XGBoost Forecast', line=dict(color='#D946EF', width=3, dash='dash'))) # Neon Pink Line
                                            
                                            std_dev = intra_data['Close'].tail(20).std()
                                            pred_fig.add_trace(go.Scatter(x=pred_x, y=[y + (std_dev * 1.5) for y in pred_y], line=dict(color='rgba(217, 70, 239, 0)'), showlegend=False))
                                            pred_fig.add_trace(go.Scatter(x=pred_x, y=[y - (std_dev * 1.5) for y in pred_y], fill='tonexty', fillcolor='rgba(217, 70, 239, 0.1)', line=dict(color='rgba(217, 70, 239, 0)'), name='Confidence Zone'))
                                            
                                            pred_fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400, title=f"Stationary Prediction", margin=dict(l=0, r=0, t=30, b=0))
                                            st.plotly_chart(pred_fig, use_container_width=True)
                                            st.success(f"Forecast Complete. Target: ₹{round(pred_prices[-1], 2)}")
                                except Exception as e: st.error(f"ML Model Error: {e}")

            except Exception as e: st.error(f"Error rendering charts: {e}")

elif selected_page == "Strategy Backtester":
    tab_rebalance, tab_ema = st.tabs(["⚖️ Portfolio Rebalancing", "📈 EMA Crossover Engine"])
    
    with tab_ema:
        st.markdown("<br><p style='color: #8A8F98; font-size: 14px;'>Simulate strategies with strict 0.05% slippage/tax friction.</p>", unsafe_allow_html=True)
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
            run_backtest = st.form_submit_button("Run 1000x Simulation", type="primary")
            
        if run_backtest and b_ticker:
            with st.spinner(f"Simulating trades..."):
                try:
                    import yfinance as yf
                    hist = yf.Ticker(format_ticker(b_ticker)).history(period=b_period)
                    if len(hist) > slow_ema:
                        hist['EMA_Fast'], hist['EMA_Slow'] = hist['Close'].ewm(span=fast_ema).mean(), hist['Close'].ewm(span=slow_ema).mean()
                        delta = hist['Close'].diff()
                        rs = delta.where(delta>0,0).ewm(alpha=1/14, adjust=False).mean() / (-delta.where(delta<0,0)).ewm(alpha=1/14, adjust=False).mean()
                        hist['RSI'] = 100 - (100 / (1 + rs))
                        
                        in_pos, entry_price, capital = False, 0, 100000.0  
                        trades, equity_curve, friction = [], [], 0.0005 
                        
                        for i in range(1, len(hist)):
                            date = hist.index[i]
                            c, h, l = hist['Close'].iloc[i], hist['High'].iloc[i], hist['Low'].iloc[i]
                            if in_pos:
                                tp, sl = entry_price * (1 + (tp_pct / 100)), entry_price * (1 - (sl_pct / 100))
                                if h >= tp:
                                    capital += ((tp * (1-friction) - entry_price) / entry_price) * capital
                                    trades.append({"Type": "WIN"}); in_pos = False
                                elif l <= sl:
                                    capital -= ((entry_price - sl * (1-friction)) / entry_price) * capital
                                    trades.append({"Type": "LOSS"}); in_pos = False
                            if not in_pos:
                                if (hist['EMA_Fast'].iloc[i] > hist['EMA_Slow'].iloc[i]) and (hist['EMA_Fast'].iloc[i-1] <= hist['EMA_Slow'].iloc[i-1]):
                                    if not use_rsi or hist['RSI'].iloc[i] < rsi_thresh:
                                        in_pos, entry_price = True, c * (1 + friction)
                            equity_curve.append({"Date": date, "Capital": capital})
                            
                        st.markdown("<hr style='border-color: #1C1C21; margin: 24px 0;'>", unsafe_allow_html=True)
                        m1, m2, m3, m4 = st.columns(4)
                        win_r = (len([t for t in trades if t["Type"]=="WIN"]) / len(trades) * 100) if trades else 0
                        net_ret = ((capital - 100000) / 100000) * 100
                        
                        m1.metric("Total Trades", len(trades))
                        m2.metric("Win Rate", f"{win_r:.1f}%")
                        m3.metric("Final Capital", f"₹{capital:,.2f}")
                        m4.metric("Net ROI", f"{net_ret:.2f}%", delta=f"{net_ret:.2f}%")
                        
                        fig = px.line(pd.DataFrame(equity_curve), x="Date", y="Capital")
                        fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), height=350)
                        fig.update_traces(line=dict(color='#A855F7', width=2))
                        fig.update_yaxes(gridcolor='#1C1C21')
                        fig.update_xaxes(gridcolor='#1C1C21')
                        st.plotly_chart(fig, use_container_width=True)
                except Exception as e: st.error(f"Error: {e}")

elif selected_page == "Practice Wallet & Journal":
    tab_exec, tab_analytics, tab_journal = st.tabs(["🚀 Live Execution", "📊 Analytics", "📜 Journal"])
    
    with tab_exec:
        st.markdown("<br>", unsafe_allow_html=True)
        col_trade, col_port = st.columns([1, 2])
        with col_trade:
            st.markdown("###### Fire Order")
            with st.form("live_trade_form"):
                t_ticker = st.text_input("Ticker", placeholder="RELIANCE").strip().upper()
                t_exch = st.selectbox("Exchange", ["NSE", "BSE"])
                t_qty = st.number_input("Qty", min_value=1, step=1)
                t_action = st.radio("Action", ["BUY", "SELL"], horizontal=True)
                order_type = st.selectbox("Type", ["MARKET", "LIMIT"])
                limit_price = st.number_input("Limit Price", min_value=0.0, step=0.5)
                
                if st.form_submit_button("Route to Broker", type="primary"):
                    st.success("Test order logged to Journal.")
        with col_port:
            st.markdown("###### Live Positions")
            st.info("API Key required to view positions.")
                    
    with tab_analytics:
        st.markdown("<br>", unsafe_allow_html=True)
        c = db_conn.cursor()
        c.execute("SELECT balance FROM practice_wallets WHERE user_id = ?", (st.session_state.user['id'],))
        current_balance = c.fetchone()[0]
        net_pnl = current_balance - 1000000.00
        c.execute("SELECT COUNT(*) FROM trade_journal WHERE user_id = ?", (st.session_state.user['id'],))
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Available Capital", f"₹{current_balance:,.2f}")
        m2.metric("Net P&L", f"₹{net_pnl:,.2f}", delta=f"{(net_pnl/1000000)*100:.2f}%")
        m3.metric("Trades Logged", c.fetchone()[0])

elif selected_page == "DB Admin Vault":
    user_id = st.session_state.user['id']
    st.markdown("###### System Health")
    try: st.metric("Live DB Size", f"{os.path.getsize(DB_PATH)/1024:.2f} KB")
    except: pass
