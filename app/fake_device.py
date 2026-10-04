import json
import random
import time

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
DEVICE_ID = "prototype1"
DURATION = 60    # samples of data (one per second)
PAUSE_AT = 15    # pause just before this sample is sent
PAUSE_LENGTH = 5  # seconds


def publish_json(client, topic, payload):
    client.publish(topic, json.dumps(payload))


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(BROKER, PORT)
client.loop_start()

# Device boots, becomes ready, then a session starts
publish_json(client, "sleep/status", {"device_id": DEVICE_ID, "state": "init", "timestamp": 0})
time.sleep(1)
publish_json(client, "sleep/status", {"device_id": DEVICE_ID, "state": "ready", "timestamp": 1000})
time.sleep(2)
publish_json(client, "sleep/status", {"device_id": DEVICE_ID, "state": "session", "timestamp": 3000})

device_time = 3000  # fake device clock in ms; keeps running during the pause

for i in range(DURATION):
    # Pause, send no data, then resume
    if i == PAUSE_AT:
        publish_json(client, "sleep/status", {"device_id": DEVICE_ID, "state": "pause", "timestamp": device_time})
        print("paused")
        time.sleep(PAUSE_LENGTH)
        device_time += PAUSE_LENGTH * 1000
        publish_json(client, "sleep/status", {"device_id": DEVICE_ID, "state": "session", "timestamp": device_time})
        print("resumed")

    hr = random.randint(60, 75)
    spo2 = random.randint(96, 99)
    temp = round(random.uniform(32.5, 33.5), 2)

    # A visible SpO2 dip between 25 s and 35 s, so the graph has some shape
    if 25 <= i < 35:
        spo2 = random.randint(88, 92)

    # Bad readings to test the "use previous value" logic
    if i == 10:
        hr = None
    if i == 20:
        spo2 = 0
    if i == 40:
        temp = None

    publish_json(client, "sleep/data", {
        "timestamp": device_time,
        "hr": hr,
        "spo2": spo2,
        "temp": temp,
        "device_id": DEVICE_ID,
    })

    # Sensor error late in the session
    if i == 45:
        publish_json(client, "sleep/status", {
            "device_id": DEVICE_ID, "state": "error",
            "detail": "ntc,pulse", "timestamp": device_time,
        })

    print(f"sent sample {i}")
    time.sleep(1)
    device_time += 1000

publish_json(client, "sleep/status", {"device_id": DEVICE_ID, "state": "stop", "timestamp": device_time})
time.sleep(0.5)  # give paho a moment to flush the last message
client.loop_stop()
client.disconnect()