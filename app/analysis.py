from collections import deque


class Analyzer:
    def __init__(self, window_size=10):
        self.window_size = window_size

        # Recent measurements used for analysis
        self.temperature_history = deque(maxlen=window_size)
        self.spo2_history = deque(maxlen=window_size)
        self.hr_history = deque(maxlen=window_size)
        
        self.added_temp = 0
        self.added_spo2 = 0
        self.added_hr = 0


        # Detected events during the test
        self.events = []

        # Used to keep track of an ongoing possible apnea
        self.apnea_active = False
        self.apnea_start_time = None

    def process(self, data):
        """
        Process one sensor measurement.

        Returns an event if something noteworthy happens,
        otherwise returns None.
        """

        # Store the new measurement
        self.temperature_history.append(data["temp"])
        self.spo2_history.append(data["spo2"])
        self.hr_history.append(data["hr"])

        if len(self.temperature_history) < self.window_size:
            return None

        avg_temp = sum(self.temperature_history) / len(self.temperature_history)

        print(f"Average Temp: {avg_temp}")

        temp_range = max(self.temperature_history) - min(self.temperature_history)

        print(f"Temperature range: {temp_range:.2f} C")

        return None

    def get_events(self):
        """Return all events detected during the test."""
        return self.events