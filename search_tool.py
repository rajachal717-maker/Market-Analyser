from ddgs import DDGS
from langchain_core.tools import Tool


def get_search_tool():
  """Initializes a clean native DDGS search tool."""

  def search_func(query: str) -> str:
    try:
      with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
        if not results:
          return f"No search results found for: {query}"
        formatted = f"Search results for '{query}':\n\n"
        for i, r in enumerate(results, 1):
          formatted += (
              f"{i}. Title: {r.get('title')}\n   Snippet: {r.get('body')}\n"
              f"   Link: {r.get('href')}\n\n"
          )
        return formatted
    except Exception as e:
      return f"Search error: {e}"

  return Tool(
      name="web_search",
      func=search_func,
      description=(
          "Use this tool to search the live internet for up-to-date facts,"
          " news, or real-time information."
      ),
  )
