import sys
import time
import json
import dbus
import yaml
import threading

from Thread import StoppableRestartableThread

import paho.mqtt.client as mqtt

from pijuice import PiJuice # Import pijuice module

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import gi
gi.require_version('ModemManager', '1.0')
from gi.repository import Gio, GLib, GObject, ModemManager

# MQTT Broker details
broker = 'tasos61.duckdns.org'
port =  8080 # Default MQTT port
path = '/ws'  # WebSocket path
subscribe_topic = 'your/subscribe/topic'
publish_topic = 'your/publish/topic'
publish_message = 'Hello, MQTT!'
client_id = 'pi0w'
qos = 1  # QoS level
retain = False  # Retain flag

def init_pijuice():
    pijuice = PiJuice(1, 0x14) # Instantiate PiJuice interface object
    return pijuice

# Callback function for when a message is received
def on_message(client, userdata, msg):
    print(f"Received message: {msg.payload.decode()} from topic: {msg.topic}")
    
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

def modem_init():
    global manager
    # Connection to ModemManager    
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    manager = ModemManager.Manager.new_sync(
    connection, Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START, None)
    
    if not manager.get_name_owner():
        sys.stderr.write('ModemManager not found in bus\n')
        sys.exit(2)
        
    # find the modem by name or iterate
    obj =  manager.get_object('/org/freedesktop/ModemManager1/Modem/0')
    #	test = manager.get_interfaces()
    #	print(test)

    modem = obj.get_modem()
    modem_location = obj.get_modem_location()
    
    modem_state = modem.get_state()
    if modem_state == ModemManager.ModemState.ENABLED:
        sys.stdout.write('Modem enabled\n')
    
    elif modem_state == ModemManager.ModemState.CONNECTED:
        sys.stdout.write('Modem connected\n')

    return modem, modem_location


def start_gps_all(modem_location):
    # trying to start gps
    supported_sources = modem_location.get_capabilities()
    # print(supported_sources)

    desired_sources = 0
    if supported_sources & ModemManager.ModemLocationSource(1):
        desired_sources |= ModemManager.ModemLocationSource(1) 
    if supported_sources & ModemManager.ModemLocationSource.GPS_NMEA:
        desired_sources |= ModemManager.ModemLocationSource.GPS_NMEA
    if supported_sources & ModemManager.ModemLocationSource.AGPS_MSB:
        desired_sources |= ModemManager.ModemLocationSource.AGPS_MSB

    # Check if we have any desired sources
    if not desired_sources:
        print("None of the desired location sources are supported by the modem")
        return

    return modem_location.setup_sync(ModemManager.ModemLocationSource(desired_sources), False, None)

def stop_gps_all(modem_location):
    supported_sources = modem_location.get_capabilities()
    desired_sources = 0
    
    if supported_sources & ModemManager.ModemLocationSource(0):
            desired_sources |= ModemManager.ModemLocationSource(0)
    
    return modem_location.setup_sync(ModemManager.ModemLocationSource(desired_sources), False, None)

def read_config_file():
    # Path to the YAML file
    yaml_file_path = 'config.yml'
    
    # Reading the YAML file
    while True:
        try:
            with open(yaml_file_path, 'r') as file:
                config = yaml.safe_load(file)
                print("YAML content:")
                print(config)
        except FileNotFoundError:
            print(f"The file {yaml_file_path} does not exist.")
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            
        time.sleep(2)

def read_alarm_state():
    # do smomething
    while True:
        pass

def test():
    while True:
        print("xaxaxaxaa")
        time.sleep(1)

def get_modem_stats(modem):
    stats = {}
    while True:
        stats['signal_quality'] = modem.get_signal_quality()[0]
        stats['signal_recent'] = modem.get_signal_quality()[1]
        stats['primary_port'] = modem.get_primary_port()
        stats['power_state'] = ModemManager.ModemPowerState.get_string(modem.get_power_state())
        stats['current_modes'] = modem.get_current_modes() # expand this in the future

        # do something with these values: e.g.: send them to mqtt broker and or check them
        # localy and act accordingly
        print(stats)
        
        time.sleep(5)

def post_message(mqtt_client, publish_topic, publish_message):
    try:
        # Publish a message to the topic every 5 seconds
        mqtt_client.publish(publish_topic, publish_message, qos=qos, retain=retain)
        print(f"Published message: {publish_message} to topic: {publish_topic}")
    except KeyboardInterrupt:
        print("Interrupted by user")
    
    # Stop the loop and disconnect from the broker
def get_modem_stats_sync(modem):
    stats = {}
    stats['signal_quality'] = modem.get_signal_quality()[0]
    stats['signal_recent'] = modem.get_signal_quality()[1]
    stats['primary_port'] = modem.get_primary_port()
    stats['power_state'] = ModemManager.ModemPowerState.get_string(modem.get_power_state())
    stats['current_modes'] = f"Initial Current Modes: {modem.get_current_modes()}"

    # do something with these values: e.g.: send them to mqtt broker and or check them
    # localy and act accordingly
    return stats

def post_battery(mqtt_client, pijuice, delay, stop_event):
    while not stop_event.is_set():
        publish_message = json.dumps(pijuice.status.GetChargeLevel())
        post_message(mqtt_client, 'battery/level', publish_message)
        time.sleep(delay)

def post_modem(mqtt_client, modem, delay, stop_event):
    while not stop_event.is_set():
        publish_message = json.dumps(get_modem_stats_sync(modem))
        post_message(mqtt_client, 'modem/stats', publish_message)
        time.sleep(delay)

def print_btn(pijuice, delay, stop_event):
    while not stop_event.is_set():
        btn_events = pijuice.status.GetButtonEvents()

        if btn_events['error'] != 'NO_ERROR':
            print("Button events reported:" + btn_events['error'])

        if 'data' in btn_events:
            if btn_events['data']['SW1'] == 'SINGLE_PRESS':
                print(btn_events)
                pijuice.status.AcceptButtonEvent('SW1')
                print(pijuice.status.GetButtonEvents())
        time.sleep(delay)
        
def main():
    modem, modem_location = modem_init()
    pijuice = init_pijuice()
    mqtt_client = mqtt_ini()

    thread_post_modem = StoppableRestartableThread(target=post_modem, args=(mqtt_client, modem), kwargs={'delay': 40}).start()    
    thread_post_battery = StoppableRestartableThread(target=post_battery, args=(mqtt_client, pijuice), kwargs={'delay': 40}).start()    
    thread_print_btn = StoppableRestartableThread(target=print_btn, args=(pijuice, ), kwargs={'delay': 2}).start()

    
    # Start the GLib main loop
    loop = GLib.MainLoop()
    loop.run()



    # thread_post_modem.stop()
    # thread_post_battery.stop()
    # thread_print_btn.stop()
    # mqtt_client.loop_stop()
    # mqtt_client.disconnect()    

    
    
    # print("Starting GPS all...")
    # print(start_gps_all(modem_location))

    # print("Stoping GPS all...")
    # print(stop_gps_all(modem_location))

    # res = modem.command_sync("AT+CFUN?", 10, None)
    # print(res)

    # res = modem.command_sync("AT+CGPS?", 10, None)
    # print(res)

    # trying to disable the modem
    # print(modem.disable_sync(None))
    
    

    # print(modem_state)
    # print(modem_time.get_network_time_sync(None))
    
    # nmea = modem.get_full_sync(None)
    # print(nmea)
    # print(nmea[1].get_cell_id(),
    # 	nmea[1].get_location_area_code(),
    # 	#nmea[1].get_mobile_country_code(),
    # 	#nmea[1].get_mobile_network_code(),
    # 	nmea[1].get_operator_code(),
    # 	nmea[1].get_tracking_area_code())
    
        #print(nmea.get_traces())
    # print(nmea[2].get_traces())

if __name__ == "__main__":
    main()




