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
# 📂 ENVIRONMENT ROUTING (STREAMLIT CLOUD FIX)
# =====================================================================
if os.path.exists('/mount/src/'):
    DB_PATH = "/tmp/market_data.db"
    BACKUP_DIR = "/tmp/backups"
else:
    DB_PATH = "market_data.db"
    BACKUP_DIR = "backups"

# =====================================================================
# 🗄️ ADVANCED PROFESSIONAL SQLITE BACKEND
# =====================================================================
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    except sqlite3.DatabaseError:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS practice_wallets (user_id INTEGER PRIMARY KEY, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS practice_holdings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ticker TEXT, quantity INTEGER, avg_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trade_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, timestamp TEXT, ticker TEXT, 
                    action TEXT, quantity INTEGER, price REAL, total_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS price_alerts (
                     id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ticker TEXT, target_price REAL, condition TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS archived_trade_journal (
                    id INTEGER PRIMARY KEY, user_id INTEGER, timestamp TEXT, ticker TEXT, 
                    action TEXT, quantity INTEGER, price REAL, total_value REAL)''')
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

def auto_prune_database():
    try:
        c = db_conn.cursor()
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT COUNT(*) FROM trade_journal WHERE timestamp < ?", (one_year_ago,))
        old_trades_count = c.fetchone()[0]
        if old_trades_count > 0:
            c.execute('''INSERT OR IGNORE INTO archived_trade_journal 
                         SELECT * FROM trade_journal WHERE timestamp < ?''', (one_year_ago,))
            c.execute('''DELETE FROM trade_journal WHERE timestamp < ?''', (one_year_ago,))
            db_conn.commit()
    except Exception as e:
        pass

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

# =====================================================================
# 🎨 SLICE / GEN-Z FINTECH UI ENGINE
# =====================================================================
st.set_page_config(page_title="J.A.R.V.I.S.", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

/* Global Layout & Typography */
html, body, [class*="css"], .stApp { 
    font-family: 'Plus Jakarta Sans', sans-serif; 
    background-color: #000000 !important; /* Pitch Black */
    color: #F4F4F5; 
}
header { background-color: transparent !important; }

/* Sidebar Styling */
[data-testid="stSidebar"] { 
    background-color: #09090B !important; 
    border-right: 1px solid #18181B; 
}

/* Inputs & Form Elements (Pill/Rounded) */
.stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea, .stNumberInput>div>div>input { 
    background-color: #121214 !important; 
    color: #FFFFFF !important; 
    border: 1px solid #27272A !important; 
    border-radius: 16px !important; 
    padding: 14px 18px !important;
    font-weight: 500;
    transition: all 0.2s ease;
}
.stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
    border-color: #7C3AED !important; /* Vibrant Purple Focus */
    box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2) !important;
}

/* Primary Buttons (Slice Pill Style) */
.stButton>button { 
    background: #FFFFFF; /* High contrast white button */
    color: #000000; 
    border: none; 
    border-radius: 9999px; /* Absolute Pill */
    font-weight: 700; 
    font-size: 15px;
    letter-spacing: 0.2px;
    padding: 0.6rem 1.8rem; 
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.stButton>button:hover {
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 10px 25px rgba(255, 255, 255, 0.15);
    background: #F4F4F5;
    color: #000000;
}

/* Action/Primary Action Button Override (Neon) */
button[kind="primary"] {
    background: linear-gradient(135deg, #7C3AED 0%, #C026D3 100%) !important;
    color: white !important;
    box-shadow: 0 8px 20px rgba(124, 58, 237, 0.3);
}
button[kind="primary"]:hover {
    box-shadow: 0 12px 30px rgba(124, 58, 237, 0.5) !important;
}

/* Gen-Z Metric Cards (Squircle & Large Data) */
div[data-testid="metric-container"] { 
    background: #0C0C0E;
    border: 1px solid #1F1F22; 
    padding: 24px 28px; 
    border-radius: 28px; /* Heavy squircle rounding */
    transition: all 0.3s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-4px);
    border-color: #3F3F46;
    box-shadow: 0 12px 30px rgba(0,0,0,0.8);
}
[data-testid="stMetricLabel"] { 
    color: #A1A1AA !important; 
    font-size: 13px !important; 
    font-weight: 600 !important;
    text-transform: capitalize; 
}
[data-testid="stMetricValue"] { 
    color: #FFFFFF !important; 
    font-family: 'Space Grotesk', sans-serif !important; 
    font-size: 36px !important; /* Massive numbers */
    font-weight: 700 !important; 
    letter-spacing: -1px;
    background: linear-gradient(90deg, #FFFFFF, #D4D4D8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-top: 6px;
}
[data-testid="stMetricDelta"] {
    font-family: 'Space Grotesk', sans-serif !important; 
    font-size: 15px !important;
    font-weight: 600 !important;
}

/* Expander Modernization */
.streamlit-expanderHeader {
    background-color: #0C0C0E !important;
    border-radius: 16px !important;
    border: 1px solid #1F1F22 !important;
    font-weight: 600 !important;
    font-size: 15px !important;
}
div[data-testid="stExpanderDetails"] {
    border: 1px solid #1F1F22;
    border-top: none;
    border-radius: 0 0 16px 16px;
    background-color: #000000;
}

/* Custom Tabs (Pill Toggles) */
.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
    background-color: transparent;
    padding-bottom: 8px;
}
.stTabs [data-baseweb="tab"] {
    height: 44px;
    background-color: #121214;
    border-radius: 9999px; /* Pill tabs */
    border: 1px solid #27272A;
    color: #A1A1AA;
    padding: 0 24px;
    font-weight: 600;
    font-size: 14px;
}
.stTabs [aria-selected="true"] {
    background-color: #FFFFFF !important;
    color: #000000 !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(255,255,255,0.1);
}

/* Dataframe Styling */
.stDataFrame {
    border-radius: 16px;
    overflow: hidden;
}

/* Floating Top Nav (App Style) */
.dash-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 30px;
    background: rgba(18, 18, 20, 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 24px;
    margin-bottom: 24px;
}
.dash-title {
    margin: 0;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #FFFFFF;
}
.dash-subtitle {
    margin: 0;
    font-size: 14px;
    color: #A1A1AA;
    font-weight: 500;
    margin-top: 4px;
}
.badge-container {
    display: flex;
    gap: 12px;
}
.badge-pill {
    background: #18181B;
    color: #E4E4E7;
    padding: 8px 16px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #27272A;
    display: flex;
    align-items: center;
    gap: 6px;
}
.badge-neon {
    background: rgba(0, 255, 163, 0.1);
    color: #00FFA3;
    border: 1px solid rgba(0, 255, 163, 0.2);
}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# =====================================================================
# 🔒 APP INVITE / LOCK SCREEN (GEN-Z VIBE)
# =====================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<div style='margin-top: 20vh;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style="background: #09090B; border: 1px solid #1F1F22; border-radius: 32px; padding: 48px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.8);">
            <div style="width: 64px; height: 64px; background: linear-gradient(135deg, #7C3AED, #C026D3); border-radius: 20px; display: flex; align-items: center; justify-content: center; margin: 0 auto 24px auto; box-shadow: 0 10px 25px rgba(124, 58, 237, 0.4);">
                <span style="font-size: 28px;">⚡</span>
            </div>
            <h2 style='font-family: "Space Grotesk", sans-serif; color: #FFFFFF; font-weight: 700; margin-bottom: 8px; font-size: 28px;'>jarvis.</h2>
            <p style='color: #A1A1AA; font-size: 15px; margin-bottom: 32px; font-weight: 500;'>Enter your access code to launch.</p>
        """, unsafe_allow_html=True)
        
        with st.form("pin_form"):
            pin = st.text_input("Access Code", type="password", max_chars=4, placeholder="••••", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Launch Workspace", width="stretch")
            
            if submitted:
                if pin == "0109":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid access code. Try again.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

try:
    from ddgs import DDGS
    search_available = True
except ImportError:
    search_available = False

if "user" not in st.session_state or not st.session_state.user:
    st.session_state.user = get_or_create_default_user()

if "nse_watchlist" not in st.session_state:
    st.session_state.nse_watchlist = ["NIFTY", "BANKNIFTY", "VMART", "NOCIL", "RELIANCE"]
if "bse_watchlist" not in st.session_state:
    st.session_state.bse_watchlist = ["SENSEX", "RELIANCE", "INFY", "TCS"]

# =====================================================================
# 🧭 SIDEBAR NAVIGATION (SLICE PROFILE)
# =====================================================================
with st.sidebar:
    user_email = st.session_state.user.get("email", "Active User")
    user_initial = user_email[0].upper()
    
    st.markdown(f"""
        <div style="background: #121214; border: 1px solid #27272A; border-radius: 20px; padding: 16px; display: flex; align-items: center; margin-bottom: 32px;">
            <div style="width: 46px; height: 46px; border-radius: 14px; background: #FFFFFF; display: flex; justify-content: center; align-items: center; color: #000000; font-weight: 800; font-family: 'Space Grotesk', sans-serif; font-size: 20px; margin-right: 14px;">{user_initial}</div>
            <div style="overflow: hidden;">
                <div style="font-size: 14px; color: #FFFFFF; font-weight: 700; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">@{user_email.split('@')[0]}</div>
                <div style="font-size: 12px; color: #00FFA3; font-weight: 600; display: flex; align-items: center; gap: 4px; margin-top: 2px;">
                    <span style="width: 6px; height: 6px; background:#00FFA3; border-radius:50%; display:inline-block;"></span> Online
                </div>
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
            "icon": {"color": "#A1A1AA", "font-size": "18px"},
            "nav-link": {"font-family": "Plus Jakarta Sans", "font-size": "15px", "font-weight": "600", "text-align": "left", "margin": "8px 0px", "--hover-color": "#18181B", "color": "#A1A1AA", "border-radius": "12px", "padding": "14px 16px", "transition": "all 0.2s"},
            "nav-link-selected": {"background-color": "#FFFFFF", "color": "#000000", "font-weight": "700", "border-radius": "12px"},
        }
    )

# =====================================================================
# 🌐 GLOBAL DASHBOARD HEADER
# =====================================================================
st.markdown(f"""
    <div class="dash-header">
        <div>
            <h1 class="dash-title">jarvis.</h1>
            <p class="dash-subtitle">{selected_page}</p>
        </div>
        <div class="badge-container">
            <div class="badge-pill">🛡️ AES-256</div>
            <div class="badge-pill badge-neon">⚡ Synced</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# =====================================================================
# MODULE ROUTING
# =====================================================================
if selected_page == "AI Assistant":
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Yo. J.A.R.V.I.S. is online and synced to your portfolio. What's the move today?"}]
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="⚡" if message["role"] == "assistant" else "👤"):
            st.markdown(message["content"])
            
    if prompt := st.chat_input("Ask a quantitative or portfolio question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"): 
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="⚡"):
            with st.spinner("Processing via NVIDIA NIM..."):
                try:
                    api_key = os.environ.get("NVIDIA_API_KEY")
                    if not api_key: 
                        st.error("NVIDIA_API_KEY missing.")
                    else:
                        active_user_id = st.session_state.user['id']
                        c = db_conn.cursor()
                        c.execute("SELECT balance FROM practice_wallets WHERE user_id = ?", (active_user_id,))
                        bal_row = c.fetchone()
                        balance = bal_row[0] if bal_row else 0.0
                        
                        c.execute("SELECT ticker, quantity, avg_price FROM practice_holdings WHERE user_id = ?", (active_user_id,))
                        holdings = c.fetchall()
                        
                        context = f"User has ₹{balance} cash. Holdings: {holdings}. Query: {prompt}"
                        
                        from langchain_nvidia_ai_endpoints import ChatNVIDIA
                        llm = ChatNVIDIA(model="nvidia/nemotron-3-ultra-550b-a55b", temperature=0, nvidia_api_key=api_key)
                        response = llm.invoke(f"You are J.A.R.V.I.S. Use this data to accurately answer the user: {context}. Give a short, smart, direct answer.").content
                        
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e: 
                    st.error(f"Error: {e}")

elif selected_page == "Web Intelligence":
    col_s1, col_s2 = st.columns([4, 1])
    with col_s1: search_query = st.text_input("Query", placeholder="Search macro indicators or sector news...", label_visibility="collapsed")
    with col_s2: search_btn = st.button("Search", width="stretch")
    if search_btn and search_query.strip():
        if not search_available: st.error("duckduckgo-search package not installed.")
        else:
            with st.spinner("Scanning..."):
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(search_query, max_results=5))
                        for i, r in enumerate(results, 1):
                            with st.expander(f"{r.get('title', 'No Title')}", expanded=(i == 1)):
                                st.write(r.get('body', ''))
                                st.markdown(f"[Read Full Source]({r.get('href', '#')})")
                except Exception as e: st.error(f"Search error: {e}")

elif selected_page == "Live Market Feed":
    import requests
    def get_exact_yf_quote(exact_symbol):
        import yfinance as yf
        try:
            ticker = yf.Ticker(exact_symbol)
            curr, prev = ticker.fast_info.get('lastPrice'), ticker.fast_info.get('previousClose')
            if curr and prev: 
                return {"Symbol": exact_symbol, "Last (₹)": round(curr, 2), "Change (%)": round(((curr - prev) / prev) * 100, 2)}
        except: pass
        return {"Symbol": exact_symbol, "Last (₹)": "N/A", "Change (%)": "N/A"}

    def search_company_symbols(query):
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=8&newsCount=0"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                quotes = resp.json().get('quotes', [])
                return [f"{q.get('symbol')} | {q.get('shortname', 'Unknown')} ({q.get('exchDisp', 'Unknown')})" 
                        for q in quotes if 'symbol' in q]
        except Exception: pass
        return []

    st.markdown("###### 🔍 Universal Asset Search")
    search_query = st.text_input("Universal Search", placeholder="Type a company name or ticker...", label_visibility="collapsed")
    
    if search_query.strip():
        with st.spinner("Scanning global exchanges..."):
            results = search_company_symbols(search_query)
        if results:
            selected_match = st.selectbox("Select exact listing:", results)
            if selected_match:
                exact_symbol = selected_match.split(" | ")[0].strip()
                with st.spinner(f"Fetching {exact_symbol}..."):
                    quote = get_exact_yf_quote(exact_symbol)
                    if quote["Last (₹)"] != "N/A":
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Asset", quote['Symbol'])
                        c2.metric("Live Price", f"₹{quote['Last (₹)']}")
                        c3.metric("Daily Change", f"{quote['Change (%)']}%", delta=f"{quote['Change (%)']}%")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        with st.expander("🔔 Set Target Price Alert", expanded=False):
                            with st.form("alert_form"):
                                target_p = st.number_input("Target Price (₹)", value=float(quote['Last (₹)']))
                                if st.form_submit_button("Save Alert"):
                                    c = db_conn.cursor()
                                    c.execute("INSERT INTO price_alerts (user_id, ticker, target_price, condition) VALUES (?, ?, ?, ?)", (st.session_state.user['id'], exact_symbol, target_p, "CROSS"))
                                    db_conn.commit()
                                    st.success(f"Alert set for {exact_symbol}!")
                    else: st.error("Live quote unavailable.")
        else: st.warning("No companies found.")
            
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col_w_left, col_w_right = st.columns([1, 1.2])
    with col_w_left:
        st.markdown("###### 📋 Watchlists")
        with st.form("watchlist_form"):
            nse_input = st.text_area("Tracked Tickers (Comma separated)", value=", ".join(st.session_state.nse_watchlist))
            if st.form_submit_button("Update List"):
                st.session_state.nse_watchlist = [t.strip().upper() for t in nse_input.split(",") if t.strip()]
                st.rerun()
    with col_w_right:
        st.markdown("###### 🔔 Active Triggers")
        c = db_conn.cursor()
        c.execute("SELECT id, ticker, target_price FROM price_alerts WHERE user_id = ?", (st.session_state.user['id'],))
        alerts = c.fetchall()
        
        if not alerts: 
            st.info("No active alerts.")
        else:
             for aid, atick, apri in alerts:
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{atick}**  →  <span style='color:#00FFA3'>₹{apri}</span>", unsafe_allow_html=True)
                if c2.button("Del", key=f"del_al_{aid}"):
                    c.execute("DELETE FROM price_alerts WHERE id = ?", (aid,))
                    db_conn.commit()
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("###### 📡 Background Scanner")
        if st.button("Start Live Scan", type="primary", width="stretch"):
            if not alerts: st.warning("Set a target price alert first.")
            else:
                scan_placeholder = st.empty()
                with scan_placeholder.container():
                    st.info("Scanning live exchange data...")
                    spinner_ph = st.empty()
                    for _ in range(300):
                        c.execute("SELECT id, ticker, target_price FROM price_alerts WHERE user_id = ?", (st.session_state.user['id'],))
                        current_alerts = c.fetchall()
                        if not current_alerts:
                            st.success("All alerts triggered or deleted.")
                            break
                        for aid, atick, apri in current_alerts:
                            try:
                                with spinner_ph: st.caption(f"Pinging {atick}...")
                                current_price = get_exact_yf_quote(atick).get('Last (₹)')
                                if current_price != "N/A" and isinstance(current_price, (int, float)):
                                    if apri * 0.995 <= current_price <= apri * 1.005:
                                        st.toast(f"🎯 TARGET HIT: {atick} at ₹{current_price}!", icon='🎯')
                                        st.success(f"**TRIGGERED:** {atick} hit ₹{current_price}.")
                                        c.execute("DELETE FROM price_alerts WHERE id = ?", (aid,))
                                        db_conn.commit()
                            except Exception: pass
                        time.sleep(5)

elif selected_page == "Screener & Diagnostics":
    screen_col1, screen_col2 = st.columns([3, 1])
    with screen_col1: target_symbol = st.text_input("Enter Ticker", value="NIFTY", placeholder="e.g. BANKNIFTY").strip().upper()
    with screen_col2: st.markdown("<br>", unsafe_allow_html=True); scan_btn = st.button("Run Scan", type="primary", width="stretch")

    if scan_btn or target_symbol:
        import yfinance as yf
        yf_target = format_ticker(target_symbol)
        
        with st.spinner(f"Analyzing {target_symbol}..."):
            try:
                ticker_obj = yf.Ticker(yf_target)
                hist = ticker_obj.history(period="6mo")
                if not hist.empty:
                    hist['EMA20'] = hist['Close'].ewm(span=20).mean()
                    hist['EMA50'] = hist['Close'].ewm(span=50).mean()
                    
                    delta = hist['Close'].diff()
                    up = delta.where(delta > 0, 0)
                    down = -delta.where(delta < 0, 0)
                    rs = up.ewm(alpha=1/14, adjust=False).mean() / down.ewm(alpha=1/14, adjust=False).mean()
                    hist['RSI'] = 100 - (100 / (1 + rs))
                    
                    hist['BB_Mid'] = hist['Close'].rolling(window=20).mean()
                    hist['BB_Std'] = hist['Close'].rolling(window=20).std()
                    hist['BB_Upper'] = hist['BB_Mid'] + (hist['BB_Std'] * 2)
                    hist['BB_Lower'] = hist['BB_Mid'] - (hist['BB_Std'] * 2)
                    
                    last_price = hist['Close'].iloc[-1]
                    last_rsi = hist['RSI'].iloc[-1]
                    trend_signal = "BULLISH" if hist['EMA20'].iloc[-1] > hist['EMA50'].iloc[-1] else "BEARISH"
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("LTP", f"₹{round(last_price, 2)}")
                    m2.metric("RSI (14)", f"{round(last_rsi, 2)}")
                    m3.metric("Trend Signal", trend_signal, delta="EMA Crossover" if trend_signal=="BULLISH" else "-EMA Crossover", delta_color="normal" if trend_signal=="BULLISH" else "inverse")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Update Plotly styling for Gen Z Vibe
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                    fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='Price', increasing_line_color='#00FFA3', decreasing_line_color='#FF0055'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA20'], line=dict(color='#7C3AED', width=2), name='EMA 20'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], line=dict(color='#FFFFFF', width=2), name='EMA 50'), row=1, col=1)
                    
                    colors = ['#00FFA3' if row['Close'] >= row['Open'] else '#FF0055' for _, row in hist.iterrows()]
                    fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                    
                    fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False, height=550, margin=dict(l=0, r=0, t=10, b=0), showlegend=False, hovermode='x unified')
                    fig.update_yaxes(gridcolor='#1F1F22')
                    fig.update_xaxes(gridcolor='#1F1F22')
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.expander("🚀 XGBoost ML Forecaster", expanded=False):
                        st.markdown(f"Training XGBoost on **Stationary Log Returns** for {target_symbol}...")
                        if st.button("Generate Forecast", type="primary"):
                            with st.spinner("Training ML Engine..."):
                                try:
                                    from xgboost import XGBRegressor
                                    intra_data = ticker_obj.history(period="5d", interval="15m")
                                    
                                    if intra_data.empty or len(intra_data) < 20:
                                        st.error(f"Not enough intraday data fetched.")
                                    else:
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
                                            pred_fig.add_trace(go.Scatter(x=np.arange(len(hist_plot)), y=hist_plot['Close'], mode='lines', name='Historical', line=dict(color='#FFFFFF', width=2)))
                                            
                                            pred_x = np.arange(len(hist_plot) - 1, len(hist_plot) + future_steps)
                                            pred_y = [hist_plot['Close'].iloc[-1]] + pred_prices
                                            
                                            pred_fig.add_trace(go.Scatter(x=pred_x, y=pred_y, mode='lines', name='XGBoost', line=dict(color='#C026D3', width=3, dash='dash'))) # Neon Pink Forecast
                                            std_dev = intra_data['Close'].tail(20).std()
                                            pred_fig.add_trace(go.Scatter(x=pred_x, y=[y + (std_dev * 1.5) for y in pred_y], line=dict(color='rgba(192, 38, 211, 0)'), showlegend=False))
                                            pred_fig.add_trace(go.Scatter(x=pred_x, y=[y - (std_dev * 1.5) for y in pred_y], fill='tonexty', fillcolor='rgba(192, 38, 211, 0.1)', line=dict(color='rgba(192, 38, 211, 0)'), name='Confidence'))
                                            
                                            pred_fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400, margin=dict(l=0, r=0, t=10, b=0))
                                            st.plotly_chart(pred_fig, use_container_width=True)
                                            st.success(f"Projected Target: ₹{round(pred_prices[-1], 2)}")
                                except Exception as e: st.error(f"ML Error: {e}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.expander("📊 Options Sentiment (PCR & IV)", expanded=False):
                        if st.button("Run Derivatives Scan"):
                            with st.spinner("Connecting to NSE..."):
                                try:
                                    from nsepython import option_chain
                                    payload = option_chain(target_symbol) 
                                    if payload and 'filtered' in payload:
                                        ce_oi = payload['filtered']['CE']['totOI']
                                        pe_oi = payload['filtered']['PE']['totOI']
                                        pcr = pe_oi / ce_oi if ce_oi > 0 else 0
                                        c1, c2 = st.columns(2)
                                        c1.metric("Put-Call Ratio (PCR)", f"{pcr:.2f}")
                                        if pcr > 1: c1.success("📈 Bullish")
                                        else: c1.error("📉 Bearish")
                                    else: st.warning("No options data.")
                                except Exception as e: st.error(f"Options Error: {e}")
                                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.expander("🔗 Sector Correlation", expanded=False):
                        col_c1, col_c2 = st.columns([1, 3])
                        with col_c1:
                            benchmark_symbol = st.selectbox("Benchmark", ["NIFTY", "BANKNIFTY", "SENSEX"])
                            if st.button("Run Correlation", width="stretch"):
                                with st.spinner("Calculating..."):
                                    try:
                                        bench_data = yf.Ticker(format_ticker(benchmark_symbol)).history(period="6mo")['Close']
                                        aligned_data = pd.concat([hist['Close'].pct_change(), bench_data.pct_change()], axis=1).dropna()
                                        aligned_data.columns = [target_symbol, benchmark_symbol]
                                        rolling_corr = aligned_data[target_symbol].rolling(window=20).corr(aligned_data[benchmark_symbol])
                                        
                                        corr_fig = go.Figure()
                                        corr_fig.add_trace(go.Scatter(x=rolling_corr.index, y=rolling_corr, mode='lines', line=dict(color='#00FFA3', width=2)))
                                        corr_fig.add_hline(y=0, line_dash="dash", line_color="rgba(255, 255, 255, 0.2)")
                                        corr_fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=350, margin=dict(l=0, r=0, t=10, b=0))
                                        with col_c2:
                                            st.plotly_chart(corr_fig, use_container_width=True)
                                            st.metric("20-Day Correlation", f"{rolling_corr.iloc[-1]:.2f}")
                                    except Exception as e: st.error(f"Error: {e}")

                else: st.error("No data fetched.")
            except Exception as e: st.error(f"Error: {e}")

elif selected_page == "Strategy Backtester":
    tab_rebalance, tab_ema = st.tabs(["⚖️ Portfolio Rebalancing", "📈 EMA Engine"])
    
    with tab_rebalance:
        st.markdown("<br>", unsafe_allow_html=True)
        col_d1, col_d2 = st.columns(2)
        start_d = col_d1.date_input("Start Date")
        end_d = col_d2.date_input("End Date")
        
        if st.button("Run Rebalancer", type="primary"):
            try:
                from data_loader import fetch_stock_data
                from strategy import RebalancingStrategy
                tickers = ['VMART', 'NOCIL', 'RELIANCE', 'TCS']
                with st.spinner("Calculating weights..."):
                    data = fetch_stock_data(tickers, start_date=str(start_d), end_date=str(end_d))
                    if not data.empty:
                        strategy = RebalancingStrategy(tickers)
                        weights = strategy.calculate_weights()
                        cols = st.columns(len(tickers))
                        for i, (t, w) in enumerate(weights.items()): cols[i].metric(t, f"{w:.2%}")
            except Exception as e: st.error(f"Error: {e}")

    with tab_ema:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("backtest_config"):
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            with col_b1: b_ticker = st.text_input("Ticker", value="BANKNIFTY").upper()
            with col_b2: b_period = st.selectbox("Historical Data", ["1y", "2y", "5y"])
            with col_b3: fast_ema = st.number_input("Fast EMA", value=20, min_value=1)
            with col_b4: slow_ema = st.number_input("Slow EMA", value=50, min_value=1)
            
            col_b5, col_b6, col_b7, col_b8 = st.columns(4)
            with col_b5: use_rsi = st.checkbox("Oversold RSI?", value=False)
            with col_b6: rsi_thresh = st.number_input("RSI <", value=40, min_value=10, max_value=90)
            with col_b7: tp_pct = st.number_input("TP (%)", value=5.0, step=0.5)
            with col_b8: sl_pct = st.number_input("SL (%)", value=2.0, step=0.5)
            run_backtest = st.form_submit_button("Run 1000x Simulation", width="stretch")
            
        if run_backtest and b_ticker:
            with st.spinner(f"Simulating {b_ticker}..."):
                try:
                    import yfinance as yf
                    hist = yf.Ticker(format_ticker(b_ticker)).history(period=b_period)
                    if len(hist) > slow_ema:
                        hist['EMA_Fast'] = hist['Close'].ewm(span=fast_ema).mean()
                        hist['EMA_Slow'] = hist['Close'].ewm(span=slow_ema).mean()
                        
                        delta = hist['Close'].diff()
                        up, down = delta.where(delta > 0, 0), -delta.where(delta < 0, 0)
                        rs = up.ewm(alpha=1/14, adjust=False).mean() / down.ewm(alpha=1/14, adjust=False).mean()
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
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        m1, m2, m3, m4 = st.columns(4)
                        win_r = (len([t for t in trades if t["Type"]=="WIN"]) / len(trades) * 100) if trades else 0
                        net_ret = ((capital - 100000) / 100000) * 100
                        
                        m1.metric("Total Trades", len(trades))
                        m2.metric("Win Rate", f"{win_r:.1f}%")
                        m3.metric("Final Capital", f"₹{capital:,.2f}")
                        m4.metric("Net ROI", f"{net_ret:.2f}%", delta=f"{net_ret:.2f}%")
                        
                        fig = px.line(pd.DataFrame(equity_curve), x="Date", y="Capital")
                        fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), height=350)
                        fig.update_traces(line=dict(color='#7C3AED', width=3))
                        fig.update_yaxes(gridcolor='#1F1F22')
                        fig.update_xaxes(gridcolor='#1F1F22')
                        st.plotly_chart(fig, use_container_width=True)
                        
                        with st.expander("🤖 AI Risk Assessment"):
                            if st.button("Generate Risk Report"):
                                api_key = os.environ.get("NVIDIA_API_KEY")
                                if api_key:
                                    from langchain_nvidia_ai_endpoints import ChatNVIDIA
                                    llm = ChatNVIDIA(model="nvidia/nemotron-3-ultra-550b-a55b", temperature=0.2, nvidia_api_key=api_key)
                                    res = llm.invoke(f"Assess EMA strategy on {b_ticker}: {len(trades)} trades, {win_r}% win rate, {net_ret}% ROI. Professional brief.").content
                                    st.info(res)
                except Exception as e: st.error(f"Error: {e}")

elif selected_page == "Practice Wallet & Journal":
    tab_exec, tab_analytics, tab_journal = st.tabs(["🚀 Execution", "📊 Analytics", "📜 Journal"])
    
    with tab_exec:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔑 Zerodha API Config", expanded=False):
            col_k1, col_k2, col_k3 = st.columns(3)
            with col_k1: api_key = st.text_input("Kite API Key", type="password")
            with col_k2: api_secret = st.text_input("Kite API Secret", type="password")
            with col_k3: request_token = st.text_input("Request Token")
            if st.button("Authenticate", width="stretch"):
                try:
                    from kiteconnect import KiteConnect
                    data = KiteConnect(api_key=api_key).generate_session(request_token, api_secret=api_secret)
                    st.session_state.kite_access_token, st.session_state.kite_api_key = data["access_token"], api_key
                    st.success("✅ Auth Success!")
                except Exception as e: st.error(f"Auth failed: {e}")

        col_trade, col_port = st.columns([1, 2])
        with col_trade:
            st.markdown("###### Fire Order")
            with st.form("live_trade_form"):
                t_ticker = st.text_input("Ticker", placeholder="e.g. RELIANCE").strip().upper()
                t_exch = st.selectbox("Exchange", ["NSE", "BSE"])
                t_qty = st.number_input("Quantity", min_value=1, step=1)
                t_action = st.radio("Action", ["BUY", "SELL"], horizontal=True)
                order_type = st.selectbox("Type", ["MARKET", "LIMIT"])
                limit_price = st.number_input("Limit Price", min_value=0.0, step=0.5)
                
                if st.form_submit_button("🔥 SUBMIT", type="primary", width="stretch") and t_ticker:
                    if "kite_access_token" not in st.session_state: st.error("Authenticate first.")
                    else:
                        try:
                            from kiteconnect import KiteConnect
                            kite = KiteConnect(api_key=st.session_state.kite_api_key)
                            kite.set_access_token(st.session_state.kite_access_token)
                            order_id = kite.place_order(
                                tradingsymbol=t_ticker, exchange=kite.EXCHANGE_NSE if t_exch=="NSE" else kite.EXCHANGE_BSE,
                                transaction_type=kite.TRANSACTION_TYPE_BUY if t_action=="BUY" else kite.TRANSACTION_TYPE_SELL,
                                quantity=int(t_qty), variety=kite.VARIETY_REGULAR, product=kite.PRODUCT_MIS,
                                order_type=kite.ORDER_TYPE_MARKET if order_type=="MARKET" else kite.ORDER_TYPE_LIMIT,
                                price=float(limit_price) if order_type=="LIMIT" else None
                            )
                            st.success(f"Order Placed! ID: {order_id}")
                            db_conn.cursor().execute("INSERT INTO trade_journal (user_id, timestamp, ticker, action, quantity, price) VALUES (?, ?, ?, ?, ?, ?)",
                                      (st.session_state.user['id'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t_ticker, f"LIVE_{t_action}", t_qty, limit_price))
                            db_conn.commit()
                        except Exception as e: st.error(f"Error: {e}")

        with col_port:
            st.markdown("###### Live Positions")
            if st.button("Refresh Holdings"):
                if "kite_access_token" in st.session_state:
                    try:
                        from kiteconnect import KiteConnect
                        kite = KiteConnect(api_key=st.session_state.kite_api_key)
                        kite.set_access_token(st.session_state.kite_access_token)
                        positions = kite.positions().get('net', [])
                        if positions: st.dataframe(pd.DataFrame(positions)[['tradingsymbol', 'quantity', 'average_price', 'last_price', 'pnl']], hide_index=True)
                        else: st.info("No open positions.")
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Authenticate to view.")
                    
    with tab_analytics:
        st.markdown("<br>", unsafe_allow_html=True)
        c = db_conn.cursor()
        c.execute("SELECT balance FROM practice_wallets WHERE user_id = ?", (st.session_state.user['id'],))
        current_balance = c.fetchone()[0]
        net_pnl = current_balance - 1000000.00
        c.execute("SELECT COUNT(*) FROM trade_journal WHERE user_id = ?", (st.session_state.user['id'],))
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Available Capital", f"₹{current_balance:,.2f}")
        m2.metric("Net Realized P&L", f"₹{net_pnl:,.2f}", delta=f"{(net_pnl/1000000)*100:.2f}%")
        m3.metric("Total Trades", c.fetchone()[0])
        
        st.markdown("<hr style='border-color: #1F1F22; margin: 24px 0;'>", unsafe_allow_html=True)
        st.markdown("###### 🗺️ Exposure Heatmap")
        if "kite_access_token" in st.session_state:
            try:
                positions = KiteConnect(api_key=st.session_state.kite_api_key).positions().get('net', [])
                if positions:
                    hm_df = pd.DataFrame(positions)
                    hm_df['P&L Status'] = hm_df['pnl'].apply(lambda x: 'Profit' if x > 0 else 'Loss')
                    hm_df['Abs P&L'] = hm_df['pnl'].abs()
                    fig = px.treemap(hm_df, path=[px.Constant("Portfolio"), 'P&L Status', 'tradingsymbol'], values='Abs P&L', color='pnl', color_continuous_scale=['#FF0055', '#121214', '#00FFA3'], color_continuous_midpoint=0)
                    fig.update_layout(template='plotly_dark', margin=dict(t=20, l=0, r=0, b=0), height=450, paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except: pass
        else: st.info("Connect API to view Heatmap.")

    with tab_journal:
        st.markdown("<br>", unsafe_allow_html=True)
        c = db_conn.cursor()
        c.execute("SELECT timestamp, ticker, action, quantity, price FROM trade_journal WHERE user_id = ? ORDER BY id DESC", (st.session_state.user['id'],))
        j_rows = c.fetchall()
        if j_rows: st.dataframe(pd.DataFrame(j_rows, columns=["Time", "Asset", "Action", "Qty", "Price"]), width="stretch", hide_index=True)
        else: st.info("No journal history.")

elif selected_page == "DB Admin Vault":
    user_id = st.session_state.user['id']
    st.markdown("###### System Health")
    try: st.metric("Live DB Size", f"{os.path.getsize(DB_PATH)/1024:.2f} KB")
    except: pass
    
    st.markdown("<hr style='border-color: #1F1F22; margin: 24px 0;'>", unsafe_allow_html=True)
    c = db_conn.cursor()
    c.execute("SELECT COUNT(*) FROM trade_journal WHERE user_id = ?", (user_id,))
    active_t = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM archived_trade_journal WHERE user_id = ?", (user_id,))
    
    col_p1, col_p2 = st.columns(2)
    col_p1.metric("Active Rows (< 1 Yr)", active_t)
    col_p2.metric("Archived (> 1 Yr)", c.fetchone()[0])

    st.markdown("<hr style='border-color: #1F1F22; margin: 24px 0;'>", unsafe_allow_html=True)
    st.markdown("###### 📥 Export")
    c.execute("SELECT * FROM trade_journal WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    if rows:
        st.download_button("📥 Download CSV", pd.DataFrame(rows).to_csv(index=False).encode('utf-8'), f"export_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        
    st.markdown("<hr style='border-color: #1F1F22; margin: 24px 0;'>", unsafe_allow_html=True)
    with st.expander("⚠️ Factory Reset"):
        confirm = st.text_input("Type 'RESET' to wipe data:")
        if st.button("🔥 Execute Reset", type="primary"):
            if confirm == "RESET":
                c.execute("UPDATE practice_wallets SET balance = 1000000.00 WHERE user_id = ?", (user_id,))
                c.execute("DELETE FROM trade_journal WHERE user_id = ?", (user_id,))
                db_conn.commit()
                st.success("Wipe complete.")
                time.sleep(1); st.rerun()
