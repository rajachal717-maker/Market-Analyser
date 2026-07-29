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
import yfinance as yf

# Page Configuration (Must be the first Streamlit command)
st.set_page_config(
    page_title="Institutional Quant & Intelligence Terminal",
    page_icon="⚡",
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

# --- 2. AUTHENTICATION UI & GATEKEEPER ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #0b0f19;
            color: #f0f6fc;
        }
        .block-container {
            padding-top: 4rem;
            max-width: 600px;
        }
        .stButton>button {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            background: linear-gradient(135deg, #1d4ed8 100%, #1e40af 100%);
            box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
        }
        .stTextInput>div>div>input {
            background-color: #1f2937;
            color: #f9fafb;
            border: 1px solid #374151;
            border-radius: 8px;
            padding: 8px 12px;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("<h2 style='text-align: center; color: #f8fafc; margin-bottom: 5px;'>⚡ TERMINAL ACCESS PORTAL</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #9ca3af; font-size: 14px; margin-bottom: 30px;'>Authenticate securely to access quantitative pipelines and neural models.</p>", unsafe_allow_html=True)

    auth_tab1, auth_tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])

    with auth_tab1:
        with st.form("login_form"):
            login_email = st.text_input("Email Address")
            login_password = st.text_input("Password", type="password")
            st.markdown("")
            login_btn = st.form_submit_button("Authenticate Session", width="stretch")

            if login_btn:
                try:
                    response = supabase.auth.sign_in_with_password({
                        "email": login_email,
                        "password": login_password,
                    })
                    st.session_state.user = response.user
                    st.success("Authentication successful! Initializing terminal...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with auth_tab2:
        with st.form("signup_form"):
            signup_email = st.text_input("New Email Address")
            signup_password = st.text_input("Choose Secure Password", type="password")
            st.markdown("")
            signup_btn = st.form_submit_button("Register Account", width="stretch")

            if signup_btn:
                try:
                    response = supabase.auth.sign_up({
                        "email": signup_email,
                        "password": signup_password,
                    })
                    st.success("Account registered successfully! Please check your email inbox to verify your account before logging in.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

    st.stop()

else:
    # --- 3. LOCAL QUANTITATIVE & AI MODULE IMPORTS ---
    from strategy import RebalancingStrategy
    from backtester import run_backtest
    from risk_manager import check_portfolio_risk

    # Groq and LangChain Imports
    from dotenv import load_dotenv
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_groq import ChatGroq

    load_dotenv()

    # Safe import for search engine module
    try:
        from duckduckgo_search import DDGS
        search_available = True
    except ImportError:
        search_available = False

    # Initialize Watchlist state securely
    if "nse_watchlist" not in st.session_state:
        st.session_state.nse_watchlist = ["VMART", "NOCIL", "RELIANCE", "TCS"]
    if "bse_watchlist" not in st.session_state:
        st.session_state.bse_watchlist = ["RELIANCE", "INFY", "TCS"]

    # --- 4. PROFESSIONAL CSS STYLING ENGINE (DASHBOARD) ---
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #0b0f19;
            color: #f0f6fc;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        [data-testid="stSidebar"] {
            background-color: #111827;
            border-right: 1px solid #1f2937;
        }
        [data-testid="stSidebar"] label {
            color: #9ca3af !important;
            font-weight: 500;
            font-size: 13px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #111827;
            padding: 8px;
            border-radius: 10px;
            border: 1px solid #1f2937;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: transparent;
            border-radius: 6px;
            color: #9ca3af;
            padding: 10px 18px;
            font-weight: 600;
            font-size: 13px;
            border: none;
            transition: all 0.2s ease-in-out;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #1f2937;
            color: #f8fafc;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2563eb !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }

        h1, h2, h3 {
            color: #f8fafc !important;
            font-weight: 700;
            letter-spacing: -0.025em;
        }

        .stButton>button {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            background: linear-gradient(135deg, #1d4ed8 100%, #1e40af 100%);
            box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
            border-color: transparent;
        }

        .stTextInput>div>div>input, .stSelectbox>div>div>div {
            background-color: #1f2937;
            color: #f9fafb;
            border: 1px solid #374151;
            border-radius: 8px;
            padding: 6px 12px;
        }

        [data-testid="stMetric"] {
            background-color: #111827;
            border: 1px solid #1f2937;
            padding: 16px;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        [data-testid="stMetricLabel"] {
            color: #9ca3af !important;
            font-size: 13px !important;
            font-weight: 500 !important;
        }
        [data-testid="stMetricValue"] {
            color: #f8fafc !important;
            font-size: 24px !important;
            font-weight: 700 !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid #1f2937;
            border-radius: 8px;
            overflow: hidden;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    def resolve_ticker_via_search(user_query: str) -> str:
        cleaned = user_query.strip()
        return cleaned.upper()

    # --- DIRECT CLOUD DATA LOADER (YFINANCE) ---
    @st.cache_data(ttl=300)
    def fetch_stock_data(tickers, start_date, end_date):
        data = {}
        for ticker in tickers:
            try:
                # Yahoo Finance requires .NS for Indian National Stock Exchange tickers
                yf_ticker = ticker if ticker.endswith('.NS') or ticker.endswith('.BO') else f"{ticker}.NS"
                
                # Fetch data directly from Yahoo Finance
                stock_data = yf.download(yf_ticker, start=start_date, end=end_date, progress=False)
                
                if not stock_data.empty:
                    # Extract the 'Close' column and store it as a pandas Series
                    data[ticker] = stock_data["Close"].squeeze()
            except Exception as e:
                pass
                
        if data:
            # Combine all ticker series into a single DataFrame and drop missing dates
            return pd.DataFrame(data).dropna()
        return pd.DataFrame()
    



    # --- 5. SIDEBAR CONFIGURATION ---
    st.sidebar.markdown("<h3 style='color: #60a5fa; font-size: 16px; margin-bottom: 0px;'>⚡ TERMINAL CONFIG</h3>", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    user_email = st.session_state.user.email
    st.sidebar.markdown(f"**Operator:** `{user_email}`")
    if st.sidebar.button("Terminate Session", width="stretch"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.sidebar.markdown("---")

    strategy_method = st.sidebar.selectbox(
        "Portfolio Optimization", ["Equal-Weight (1/N)", "Max Sharpe Ratio"]
    )
    time_period = st.sidebar.selectbox(
        "Lookback Window", ["6mo", "1y", "2y", "5y"]
    )
    max_dd_limit = st.sidebar.slider(
        "Circuit Breaker Threshold (%)", -30, -5, -15
    )

    run_button = st.sidebar.button(
        "Run Quantitative Model", width="stretch"
    )

    # --- 6. MAIN APPLICATION HEADER ---
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.title("Institutional Portfolio & Intelligence Terminal")
        st.markdown(
            "<p style='color: #9ca3af; font-size: 14px; margin-top: -10px;'>Advanced Quantitative Strategy Execution, Real-Time Risk Diagnostics, and Web Intelligence</p>",
            unsafe_allow_html=True,
        )
    with col_h2:
        st.markdown(
            "<div style='text-align: right; padding-top: 10px;'><span style='background-color: rgba(6, 95, 70, 0.4); color: #34d399; border: 1px solid #059669; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.5px;'>● SYSTEM ONLINE</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # --- 7. NAVIGATION TABS LAYOUT ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "💬 AI Analyst Console",
            "🌐 Market Intelligence",
            "🔴 Live NSE & BSE Feed",
            "🛡️ Risk & Circuit Breakers",
            "⚖️ Optimal Allocations",
            "📈 Performance Analytics",
            "📊 Historical Price Data",
        ]
    )

    # --- TAB 1: AI Analyst Console ---
    with tab1:
        st.subheader("Autonomous AI Assistant Console")
        st.write("Engage directly with the neural assistant for portfolio insights and tactical market reviews.")

        if "messages" not in st.session_state:
            st.session_state.messages = [{
                "role": "assistant",
                "content": "Terminal connected. Ready for quantitative queries or market evaluations.",
            }]

        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar="🤖" if message["role"] == "assistant" else "👤"):
                st.markdown(message["content"])

        if prompt := st.chat_input("Enter analysis query..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Processing analysis..."):
                    try:
                        api_key = os.environ.get("GROQ_API_KEY")
                        if not api_key:
                            st.error("GROQ_API_KEY is missing. Please configure it in your environment variables.")
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
        st.subheader("Real-Time Web Intelligence Scraper")
        st.write("Scan live news feeds and macroeconomic indicators across global sources.")

        col_s1, col_s2 = st.columns([4, 1])
        with col_s1:
            search_query = st.text_input(
                "Search Query",
                placeholder="e.g., global inflation metrics or sector earnings",
                label_visibility="collapsed",
            )
        with col_s2:
            search_btn = st.button("Search Web", width="stretch")

        if search_btn:
            if not search_query.strip():
                st.warning("Please enter a valid search string.")
            elif not search_available:
                st.error("Search package (`duckduckgo-search`) is not installed. Run: `pip install duckduckgo-search`")
            else:
                with st.spinner("Querying live network feeds..."):
                    try:
                        with DDGS() as ddgs:
                            results = list(ddgs.text(search_query, max_results=5))
                            if not results:
                                st.info("No matching intelligence data found.")
                            else:
                                st.success(f"Retrieved {len(results)} live records for '{search_query}':")
                                for i, r in enumerate(results, 1):
                                    with st.expander(f"[{i}] {r.get('title', 'No Title')}", expanded=(i == 1)):
                                        st.write(f"**Overview:** {r.get('body', '')}")
                                        st.markdown(f"**Reference Link:** [Open]({r.get('href', '#')})")
                    except Exception as e:
                        st.error(f"Search execution error: {e}")

    # --- TAB 3: Live NSE & BSE Market Feed (Protected by Circuit Breaker) ---
    with tab3:
        st.subheader("🔴 Live Exchange Terminal (NSE & BSE)")
        st.markdown("Streaming live quotes with fault-tolerant circuit breaker protection.")

        with st.form("watchlist_form"):
            col_w1, col_w2 = st.columns(2)
            with col_w1:
                nse_input = st.text_area("NSE Tickers (comma separated)", value=", ".join(st.session_state.nse_watchlist))
            with col_w2:
                bse_input = st.text_area("BSE Symbols (comma separated)", value=", ".join(st.session_state.bse_watchlist))
            
            update_watchlist_btn = st.form_submit_button("Apply Watchlists & Refresh", width="stretch")

        if update_watchlist_btn:
            st.session_state.nse_watchlist = [t.strip().upper() for t in nse_input.split(",") if t.strip()]
            st.session_state.bse_watchlist = [t.strip().upper() for t in bse_input.split(",") if t.strip()]
            st.success("Watchlists updated successfully!")

        refresh_rate = st.slider("Refresh Interval (seconds)", min_value=5, max_value=60, value=10, key="live_refresh_slider")
        auto_refresh = st.checkbox("Enable Live Auto-Refresh", value=False, key="live_auto_checkbox")

        col_t1, col_t2 = st.columns(2)
        placeholder_nse = col_t1.empty()
        placeholder_bse = col_t2.empty()
        status_placeholder = st.empty()

        async def fetch_nse_live_async(client, symbol):
            try:
                url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                response = await client.get(url, headers=headers, timeout=4.0)
                if response.status_code == 200:
                    data = response.json()
                    p_info = data.get("priceInfo", {})
                    return {
                        "Symbol": symbol,
                        "Exchange": "NSE",
                        "Last Price (₹)": p_info.get("lastPrice", 0.0),
                        "Change (%)": p_info.get("pChange", 0.0),
                        "Day High (₹)": p_info.get("intraDayHighLow", {}).get("max", 0.0),
                        "Day Low (₹)": p_info.get("intraDayHighLow", {}).get("min", 0.0),
                    }
            except Exception:
                pass
            return {"Symbol": symbol, "Exchange": "NSE", "Last Price (₹)": "N/A", "Change (%)": "N/A", "Day High (₹)": "N/A", "Day Low (₹)": "N/A"}

        async def fetch_bse_live_async(client, symbol):
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bseindia.com/'
            }
            try:
                search_url = f"https://api.bseindia.com/Msource/1D/getQouteSearch.aspx?Type=EQ&text={symbol}&flag=site"
                resp = await client.get(search_url, headers=headers, timeout=4.0)
                soup = BeautifulSoup(resp.content, "html.parser")
                a_tag = soup.find("a")
                if a_tag and "href" in a_tag.attrs:
                    code_match = re.search(r"/(\d+)/", a_tag["href"])
                    if code_match:
                        scrip_code = code_match.group(1)
                        quote_url = f"https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?&scripcode={scrip_code}&flag=0"
                        q_resp = await client.get(quote_url, headers=headers, timeout=4.0)
                        q_data = q_resp.json()
                        curr_val = q_data.get("CurrVal")
                        prev_close = q_data.get("PrevClose")
                        p_change = round(((float(curr_val) - float(prev_close)) / float(prev_close)) * 100, 2) if curr_val and prev_close else 0.0
                        
                        return {
                            "Symbol": symbol,
                            "Exchange": "BSE",
                            "Last Price (₹)": float(curr_val) if curr_val else "N/A",
                            "Change (%)": p_change,
                            "Scrip Code": scrip_code
                        }
            except Exception:
                pass
            return {"Symbol": symbol, "Exchange": "BSE", "Last Price (₹)": "N/A", "Change (%)": "N/A", "Scrip Code": "N/A"}

        @exchange_breaker
        def execute_exchange_fetch(nse_tuple, bse_tuple):
            async def fetch_all():
                async with httpx.AsyncClient() as client:
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
                st.warning("⚠️ Exchange API connection unstable (Circuit Breaker Tripped). Serving fallback placeholders.")
                df_fallback_nse = pd.DataFrame([{"Symbol": s, "Exchange": "NSE", "Last Price (₹)": "Offline", "Change (%)": 0.0, "Day High (₹)": 0.0, "Day Low (₹)": 0.0} for s in nse_tuple])
                df_fallback_bse = pd.DataFrame([{"Symbol": s, "Exchange": "BSE", "Last Price (₹)": "Offline", "Change (%)": 0.0, "Scrip Code": "N/A"} for s in bse_tuple])
                return df_fallback_nse, df_fallback_bse

        df_nse, df_bse = get_cached_live_markets_safe(tuple(st.session_state.nse_watchlist), tuple(st.session_state.bse_watchlist))

        placeholder_nse.markdown("### **NSE Feed**")
        placeholder_nse.dataframe(df_nse, width="stretch", hide_index=True)

        placeholder_bse.markdown("### **BSE Feed**")
        placeholder_bse.dataframe(df_bse, width="stretch", hide_index=True)

        if auto_refresh:
            status_placeholder.text(f"Last updated: {time.strftime('%H:%M:%S')} | Refreshing every {refresh_rate}s...")
            time.sleep(refresh_rate)
            st.rerun()

    # --- EXECUTION ENGINE FOR QUANTITATIVE TABS (4, 5, 6, 7) ---
    if run_button:
        tickers = [resolve_ticker_via_search(t) for t in st.session_state.nse_watchlist]

        if not tickers:
            st.error("Please supply valid asset ticker symbols in the Live NSE & BSE Feed tab.")
        else:
            with st.spinner("Connecting live exchange watchlist to quantitative engines & backtesters..."):
                days_map = {"6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
                start_date = (
                    datetime.today() - timedelta(days=days_map.get(time_period, 365))
                ).strftime("%Y-%m-%d")
                end_date = datetime.today().strftime("%Y-%m-%d")

                df_prices = fetch_stock_data(
                    tickers, start_date=start_date, end_date=end_date
                )

                if df_prices.empty:
                    st.error("Failed to fetch market data from the backend API. Ensure FastAPI is running on `http://localhost:8000`.")
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
            st.subheader("Automated Risk Monitor & Circuit Breakers")
            if "CIRCUIT BREAKER" in res["risk_status"]:
                st.error(res["risk_status"])
            elif "WARNING" in res["risk_status"]:
                st.warning(res["risk_status"])
            else:
                st.success(f"✅ Status: Normal Operation (Current Drawdown: {res['current_dd']*100:.2f}%)")

        with tab5:
            st.subheader("Target Portfolio Allocation Matrix")
            cols = st.columns(len(res["safe_weights"]) if res["safe_weights"] else 1)
            for i, (ticker, weight) in enumerate(res["safe_weights"].items()):
                with cols[i]:
                    st.metric(label=ticker, value=f"{weight * 100:.2f}%")

            st.markdown("---")
            df_w = pd.DataFrame(
                list(res["safe_weights"].items()),
                columns=["Ticker", "Safe Target Weight"],
            )
            st.dataframe(df_w, width="stretch", hide_index=True)

        with tab6:
            st.subheader("Historical Performance Analytics")
            m_cols = st.columns(4)
            m_cols[0].metric("CAGR", f"{res['metrics'].get('CAGR', 0)}%")
            m_cols[1].metric("Sharpe Ratio", f"{res['metrics'].get('Sharpe Ratio', 0)}")
            m_cols[2].metric("Annualized Vol", f"{res['metrics'].get('Annualized Volatility', 0)}%")
            m_cols[3].metric("Max Drawdown", f"{res['metrics'].get('Maximum Drawdown', 0)}%")

            st.markdown("---")
            st.markdown("### Cumulative Portfolio Equity Curve")
            st.line_chart(res["equity_curve"])

        with tab7:
            st.subheader("Normalized Asset Price History")
            st.line_chart(res["df_prices"])
