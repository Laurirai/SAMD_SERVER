import json

import paho.mqtt.client as mqtt
from app.state import session
from app.analysis import Analyzer


BROKER = "localhost"
PORT = 1883
DATA_TOPIC = "sleep/data"
STATUS_TOPIC = "sleep/status"

analyzer = Analyzer()
session.get_events = analyzer.get_events
session.on_reset = analyzer.reset
session.get_summary = analyzer.get_summary

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker with result: {reason_code}")

    client.subscribe(DATA_TOPIC)
    client.subscribe(STATUS_TOPIC)

    print(f"Subscribed to: {DATA_TOPIC}")
    print(f"Subscribed to: {STATUS_TOPIC}")


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"Received invalid JSON or text on topic: {message.topic}")
        return

    if message.topic == DATA_TOPIC:
        reading = session.add_reading(data)
        event = analyzer.process(reading)
        if event:
            print(f"Event: {event}")

    elif message.topic == STATUS_TOPIC:
        print(f"Received device status: {data}")
        session.set_status(data)


def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT)
    client.loop_start()

    return client