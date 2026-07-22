from data_loader import get_stock_data
from strategy import RebalancingStrategy

def run_backtest():
    tickers = ['AAPL', 'MSFT', 'GOOGL']
    
    # 1. Load Data
    data = get_stock_data(tickers, '2026-01-01', '2026-07-16')
    
    # 2. Initialize Strategy with our tickers
    strategy = RebalancingStrategy(tickers)
    
    # 3. Calculate target weights
    target_weights = strategy.calculate_weights()
    
    print("-" * 30)
    print("Equal Weight Target Portfolio:")
    for ticker, weight in target_weights.items():
        print(f"{ticker}: {weight:.2%}")
    print("-" * 30)

if __name__ == "__main__":
    run_backtest()

  