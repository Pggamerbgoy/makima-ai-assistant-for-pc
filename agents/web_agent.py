"""
agents/web_agent.py
Web search and page fetching for Makima.
"""

import logging
import webbrowser

logger = logging.getLogger("Makima.WebAgent")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


class WebAgent:

    SEARCH_URL = "https://www.google.com/search?q="
    DDGS_URL = "https://api.duckduckgo.com/"

    def __init__(self, ai):
        self.ai = ai

    def search(self, query: str) -> str:
        """Try DuckDuckGo instant answers first, then open browser as fallback."""
        if REQUESTS_AVAILABLE:
            try:
                resp = requests.get(
                    self.DDGS_URL,
                    params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
                    timeout=5,
                    headers={"User-Agent": "Makima-Assistant/1.0"},
                )
                data = resp.json()
                abstract = data.get("AbstractText", "")
                answer = data.get("Answer", "")
                result = abstract or answer
                if result:
                    return f"Here's what I found: {result[:300]}"
            except Exception as e:
                logger.warning(f"DuckDuckGo search failed: {e}")

        # Fallback: open browser
        url = self.SEARCH_URL + query.replace(" ", "+")
        webbrowser.open(url)
        return f"Opened Google search for '{query}' in your browser."

    def open_url(self, url: str) -> str:
        webbrowser.open(url)
        return f"Opened {url}."

    def fetch_summary(self, url: str) -> str:
        """Fetch a page and summarize it with AI."""
        if not REQUESTS_AVAILABLE or not BS4_AVAILABLE:
            return "requests/beautifulsoup4 not installed. Can't fetch pages."
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            # Get main text content
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text() for p in paragraphs[:10])
            text = text[:2000]

            prompt = (
                "Summarize the following web page content in 3 concise sentences. "
                "Focus on the main ideas only.\n\n"
                f"{text}"
            )

            # Prefer a plain-text generation API when available (AIHandler)
            if hasattr(self.ai, "generate_response"):
                try:
                    return self.ai.generate_response(
                        system_prompt="You are a summarization assistant.",
                        user_message=prompt,
                        temperature=0.2,
                    )
                except Exception:
                    pass

            result = self.ai.chat(prompt)
            # AIHandler.chat → (reply, emotion); legacy backends may return str
            if isinstance(result, tuple) and len(result) >= 1:
                return result[0]
            return str(result)
        except Exception as e:
            return f"Couldn't fetch that page: {e}"
