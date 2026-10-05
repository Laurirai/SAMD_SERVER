from collections import deque

# --- Tuning constants: adjust after testing with the real device ---
BASELINE_SIZE = 10   # samples in the temperature baseline
MB_DROP = 5.0        # °C below baseline that starts mouth breathing
MB_RECOVER = 2.0     # back within this many °C of baseline ends it


class Analyzer:
    def __init__(self):
        self.reset()

    def reset(self):
        """Clear everything so the next session starts clean."""
        self.temp_baseline = deque(maxlen=BASELINE_SIZE)
        self.mouth_breathing = False
        self.mouth_breathing_seconds = 0
        self.events = []

    def process(self, data):
        """Process one sample (one per second)."""
        temp = data.get("temp")
        if temp is None:  # only before the first valid reading
            return None

        # Fill the baseline first, no detection until it is full
        if len(self.temp_baseline) < BASELINE_SIZE:
            self.temp_baseline.append(temp)
            return None

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

        return None

    def get_summary(self):
        """Results that get merged into the session stats."""
        return {"mouth_breathing_s": self.mouth_breathing_seconds}

    def get_events(self):
        return self.events