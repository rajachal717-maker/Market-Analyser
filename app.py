from datetime import datetime, timedelta
import os
import pandas as pd
import streamlit as st
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

# Page Configuration (Must be the first Streamlit command)
st.set_page_config(
    page_title="Institutional Quant Terminal",
    page_icon="✨",
    layout="wide",
)

# --- CIRCUIT BREAKER CONFIGURATION ---
exchange_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

# --- 1. SUPABASE CONNECTION SETUP ---
@st.cache_resource
def init_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL") or "https://zthirxdbxhdjfpbcpqmk.supabase.co"
    key = os.environ.get("SUPABASE_KEY") or "sb_publishable_C087lxhuIIfwtXmFj-taIw_nR_z1Og7"
    return create_client(url, key)

supabase = init_supabase()

# --- GEMINI-STYLE GLOBAL CSS CONFIGURATION ---
GEMINI_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Inter:wght@400;500;600&display=swap');

/* Main Body & Backgrounds */
html, body, [class*="css"], .stApp {
    font-family: 'Google Sans', 'Inter', sans-serif;
    background-color: #131314;
    color: #e3e3e3;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #1e1f20 !important;
    border-right: 1px solid #3c4043;
}
[data-testid="stSidebar"] label {
    color: #c4c7c5 !important;
    font-weight: 500;
    font-size: 13px;
    margin-bottom: 4px;
}

/* Inputs & Form Fields (Pill-shaped, modern) */
.stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea {
    background-color: #1e1f20 !important;
    color: #e3e3e3 !important;
    border: 1px solid #3c4043 !important;
    border-radius: 24px !important;
    padding: 10px 16px !important;
    transition: border-color 0.2s ease;
}
.stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
    border-color: #8ab4f8 !important;
    box-shadow: 0 0 0 1px #8ab4f8 !important;
}

/* Buttons (Gemini subtle style) */
.stButton>button {
    background-color: transparent;
    color: #8ab4f8;
    border: 1px solid #3c4043;
    border-radius: 24px;
    font-weight: 500;
    padding: 0.5rem 1.2rem;
    transition: all 0.2s ease;
}
.stButton>button:hover {
    background-color: rgba(138, 180, 248, 0.08);
    border-color: #8ab4f8;
    color: #8ab4f8;
}

/* Primary Action Button Override */
[data-testid="stSidebar"] .stButton>button {
    background-color: #c2e7ff;
    color: #001d35;
    border: none;
    font-weight: 600;
}
[data-testid="stSidebar"] .stButton>button:hover {
    background-color: #b0dfff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* Modern Minimalist Tabs */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent;
    gap: 24px;
    border-bottom: 1px solid #3c4043;
    padding: 0;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    border: none;
    color: #c4c7c5;
    border-radius: 0;
    border-bottom: 3px solid transparent;
    padding: 12px 4px;
    font-weight: 500;
    font-size: 14px;
}
.stTabs [aria-selected="true"] {
    color: #8ab4f8 !important;
    background-color: transparent !important;
    border-bottom: 3px solid #8ab4f8;
    box-shadow: none !important;
}

/* Metric Cards */
[data-testid="stMetric"] {
    background-color: #1e1f20;
    border: 1px solid #3c4043;
    padding: 20px;
    border-radius: 12px;
    box-shadow: none;
}
[data-testid="stMetricLabel"] {
    color: #c4c7c5 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
[data-testid="stMetricValue"] {
    color: #e3e3e3 !important;
    font-size: 28px !important;
    font-weight: 400 !important;
}

/* Chat Interface */
[data-testid="stChatMessage"] {
    background-color: transparent !important;
    padding: 1rem 0 !important;
}
[data-testid="stChatInput"] {
    background-color: #1e1f20 !important;
    border: 1px solid #3c4043 !important;
    border-radius: 24px !important;
}
[data-testid="stChatInput"] textarea {
    color: #e3e3e3 !important;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    border: 1px solid #3c4043;
    border-radius: 12px;
    overflow: hidden;
}

/* Typography Overrides */
h1, h2, h3 {
    color: #e3e3e3 !important;
    font-weight: 400;
    letter-spacing: -0.01em;
}
</style>
"""

# --- 2. AUTHENTICATION UI & GATEKEEPER ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.markdown(GEMINI_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .block-container { max-width: 500px; padding-top: 6rem; }
        </style>
        """, unsafe_allow_html=True
    )

    st.markdown("<h2 style='text-align: center; margin-bottom: 8px;'>✨ Welcome to Terminal</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #c4c7c5; font-size: 14px; margin-bottom: 32px;'>Sign in to access your quantitative workflows.</p>", unsafe_allow_html=True)

    auth_tab1, auth_tab2 = st.tabs(["Sign In", "Create Account"])

    with auth_tab1:
        with st.form("login_form"):
            login_email = st.text_input("Email")
            login_password = st.text_input("Password", type="password")
            st.markdown("")
            login_btn = st.form_submit_button("Continue", width="stretch")

            if login_btn:
                try:
                    response = supabase.auth.sign_in_with_password({
                        "email": login_email,
                        "password": login_password,
                    })
                    st.session_state.user = response.user
                    st.success("Authentication successful! Initializing...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with auth_tab2:
        with st.form("signup_form"):
            signup_email = st.text_input("Email")
            signup_password = st.text_input("Password", type="password")
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

# Inject Global CSS
st.markdown(GEMINI_CSS, unsafe_allow_html=True)

# --- 3. LOCAL QUANTITATIVE & AI MODULE IMPORTS ---
from strategy import RebalancingStrategy
from backtester import run_backtest
from risk_manager import check_portfolio_risk

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv()

# Updated package import to clear the warning
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

@st.cache_data(ttl=0)
def fetch_stock_data(tickers, start_date, end_date):
    import yfinance as yf
    import pandas as pd
    import streamlit as st
    
    data = {}
    for ticker in tickers:
        yf_ticker = ticker if ("." in ticker) else f"{ticker}.NS"
        try:
            # Bypass the new multi-level column structure
            stock_data = yf.download(
                yf_ticker, 
                start=start_date, 
                end=end_date, 
                progress=False, 
                multi_level_index=False
            )
            
            if not stock_data.empty and 'Close' in stock_data.columns:
                data[ticker] = stock_data['Close']
            else:
                st.warning(f"No Close price data found for {yf_ticker}")
                
        except Exception as e:
            # Output the exact python error to the UI
            st.error(f"yfinance failed for {yf_ticker}: {str(e)}")
            
    if data:
        return pd.DataFrame(data).dropna()
    return pd.DataFrame()

 

    


# --- 5. SIDEBAR CONFIGURATION ---
st.sidebar.markdown(
    f"""
    <div style="background-color: #131314; padding: 16px; border-radius: 12px; border: 1px solid #3c4043; margin-bottom: 24px;">
        <div style="font-size: 11px; color: #c4c7c5; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Active Session</div>
        <div style="font-size: 13px; color: #e3e3e3; margin-top: 4px; overflow: hidden; text-overflow: ellipsis;">{st.session_state.user.email}</div>
    </div>
    """,
    unsafe_allow_html=True
)

if st.sidebar.button("Sign Out", width="stretch"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("<br>", unsafe_allow_html=True)
st.sidebar.markdown("<div style='font-size: 14px; font-weight: 500; color: #e3e3e3; margin-bottom: 16px;'>Model Parameters</div>", unsafe_allow_html=True)

strategy_method = st.sidebar.selectbox(
    "Optimization Objective", ["Equal-Weight (1/N)", "Max Sharpe Ratio"]
)
time_period = st.sidebar.selectbox(
    "Historical Window", ["6mo", "1y", "2y", "5y"]
)
max_dd_limit = st.sidebar.slider(
    "Risk Tolerance (Max Drawdown %)", -30, -5, -15
)

st.sidebar.markdown("<br>", unsafe_allow_html=True)
run_button = st.sidebar.button("Execute Pipeline", width="stretch")

# --- 6. MAIN APPLICATION HEADER ---
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.markdown("<h2 style='margin-bottom: 4px;'>Institutional Intelligence Terminal</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #c4c7c5; font-size: 14px;'>Advanced Quantitative Strategy Execution & AI Analysis</p>", unsafe_allow_html=True)
with col_h2:
    st.markdown(
        """
        <div style='text-align: right; padding-top: 16px;'>
            <span style='background-color: rgba(129, 201, 149, 0.1); color: #81c995; padding: 6px 12px; border-radius: 16px; font-size: 11px; font-weight: 600; border: 1px solid rgba(129, 201, 149, 0.2);'>
                ● ONLINE
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- 7. NAVIGATION TABS LAYOUT ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "AI Assistant",
        "Web Intelligence",
        "Live Market Feed",
        "Risk Diagnostics",
        "Optimal Weights",
        "Analytics",
        "Price History",
    ]
)

# --- TAB 1: AI Analyst Console ---
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant",
            "content": "Hi there. I'm J.A.R.V.I.S., your terminal assistant. How can I help analyze the markets today?",
        }]

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
                        st.error("GROQ_API_KEY is missing. Please configure it.")
                    else:
                        chat_llm = ChatGroq(
                            model="llama-3.1-8b-instant",
                            temperature=0.1,
                            groq_api_key=api_key,
                        )
                        messages = [
                            SystemMessage(
                                content="You are J.A.R.V.I.S., an advanced institutional quantitative trading assistant. Provide precise, technical, and data-driven market analysis. Do not include knowledge-cutoff disclaimers, standard AI boilerplate, or financial advice warnings."
                            ),
                            HumanMessage(content=prompt),
                        ]
                        response_msg = chat_llm.invoke(messages).content
                        st.markdown(response_msg)
                        st.session_state.messages.append({"role": "assistant", "content": response_msg})
                except Exception as e:
                    err_msg = f"API connection error: {e}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})

# --- TAB 2: Market Intelligence Search ---
with tab2:
    st.markdown("<br>", unsafe_allow_html=True)
    col_s1, col_s2 = st.columns([4, 1])
    with col_s1:
        search_query = st.text_input(
            "Query",
            placeholder="Search global macro indicators or sector news...",
            label_visibility="collapsed",
        )
    with col_s2:
        search_btn = st.button("Search Web", width="stretch")

    if search_btn:
        if not search_query.strip():
            st.warning("Please enter a valid search string.")
        elif not search_available:
            st.error("Search package (`ddgs`) is not installed. Run `pip install ddgs`.")
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
                    st.error(f"Search execution error: {e}")

# --- TAB 3: Live NSE & BSE Market Feed ---
with tab3:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("watchlist_form", border=False):
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            nse_input = st.text_area("NSE Tickers (comma separated)", value=", ".join(st.session_state.nse_watchlist))
        with col_w2:
            bse_input = st.text_area("BSE Symbols (comma separated)", value=", ".join(st.session_state.bse_watchlist))
        
        update_watchlist_btn = st.form_submit_button("Update Watchlists")

    if update_watchlist_btn:
        st.session_state.nse_watchlist = [t.strip().upper() for t in nse_input.split(",") if t.strip()]
        st.session_state.bse_watchlist = [t.strip().upper() for t in bse_input.split(",") if t.strip()]

    st.markdown("<hr style='border-color: #3c4043; margin: 24px 0;'>", unsafe_allow_html=True)
    
    col_ctrl1, col_ctrl2 = st.columns([1, 2])
    with col_ctrl1:
        auto_refresh = st.checkbox("Auto-Refresh Stream", value=False)
    with col_ctrl2:
        refresh_rate = st.slider("Interval (s)", min_value=5, max_value=60, value=10, label_visibility="collapsed")

    col_t1, col_t2 = st.columns(2)
    placeholder_nse = col_t1.empty()
    placeholder_bse = col_t2.empty()
    status_placeholder = st.empty()

    async def fetch_nse_live_async(client, symbol):
        try:
            url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
            # Inherits cookies/headers from the parent AsyncClient
            response = await client.get(url, timeout=4.0)
            if response.status_code == 200:
                data = response.json()
                p_info = data.get("priceInfo", {})
                return {
                    "Symbol": symbol,
                    "Exchange": "NSE",
                    "Last (₹)": p_info.get("lastPrice", 0.0),
                    "Change (%)": p_info.get("pChange", 0.0),
                }
        except Exception:
            pass
        return {"Symbol": symbol, "Exchange": "NSE", "Last (₹)": "N/A", "Change (%)": "N/A"}

    async def fetch_bse_live_async(client, symbol):
        try:
            search_url = f"https://api.bseindia.com/Msource/1D/getQouteSearch.aspx?Type=EQ&text={symbol}&flag=site"
            resp = await client.get(search_url, timeout=4.0)
            soup = BeautifulSoup(resp.content, "html.parser")
            a_tag = soup.find("a")
            if a_tag and "href" in a_tag.attrs:
                code_match = re.search(r"/(\d+)/", a_tag["href"])
                if code_match:
                    scrip_code = code_match.group(1)
                    quote_url = f"https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?&scripcode={scrip_code}&flag=0"
                    q_resp = await client.get(quote_url, timeout=4.0)
                    q_data = q_resp.json()
                    curr_val = q_data.get("CurrVal")
                    prev_close = q_data.get("PrevClose")
                    p_change = round(((float(curr_val) - float(prev_close)) / float(prev_close)) * 100, 2) if curr_val and prev_close else 0.0
                    
                    return {
                        "Symbol": symbol,
                        "Exchange": "BSE",
                        "Last (₹)": float(curr_val) if curr_val else "N/A",
                        "Change (%)": p_change,
                    }
        except Exception:
            pass
        return {"Symbol": symbol, "Exchange": "BSE", "Last (₹)": "N/A", "Change (%)": "N/A"}

    @exchange_breaker
    def execute_exchange_fetch(nse_tuple, bse_tuple):
        async def fetch_all():
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.nseindia.com/'
            }
            
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                # Bypass NSE WAF by pinging homepage to capture session cookies first
                try:
                    await client.get("https://www.nseindia.com", timeout=5.0)
                except Exception:
                    pass
                
                nse_tasks = [fetch_nse_live_async(client, sym) for sym in nse_tuple]
                bse_tasks = [fetch_bse_live_async(client, sym) for sym in bse_tuple]
                nse_res = await asyncio.gather(*nse_tasks)
                bse_res = await asyncio.gather(*bse_tasks)
                return pd.DataFrame(nse_res), pd.DataFrame(bse_res)

        return asyncio.run(fetch_all())

    @st.cache_data(ttl=15)
    def get_cached_live_markets_safe(nse_tuple, bse_tuple):
        try:
            return execute_exchange_fetch(nse_tuple, bse_tuple)
        except pybreaker.CircuitBreakerError:
            df_fallback_nse = pd.DataFrame([{"Symbol": s, "Exchange": "NSE", "Last (₹)": "Offline", "Change (%)": 0.0} for s in nse_tuple])
            df_fallback_bse = pd.DataFrame([{"Symbol": s, "Exchange": "BSE", "Last (₹)": "Offline", "Change (%)": 0.0} for s in bse_tuple])
            return df_fallback_nse, df_fallback_bse

    df_nse, df_bse = get_cached_live_markets_safe(tuple(st.session_state.nse_watchlist), tuple(st.session_state.bse_watchlist))

    placeholder_nse.markdown("<h4 style='color:#e3e3e3; font-size: 16px;'>NSE Equities</h4>", unsafe_allow_html=True)
    placeholder_nse.dataframe(df_nse, width="stretch", hide_index=True)

    placeholder_bse.markdown("<h4 style='color:#e3e3e3; font-size: 16px;'>BSE Equities</h4>", unsafe_allow_html=True)
    placeholder_bse.dataframe(df_bse, width="stretch", hide_index=True)

    if auto_refresh:
        status_placeholder.markdown(f"<span style='color: #c4c7c5; font-size: 12px;'>Syncing at {time.strftime('%H:%M:%S')}</span>", unsafe_allow_html=True)
        time.sleep(refresh_rate)
        st.rerun()

# --- EXECUTION ENGINE FOR QUANTITATIVE TABS (4, 5, 6, 7) ---
if run_button:
    tickers = [resolve_ticker_via_search(t) for t in st.session_state.nse_watchlist]

    if not tickers:
        st.error("Please supply valid asset ticker symbols.")
    else:
        with st.spinner("Compiling quantitative models..."):
            days_map = {"6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
            start_date = (
                datetime.today() - timedelta(days=days_map.get(time_period, 365))
            ).strftime("%Y-%m-%d")
            end_date = datetime.today().strftime("%Y-%m-%d")

            df_prices = fetch_stock_data(
                tickers, start_date=start_date, end_date=end_date
            )

            # --- UPDATED ERROR HANDLING ---
            if df_prices.empty:
                st.error(f"Data pipeline failed. yfinance returned empty data for tickers: {tickers}. Check your ticker symbols or network connection.")
            else:
                method_mapping = "equal" if "Equal-Weight" in strategy_method else "max_sharpe"
                strategy = RebalancingStrategy(tickers, method=method_mapping)
                target_weights = strategy.calculate_weights()

                safe_weights, risk_status, current_dd = check_portfolio_risk(
                    df_prices, target_weights, max_drawdown_limit=max_dd_limit / 100.0
                )

                metrics, equity_curve = run_backtest(df_prices, safe_weights)

                st.session_state.quant_results = {
                    "df_prices": df_prices,
                    "safe_weights": safe_weights,
                    "risk_status": risk_status,
                    "current_dd": current_dd,
                    "metrics": metrics,
                    "equity_curve": equity_curve
                }

if "quant_results" in st.session_state:
    res = st.session_state.quant_results

    with tab4:
        st.markdown("<br>", unsafe_allow_html=True)
        if "CIRCUIT BREAKER" in res["risk_status"]:
            st.error(res["risk_status"])
        elif "WARNING" in res["risk_status"]:
            st.warning(res["risk_status"])
        else:
            st.success(f"Status: Nominal (Current Drawdown: {res['current_dd']*100:.2f}%)")

    with tab5:
        st.markdown("<br>", unsafe_allow_html=True)
        cols = st.columns(len(res["safe_weights"]) if res["safe_weights"] else 1)
        for i, (ticker, weight) in enumerate(res["safe_weights"].items()):
            with cols[i]:
                st.metric(label=ticker, value=f"{weight * 100:.2f}%")

    with tab6:
        st.markdown("<br>", unsafe_allow_html=True)
        m_cols = st.columns(4)
        m_cols[0].metric("CAGR", f"{res['metrics'].get('CAGR', 0)}%")
        m_cols[1].metric("Sharpe Ratio", f"{res['metrics'].get('Sharpe Ratio', 0)}")
        m_cols[2].metric("Ann. Volatility", f"{res['metrics'].get('Annualized Volatility', 0)}%")
        m_cols[3].metric("Max Drawdown", f"{res['metrics'].get('Maximum Drawdown', 0)}%")

        st.markdown("<br><h4 style='font-size: 16px;'>Equity Curve</h4>", unsafe_allow_html=True)
        st.line_chart(res["equity_curve"])

    with tab7:
        st.markdown("<br>", unsafe_allow_html=True)
        st.line_chart(res["df_prices"])

