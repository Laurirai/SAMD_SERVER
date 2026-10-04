import json
import random


SESSION_LENGTH = 180
APNEA_START = 100
APNEA_END = 115


def generate_test_data():
    data = []

    for timestamp in range(SESSION_LENGTH):

        # Normal baseline
        hr = 72 + random.randint(-3, 3)
        spo2 = 98 + random.choice([-1, 0, 0, 0, 1])

        # Normal breathing:
        # temperature moves up and down noticeably
        temp = 30.5 + random.uniform(-0.8, 0.8)

        # Possible apnea
        if APNEA_START <= timestamp < APNEA_END:
            # Much less temperature variation
            temp = 30.5 + random.uniform(-0.15, 0.15)

        # SpO2 starts reacting
        if 115 <= timestamp < 125:
            drop = (timestamp - 115) * 0.3
            spo2 = 98 - drop

        # HR starts rising
        if 120 <= timestamp < 130:
            rise = (timestamp - 120) * 1.5
            hr = 72 + rise


        # Recovery

        if 125 <= timestamp < 140:
            recovery = (timestamp - 125) * 0.2
            spo2 = 95 + recovery

        if 130 <= timestamp < 145:
            recovery = (timestamp - 130) * 0.8
            hr = 87 - recovery


        # Simulate occasional
        # invalid sensor readings

        if timestamp == 47:
            hr = None

        if timestamp == 83:
            spo2 = 0

        if timestamp == 151:
            temp = None

        # Create device-style packet
        packet = {
            "timestamp": timestamp,
            "hr": round(hr, 1) if hr is not None else None,
            "spo2": round(spo2, 1) if spo2 is not None else None,
            "temp": round(temp, 2) if temp is not None else None,
            "device_id": "prototype1"
        }

        data.append(packet)

    return data


if __name__ == "__main__":
    test_data = generate_test_data()

    with open("test_session.json", "w") as file:
        json.dump(test_data, file, indent=4)

    print(f"Generated {len(test_data)} samples.")
    print("Saved to test_session.json")