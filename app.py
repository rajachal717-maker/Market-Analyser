from datetime import datetime, timedelta
import os
import pandas as pd
import streamlit as st

# Local Modules
from backtester import run_backtest
from data_loader import fetch_stock_data
from risk_manager import check_portfolio_risk
from strategy import calculate_portfolio_weights

# Groq and LangChain Agent Imports
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

# Page Configuration
st.set_page_config(
    page_title="Institutional Quant & Intelligence Terminal",
    page_icon="⚡",
    layout="wide",
)

# --- PROFESSIONAL CSS STYLING ENGINE ---
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
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
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


# Sidebar Configuration Panel
st.sidebar.markdown(
    "<h3 style='color: #60a5fa; font-size: 16px; margin-bottom: 0px;'>⚡"
    " TERMINAL CONFIG</h3>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")
ticker_input = st.sidebar.text_input(
    "Asset Universe (Tickers)",
    value="AAPL, MSFT, GOOGL, AMZN",
    help="Comma-separated ticker symbols.",
)
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

# Professional Header Section
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
  st.title("Institutional Portfolio & Intelligence Terminal")
  st.markdown(
      "<p style='color: #9ca3af; font-size: 14px; margin-top: -10px;'>Advanced"
      " Quantitative Strategy Execution, Real-Time Risk Diagnostics, and Web"
      " Intelligence</p>",
      unsafe_allow_html=True,
  )
with col_h2:
  st.markdown(
      "<div style='text-align: right; padding-top: 10px;'><span"
      " style='background-color: rgba(6, 95, 70, 0.4); color: #34d399; border:"
      " 1px solid #059669; padding: 6px 12px; border-radius: 6px; font-size:"
      " 12px; font-weight: 600; letter-spacing: 0.5px;'>● SYSTEM"
      " ONLINE</span></div>",
      unsafe_allow_html=True,
  )

st.markdown("---")

# Navigation Tabs Layout
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "💬 AI Analyst Console",
        "🌐 Market Intelligence",
        "🛡️ Risk & Circuit Breakers",
        "⚖️ Optimal Allocations",
        "📈 Performance Analytics",
        "📊 Historical Price Data",
    ]
)

# --- TAB 1: AI Analyst Console ---
with tab1:
  st.subheader("Autonomous AI Assistant Console")
  st.write(
      "Engage directly with the neural assistant for portfolio insights and"
      " tactical market reviews."
  )

  if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "Terminal connected. Ready for quantitative queries or market"
            " evaluations."
        ),
    }]

  for message in st.session_state.messages:
    with st.chat_message(
        message["role"], avatar="🤖" if message["role"] == "assistant" else "👤"
    ):
      st.markdown(message["content"])

  if prompt := st.chat_input("Enter analysis query..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
      st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
      with st.spinner("Processing analysis..."):
        try:
          api_key = None
          try:
            api_key = st.secrets.get("GROQ_API_KEY")
          except Exception:
            pass

          if not api_key:
            api_key = os.environ.get("GROQ_API_KEY")

          if not api_key:
            st.error(
                "GROQ_API_KEY is missing. Please configure it in Streamlit Cloud"
                " Secrets or your local environment."
            )
          else:
            chat_llm = ChatGroq(
                model="llama-3.1-8b-instant",
                temperature=0.1,
                groq_api_key=api_key,
            )

            messages = [
                SystemMessage(
                    content=(
                        "You are J.A.R.V.I.S., an advanced institutional"
                        " quantitative trading assistant. Provide precise,"
                        " technical, and data-driven market analysis. Do not"
                        " include knowledge-cutoff disclaimers, standard AI"
                        " boilerplate, or financial advice warnings."
                    )
                ),
                HumanMessage(content=prompt),
            ]

            response_msg = chat_llm.invoke(messages).content

            st.markdown(response_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": response_msg}
            )
        except Exception as e:
          err_msg = f"API connection error (Status 400/Request Failed): {e}"
          st.error(err_msg)
          st.session_state.messages.append(
              {"role": "assistant", "content": err_msg}
          )

# --- TAB 2: Market Intelligence Search ---
with tab2:
  st.subheader("Real-Time Web Intelligence Scraper")
  st.write(
      "Scan live news feeds and macroeconomic indicators across global sources."
  )

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
      st.error(
          "Search package (`ddgs`) is not installed. Run: `pip install ddgs`"
      )
    else:
      with st.spinner("Querying live network feeds..."):
        try:
          with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
            if not results:
              st.info("No matching intelligence data found.")
            else:
              st.success(
                  f"Retrieved {len(results)} live records for '{search_query}':"
              )
              for i, r in enumerate(results, 1):
                with st.expander(
                    f"[{i}] {r.get('title', 'No Title')}", expanded=(i == 1)
                ):
                  st.write(f"**Overview:** {r.get('body', '')}")
                  st.markdown(f"**Reference Link:** [Open]({r.get('href', '#')})")
        except Exception as e:
          st.error(f"Search execution error: {e}")

# --- EXECUTION ENGINE FOR QUANTITATIVE TABS (3, 4, 5, 6) ---
if run_button:
  raw_tokens = [t.strip() for t in ticker_input.split(",") if t.strip()]
  tickers = [resolve_ticker_via_search(t) for t in raw_tokens]

  if not tickers:
    st.error("Please supply valid asset ticker symbols.")
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
        st.error(
            "Failed to fetch market data. Ensure valid ticker symbols (e.g.,"
            " GOOGL instead of GOOGLE)."
        )
      else:
        method_key = (
            "max_sharpe" if "Sharpe" in strategy_method else "equal"
        )
        raw_weights = calculate_portfolio_weights(tickers, method=method_key)

        safe_weights, risk_status, current_dd = check_portfolio_risk(
            df_prices, raw_weights, max_drawdown_limit=max_dd_limit / 100.0
        )

        metrics, equity_curve = run_backtest(df_prices, safe_weights)

        with tab3:
          st.subheader("Automated Risk Monitor & Circuit Breakers")
          if "CIRCUIT BREAKER" in risk_status:
            st.error(risk_status)
          elif "WARNING" in risk_status:
            st.warning(risk_status)
          else:
            st.success(
                f"✅ Status: Normal Operation (Current Drawdown:"
                f" {current_dd*100:.2f}%)"
            )

        with tab4:
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

        with tab5:
          st.subheader("Historical Performance Analytics")
          m_cols = st.columns(4)
          m_cols[0].metric("CAGR", f"{metrics.get('CAGR', 0)}%")
          m_cols[1].metric("Sharpe Ratio", f"{metrics.get('Sharpe Ratio', 0)}")
          m_cols[2].metric(
              "Annualized Vol", f"{metrics.get('Annualized Volatility', 0)}%"
          )
          m_cols[3].metric(
              "Max Drawdown", f"{metrics.get('Maximum Drawdown', 0)}%"
          )

          st.markdown("---")
          st.markdown("### Cumulative Portfolio Equity Curve")
          st.line_chart(equity_curve, use_container_width=True)

        with tab6:
          st.subheader("Normalized Asset Price History")
          st.line_chart(df_prices, use_container_width=True)
