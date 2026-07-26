"""
score_manager.py
================
Saves and loads the high score plus the score history to a local JSON file
(`scores.json`, sitting next to main.py).

Everything is wrapped in error handling: if the file is missing, unreadable,
corrupt, or the folder is read-only, the game keeps running with in-memory
scores instead of crashing.
"""

import json
import os
import sys
import tempfile
from datetime import datetime

from settings import SCORES_FILE, HISTORY_KEEP, HISTORY_SHOW

# ---------------------------------------------------------------------------
# Browser support (the WebAssembly build made with pygbag)
# ---------------------------------------------------------------------------
# In a browser there is no real disk: the virtual filesystem is thrown away
# when the tab reloads.  There we keep the scores in localStorage instead, so
# the high score still survives between visits.  On the desktop none of this
# runs and scores.json is used exactly as before.
IS_WEB = (sys.platform == "emscripten")
WEB_STORAGE_KEY = "zombiewar.scores.v1"


def _web_storage():
    """Return the browser's localStorage object, or None when not in a browser."""
    if not IS_WEB:
        return None
    try:
        import platform as _platform            # pygbag injects .window here
        return getattr(_platform, "window").localStorage
    except Exception:
        return None


class ScoreManager:
    """Owns the persistent score data for Zombie War."""

    def __init__(self, path=SCORES_FILE):
        self.path = path
        self.high_score = 0
        self.history = []       # newest run first
        self.games_played = 0
        self.last_error = None  # shown quietly in the corner if saving failed
        self.load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self):
        """Read the saved scores.  Any problem simply resets to empty defaults."""
        try:
            raw = None
            storage = _web_storage()
            if storage is not None:                  # browser build
                raw = storage.getItem(WEB_STORAGE_KEY)
                if raw is None:
                    self._reset()
                    return
                data = json.loads(raw)
            else:                                    # desktop build
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("scores.json must contain a JSON object")

            self.high_score = int(data.get("high_score", 0) or 0)
            self.games_played = int(data.get("games_played", 0) or 0)

            history = data.get("history", [])
            clean = []
            if isinstance(history, list):
                for entry in history:
                    if not isinstance(entry, dict):
                        continue
                    try:
                        clean.append({
                            "score": int(entry.get("score", 0) or 0),
                            "kills": int(entry.get("kills", 0) or 0),
                            "wave": int(entry.get("wave", 1) or 1),
                            "date": str(entry.get("date", "")),
                        })
                    except (TypeError, ValueError):
                        continue        # skip a single bad row, keep the rest
            self.history = clean[:HISTORY_KEEP]

            # Repair the high score if the file disagrees with its own history.
            for entry in self.history:
                self.high_score = max(self.high_score, entry["score"])

        except FileNotFoundError:
            self._reset()                       # first ever launch
        except (json.JSONDecodeError, ValueError, OSError, TypeError) as exc:
            self.last_error = "Could not read scores.json ({}). Starting fresh.".format(
                type(exc).__name__)
            self._reset()

    def _reset(self):
        self.high_score = 0
        self.history = []
        self.games_played = 0

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------
    def save(self):
        """
        Write scores.json atomically (temp file + replace) so a crash or a
        power cut can never leave a half-written, corrupt score file behind.
        """
        data = {
            "high_score": int(self.high_score),
            "games_played": int(self.games_played),
            "history": self.history[:HISTORY_KEEP],
        }

        # Browser build: localStorage instead of a file on disk.
        storage = _web_storage()
        if storage is not None:
            try:
                storage.setItem(WEB_STORAGE_KEY, json.dumps(data))
                self.last_error = None
                return True
            except Exception as exc:
                self.last_error = "Could not save scores ({}).".format(type(exc).__name__)
                return False

        try:
            folder = os.path.dirname(os.path.abspath(self.path)) or "."
            os.makedirs(folder, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix=".scores_", suffix=".tmp", dir=folder)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2)
                # mkstemp creates the file private (0600); make the score file
                # normally readable like any other project file.
                try:
                    os.chmod(tmp_path, 0o644)
                except OSError:
                    pass
                os.replace(tmp_path, self.path)
            except Exception:
                # Clean up the temp file if anything went wrong mid-write.
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError) as exc:
            self.last_error = "Could not save scores ({}).".format(type(exc).__name__)
            return False

    # ------------------------------------------------------------------
    # Recording a finished run
    # ------------------------------------------------------------------
    def record(self, score, kills, wave):
        """
        Add one finished game to the history (newest first) and update the
        high score.  Returns True when this run set a new record.
        """
        try:
            score = int(score)
            kills = int(kills)
            wave = int(wave)
        except (TypeError, ValueError):
            score, kills, wave = 0, 0, 1

        entry = {
            "score": score,
            "kills": kills,
            "wave": wave,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.history.insert(0, entry)                  # newest score at the top
        self.history = self.history[:HISTORY_KEEP]
        self.games_played += 1

        is_record = score > self.high_score
        if is_record:
            self.high_score = score

        self.save()
        return is_record

    # ------------------------------------------------------------------
    # Reading helpers used by the UI
    # ------------------------------------------------------------------
    def recent(self, count=HISTORY_SHOW):
        """The most recent runs, newest first (at most `count` of them)."""
        return self.history[:count]

    def best_entry(self):
        """The single best run ever recorded, or None."""
        if not self.history:
            return None
        return max(self.history, key=lambda e: e["score"])
