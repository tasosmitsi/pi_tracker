import paho.mqtt.client as mqtt
from paho.mqtt.enums import MQTTProtocolVersion
import fnmatch
from actions import *

# MQTT Broker details
broker = 'tasos61.duckdns.org'
port =  8080 # Default MQTT port
path = '/ws'  # WebSocket path
client_id = 'pi0w'
subscribe_topics = [
    client_id + "/command"
]

qos = 1  # QoS level
retain = False  # Retain flag

def mqtt_ini():
    # Create an MQTT client instance
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=client_id,
                         transport="websockets",
                         protocol=MQTTProtocolVersion.MQTTv5)
    
    # Connect to the MQTT broker using WebSockets
    client.ws_set_options(path=path)  # Set the WebSocket path
    
    # Set the on_message callback function
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_unsubscribe = on_unsubscribe
    client.on_message = on_message

    while True:
        # Start the MQTT client loop in a separate thread
        try:
            client.loop_start()
            break
        except Exception as e:
            print(e)

    while True:
        # Connect to the MQTT broker
        try:
            client.connect(broker, port, 60)
            break
        except Exception as e:
            print(e)

    return client


def post_message(mqtt_client, publish_topic, publish_message):
    try:
        # Publish a message to the topic every 5 seconds
        mqtt_client.publish(client_id + "/" + publish_topic, publish_message, qos=qos, retain=retain)
        # print(f"Published message: {publish_message} to topic: {publish_topic}")
    except Exception as e:
        print(e)

# Callback function for when a message is received
def on_message(client, userdata, msg):
    # do something to filter incoming messages and call the necessary functions
    # Decode the message payload
    message = msg.payload.decode()
    print(f"Received message: {message} from topic: {msg.topic}, with qos: {msg.qos}")
    
    # Filter incoming messages based on the topic
    if msg.topic not in subscribe_topics:
        print(f"Received message: {message} from topic: {msg.topic}, Unknown topic, message ignored.")
        post_message(config.mqtt_client, 'errors', f"Received message: {message} from topic: {msg.topic}, Unknown topic, message ignored.")
        return

    # Filter incoming messages based on the message and topic
    if msg.topic == client_id + "/command" and message == "disarm_alarm":
        disarm_alarm()
    elif msg.topic == client_id + "/command" and message == "arm_alarm":
        arm_alarm()
    # add more else if here
    else:
        print(f"Received message: {message} from topic: {msg.topic}, Unknown command.")
        post_message(config.mqtt_client, 'errors', f"Received message: {message} from topic: {msg.topic}, Unknown command.")
        return

    # post the new alarm state back immediately
    post_message(config.mqtt_client, 'telemetry/alarm_state', config.alarm_state)
    # clear the errors by posting empty string
    post_message(config.mqtt_client, 'errors', f"")
    return

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Failed to connect: {reason_code}. loop_forever() will retry connection")
    else:
        # we should always subscribe from on_connect callback to be sure
        # our subscribed is persisted across reconnections.
        # ------------------------
        while True:
            # Subscribe to debuging topic
            try:
                client.subscribe(client_id + "/command/#")
                break
            except Exception as e:
                print(e)
        # ------------------------
        # for topic in subscribe_topics:
        #     while True:
        #         # Subscribe to the topic
        #         try:
        #             client.subscribe(topic)
        #             break
        #         except Exception as e:
        #             print(e)

def on_subscribe(client, userdata, mid, reason_code_list, properties):
    # Since we subscribed only for a single channel, reason_code_list contains
    # a single entry
    if reason_code_list[0].is_failure:
        print(f"Broker rejected you subscription: {reason_code_list[0]}")
    else:
        print(f"Broker granted the following QoS: {reason_code_list[0].value}")

def on_unsubscribe(client, userdata, mid, reason_code_list, properties):
    # Be careful, the reason_code_list is only present in MQTTv5.
    # In MQTTv3 it will always be empty
    if len(reason_code_list) == 0 or not reason_code_list[0].is_failure:
        print("unsubscribe succeeded (if SUBACK is received in MQTTv3 it success)")
    else:
        print(f"Broker replied with failure: {reason_code_list[0]}")
    # client.disconnect()
