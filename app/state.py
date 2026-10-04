from threading import Lock


class SessionState:
    def __init__(self):
        self.lock = Lock()  # MQTT thread writes, web threads read
        self.device_state = "offline"  # offline/init/ready/session/pause/stop
        self.error = None
        self.session_id = 0
        self.readings = []
        self.last_temp = None
        self.last_hr = None
        self.last_spo2 = None

    def _reset_session(self):
        self.session_id += 1
        self.readings = []
        self.start_ts = None
        self.last_hr = None
        self.last_spo2 = None

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
            self.readings.append(reading)
            return {**reading, "timestamp": data["timestamp"]}

    @staticmethod
    def _summary(values):
        values = [v for v in values if v is not None]
        if not values:
            return None
        return {"avg": sum(values) / len(values), "min": min(values), "max": max(values)}

    def snapshot(self, since=0, session_id=None):
        with self.lock:
            # If the browser's session is stale, send everything from the start
            if session_id != self.session_id:
                since = 0

            stats = None
            if self.readings:
                stats = {
                    "duration": self.readings[-1]["t"],
                    "hr": self._summary(r["hr"] for r in self.readings),
                    "spo2": self._summary(r["spo2"] for r in self.readings),
                    "temp": self._summary(r["temp"] for r in self.readings),
                }

            return {
                "device_state": self.device_state,
                "error": self.error,
                "session_id": self.session_id,
                "total": len(self.readings),
                "readings": self.readings[since:],
                "stats": stats,
            }


session = SessionState()