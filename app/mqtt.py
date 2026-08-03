import json
import paho.mqtt.client as mqtt
from analysis import Analyzer


BROKER = "localhost"
PORT = 1883
TOPIC = "sleep/data"

analyzer = Analyzer()

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker with result: {reason_code}")
    client.subscribe(TOPIC)
    print(f"Subscribed to: {TOPIC}")


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode())
        print(f"Received: {data}")

        event = analyzer.process(data)

        if event:
            print(f"Event: {event}")

    except json.JSONDecodeError:
        print("Received invalid JSON")


def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT)

    client.loop_start()

    return client