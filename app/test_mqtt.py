from mqtt import start_mqtt


client = start_mqtt()

input("Press Enter to stop...\n")

client.loop_stop()
client.disconnect()