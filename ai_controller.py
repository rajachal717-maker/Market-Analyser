from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_groq import ChatGroq

# Import local modules
from data_loader import fetch_stock_data
from search_tool import get_search_tool
from strategy import calculate_portfolio_weights

load_dotenv()


# Define Tool 1: Stock Data Fetcher
def stock_data_fetcher_func(tickers_str: str) -> str:
  """Fetch historical stock price data for comma-separated tickers."""
  df = fetch_stock_data(tickers_str, period="10y")
  if df.empty:
    return f"Error: No price data found for {tickers_str}."
  return f"Successfully fetched data. Shape: {df.shape}"


# Define Tool 2: Portfolio Optimizer
def portfolio_optimizer_func(tickers_str: str) -> str:
  """Calculate optimal portfolio weights for tickers."""
  weights = calculate_portfolio_weights(tickers_str, method="max_sharpe")
  return f"Calculated Portfolio Weights:\n{weights}"


def run_agent(query: str):
  # Initialize LLM using Groq
  llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, max_retries=2)

  # Collect tools including search
  tools = [stock_data_fetcher_func, portfolio_optimizer_func, get_search_tool()]

  # Create modern agent executor
  agent = create_agent(model=llm, tools=tools)

  print(f"\n> Running Agent Query: {query}\n")
  response = agent.invoke({"messages": [("user", query)]})
  return response


if __name__ == "__main__":
  run_agent(
      "Search the web for recent market trends on AAPL and calculate target"
      " portfolio weights for AAPL and MSFT."
  )
