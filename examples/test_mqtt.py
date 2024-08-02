import paho.mqtt.client as mqtt
import time

# MQTT Broker details
broker = '192.168.8.233'
port =  80 # Default MQTT port
path = '/ws'  # WebSocket path
subscribe_topic = 'your/subscribe/topic'
publish_topic = 'your/publish/topic'
publish_message = 'Hello, MQTT!'
client_id = 'pi0w'
qos = 1  # QoS level
retain = False  # Retain flag

# Callback function for when a message is received
def on_message(client, userdata, msg):
    print(f"Received message: {msg.payload.decode()} from topic: {msg.topic}")

# Create an MQTT client instance
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                     client_id=client_id,
                     transport="websockets",
                     protocol=mqtt.MQTTv5)

# Set the on_message callback function
client.on_message = on_message

# Connect to the MQTT broker using WebSockets
client.ws_set_options(path=path)  # Set the WebSocket path

# Connect to the MQTT broker
client.connect(broker, port, 60)

# Subscribe to the topic
client.subscribe(subscribe_topic)

# Start the MQTT client loop in a separate thread
client.loop_start()

try:
    while True:
        # Publish a message to the topic every 5 seconds
        client.publish(publish_topic, publish_message, qos=qos, retain=retain)
        print(f"Published message: {publish_message} to topic: {publish_topic}")
        time.sleep(5)
except KeyboardInterrupt:
    print("Interrupted by user")

# Stop the loop and disconnect from the broker
client.loop_stop()
client.disconnect()