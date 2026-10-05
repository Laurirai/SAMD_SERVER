import json
from datetime import datetime
from pathlib import Path
from threading import Lock, Timer

# <project root>/sessions, next to the app folder
SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"
RESET_DELAY = 30  # seconds after "stop" before the session data is cleared


class SessionState:
    def __init__(self):
        self.lock = Lock()  # MQTT thread writes, web threads read
        self.device_state = "offline"  # offline/init/ready/session/pause/stop/idle
        self.error = None
        self.session_id = 0
        self.readings = []
        self.last_hr = None
        self.last_spo2 = None
        self.last_temp = None
        self.saved = False  # has the current session been written to disk?
        self.reset_timer = None

        # Set from mqtt.py so this file doesn't need to import the analyzer
        self.analyze = lambda reading: None
        self.get_events = lambda: []
        self.get_summary = lambda: {}
        self.on_reset = lambda: None

    def _reset_session(self):
        """Start a clean session. Caller must hold the lock."""
        self._save_session()  # never lose data that wasn't saved yet

        if self.reset_timer is not None:
            self.reset_timer.cancel()
            self.reset_timer = None

        self.session_id += 1
        self.error = None
        self.readings = []
        self.last_hr = None
        self.last_spo2 = None
        self.last_temp = None
        self.saved = False
        self.on_reset()  # resets the analyzer

    def _timed_reset(self, session_id):
        """Runs on the timer thread, RESET_DELAY seconds after a stop."""
        with self.lock:
            # If the id changed, a new session started and this timer is outdated
            if self.session_id == session_id:
                self._reset_session()
                if self.device_state == "stop":
                    self.device_state = "idle"  # online, but no state box ticked

    def _save_session(self):
        """Write the current session to sessions/session_NNN.json. Caller must hold the lock."""
        if not self.readings or self.saved:
            return
        try:
            SESSIONS_DIR.mkdir(exist_ok=True)
            numbers = [int(p.stem.split("_")[1]) for p in SESSIONS_DIR.glob("session_*.json")]
            number = max(numbers, default=0) + 1

            data = {
                "session": number,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "stats": self._stats(),
            }
            path = SESSIONS_DIR / f"session_{number:03d}.json"
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.saved = True
            print(f"Saved Session {number} to {path}")
        except Exception as e:
            print(f"Could not save session: {e}")

    def set_status(self, status):
        with self.lock:
            new = status.get("state")

            if new == "error":
                # Keep the current state, just remember the detail
                self.error = status.get("detail")
                return

            # A "session" message after a pause is a resume, not a new session
            if new == "session" and self.device_state != "pause":
                self._reset_session()

            if new in ("init", "ready", "session"):
                self.error = None

            # Session ended: save it and schedule the clear-out
            if new == "stop" and self.device_state in ("session", "pause"):
                self._save_session()
                self.reset_timer = Timer(RESET_DELAY, self._timed_reset, args=(self.session_id,))
                self.reset_timer.daemon = True  # don't block server shutdown
                self.reset_timer.start()

            self.device_state = new

    def add_reading(self, data):
        """Fill in bad values and store the reading. Returns the cleaned dict."""
        with self.lock:
            hr = data.get("hr") or self.last_hr
            spo2 = data.get("spo2") or self.last_spo2
            temp = data.get("temp") or self.last_temp
            self.last_hr, self.last_spo2, self.last_temp = hr, spo2, temp

            reading = {
                "t": len(self.readings),  # seconds since session start
                "hr": hr,
                "spo2": spo2,
                "temp": temp,
            }
            # Analyze before the reading becomes visible, so it always has its score
            reading["score"] = self.analyze(reading)
            self.readings.append(reading)
            return {**reading, "timestamp": data["timestamp"]}

    @staticmethod
    def _summary(values):
        values = [v for v in values if v is not None]
        if not values:
            return None
        return {"avg": sum(values) / len(values), "min": min(values), "max": max(values)}

    def _stats(self):
        """Caller must hold the lock."""
        if not self.readings:
            return None

        stats = {
            "duration": self.readings[-1]["t"],
            "hr": self._summary(r["hr"] for r in self.readings),
            "spo2": self._summary(r["spo2"] for r in self.readings),
            "temp": self._summary(r["temp"] for r in self.readings),
        }
        stats.update(self.get_summary())
        return stats

    def snapshot(self, since=0, session_id=None):
        with self.lock:
            # If the browser's session is stale, send everything from the start
            if session_id != self.session_id:
                since = 0

            return {
                "device_state": self.device_state,
                "error": self.error,
                "session_id": self.session_id,
                "total": len(self.readings),
                "readings": self.readings[since:],
                "stats": self._stats(),
            }


session = SessionState()