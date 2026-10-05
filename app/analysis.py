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

# Apnea: a mouth breathing episode plus an SpO2 drop (HR rise is recorded)
SPO2_BASELINE_SIZE = 30   # samples in the SpO2 baseline
APNEA_SPO2_DROP = 3.0     # % below baseline that counts as a desaturation
APNEA_SPO2_HOLD = 3       # samples in a row the drop must hold
APNEA_MIN_SECONDS = 60    # low airflow must last this long before apnea can be declared
APNEA_MAX_SECONDS = 180   # no desaturation by now: mouth breathing only
APNEA_HR_RISE = 10.0      # BPM above baseline that is recorded as an HR rise
APNEA_WATCH_SECONDS = 30  # keep watching SpO2 and HR this long after the episode ends

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
        # Mouth breathing
        self.temp_baseline = deque(maxlen=BASELINE_SIZE)
        self.mouth_breathing = False
        self.mouth_breathing_seconds = 0

        # The current low-airflow (mouth breathing) episode
        self.episode_start = None
        self.episode_seconds = 0
        self.episode_min_spo2 = float("inf")
        self.episode_is_apnea = False

        # Nightmare
        self.hr_baseline = deque(maxlen=HR_BASELINE_SIZE)
        self.hr_high = False
        self.hr_high_seconds = 0
        self.hr_high_start = None
        self.hr_event_counted = False

        # Apnea
        self.spo2_baseline = deque(maxlen=SPO2_BASELINE_SIZE)
        self.spo2_low_count = 0       # consecutive samples with a low SpO2
        self.apnea_ruled_out = False  # this episode can no longer become apnea
        self.apnea_event = None       # the event being tracked (episode or follow-up)
        self.apnea_watch_left = 0

        # Overall score
        self.score = SCORE_START
        self.clean_streak = 0

        self.events = []

    def process(self, data):
        """Process one sample (one per second). Returns the overall score (%)."""
        t = data["t"]

        # Detection only counts once all baselines are full (warm-up is over)
        active = (len(self.temp_baseline) >= BASELINE_SIZE
                  and len(self.hr_baseline) >= HR_BASELINE_SIZE
                  and len(self.spo2_baseline) >= SPO2_BASELINE_SIZE)

        self._check_mouth_breathing(data.get("temp"), t)
        self._check_nightmare(data.get("hr"), t)
        self._check_apnea(data.get("spo2"), data.get("hr"))
        return self._update_score(active)

    #Mouth breathing

    def _check_mouth_breathing(self, temp, t):
        if temp is None:  # only before the first valid reading
            return

        # Fill the baseline first, no detection until it is full
        if len(self.temp_baseline) < BASELINE_SIZE:
            self.temp_baseline.append(temp)
            return

        baseline = sum(self.temp_baseline) / len(self.temp_baseline)
        drop = baseline - temp
        was_active = self.mouth_breathing

        if self.mouth_breathing:
            if drop < MB_RECOVER:
                self.mouth_breathing = False
        elif drop >= MB_DROP:
            self.mouth_breathing = True

        if self.mouth_breathing:
            if not was_active:
                self._start_episode(t)
            self.episode_seconds += 1
            if not self.episode_is_apnea:  # apnea seconds are not mouth breathing
                self.mouth_breathing_seconds += 1
        else:
            self.temp_baseline.append(temp)  # only normal samples update the baseline

    def _start_episode(self, t):
        self.episode_start = t
        self.episode_seconds = 0
        self.episode_min_spo2 = float("inf")
        self.episode_is_apnea = False
        self.spo2_low_count = 0
        self.apnea_ruled_out = False
        self.apnea_event = None  # a new episode ends the previous event's follow-up

    #Nightmare

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
                # An HR rise during or just after an apnea event belongs to the apnea
                if self.apnea_event is None:
                    self.events.append({"type": "nightmare", "start_s": self.hr_high_start})
        else:
            self.hr_baseline.append(hr)  # only normal samples update the baseline

    #Apnea 

    def _check_apnea(self, spo2, hr):
        if spo2 is None:  # only before the first valid reading
            return

        # Fill the baseline first, no detection until it is full
        if len(self.spo2_baseline) < SPO2_BASELINE_SIZE:
            self.spo2_baseline.append(spo2)
            return

        spo2_base = sum(self.spo2_baseline) / len(self.spo2_baseline)
        hr_base = sum(self.hr_baseline) / len(self.hr_baseline) if self.hr_baseline else None

        if spo2_base - spo2 >= APNEA_SPO2_DROP:
            self.spo2_low_count += 1
        else:
            self.spo2_low_count = 0

        if self.mouth_breathing:
            self.episode_min_spo2 = min(self.episode_min_spo2, spo2)

            # Decide whether this episode is apnea
            if self.apnea_event is None and not self.apnea_ruled_out:
                if (self.episode_seconds >= APNEA_MIN_SECONDS
                        and self.spo2_low_count >= APNEA_SPO2_HOLD):
                    self._confirm_apnea()
                elif self.episode_seconds >= APNEA_MAX_SECONDS:
                    self.apnea_ruled_out = True  # mouth breathing only

        # While an event is tracked (episode and follow-up): lowest SpO2 and HR rise
        event = self.apnea_event
        if event is not None:
            event["min_spo2"] = min(event["min_spo2"], spo2)
            if hr is not None and hr_base is not None and hr - hr_base >= APNEA_HR_RISE:
                event["hr_rise"] = True

            if not self.mouth_breathing:  # episode over: count down the follow-up
                self.apnea_watch_left -= 1
                if self.apnea_watch_left <= 0:
                    self.apnea_event = None

        # Only normal samples update the baseline
        if not self.mouth_breathing and self.apnea_event is None:
            self.spo2_baseline.append(spo2)

    def _confirm_apnea(self):
        """This episode is apnea: erase the earlier detections that belong to it."""
        self.mouth_breathing_seconds -= self.episode_seconds
        self.episode_is_apnea = True
        self.events = [e for e in self.events
                       if not (e["type"] == "nightmare" and e["start_s"] >= self.episode_start)]

        event = {
            "type": "apnea",
            "start_s": self.episode_start,
            "min_spo2": self.episode_min_spo2,
            "hr_rise": False,
        }
        self.events.append(event)
        self.apnea_event = event
        self.apnea_watch_left = APNEA_WATCH_SECONDS

    #Overall score

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

    # Results

    def get_summary(self):
        """Results that get merged into the session stats."""
        nightmares = [e["start_s"] for e in self.events if e["type"] == "nightmare"]
        apneas = [e for e in self.events if e["type"] == "apnea"]
        return {
            "mouth_breathing_s": self.mouth_breathing_seconds,
            "nightmare_events": len(nightmares),
            "nightmare_time_stamp": nightmares,
            "apnea_events": len(apneas),
            "apnea_time_stamp": [e["start_s"] for e in apneas],
            "apnea_lowest_spo2": [e["min_spo2"] for e in apneas],
            "apnea_hr_rise": [e["hr_rise"] for e in apneas],
        }

    def get_events(self):
        return self.events