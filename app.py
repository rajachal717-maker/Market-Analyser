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
from nsepython import nse_eq

# Page Configuration (Must be the first Streamlit command)
st.set_page_config(
    page_title="Institutional Quant & Intelligence Terminal",
    page_icon="⚡",
    layout="wide",
)

# --- 1. SUPABASE CONNECTION SETUP (Bypassing local secrets crash) ---
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
            login_btn = st.form_submit_button("Authenticate Session", use_container_width=True)

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
            signup_btn = st.form_submit_button("Register Account", use_container_width=True)

            if signup_btn:
                try:
                    response = supabase.auth.sign_up({
                        "email": signup_email,
                        "password": signup_password,
                    })
                    st.success("Account registered successfully! Please check your email inbox to verify your account before logging in.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

    st.stop()  # Locks the rest of the application until authenticated

else:
    # --- 3. LOCAL QUANTITATIVE & AI MODULE IMPORTS ---
    from backtester import run_backtest
    from data_loader import fetch_stock_data
    from risk_manager import check_portfolio_risk
    from strategy import calculate_portfolio_weights

    # Groq and LangChain Imports
    from dotenv import load_dotenv
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_groq import ChatGroq

    load_dotenv()

    # Safe import for search engine module
    try:
        from ddgs import DDGS
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

    # --- 5. SIDEBAR CONFIGURATION ---
    st.sidebar.markdown("<h3 style='color: #60a5fa; font-size: 16px; margin-bottom: 0px;'>⚡ TERMINAL CONFIG</h3>", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    # Operator Info & Logout Widget
    user_email = st.session_state.user.email
    st.sidebar.markdown(f"**Operator:** `{user_email}`")
    if st.sidebar.button("Terminate Session", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.sidebar.markdown("---")

    strategy_method = st.sidebar.selectbox(
        "Portfolio Optimization", ["Max Sharpe Ratio", "Equal-Weight (1/N)"]
    )
    time_period = st.sidebar.selectbox(
        "Lookback Window", ["6mo", "1y", "2y", "5y"]
    )
    max_dd_limit = st.sidebar.slider(
        "Circuit Breaker Threshold (%)", -30, -5, -15
    )

    run_button = st.sidebar.button(
        "Run Quantitative Model", use_container_width=True
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
                        err_msg = f"API connection error (Status 400/Request Failed): {e}"
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
            search_btn = st.button("Search Web", use_container_width=True)

        if search_btn:
            if not search_query.strip():
                st.warning("Please enter a valid search string.")
            elif not search_available:
                st.error("Search package (`ddgs`) is not installed. Run: `pip install ddgs`")
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

    # --- TAB 3: Live NSE & BSE Market Feed ---
    with tab3:
        st.subheader("🔴 Live Exchange Terminal (NSE & BSE)")
        st.markdown("Streaming live quotes and market metrics for Indian equities across exchanges.")

        with st.form("watchlist_form"):
            col_w1, col_w2 = st.columns(2)
            with col_w1:
                nse_input = st.text_area("NSE Tickers (comma separated)", value=", ".join(st.session_state.nse_watchlist))
            with col_w2:
                bse_input = st.text_area("BSE Symbols (comma separated)", value=", ".join(st.session_state.bse_watchlist))
            
            update_watchlist_btn = st.form_submit_button("Apply Watchlists & Refresh", use_container_width=True)

        if update_watchlist_btn:
            st.session_state.nse_watchlist = [t.strip().upper() for t in nse_input.split(",") if t.strip()]
            st.session_state.bse_watchlist = [t.strip().upper() for t in bse_input.split(",") if t.strip()]
            st.success("Watchlists updated successfully!")

        refresh_rate = st.slider("Refresh Interval (seconds)", min_value=3, max_value=30, value=5, key="live_refresh_slider")
        auto_refresh = st.checkbox("Enable Live Auto-Refresh", value=True, key="live_auto_checkbox")

        col_t1, col_t2 = st.columns(2)
        placeholder_nse = col_t1.empty()
        placeholder_bse = col_t2.empty()
        status_placeholder = st.empty()

        def fetch_nse_live(symbols):
            rows = []
            for symbol in symbols:
                try:
                    data = nse_eq(symbol)
                    p_info = data.get("priceInfo", {})
                    rows.append({
                        "Symbol": symbol,
                        "Exchange": "NSE",
                        "Last Price (₹)": p_info.get("lastPrice"),
                        "Change (%)": p_info.get("pChange"),
                        "Day High (₹)": p_info.get("intraDayHighLow", {}).get("max"),
                        "Day Low (₹)": p_info.get("intraDayHighLow", {}).get("min"),
                    })
                except Exception:
                    rows.append({"Symbol": symbol, "Exchange": "NSE", "Last Price (₹)": 0.0, "Change (%)": 0.0, "Day High (₹)": 0.0, "Day Low (₹)": 0.0})
            return pd.DataFrame(rows)

        def fetch_bse_live(symbols):
            rows = []
            headers = {'user-agent': 'Mozilla/5.0'}
            for symbol in symbols:
                try:
                    search_url = f"https://api.bseindia.com/Msource/1D/getQouteSearch.aspx?Type=EQ&text={symbol}&flag=site"
                    resp = requests.get(search_url, headers=headers, timeout=5)
                    soup = BeautifulSoup(resp.content, "html.parser")
                    a_tag = soup.find("a")
                    if a_tag and "href" in a_tag.attrs:
                        code_match = re.search(r"/(\d+)/", a_tag["href"])
                        if code_match:
                            scrip_code = code_match.group(1)
                            quote_url = f"https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?&scripcode={scrip_code}&flag=0"
                            q_resp = requests.get(quote_url, headers=headers, timeout=5)
                            q_data = q_resp.json()
                            curr_val = q_data.get("CurrVal")
                            prev_close = q_data.get("PrevClose")
                            p_change = round(((float(curr_val) - float(prev_close)) / float(prev_close)) * 100, 2) if curr_val and prev_close else 0.0
                            
                            rows.append({
                                "Symbol": symbol,
                                "Exchange": "BSE",
                                "Last Price (₹)": float(curr_val) if curr_val else 0.0,
                                "Change (%)": p_change,
                                "Scrip Code": scrip_code
                            })
                            continue
                except Exception:
                    pass
                rows.append({"Symbol": symbol, "Exchange": "BSE", "Last Price (₹)": 0.0, "Change (%)": 0.0, "Scrip Code": "N/A"})
            return pd.DataFrame(rows)

        df_nse = fetch_nse_live(st.session_state.nse_watchlist)
        df_bse = fetch_bse_live(st.session_state.bse_watchlist)

        placeholder_nse.markdown("### **NSE Feed**")
        placeholder_nse.dataframe(df_nse, use_container_width=True, hide_index=True)

        placeholder_bse.markdown("### **BSE Feed**")
        placeholder_bse.dataframe(df_bse, use_container_width=True, hide_index=True)

        if auto_refresh:
            status_placeholder.text(f"Last updated: {time.strftime('%H:%M:%S')} | Refreshing every {refresh_rate}s...")
            time.sleep(refresh_rate)
            st.rerun()

    # --- EXECUTION ENGINE FOR QUANTITATIVE TABS (4, 5, 6, 7) ---
    if run_button:
        tickers = [resolve_ticker_via_search(t) for t in st.session_state.nse_watchlist]

        if not tickers:
            st.error("Please supply valid asset ticker symbols in the Live NSE Feed tab.")
        else:
            with st.spinner("Executing quantitative pipelines & risk engines..."):
                days_map = {"6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
                start_date = (
                    datetime.today() - timedelta(days=days_map.get(time_period, 365))
                ).strftime("%Y-%m-%d")
                end_date = datetime.today().strftime("%Y-%m-%d")

                df_prices = fetch_stock_data(
                    tickers, start_date=start_date, end_date=end_date
                )

                if df_prices.empty:
                    st.error("Failed to fetch market data. Ensure valid ticker symbols (e.g., VMART instead of V-MART).")
                else:
                    method_key = "max_sharpe" if "Sharpe" in strategy_method else "equal"
                    raw_weights = calculate_portfolio_weights(tickers, method=method_key)

                    safe_weights, risk_status, current_dd = check_portfolio_risk(
                        df_prices, raw_weights, max_drawdown_limit=max_dd_limit / 100.0
                    )

                    metrics, equity_curve = run_backtest(df_prices, safe_weights)

                    with tab4:
                        st.subheader("Automated Risk Monitor & Circuit Breakers")
                        if "CIRCUIT BREAKER" in risk_status:
                            st.error(risk_status)
                        elif "WARNING" in risk_status:
                            st.warning(risk_status)
                        else:
                            st.success(f"✅ Status: Normal Operation (Current Drawdown: {current_dd*100:.2f}%)")

                    with tab5:
                        st.subheader("Target Portfolio Allocation Matrix")
                        cols = st.columns(len(safe_weights) if safe_weights else 1)
                        for i, (ticker, weight) in enumerate(safe_weights.items()):
                            with cols[i]:
                                st.metric(label=ticker, value=f"{weight * 100:.2f}%")

                        st.markdown("---")
                        df_w = pd.DataFrame(
                            list(safe_weights.items()),
                            columns=["Ticker", "Safe Target Weight"],
                        )
                        st.dataframe(df_w, use_container_width=True)

                    with tab6:
                        st.subheader("Historical Performance Analytics")
                        m_cols = st.columns(4)
                        m_cols[0].metric("CAGR", f"{metrics.get('CAGR', 0)}%")
                        m_cols[1].metric("Sharpe Ratio", f"{metrics.get('Sharpe Ratio', 0)}")
                        m_cols[2].metric("Annualized Vol", f"{metrics.get('Annualized Volatility', 0)}%")
                        m_cols[3].metric("Max Drawdown", f"{metrics.get('Maximum Drawdown', 0)}%")

                        st.markdown("---")
                        st.markdown("### Cumulative Portfolio Equity Curve")
                        st.line_chart(equity_curve, use_container_width=True)

                    with tab7:
                        st.subheader("Normalized Asset Price History")
                        st.line_chart(df_prices, use_container_width=True)
