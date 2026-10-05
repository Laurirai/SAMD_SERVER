import json
import random
import time

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
DEVICE_ID = "prototype1"
DELAY = 0.05  # seconds between samples; the server counts samples, so this is safe. Use 1 for real time.
PAUSE_SECONDS = 5  # real seconds the device stays paused

# Normal ranges (low, high)
NORMAL = {"hr": (62, 74), "spo2": (96, 99), "temp": (32.5, 33.5)}
LOW_TEMP = (26.0, 27.0)

PAUSE = "pause"  # marker for a pause in the scenario

# (name, seconds, overrides): overrides replace the normal range for the whole segment
SCENARIO = [
    ("calm, baselines settle",    60, {}),
    ("mouth breathing only (1)",  20, {"temp": LOW_TEMP}),
    ("session pause",              0, PAUSE),
    ("mouth breathing only (2)",  20, {"temp": LOW_TEMP}),
    ("calm",                      60, {}),
    ("apnea: low airflow",        65, {"temp": LOW_TEMP}),
    ("apnea: desaturation",       25, {"temp": LOW_TEMP, "spo2": (85, 89)}),
    ("apnea: recovery",           20, {"spo2": (90, 94), "hr": (88, 98)}),
    ("calm",                      60, {}),
    ("long mouth breathing",     240, {"temp": LOW_TEMP}),
    ("calm",                      60, {}),
]


def sample(overrides):
    values = {}
    for key, normal in NORMAL.items():
        low, high = overrides.get(key, normal)
        value = random.uniform(low, high)
        values[key] = round(value, 2) if key == "temp" else round(value)
    return values


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(BROKER, PORT)
client.loop_start()


def status(state, timestamp):
    client.publish("sleep/status", json.dumps(
        {"device_id": DEVICE_ID, "state": state, "timestamp": timestamp}))


status("init", 0)
time.sleep(1)
status("ready", 1000)
time.sleep(2)
status("session", 3000)

device_time = 3000
for name, seconds, overrides in SCENARIO:
    if overrides == PAUSE:
        print(f"--- {name}: paused for {PAUSE_SECONDS} s")
        status("pause", device_time)
        time.sleep(PAUSE_SECONDS)
        device_time += PAUSE_SECONDS * 1000  # the device clock keeps running
        status("session", device_time)
        continue

    print(f"--- {name} ({seconds} samples)")
    for _ in range(seconds):
        payload = {"timestamp": device_time, **sample(overrides), "device_id": DEVICE_ID}
        client.publish("sleep/data", json.dumps(payload))
        device_time += 1000
        time.sleep(DELAY)

status("stop", device_time)
time.sleep(0.5)  # give paho a moment to flush the last message
client.loop_stop()
client.disconnect()