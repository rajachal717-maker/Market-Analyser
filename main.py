from data_loader import fetch_stock_data
from strategy import RebalancingStrategy

def run_backtest():
    # Updated to match your active Indian equities and watchlists
    tickers = ['VMART', 'NOCIL', 'RELIANCE', 'TCS']
    
    # 1. Load Data using fetch_stock_data (matching app.py)
    data = fetch_stock_data(tickers, start_date='2026-01-01', end_date='2026-07-28')
    
    if data.empty:
        print("❌ Failed to fetch data. Check your tickers or network connection.")
        return

    # 2. Initialize Strategy with our tickers
    strategy = RebalancingStrategy(tickers)
    
    # 3. Calculate target weights
    target_weights = strategy.calculate_weights()
    
    print("-" * 30)
    print("Portfolio Allocation Target Matrix:")
    for ticker, weight in target_weights.items():
        print(f"{ticker}: {weight:.2%}")
    print("-" * 30)

if __name__ == "__main__":
    run_backtest()
