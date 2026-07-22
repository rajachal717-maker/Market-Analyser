from ddgs import DDGS


def perform_web_search(query: str, max_results: int = 5):
  """Searches the live internet and prints formatted results."""
  print(f"\nSearching the web for: '{query}'...\n")
  try:
    with DDGS() as ddgs:
      results = list(ddgs.text(query, max_results=max_results))
      if not results:
        print("No search results found.")
        return

      for i, r in enumerate(results, 1):
        print(f"[{i}] {r.get('title')}")
        print(f"    Snippet: {r.get('body')}")
        print(f"    Link: {r.get('href')}\n")
  except Exception as e:
    print(f"An error occurred during search: {e}")


if __name__ == "__main__":
  # Interactive search prompt
  user_query = input("Enter what you want to search on the internet: ")
  if user_query.strip():
    perform_web_search(user_query)
  else:
    print("Query cannot be empty.")