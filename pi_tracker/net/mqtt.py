import fnmatch
import logging
import ssl

import paho.mqtt.client as mqtt
from paho.mqtt.enums import MQTTProtocolVersion

from pi_tracker import alarm, settings
from pi_tracker.actions import arm_alarm, disarm_alarm
from pi_tracker.failure_log import FailureLog

log = logging.getLogger(__name__)

# Broker details, client id, QoS and certificates come from config.yml (see pi_tracker/settings.py)

# Failed and refused connection attempts. paho retries by itself; this keeps the log short.
_connection = FailureLog('MQTT connect', log)

def mqtt_ini():
    cfg = settings.current.mqtt

    # Create an MQTT client instance
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=cfg.client_id,
                         transport="websockets",
                         protocol=MQTTProtocolVersion.MQTTv5)
    
    # Connect to the MQTT broker using WebSockets
    client.ws_set_options(path=cfg.path)  # Set the WebSocket path

    # Set the client's certificate and key for mutual authentication
    client.tls_set(
        ca_certs=cfg.ca_certs,
        certfile=cfg.certfile,
        keyfile=cfg.keyfile,
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    client.tls_insecure_set(False)  # Set to False to verify server certificate
    
    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_disconnect = on_disconnect
    client.on_subscribe = on_subscribe
    client.on_unsubscribe = on_unsubscribe
    client.on_message = on_message

    # Don't wait for the broker. paho connects in its own thread and keeps
    # retrying, waiting longer after each failure, also when a connection drops.
    client.reconnect_delay_set(min_delay=cfg.reconnect_min_s, max_delay=cfg.reconnect_max_s)
    client.connect_async(cfg.host, cfg.port, cfg.keepalive_s)
    client.loop_start()
    return client


def post_message(mqtt_client, publish_topic, publish_message):
    cfg = settings.current.mqtt
    if not mqtt_client.is_connected():
        # Telemetry goes out again on the next tick. Queueing it while offline
        # would only grow memory and send a burst of stale messages later.
        log.debug("Not connected, %s not published", publish_topic)
        return
    try:
        # Publish a message to the topic every 5 seconds
        mqtt_client.publish(cfg.client_id + "/" + publish_topic, publish_message, qos=cfg.qos, retain=cfg.retain)
        # print(f"Published message: {publish_message} to topic: {publish_topic}")
    except Exception as e:
        log.warning("Publishing to %s failed: %s", publish_topic, e)

# Callback function for when a message is received
def on_message(client, userdata, msg):
    client_id = settings.current.mqtt.client_id
    subscribe_topics = [
        client_id + "/command"
    ]

    # do something to filter incoming messages and call the necessary functions
    # Decode the message payload
    message = msg.payload.decode()
    log.info("Received message: %s from topic: %s, with qos: %s", message, msg.topic, msg.qos)
    
    # Filter incoming messages based on the topic
    if msg.topic not in subscribe_topics:
        log.warning("Received message: %s from topic: %s, Unknown topic, message ignored.", message, msg.topic)
        post_message(client,'errors', f"Received message: {message} from topic: {msg.topic}, Unknown topic, message ignored.")
        return

    # Filter incoming messages based on the message and topic
    if msg.topic == client_id + "/command" and message == "disarm_alarm":
        disarm_alarm()
    elif msg.topic == client_id + "/command" and message == "arm_alarm":
        arm_alarm()
    # add more else if here
    else:
        log.warning("Received message: %s from topic: %s, Unknown command.", message, msg.topic)
        post_message(client,'errors', f"Received message: {message} from topic: {msg.topic}, Unknown command.")
        return

    # post the new alarm state back immediately
    post_message(client,'telemetry/alarm_state', alarm.current.state)
    # clear the errors by posting empty string
    post_message(client,'errors', f"")
    return

def on_connect(client, userdata, flags, reason_code, properties):
    cfg = settings.current.mqtt
    if reason_code.is_failure:
        _connection.failed(ConnectionRefusedError("the broker refused: %s" % reason_code))
        return
    _connection.succeeded()
    log.info("Connected to the MQTT broker at %s:%s", cfg.host, cfg.port)

    # Subscribe on every connect, so the subscription is back after a reconnect
    topic = cfg.client_id + "/command/#"
    result, _ = client.subscribe(topic)
    if result != mqtt.MQTT_ERR_SUCCESS:
        log.error("Can't subscribe to %s: %s", topic, mqtt.error_string(result))

def on_connect_fail(client, userdata):
    # paho doesn't say why; it's usually no network, or the broker is down
    cfg = settings.current.mqtt
    _connection.failed(ConnectionError("can't reach %s:%s" % (cfg.host, cfg.port)))

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code.is_failure:
        log.warning("Lost the connection to the MQTT broker (%s), reconnecting", reason_code)
    else:
        log.info("Disconnected from the MQTT broker")

def on_subscribe(client, userdata, mid, reason_code_list, properties):
    # Since we subscribed only for a single channel, reason_code_list contains
    # a single entry
    if reason_code_list[0].is_failure:
        log.error("Broker rejected your subscription: %s", reason_code_list[0])
    else:
        log.info("Broker granted the following QoS: %s", reason_code_list[0].value)

def on_unsubscribe(client, userdata, mid, reason_code_list, properties):
    # Be careful, the reason_code_list is only present in MQTTv5.
    # In MQTTv3 it will always be empty
    if len(reason_code_list) == 0 or not reason_code_list[0].is_failure:
        log.info("unsubscribe succeeded (if SUBACK is received in MQTTv3 it success)")
    else:
        log.error("Broker replied with failure: %s", reason_code_list[0])
    # client.disconnect()
