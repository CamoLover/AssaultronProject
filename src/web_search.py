"""
Shared web search utility (Brave Search API).

Used both by the autonomous agent (as a tool) and by the conversational layer
for quick, inline "search-and-answer" replies without launching the agent.
"""

import os
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger('assaultron.web_search')


def web_search(query: str, count: int = 5) -> Dict[str, Any]:
    """
    Perform a web search using the Brave Search API.

    Args:
        query: Search query
        count: Max number of results to return

    Returns:
        Dict with a success flag and either 'results' (list of
        {title, url, description}) or an 'error' message. 'results' is always
        present (possibly empty) so callers can treat it uniformly.
    """
    try:
        api_key = os.getenv("BRAVE_BROWSER_API_KEY", "")
        if not api_key or "YOUR_API_KEY" in api_key:
            return {"success": False, "error": "Brave Search API key not configured", "results": []}

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        params = {"q": query, "count": count}

        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get("web", {}).get("results", [])[:count]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", "")
                })
            logger.info(f"Web search completed: {len(results)} results for '{query}'")
            return {"success": True, "query": query, "results": results, "count": len(results)}
        else:
            return {"success": False, "error": f"Search API returned {response.status_code}", "results": []}
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {"success": False, "error": str(e), "results": []}
