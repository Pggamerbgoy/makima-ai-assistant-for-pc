"""
systems/web_music.py
Browser-based music playback for YouTube and Spotify Web.
"""

import webbrowser
import logging
import urllib.parse

logger = logging.getLogger("Makima.WebMusic")

class WebMusic:
    """Handles opening music links in the default browser."""

    YOUTUBE_SEARCH = "https://www.youtube.com/results?search_query="
    SPOTIFY_WEB_SEARCH = "https://open.spotify.com/search/"

    def play_youtube(self, query: str) -> str:
        """Search and play a song on YouTube."""
        if not query:
            return "What would you like to play on YouTube?"
        
        encoded_query = urllib.parse.quote(query)
        url = f"{self.YOUTUBE_SEARCH}{encoded_query}"
        webbrowser.open(url)
        return f"Opening '{query}' on YouTube."

    def play_web_spotify(self, query: str) -> str:
        """Search and play a song on Spotify Web."""
        if not query:
            return "What would you like to play on Spotify Web?"
        
        encoded_query = urllib.parse.quote(query)
        url = f"{self.SPOTIFY_WEB_SEARCH}{encoded_query}"
        webbrowser.open(url)
        return f"Opening '{query}' on Spotify Web."

    def play_any(self, query: str) -> str:
        """Default to YouTube if platform not specified."""
        return self.play_youtube(query)
