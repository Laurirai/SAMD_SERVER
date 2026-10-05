from collections import deque

# --- Tuning constants: adjust after testing with the real device ---
# Mouth breathing (NTC temperature)
BASELINE_SIZE = 10   # samples in the temperature baseline
MB_DROP = 5.0        # °C below baseline that starts mouth breathing
MB_RECOVER = 2.0     # back within this many °C of baseline ends it

# Nightmare (heart rate)
HR_BASELINE_SIZE = 30  # samples in the heart rate baseline
NM_RISE = 15.0         # BPM above baseline that counts as a high heart rate
NM_RECOVER = 5.0       # back within this many BPM of baseline ends the episode
NM_MIN_SECONDS = 5     # must stay high this long to count as an event

# Overall score (%)
SCORE_START = 80.0
SCORE_PENALTY = 0.1        # % lost per second for each active complication
SCORE_GAIN = 1.0           # % gained after a clean stretch
SCORE_CLEAN_SECONDS = 60   # clean seconds in a row needed for one gain


class Analyzer:
    def __init__(self):
        self.reset()

    def reset(self):
        """Clear everything so the next session starts clean."""
        self.temp_baseline = deque(maxlen=BASELINE_SIZE)
        self.mouth_breathing = False
        self.mouth_breathing_seconds = 0

        self.hr_baseline = deque(maxlen=HR_BASELINE_SIZE)
        self.hr_high = False
        self.hr_high_seconds = 0
        self.hr_high_start = None
        self.hr_event_counted = False

        self.score = SCORE_START
        self.clean_streak = 0

        self.events = []

    def process(self, data):
        """Process one sample (one per second). Returns the overall score (%)."""
        # Detection only counts once both baselines are full (warm-up is over)
        active = (len(self.temp_baseline) >= BASELINE_SIZE
                  and len(self.hr_baseline) >= HR_BASELINE_SIZE)

        self._check_mouth_breathing(data.get("temp"))
        self._check_nightmare(data.get("hr"), data["t"])
        return self._update_score(active)

    def _check_mouth_breathing(self, temp):
        if temp is None:  # only before the first valid reading
            return

        # Fill the baseline first, no detection until it is full
        if len(self.temp_baseline) < BASELINE_SIZE:
            self.temp_baseline.append(temp)
            return

        baseline = sum(self.temp_baseline) / len(self.temp_baseline)
        drop = baseline - temp

        if self.mouth_breathing:
            if drop < MB_RECOVER:
                self.mouth_breathing = False
        elif drop >= MB_DROP:
            self.mouth_breathing = True

        if self.mouth_breathing:
            self.mouth_breathing_seconds += 1  # one sample = one second
        else:
            self.temp_baseline.append(temp)  # only normal samples update the baseline

    def _check_nightmare(self, hr, t):
        if hr is None:  # only before the first valid reading
            return

        # Fill the baseline first, no detection until it is full
        if len(self.hr_baseline) < HR_BASELINE_SIZE:
            self.hr_baseline.append(hr)
            return

        baseline = sum(self.hr_baseline) / len(self.hr_baseline)
        rise = hr - baseline

        if self.hr_high:
            if rise < NM_RECOVER:
                self.hr_high = False
        elif rise >= NM_RISE:
            # A new high-HR episode starts
            self.hr_high = True
            self.hr_high_seconds = 0
            self.hr_high_start = t
            self.hr_event_counted = False

        if self.hr_high:
            self.hr_high_seconds += 1
            if self.hr_high_seconds >= NM_MIN_SECONDS and not self.hr_event_counted:
                self.hr_event_counted = True  # one event per episode
                self.events.append({"type": "nightmare", "start_s": self.hr_high_start})
        else:
            self.hr_baseline.append(hr)  # only normal samples update the baseline

    def _update_score(self, active):
        """Update the overall score for this second and return it."""
        if active:
            penalty = 0.0
            if self.mouth_breathing:
                penalty += SCORE_PENALTY
            if self.hr_high and self.hr_event_counted:  # confirmed nightmare only
                penalty += SCORE_PENALTY

            if penalty > 0:
                self.score -= penalty
                self.clean_streak = 0
            else:
                self.clean_streak += 1
                if self.clean_streak >= SCORE_CLEAN_SECONDS:
                    self.score += SCORE_GAIN
                    self.clean_streak = 0

            self.score = max(0.0, min(100.0, self.score))

        return round(self.score, 2)

    def get_summary(self):
        """Results that get merged into the session stats."""
        nightmares = [e["start_s"] for e in self.events if e["type"] == "nightmare"]
        return {
            "mouth_breathing_s": self.mouth_breathing_seconds,
            "nightmare_events": len(nightmares),
            "nightmare_time_stamp": nightmares,
        }

    def get_events(self):
        return self.events