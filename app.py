from datetime import datetime, timedelta
import os
import io
import secrets
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_option_menu import option_menu
from supabase import Client, create_client
import time
import requests
import json
from bs4 import BeautifulSoup
import re
import asyncio
import httpx
import pybreaker
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ===== CLOUD API CONFIGURATION =====
CLOUD_API_URL = os.environ.get("API_URL") or "http://127.0.0.1:8000"

# Page Configuration
st.set_page_config(
    page_title="Institutional Quant Terminal",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CIRCUIT BREAKER CONFIGURATION ---
exchange_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

# --- 1. SUPABASE CONNECTION SETUP ---
@st.cache_resource
def init_supabase() -> Client:
    # Completely ignoring Streamlit Cloud secrets to force the correct key
    url = "https://zthirxdbxhdjfpbcpqmk.supabase.co"
    
    # PASTE YOUR REAL ANON KEY HERE (keep the quotes!)
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwaGl2dGphcWllaHlvYWlmc3ZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NzQ3NzQsImV4cCI6MjEwMDQ1MDc3NH0.pWzNxv4PZFlHcGghvwOdRlcOJY_JWTwyZA2vZ25bLUg" 
    
    return create_client(url, key)

supabase = init_supabase()



# --- 2. CRYPTOGRAPHIC VAULT (AES-256-GCM) ---
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

# --- FINTECH OLED GLOBAL CSS CONFIGURATION ---
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif;
    background-color: #000000 !important;
    color: #E3E3E3;
}

header { background-color: transparent !important; }

[data-testid="stSidebar"] {
    background-color: #0A0A0A !important;
    border-right: 1px solid #1A1A1A;
}
[data-testid="stSidebar"] label {
    color: #9AA0A6 !important;
    font-weight: 500;
    font-size: 13px;
}

.stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea, .stNumberInput>div>div>input {
    background-color: #121212 !important;
    color: #FFFFFF !important;
    border: 1px solid #2B2B2B !important;
    border-radius: 8px !important;
    padding: 10px 16px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
    border-color: #2962FF !important;
    box-shadow: 0 0 0 1px #2962FF !important;
}

.stButton>button {
    background-color: #2962FF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5rem 1.2rem;
    transition: all 0.2s ease;
}
.stButton>button:hover {
    background-color: #1C44B2;
    color: #FFFFFF;
    transform: translateY(-1px);
}

[data-testid="stForm"] .stButton>button {
    background-color: transparent;
    border: 1px solid #2962FF;
    color: #2962FF;
}
[data-testid="stForm"] .stButton>button:hover {
    background-color: rgba(41, 98, 255, 0.1);
}

div[data-testid="metric-container"] {
    background-color: #121212; 
    border: 1px solid #2B2B2B; 
    padding: 15px 20px;
    border-radius: 12px;       
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    transition: transform 0.2s ease-in-out, border 0.2s ease-in-out;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    border: 1px solid #2962FF; 
}

[data-testid="stMetricLabel"] {
    color: #9AA0A6 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 26px !important;
    font-weight: 600 !important;
}

div[data-testid="stMetricDelta"] svg[title="Up"] { color: #00E676 !important; }
div[data-testid="stMetricDelta"] > div:has(svg[title="Up"]) { color: #00E676 !important; font-weight: 600; }
div[data-testid="stMetricDelta"] svg[title="Down"] { color: #FF1744 !important; }
div[data-testid="stMetricDelta"] > div:has(svg[title="Down"]) { color: #FF1744 !important; font-weight: 600; }

[data-testid="stChatMessage"] { background-color: transparent !important; }
[data-testid="stChatInput"] { background-color: #121212 !important; border: 1px solid #2B2B2B !important; border-radius: 8px !important; }
[data-testid="stChatInput"] textarea { color: #FFFFFF !important; }

[data-testid="stDataFrame"] { border: 1px solid #1A1A1A; border-radius: 12px; overflow: hidden; }

h1, h2, h3, h4, h5 { color: #FFFFFF !important; font-weight: 600 !important; letter-spacing: -0.5px; }
</style>
"""

# --- 3. AUTHENTICATION GATEKEEPER ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown("<style>.block-container { max-width: 500px; padding-top: 6rem; }</style>", unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center; margin-bottom: 8px;'>✨ Welcome to Terminal</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #9AA0A6; font-size: 14px; margin-bottom: 32px;'>Sign in to access your quantitative workflows.</p>", unsafe_allow_html=True)

    # ADD THIS DIAGNOSTIC LINE:
    st.warning(f"🔍 DEBUG: The app is using a key that starts with: {supabase.supabase_key[:15]}...")

    auth_tab1, auth_tab2 = st.tabs(["Sign In", "Create Account"])
    

    with auth_tab1:
        with st.form("login_form"):
            login_email = st.text_input("Email", autocomplete="email")
            login_password = st.text_input("Password", type="password", autocomplete="current-password")
            st.markdown("")
            login_btn = st.form_submit_button("Continue", width="stretch")

            if login_btn:
                try:
                    response = supabase.auth.sign_in_with_password({
                        "email": login_email,
                        "password": login_password,
                    })
                    st.session_state.user = response.user
                    st.success("Authentication successful! Initializing Crypto Vault...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with auth_tab2:
        with st.form("signup_form"):
            signup_email = st.text_input("Email", autocomplete="email")
            signup_password = st.text_input("Password", type="password", autocomplete="new-password")
            st.markdown("")
            signup_btn = st.form_submit_button("Create Account", width="stretch")

            if signup_btn:
                try:
                    response = supabase.auth.sign_up({
                        "email": signup_email,
                        "password": signup_password,
                    })
                    st.success("Account registered! Please check your email inbox to verify.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

    st.stop()

# =====================================================================
# MAIN APPLICATION
# =====================================================================
st.markdown(THEME_CSS, unsafe_allow_html=True)

try:
    from strategy import RebalancingStrategy
    from backtester import run_backtest
    from risk_manager import check_portfolio_risk
except ImportError:
    pass # In case local modules are missing during test deploys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv()

try:
    from ddgs import DDGS
    search_available = True
except ImportError:
    search_available = False

if "nse_watchlist" not in st.session_state:
    st.session_state.nse_watchlist = ["VMART", "NOCIL", "RELIANCE", "TCS"]
if "bse_watchlist" not in st.session_state:
    st.session_state.bse_watchlist = ["RELIANCE", "INFY", "TCS"]

def resolve_ticker_via_search(user_query: str) -> str:
    cleaned = user_query.strip()
    return cleaned.upper()

def push_to_timescaledb(df, table_name, db_uri):
    try:
        from sqlalchemy import create_engine
        engine = create_engine(db_uri)
        df.index.name = 'trade_timestamp' 
        df.to_sql(table_name, engine, if_exists='append')
        return True
    except Exception as e:
        print(f"Database push failed: {e}")
        return False

@st.cache_data(ttl=0)
def fetch_stock_data_hybrid(tickers, start_date, end_date, interval="1d", db_uri=None):
    import yfinance as yf
    os.makedirs("market_data", exist_ok=True)
    data = {}
    for ticker in tickers:
        yf_ticker = ticker if ("." in ticker) else f"{ticker}.NS"
        parquet_path = f"market_data/{yf_ticker}_{interval}.parquet.enc"
        
        if os.path.exists(parquet_path):
            try:
                with open(parquet_path, "rb") as f:
                    encrypted_bytes = f.read()
                decrypted_bytes = vault.decrypt_data(encrypted_bytes)
                buf = io.BytesIO(decrypted_bytes)
                df_ticker = pd.read_parquet(buf, engine='pyarrow')
                
                if df_ticker.index.tz is not None:
                    df_ticker.index = df_ticker.index.tz_localize(None)
                    
                df_ticker = df_ticker[(df_ticker.index >= pd.to_datetime(start_date)) & (df_ticker.index <= pd.to_datetime(end_date))]
                
                if not df_ticker.empty and 'Close' in df_ticker.columns:
                    data[ticker] = df_ticker['Close']
                    continue
            except Exception as e:
                st.warning(f"Encrypted load failed for {ticker}: {e}")

        try:
            stock_data = yf.download(yf_ticker, start=start_date, end=end_date, interval=interval, progress=False, multi_level_index=False)
            if not stock_data.empty:
                if stock_data.index.tz is not None:
                    stock_data.index = stock_data.index.tz_localize(None)
                buf = io.BytesIO()
                stock_data.to_parquet(buf, engine='pyarrow', compression='snappy')
                encrypted_payload = vault.encrypt_data(buf.getvalue())
                with open(parquet_path, "wb") as f:
                    f.write(encrypted_payload)
                if db_uri:
                    push_to_timescaledb(stock_data, "intraday_prices" if interval != "1d" else "historical_prices", db_uri)
                if 'Close' in stock_data.columns:
                    data[ticker] = stock_data['Close']
        except Exception:
            pass
            
    if data:
        df_final = pd.DataFrame(data)
        df_final = df_final.ffill().bfill().dropna(axis=0, how='all')
        return df_final
    return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 5. SIDEBAR NAVIGATION & CONFIGURATION ---
with st.sidebar:
    
    # Safely extract user email 
    if isinstance(st.session_state.user, dict):
        user_email = st.session_state.user.get("email", "Active User")
    else:
        user_email = getattr(st.session_state.user, "email", "Active User")

    st.markdown(
        f"""
        <div style="background-color: #121212; padding: 16px; border-radius: 12px; border: 1px solid #2B2B2B; margin-bottom: 24px;">
            <div style="font-size: 11px; color: #9AA0A6; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Active Session</div>
            <div style="font-size: 13px; color: #FFFFFF; margin-top: 4px; overflow: hidden; text-overflow: ellipsis;">{user_email}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # -- SAAS MENU ROUTING --
    selected_page = option_menu(
        menu_title="Main Menu",
        options=["AI Assistant", "Web Intelligence", "Live Market Feed", "Portfolio & Quant Suite", "Screener & Diagnostics", "Practice Wallet"],
        icons=["robot", "globe", "activity", "pie-chart", "search", "wallet2"],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#2962FF", "font-size": "16px"},
            "nav-link": {"font-size": "14px", "text-align": "left", "margin":"0px", "--hover-color": "#1A1A1A", "color": "#9AA0A6"},
            "nav-link-selected": {"background-color": "#121212", "color": "#00E676", "border-left": "3px solid #2962FF"},
        }
    )

    st.markdown("<hr style='border-color: #1A1A1A; margin: 24px 0;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 14px; font-weight: 500; color: #FFFFFF; margin-bottom: 16px;'>Pipeline Configuration</div>", unsafe_allow_html=True)

    data_mode = st.radio("Data Resolution", ["Daily (End of Day)", "Intraday (5-Minute)"])
    strategy_method = st.selectbox("Optimization Objective", ["Equal-Weight (1/N)", "Max Sharpe Ratio"])
    
    if data_mode == "Intraday (5-Minute)":
        time_period = st.selectbox("Historical Window", ["1 Day", "5 Days", "1 Month", "60 Days"], index=1)
        days_map = {"1 Day": 1, "5 Days": 5, "1 Month": 30, "60 Days": 60}
        active_interval = "5m"
    else:
        time_period = st.selectbox("Historical Window", ["6mo", "1y", "2y", "5y"])
        days_map = {"6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
        active_interval = "1d"

    max_dd_limit = st.slider("Risk Tolerance (Max Drawdown %)", -30, -5, -15)
    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button("Execute Pipeline", width="stretch")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sign Out", width="stretch"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.pop("vault_key", None)
        st.rerun()

# --- 6. EXECUTION ENGINE ---
if run_button:
    tickers = [resolve_ticker_via_search(t) for t in st.session_state.nse_watchlist]
    if not tickers:
        st.sidebar.error("Please supply valid asset ticker symbols.")
    else:
        with st.sidebar:
            with st.spinner("Compiling models..."):
                lookback = days_map.get(time_period, 365)
                start_date = (datetime.today() - timedelta(days=lookback)).strftime("%Y-%m-%d")
                end_date = datetime.today().strftime("%Y-%m-%d")

                df_prices = fetch_stock_data_hybrid(tickers, start_date=start_date, end_date=end_date, interval=active_interval)

                if df_prices.empty:
                    st.error(f"Pipeline failed for: {tickers}")
                else:
                    try:
                        method_mapping = "equal" if "Equal-Weight" in strategy_method else "max_sharpe"
                        strategy = RebalancingStrategy(df_prices.columns.tolist(), df_prices=df_prices, method=method_mapping)
                        target_weights = strategy.calculate_weights()
                        safe_weights, risk_status, current_dd = check_portfolio_risk(df_prices, target_weights, max_drawdown_limit=max_dd_limit / 100.0)
                        metrics, equity_curve = run_backtest(df_prices, safe_weights)

                        st.session_state.quant_results = {
                            "df_prices": df_prices, "safe_weights": safe_weights, 
                            "risk_status": risk_status, "current_dd": current_dd, 
                            "metrics": metrics, "equity_curve": equity_curve
                        }
                        st.success("Success! Check Portfolio Suite.")
                    except Exception as e:
                        st.error(f"Backtest error: {e}")

# --- 7. MAIN APPLICATION HEADER ---
col_h1, col_h2 = st.columns([3, 2])
with col_h1:
    st.markdown("<h2 style='margin-bottom: 4px;'>Institutional Intelligence Terminal</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #9AA0A6; font-size: 14px;'>Active Module: <b>{selected_page}</b></p>", unsafe_allow_html=True)
with col_h2:
    st.markdown(
        """
        <div style='text-align: right; padding-top: 16px; display: flex; gap: 8px; justify-content: flex-end;'>
            <span style='background-color: rgba(41, 98, 255, 0.1); color: #2962FF; padding: 6px 12px; border-radius: 16px; font-size: 11px; font-weight: 600; border: 1px solid rgba(41, 98, 255, 0.2);'>
                🔒 AES-256 SECURED
            </span>
            <span style='background-color: rgba(0, 230, 118, 0.1); color: #00E676; padding: 6px 12px; border-radius: 16px; font-size: 11px; font-weight: 600; border: 1px solid rgba(0, 230, 118, 0.2);'>
                ● ONLINE
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
st.markdown("<hr style='border-color: #2B2B2B; margin: 16px 0 24px 0;'>", unsafe_allow_html=True)

# ==========================================
# MODULE ROUTER (Based on Sidebar Selection)
# ==========================================

if selected_page == "AI Assistant":
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hi there. I'm J.A.R.V.I.S., your terminal assistant. How can I help analyze the markets today?"}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="✨" if message["role"] == "assistant" else "👤"):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a quantitative or market question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="✨"):
            with st.spinner("Thinking..."):
                try:
                    api_key = os.environ.get("GROQ_API_KEY")
                    if not api_key:
                        st.error("GROQ_API_KEY is missing.")
                    else:
                        chat_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, groq_api_key=api_key)
                        messages = [SystemMessage(content="You are J.A.R.V.I.S., an advanced institutional quantitative trading assistant."), HumanMessage(content=prompt)]
                        response_msg = chat_llm.invoke(messages).content
                        st.markdown(response_msg)
                        st.session_state.messages.append({"role": "assistant", "content": response_msg})
                except Exception as e:
                    st.error(f"API connection error: {e}")

elif selected_page == "Web Intelligence":
    col_s1, col_s2 = st.columns([4, 1])
    with col_s1:
        search_query = st.text_input("Query", placeholder="Search global macro indicators or sector news...", label_visibility="collapsed")
    with col_s2:
        search_btn = st.button("Search Web", width="stretch")

    if search_btn and search_query.strip():
        if not search_available:
            st.error("Search package (`ddgs`) is not installed.")
        else:
            with st.spinner("Scanning sources..."):
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(search_query, max_results=5))
                        if not results:
                            st.info("No matching intelligence data found.")
                        else:
                            for i, r in enumerate(results, 1):
                                with st.expander(f"{r.get('title', 'No Title')}", expanded=(i == 1)):
                                    st.write(r.get('body', ''))
                                    st.markdown(f"[Source Link]({r.get('href', '#')})")
                except Exception as e:
                    st.error(f"Search error: {e}")

elif selected_page == "Live Market Feed":
    def get_yf_quote(symbol, exchange):
        import yfinance as yf
        symbol = symbol.strip().upper()
        yf_ticker = f"{symbol}.NS" if exchange == "NSE" else f"{symbol}.BO"
        try:
            ticker = yf.Ticker(yf_ticker)
            curr, prev = ticker.fast_info.get('lastPrice'), ticker.fast_info.get('previousClose')
            if curr and prev:
                change = round(((curr - prev) / prev) * 100, 2)
                return {"Symbol": symbol, "Exchange": exchange, "Last (₹)": round(curr, 2), "Change (%)": change}
        except: pass
        return {"Symbol": symbol, "Exchange": exchange, "Last (₹)": "N/A", "Change (%)": "N/A"}
    
    st.markdown("<div style='font-size: 14px; font-weight: 500; color: #FFFFFF; margin-bottom: 8px;'>🔍 Quick Quote Search</div>", unsafe_allow_html=True)
    col_sq1, col_sq2, col_sq3 = st.columns([3, 1, 1])
    with col_sq1: search_ticker = st.text_input("Search Ticker", placeholder="e.g. ZOMATO, ITC", label_visibility="collapsed")
    with col_sq2: search_exchange = st.selectbox("Exchange", ["NSE", "BSE"], label_visibility="collapsed")
    with col_sq3: search_quote_btn = st.button("Get Quote", width="stretch")

    if search_quote_btn and search_ticker.strip():
        with st.spinner("Resolving quote..."):
            quote = get_yf_quote(search_ticker, search_exchange)
            if quote["Last (₹)"] != "N/A":
                c1, c2, c3 = st.columns(3)
                c1.metric("Asset", quote['Symbol'])
                c2.metric("Last Price", f"₹{quote['Last (₹)']}")
                c3.metric("Daily Change", f"{quote['Change (%)']}%")
            else: st.error("Quote not found.")

    st.markdown("<hr style='border-color: #2B2B2B; margin: 24px 0;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 14px; font-weight: 500; color: #FFFFFF; margin-bottom: 8px;'>📋 Managed Watchlists</div>", unsafe_allow_html=True)
    
    with st.form("watchlist_form", border=False):
        c_w1, c_w2 = st.columns(2)
        with c_w1: nse_input = st.text_area("NSE Tickers (comma separated)", value=", ".join(st.session_state.nse_watchlist))
        with c_w2: bse_input = st.text_area("BSE Symbols (comma separated)", value=", ".join(st.session_state.bse_watchlist))
        if st.form_submit_button("Update Watchlists"):
            st.session_state.nse_watchlist = [t.strip().upper() for t in nse_input.split(",") if t.strip()]
            st.session_state.bse_watchlist = [t.strip().upper() for t in bse_input.split(",") if t.strip()]

    async def fetch_live_async(sym, ex): return await asyncio.to_thread(get_yf_quote, sym, ex)
    @st.cache_data(ttl=15)
    def get_cached_live_markets_safe(nse_tuple, bse_tuple):
        async def fetch_all():
            n_res = await asyncio.gather(*(fetch_live_async(s, "NSE") for s in nse_tuple))
            b_res = await asyncio.gather(*(fetch_live_async(s, "BSE") for s in bse_tuple))
            return pd.DataFrame(n_res), pd.DataFrame(b_res)
        return asyncio.run(fetch_all())

    df_nse, df_bse = get_cached_live_markets_safe(tuple(st.session_state.nse_watchlist), tuple(st.session_state.bse_watchlist))
    
    c_t1, c_t2 = st.columns(2)
    c_t1.markdown("#### NSE Equities")
    if not df_nse.empty: 
        df_nse["Last (₹)"] = df_nse["Last (₹)"].astype(str)
        c_t1.dataframe(df_nse, width="stretch", hide_index=True)
        
    c_t2.markdown("#### BSE Equities")
    if not df_bse.empty: 
        df_bse["Last (₹)"] = df_bse["Last (₹)"].astype(str)
        c_t2.dataframe(df_bse, width="stretch", hide_index=True)

elif selected_page == "Portfolio & Quant Suite":
    if "quant_results" not in st.session_state:
        st.info("💡 Open the sidebar menu and click **Execute Pipeline** to generate portfolio models.")
    else:
        res = st.session_state.quant_results
        st.markdown("#### 🛡️ Risk Diagnostics")
        if "CIRCUIT BREAKER" in res["risk_status"]: st.error(res["risk_status"])
        elif "WARNING" in res["risk_status"]: st.warning(res["risk_status"])
        else: st.success(f"Status: Nominal (Current Drawdown: {res['current_dd']*100:.2f}%)")
        
        st.markdown("<hr style='border-color: #2B2B2B;'>", unsafe_allow_html=True)
        st.markdown("#### ⚖️ Optimal Portfolio Allocations")
        cols = st.columns(len(res["safe_weights"]) if res["safe_weights"] else 1)
        for i, (ticker, weight) in enumerate(res["safe_weights"].items()):
            with cols[i]: st.metric(label=ticker, value=f"{weight * 100:.2f}%")

        st.markdown("<hr style='border-color: #2B2B2B;'>", unsafe_allow_html=True)
        st.markdown("#### 📈 Quantitative Performance")
        m_cols = st.columns(4)
        m_cols[0].metric("CAGR", f"{res['metrics'].get('CAGR', 0)}%")
        m_cols[1].metric("Sharpe Ratio", f"{res['metrics'].get('Sharpe Ratio', 0)}")
        m_cols[2].metric("Ann. Volatility", f"{res['metrics'].get('Annualized Volatility', 0)}%")
        m_cols[3].metric("Max Drawdown", f"{res['metrics'].get('Maximum Drawdown', 0)}%")
        st.line_chart(res["equity_curve"])

elif selected_page == "Screener & Diagnostics":
    screen_col1, screen_col2 = st.columns([3, 1])
    with screen_col1: target_symbol = st.text_input("Enter Ticker", value="VMART", placeholder="e.g. NOCIL, VMART").strip().upper()
    with screen_col2: scan_btn = st.button("Run Diagnostic Scan", width="stretch")

    if scan_btn or target_symbol:
        import yfinance as yf
        yf_target = target_symbol if ("." in target_symbol) else f"{target_symbol}.NS"
        with st.spinner(f"Analyzing {target_symbol}..."):
            try:
                ticker_obj = yf.Ticker(yf_target)
                hist = ticker_obj.history(period="6mo")
                info = ticker_obj.info
                if not hist.empty:
                    hist['EMA20'], hist['EMA50'] = hist['Close'].ewm(span=20).mean(), hist['Close'].ewm(span=50).mean()
                    hist['RSI'] = calculate_rsi(hist['Close'])
                    
                    last_price, last_rsi = hist['Close'].iloc[-1], round(hist['RSI'].iloc[-1], 2)
                    trend_signal = "🟢 BULLISH" if hist['EMA20'].iloc[-1] > hist['EMA50'].iloc[-1] else "🔴 BEARISH"
                    rsi_status = "🔥 Overbought" if last_rsi > 70 else ("🧊 Oversold" if last_rsi < 30 else "⚖️ Neutral")
                    
                    st.markdown("##### Technical Signals")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Current Price", f"₹{round(last_price, 2)}")
                    m2.metric("RSI (14)", f"{last_rsi}", delta=rsi_status, delta_color="off")
                    m3.metric("Trend Signal", trend_signal)
                    
                    st.markdown("<br>##### Price Action & Moving Averages (20 vs 50 EMA)", unsafe_allow_html=True)
                    st.line_chart(hist[['Close', 'EMA20', 'EMA50']])
                else: st.error("Could not retrieve price action.")
            except Exception as e: st.error(f"Error: {e}")

elif selected_page == "Practice Wallet":
    
    # 1. Safely extract ID with fallback
    if isinstance(st.session_state.user, dict):
        user_id = st.session_state.user.get("id")
    else:
        user_id = getattr(st.session_state.user, "id", None)

    # 2. Force the UI to show us the REAL error if one happens
    def get_wallet_balance():
        if not user_id:
            st.error("Authentication Error: user_id is missing.")
            return 0.0
            
        try:
            res = supabase.table("practice_wallets").select("balance").eq("user_id", user_id).execute()
            if not res.data:
                supabase.table("practice_wallets").insert({"user_id": user_id, "balance": 1000000.00}).execute()
                return 1000000.00
            return float(res.data[0]["balance"])
        except Exception as e:
            st.error(f"Supabase Database Error: {str(e)}")
            return 0.0

    def get_holdings():
        if not user_id: return []
        try:
            res = supabase.table("practice_holdings").select("*").eq("user_id", user_id).execute()
            return res.data
        except Exception as e:
            st.error(f"Holdings Error: {str(e)}")
            return []
            
    def fetch_live_price_for_wallet(symbol, exchange):
        import yfinance as yf
        yf_ticker = f"{symbol}.NS" if exchange == "NSE" else f"{symbol}.BO"
        try:
            return yf.Ticker(yf_ticker).fast_info.get('lastPrice', "N/A")
        except: return "N/A"

    balance = get_wallet_balance()
    holdings = get_holdings()
    
    st.markdown(
        f"""
        <div style="background-color: #121212; padding: 20px; border-radius: 12px; border: 1px solid #2B2B2B; margin-bottom: 24px;">
            <div style="font-size: 13px; color: #9AA0A6; text-transform: uppercase; font-weight: 500;">Available Buying Power</div>
            <div style="font-size: 32px; color: #00E676; font-weight: 700;">₹{balance:,.2f}</div>
        </div>
        """, unsafe_allow_html=True
    )
    
    col_trade, col_port = st.columns([1, 2])
    with col_trade:
        st.markdown("##### Execute Trade")
        with st.form("practice_trade_form_v2"):
            trade_ticker = st.text_input("Ticker Symbol")
            trade_exchange = st.selectbox("Exchange", ["NSE", "BSE"])
            trade_qty = st.number_input("Quantity", min_value=1, step=1)
            trade_action = st.radio("Action", ["BUY", "SELL"], horizontal=True)
            
            if st.form_submit_button("Submit Order", width="stretch") and trade_ticker:
                with st.spinner("Executing..."):
                    price = fetch_live_price_for_wallet(trade_ticker.upper(), trade_exchange)
                    if price == "N/A":
                        st.error("Invalid Ticker.")
                    else:
                        total_cost, ticker_db = float(price) * trade_qty, trade_ticker.upper()
                        if trade_action == "BUY":
                            if balance >= total_cost:
                                supabase.table("practice_wallets").update({"balance": balance - total_cost}).eq("user_id", user_id).execute()
                                existing = next((item for item in holdings if item["ticker"] == ticker_db), None)
                                if existing:
                                    new_qty = existing["quantity"] + trade_qty
                                    new_avg = ((existing["quantity"] * float(existing["avg_price"])) + total_cost) / new_qty
                                    supabase.table("practice_holdings").update({"quantity": new_qty, "avg_price": new_avg}).eq("id", existing["id"]).execute()
                                else: supabase.table("practice_holdings").insert({"user_id": user_id, "ticker": ticker_db, "quantity": trade_qty, "avg_price": price}).execute()
                                st.success(f"Bought {trade_qty} {ticker_db}!")
                                time.sleep(1)
                                st.rerun()
                            else: st.error("Insufficient Funds.")
                        elif trade_action == "SELL":
                            existing = next((item for item in holdings if item["ticker"] == ticker_db), None)
                            if existing and existing["quantity"] >= trade_qty:
                                supabase.table("practice_wallets").update({"balance": balance + total_cost}).eq("user_id", user_id).execute()
                                new_qty = existing["quantity"] - trade_qty
                                if new_qty == 0: supabase.table("practice_holdings").delete().eq("id", existing["id"]).execute()
                                else: supabase.table("practice_holdings").update({"quantity": new_qty}).eq("id", existing["id"]).execute()
                                st.success(f"Sold {trade_qty} {ticker_db}!")
                                time.sleep(1)
                                st.rerun()
                            else: st.error("Not enough shares to sell.")

    with col_port:
        st.markdown("##### Current Holdings")
        if not holdings: st.info("Portfolio empty.")
        else:
            portfolio_data = []
            for h in holdings:
                live_price = fetch_live_price_for_wallet(h["ticker"], "NSE")
                live_price = float(live_price) if live_price != "N/A" else float(h["avg_price"])
                invested, current_val = h["quantity"] * float(h["avg_price"]), h["quantity"] * live_price
                portfolio_data.append({
                    "Asset": h["ticker"], "Qty": h["quantity"], "Avg Buy": round(float(h["avg_price"]), 2),
                    "Live Price": round(live_price, 2), "P&L (₹)": round(current_val - invested, 2)
                })
            st.dataframe(pd.DataFrame(portfolio_data), width="stretch", hide_index=True)
