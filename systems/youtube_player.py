"""
systems/youtube_player.py

🎵 YouTube Player — Real Audio Playback
─────────────────────────────────────────
Plays YouTube songs/videos as AUDIO using yt-dlp + VLC/mpv/pygame.
No browser. No search page. Just instant playback.

Install:
    pip install yt-dlp
    pip install python-vlc     ← preferred (uses system VLC)
    OR
    pip install pygame         ← fallback (downloads audio to temp file)

    Also install VLC media player: https://www.videolan.org/vlc/

How it works:
    1. yt-dlp searches YouTube and gets the best audio stream URL
    2. VLC (or mpv) plays the stream directly — no file download needed
    3. If VLC unavailable, downloads to temp file and plays with pygame

Commands (handled by CommandRouter):
    "play [song] on youtube"             → search + play
    "play [song]"                        → play (if Spotify not configured)
    "pause youtube" / "stop youtube"     → pause
    "resume youtube"                     → resume
    "skip youtube" / "next youtube"      → play next search result
    "youtube volume [0-100]"             → set volume
    "what's playing on youtube"          → show current track
    "queue [song] on youtube"            → add to queue
"""

import os
import re
import json
import logging
import threading
import subprocess
import tempfile
import time
from typing import Optional, Callable

logger = logging.getLogger("Makima.YouTubePlayer")

# ── Optional imports ──────────────────────────────────────────────────────────

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    logger.warning("yt-dlp not installed. Run: pip install yt-dlp")

try:
    import vlc as _vlc
    VLC_AVAILABLE = True
except ImportError:
    _vlc = None
    VLC_AVAILABLE = False

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    pygame = None
    PYGAME_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# YouTubePlayer
# ═══════════════════════════════════════════════════════════════════════════════

class YouTubePlayer:
    """
    Search YouTube and play audio directly — no browser needed.
    Falls back gracefully: VLC → mpv (subprocess) → pygame (download)
    """

    def __init__(self, speak_callback: Callable = None):
        self.speak = speak_callback or (lambda t, **kw: None)

        # Playback state
        self._current_track: Optional[dict] = None    # {title, url, stream_url, channel}
        self._queue: list[dict] = []
        self._playing: bool = False
        self._paused: bool = False
        self._volume: int = 70

        # VLC instance
        self._vlc_instance = None
        self._vlc_player = None
        self._mpv_proc: Optional[subprocess.Popen] = None

        self._init_vlc()
        logger.info(f"YouTubePlayer ready. VLC={VLC_AVAILABLE}, yt-dlp={YTDLP_AVAILABLE}")

    # ── Init ──────────────────────────────────────────────────────────────────

    def _init_vlc(self):
        if VLC_AVAILABLE:
            try:
                self._vlc_instance = _vlc.Instance("--no-xlib --quiet")
                self._vlc_player = self._vlc_instance.media_player_new()
                self._vlc_player.audio_set_volume(self._volume)
                logger.info("✅ VLC initialized for YouTube playback")
            except Exception as e:
                logger.warning(f"VLC init failed: {e}")
                self._vlc_instance = None
                self._vlc_player = None

    @property
    def available(self) -> bool:
        return YTDLP_AVAILABLE

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search YouTube and return list of {title, url, duration, channel}."""
        if not YTDLP_AVAILABLE:
            return []

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,   # don't download, just get info
            "default_search": "ytsearch",
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                entries = info.get("entries", [])
                results = []
                for e in entries:
                    if e:
                        results.append({
                            "title":    e.get("title", "Unknown"),
                            "url":      f"https://www.youtube.com/watch?v={e.get('id', '')}",
                            "duration": e.get("duration", 0),
                            "channel":  e.get("channel") or e.get("uploader", ""),
                            "id":       e.get("id", ""),
                        })
                return results
        except Exception as e:
            logger.warning(f"YouTube search failed: {e}")
            return []

    def _get_stream_url(self, video_url: str) -> Optional[str]:
        """Get the best audio-only stream URL for a YouTube video."""
        if not YTDLP_AVAILABLE:
            return None

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                # Try to get direct audio URL
                if "url" in info:
                    return info["url"]
                # From formats, pick best audio
                formats = info.get("formats", [])
                audio_fmts = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
                if not audio_fmts:
                    audio_fmts = formats
                if audio_fmts:
                    best = max(audio_fmts, key=lambda f: f.get("abr") or f.get("tbr") or 0)
                    return best.get("url")
        except Exception as e:
            logger.warning(f"Stream URL extraction failed: {e}")
        return None

    # ── Playback ──────────────────────────────────────────────────────────────

    def play(self, query: str) -> str:
        """Search for query and play the top result."""
        if not YTDLP_AVAILABLE:
            return (
                "yt-dlp is not installed. Run:\n"
                "  pip install yt-dlp\n"
                "Then restart Makima."
            )

        results = self.search(query, max_results=3)
        if not results:
            return f"Couldn't find '{query}' on YouTube. Try a different search?"

        track = results[0]
        # Save rest as queue
        self._queue = results[1:]

        return self._play_track(track)

    def _play_track(self, track: dict) -> str:
        """Get stream URL and start playback."""
        title = track["title"]
        url   = track["url"]

        logger.info(f"Getting stream for: {title}")
        stream_url = self._get_stream_url(url)

        if not stream_url:
            return f"Couldn't get audio stream for '{title}'. Trying next..."

        track["stream_url"] = stream_url
        self._current_track = track

        # Try VLC first
        if self._vlc_player:
            return self._play_vlc(stream_url, track)

        # Try mpv (if installed)
        if self._mpv_available():
            return self._play_mpv(stream_url, track)

        # Last resort: download to temp file + pygame
        if PYGAME_AVAILABLE:
            threading.Thread(
                target=self._play_pygame_download, args=(url, track), daemon=True
            ).start()
            return f"🎵 Downloading and playing: {title}"

        return (
            "No audio player available. Install one:\n"
            "  pip install python-vlc   (+ VLC app from videolan.org)\n"
            "  OR: pip install pygame"
        )

    def _play_vlc(self, stream_url: str, track: dict) -> str:
        try:
            # Stop current
            self._vlc_player.stop()
            media = self._vlc_instance.media_new(stream_url)
            self._vlc_player.set_media(media)
            self._vlc_player.audio_set_volume(self._volume)
            self._vlc_player.play()
            self._playing = True
            self._paused = False
            dur = self._fmt_duration(track.get("duration", 0))
            ch  = track.get("channel", "")
            return f"🎵 Playing: {track['title']}" + (f" — {ch}" if ch else "") + (f" [{dur}]" if dur else "")
        except Exception as e:
            logger.warning(f"VLC playback error: {e}")
            return f"VLC error: {e}"

    def _play_mpv(self, stream_url: str, track: dict) -> str:
        try:
            if self._mpv_proc and self._mpv_proc.poll() is None:
                self._mpv_proc.terminate()
            self._mpv_proc = subprocess.Popen(
                ["mpv", "--no-video", "--volume=" + str(self._volume), stream_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self._playing = True
            self._paused = False
            return f"🎵 Playing via mpv: {track['title']}"
        except Exception as e:
            return f"mpv error: {e}"

    def _play_pygame_download(self, url: str, track: dict):
        """Last resort: download audio to temp file and play with pygame."""
        try:
            ydl_opts = {
                "quiet": True,
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tempfile.gettempdir(), "makima_yt_%(id)s.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "noplaylist": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # May have been converted to .mp3
                mp3 = os.path.splitext(filename)[0] + ".mp3"
                target = mp3 if os.path.exists(mp3) else filename

            pygame.mixer.init()
            pygame.mixer.music.load(target)
            pygame.mixer.music.set_volume(self._volume / 100.0)
            pygame.mixer.music.play()
            self._playing = True
            self._paused = False
            self.speak(f"Playing {track['title']}")
        except Exception as e:
            logger.error(f"pygame download/play failed: {e}")
            self.speak("Sorry, I couldn't play that song.")

    # ── Controls ──────────────────────────────────────────────────────────────

    def pause(self) -> str:
        if not self._playing:
            return "Nothing is playing on YouTube."
        if self._vlc_player:
            try:
                self._vlc_player.pause()
                self._paused = not self._paused
                return "⏸ Paused." if self._paused else "▶ Resumed."
            except Exception as e:
                return f"Pause error: {e}"
        if self._mpv_proc:
            return "Use 'resume youtube' to control mpv playback."
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.pause()
            self._paused = True
            return "⏸ Paused."
        return "Nothing to pause."

    def resume(self) -> str:
        if self._vlc_player and self._paused:
            try:
                self._vlc_player.pause()   # VLC pause toggles
                self._paused = False
                return "▶ Resumed."
            except Exception as e:
                return f"Resume error: {e}"
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.unpause()
            self._paused = False
            return "▶ Resumed."
        return "Nothing to resume."

    def stop(self) -> str:
        if self._vlc_player:
            try:
                self._vlc_player.stop()
            except Exception:
                pass
        if self._mpv_proc and self._mpv_proc.poll() is None:
            self._mpv_proc.terminate()
            self._mpv_proc = None
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.stop()
        self._playing = False
        self._paused = False
        self._current_track = None
        return "⏹ Stopped."

    def skip(self) -> str:
        """Play next item in queue."""
        if not self._queue:
            return "Queue is empty. Tell me what to play next!"
        next_track = self._queue.pop(0)
        return self._play_track(next_track)

    def queue(self, query: str) -> str:
        """Add a song to the queue."""
        results = self.search(query, max_results=1)
        if not results:
            return f"Couldn't find '{query}'."
        self._queue.append(results[0])
        return f"📋 Queued: {results[0]['title']}"

    def set_volume(self, vol: int) -> str:
        vol = max(0, min(100, vol))
        self._volume = vol
        if self._vlc_player:
            try:
                self._vlc_player.audio_set_volume(vol)
            except Exception:
                pass
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.set_volume(vol / 100.0)
        return f"🔊 YouTube volume: {vol}%"

    def now_playing(self) -> str:
        if not self._current_track:
            return "Nothing is playing on YouTube right now."
        t = self._current_track
        state = " (paused)" if self._paused else ""
        ch    = f" — {t['channel']}" if t.get("channel") else ""
        dur   = f" [{self._fmt_duration(t.get('duration', 0))}]" if t.get("duration") else ""
        queued = f"\n📋 {len(self._queue)} tracks queued" if self._queue else ""
        return f"🎵 {t['title']}{ch}{dur}{state}{queued}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_duration(secs: int) -> str:
        if not secs:
            return ""
        m, s = divmod(int(secs), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @staticmethod
    def _mpv_available() -> bool:
        try:
            subprocess.run(["mpv", "--version"], capture_output=True, timeout=2)
            return True
        except Exception:
            return False


# ── Module-level singleton ────────────────────────────────────────────────────

_player: Optional[YouTubePlayer] = None

def get_youtube_player(speak_callback=None) -> YouTubePlayer:
    global _player
    if _player is None:
        _player = YouTubePlayer(speak_callback=speak_callback)
    return _player
