import paho.mqtt.client as mqtt

# MQTT Broker details
broker = 'tasos61.duckdns.org'
port =  8080 # Default MQTT port
path = '/ws'  # WebSocket path
subscribe_topic = 'your/subscribe/topic'
publish_topic = 'your/publish/topic'
client_id = 'pi0w'
qos = 1  # QoS level
retain = False  # Retain flag

def mqtt_ini():
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

    return client


def post_message(mqtt_client, publish_topic, publish_message):
    try:
        # Publish a message to the topic every 5 seconds
        mqtt_client.publish(client_id + "/" + publish_topic, publish_message, qos=qos, retain=retain)
        print(f"Published message: {publish_message} to topic: {publish_topic}")
    except KeyboardInterrupt:
        print("Interrupted by user")

# Callback function for when a message is received
def on_message(client, userdata, msg):
    print(f"Received message: {msg.payload.decode()} from topic: {msg.topic}")