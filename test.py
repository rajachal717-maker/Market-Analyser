import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

class Portfolio:
    def __init__(self, initial_cash, assets_weights):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.holdings = {asset: 0 for asset in assets_weights}
        self.weights = assets_weights
        self.portfolio_value = initial_cash

    def update_holdings(self, prices):
        asset_value = sum(self.holdings[asset] * prices[asset] for asset in self.holdings)
        self.portfolio_value = self.cash + asset_value
        return self.portfolio_value

class RebalancingEngine:
    def __init__(self, portfolio):
        self.portfolio = portfolio

    def calculate_rebalance(self, prices):
        total_value = self.portfolio.update_holdings(prices)
        orders = {}
        for asset, target_weight in self.portfolio.weights.items():
            target_value = total_value * target_weight
            current_value = self.portfolio.holdings[asset] * prices[asset]
            shares_to_trade = (target_value - current_value) / prices[asset]
            orders[asset] = int(shares_to_trade)  # Rounding to whole shares
        return orders

class Backtester:
    def __init__(self, data, portfolio, engine, fee=0.001, slippage=0.0005):
        self.data = data
        self.portfolio = portfolio
        self.engine = engine
        self.fee = fee
        self.slippage = slippage
        self.history = []

    def run(self):
        for date, row in self.data.iterrows():
            prices = row.to_dict()
            self.portfolio.update_holdings(prices)
            orders = self.engine.calculate_rebalance(prices)
            
            for asset, shares in orders.items():
                execution_price = prices[asset] * (1 + (self.slippage if shares > 0 else -self.slippage))
                trade_cost = shares * execution_price
                commission = abs(trade_cost) * self.fee
                
                if self.portfolio.cash >= (trade_cost + commission):
                    self.portfolio.holdings[asset] += shares
                    self.portfolio.cash -= (trade_cost + commission)
            
            self.history.append({'date': date, 'total_value': self.portfolio.portfolio_value})
        return pd.DataFrame(self.history).set_index('date')

# --- Execution Setup ---
# 1. Mock Data
dates = pd.date_range('2026-01-01', periods=100)
data = pd.DataFrame({
    'AAPL': np.random.normal(150, 2, 100).cumsum(),
    'MSFT': np.random.normal(300, 5, 100).cumsum()
}, index=dates)

# 2. Initialize Components
portfolio = Portfolio(100000, {'AAPL': 0.5, 'MSFT': 0.5})
engine = RebalancingEngine(portfolio)
backtester = Backtester(data, portfolio, engine)

# 3. Run
results = backtester.run()

# 4. Metrics
returns = results['total_value'].pct_change().dropna()
sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
print(f"Backtest Complete. Sharpe Ratio: {sharpe:.2f}")

# 5. Plotting
results.plot()
plt.title("Portfolio Equity Curve")
plt.show()