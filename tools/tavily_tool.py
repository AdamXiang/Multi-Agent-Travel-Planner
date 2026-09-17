"""
tools/tavily_tool.py
======================

Wraps the Tavily search API (https://tavily.com/) so hotel_agent
(agent/nodes.py) can look up hotel recommendations via a general web search,
since there's no dedicated hotel-booking API in this project.
"""

import os

import requests
from dotenv import load_dotenv
from tavily import TavilyClient

# Load environment variables from a .env file
load_dotenv()

# Initialize the Tavily client with the API key from environment variables
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def tavily_search(query: str, limit: int = 5):
    """
    Search for a query using the Tavily API.

    Args:
        query (str): The search query.
        limit (int): The maximum number of results to return.

    Returns:
        list: A list of search results.
    """

    results = []

    try:
        # Perform the search using the Tavily client
        response = client.search(query=query, max_results=limit)

        # Process the response and extract relevant information
        for idx, result in enumerate(response.get("results", []), 1):
            title = result.get("title", "Unknown")
            url = result.get("url", "")
            snippet = result.get("content", "").strip()

            # Only include results with a snippet longer than 300 characters
            if len(snippet) > 300:
                snippet = (
                    snippet[:300].rsplit(" ", 1)[0] + "..."
                )  # Truncate snippet to 300 characters
            results.append(
                f"{idx}. **Title**: {title}\n\n **URL**: {url}\n\n **Snippet**: {snippet}\n"
            )

        return "\n".join(results)
    except requests.exceptions.Timeout as e:
        # Note: this only catches a request *timeout*. The TavilyClient can
        # also raise other exceptions (e.g. authentication errors from a bad
        # or missing TAVILY_API_KEY, or its own SDK-specific errors), which
        # are NOT caught here and would currently propagate up and fail the
        # whole graph run. Worth knowing about if hotel_agent ever crashes
        # instead of gracefully returning an error string like flight_agent
        # does — that's a good next thing to research once you're
        # comfortable with try/except: catching the SDK's actual base
        # exception class (or a plain `except Exception`) here as well.
        print(f"An error occurred while searching: {e}")
        return []
