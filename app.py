import streamlit as st
import yfinance as yf
import pandas as pd
import asyncio
from datetime import datetime, timedelta

# =====================================================================
# 1. PAGE CONFIGURATION & STATE
# =====================================================================
st.set_page_config(page_title="J.A.R.V.I.S. Terminal", layout="wide", page_icon="🤖")

if "nse_watchlist" not in st.session_state:
    # Defaulting to your active tracking list
    st.session_state.nse_watchlist = ["VMART", "NOCIL", "RELIANCE", "TCS"]
if "bse_watchlist" not in st.session_state:
    st.session_state.bse_watchlist = ["RELIANCE", "INFY", "TCS"]
if "quant_results" not in st.session_state:
    st.session_state.quant_results = {}

# =====================================================================
# 2. PROPRIETARY ALGO PLACEHOLDERS (Replace with your actual imports)
# =====================================================================
# Example: from jarvis_brain import RebalancingStrategy, check_portfolio_risk, run_backtest

def resolve_ticker_via_search(t):
    return t.strip().upper()

class RebalancingStrategy:
    def __init__(self, tickers, method="equal"):
        self.tickers = tickers
        self.method = method
    def calculate_weights(self):
        weight = 1.0 / len(self.tickers) if self.tickers else 0
        return {t: weight for t in self.tickers}

def check_portfolio_risk(df_prices, target_weights, max_drawdown_limit):
    # Dummy logic: Replace with your actual risk logic
    return target_weights, "Status: Nominal", 0.05

def run_backtest(df_prices, safe_weights):
    # Dummy logic: Replace with your actual backtest logic
    metrics = {"CAGR": 12.5, "Sharpe Ratio": 1.2, "Annualized Volatility": 15.0, "Maximum Drawdown": -8.5}
    equity_curve = pd.Series([100, 102, 101, 105, 108], index=pd.date_range(start="2026-01-01", periods=5))
    return metrics, equity_curve

# =====================================================================
# 3. CORE DATA PIPELINES (Cloud-Safe via yfinance)
# =====================================================================
@st.cache_data(ttl=0) # Set ttl=300 for production to cache for 5 mins
def fetch_stock_data(tickers, start_date, end_date):
    """Fetches historical data for the quantitative models."""
    data = {}
    for ticker in tickers:
        try:
            yf_ticker = ticker if ("." in ticker) else f"{ticker}.NS"
            stock_data = yf.download(yf_ticker, start=start_date, end=end_date, progress=False)
            
            if not stock_data.empty and 'Close' in stock_data:
                data[ticker] = stock_data['Close'].squeeze()
        except Exception as e:
            st.warning(f"Failed to fetch {ticker}: {e}")
            
    if data:
        return pd.DataFrame(data).dropna()
    return pd.DataFrame()

def fetch_live_quote(symbol, exchange):
    """Fetches real-time(ish) snapshot data for the terminal stream."""
    suffix = ".NS" if exchange == "NSE" else ".BO"
    yf_ticker = f"{symbol}{suffix}"
    try:
        ticker = yf.Ticker(yf_ticker)
        current_price = ticker.fast_info['lastPrice']
        prev_close = ticker.fast_info['previousClose']
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        return {
            "Symbol": symbol,
            "Exchange": exchange,
            "Last (₹)": round(current_price, 2),
            "Change (%)": round(change_pct, 2)
        }
    except Exception:
        return {"Symbol": symbol, "Exchange": exchange, "Last (₹)": "N/A", "Change (%)": "N/A"}

async def fetch_all_live(nse_list, bse_list):
    """Asynchronously fetches live data for all watchlists."""
    nse_tasks = [asyncio.to_thread(fetch_live_quote, sym, "NSE") for sym in nse_list]
    bse_tasks = [asyncio.to_thread(fetch_live_quote, sym, "BSE") for sym in bse_list]
    
    nse_res = await asyncio.gather(*nse_tasks)
    bse_res = await asyncio.gather(*bse_tasks)
    
    return pd.DataFrame(nse_res), pd.DataFrame(bse_res)

# =====================================================================
# 4. USER INTERFACE
# =====================================================================
st.title("J.A.R.V.I.S. Quantitative Terminal")

# Sidebar Configuration
with st.sidebar:
    st.header("System Parameters")
    st.button("Update Watchlists")
    auto_refresh = st.checkbox("Auto-Refresh Stream")
    
    st.divider()
    st.subheader("Model Settings")
    time_period = st.selectbox("Lookback Period", ["6mo", "1y", "2y", "5y"], index=1)
    strategy_method = st.selectbox("Strategy Method", ["Equal-Weight", "Max-Sharpe"])
    max_dd_limit = st.slider("Max Drawdown Limit (%)", 5, 50, 20)
    
    run_button = st.button("Execute Pipeline", type="primary")

# Main Terminal Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Live Stream", "NSE Market", "BSE Market", 
    "Risk Status", "Target Weights", "Backtest Metrics", "Price Data"
])

# --- TAB 1: Live Watchlist Stream ---
with tab1:
    st.markdown("### Active Watchlist Quotes")
    if st.button("Refresh Live Data") or auto_refresh:
        with st.spinner("Pinging global exchanges..."):
            df_nse_live, df_bse_live = asyncio.run(fetch_all_live(st.session_state.nse_watchlist, st.session_state.bse_watchlist))
            
            st.write("#### NSE Watchlist")
            st.dataframe(df_nse_live, use_container_width=True, hide_index=True)
            
            st.write("#### BSE Watchlist")
            st.dataframe(df_bse_live, use_container_width=True, hide_index=True)

# --- EXECUTE PIPELINE LOGIC ---
if run_button:
    tickers = [resolve_ticker_via_search(t) for t in st.session_state.nse_watchlist]

    if not tickers:
        st.error("System Error: Please supply valid asset ticker symbols.")
    else:
        with st.spinner("Compiling quantitative models..."):
            days_map = {"6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
            start_date = (datetime.today() - timedelta(days=days_map.get(time_period, 365))).strftime("%Y-%m-%d")
            end_date = datetime.today().strftime("%Y-%m-%d")

            # Execute cloud-safe fetch
            df_prices = fetch_stock_data(tickers, start_date=start_date, end_date=end_date)

            if df_prices.empty:
                st.error(f"Data pipeline failed. yfinance could not fetch historical data for: {tickers}")
            else:
                method_mapping = "equal" if "Equal-Weight" in strategy_method else "max_sharpe"
                strategy = RebalancingStrategy(tickers, method=method_mapping)
                target_weights = strategy.calculate_weights()

                safe_weights, risk_status, current_dd = check_portfolio_risk(
                    df_prices, target_weights, max_drawdown_limit=max_dd_limit / 100.0
                )

                metrics, equity_curve = run_backtest(df_prices, safe_weights)

                # Save to session state so tabs don't clear on refresh
                st.session_state.quant_results = {
                    "df_prices": df_prices,
                    "safe_weights": safe_weights,
                    "risk_status": risk_status,
                    "current_dd": current_dd,
                    "metrics": metrics,
                    "equity_curve": equity_curve
                }
                st.success("Quantitative models compiled successfully!")

# --- TABS 4-7: QUANTITATIVE DASHBOARD ---
if st.session_state.quant_results:
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
