import json
import config
import gi
gi.require_version('ModemManager', '1.0')
from gi.repository import ModemManager

from mqtt import *
from actions import *

def post_battery(mqtt_client, pijuice):
    publish_message = json.dumps(pijuice.status.GetChargeLevel())
    post_message(mqtt_client, 'battery/level', publish_message)
    return True

def post_modem(mqtt_client, modem):
    publish_message = json.dumps(get_modem_stats_sync(modem))
    post_message(mqtt_client, 'modem/stats', publish_message)
    return True

def change_alarm_state(pijuice):
    while True:
        btn_state = get_btn_state(pijuice.status.GetButtonEvents())
        # btn_state = get_btn_state(config.btn_state)
        # print(btn_state)
        if btn_state:
            break
    # change the alarm state since the button has been pressed
    # only if the alarm is un-armed (0), the alarm can be activated
    # for every other state the button should do nothing
    if btn_state == "pressed": 
        arm_alarm()
        pijuice.status.AcceptButtonEvent('SW1')
        # print(pijuice.status.GetButtonEvents())
        
    return True

def get_btn_state(btn_events):
    if "error" not in btn_events:
        return False

    if btn_events['error'] != 'NO_ERROR':
        print("Button events reported:" + btn_events['error'])
        return False

    if 'data' not in btn_events:
        return False
        
    if btn_events['data']['SW1'] == 'SINGLE_PRESS':
        print(btn_events)
        return "pressed"

    return True

def telemetry(mqtt_client, modem, pijuice):
    post_message(mqtt_client, 'telemetry/power_management', json.dumps(get_power_management_stats_sync(pijuice)))
    post_message(mqtt_client, 'telemetry/modem', json.dumps(get_modem_stats_sync(modem)))
    post_message(mqtt_client, 'telemetry/alarm_state', config.alarm_state)
    return True

def get_power_management_stats_sync(pijuice):
    stats = {}
    stats['status'] = pijuice.status.GetStatus()
    stats['charge_level'] = pijuice.status.GetChargeLevel()
    stats['fault_status'] = pijuice.status.GetFaultStatus()
    stats['button_events'] = pijuice.status.GetButtonEvents()
    stats['battery_temperature'] = pijuice.status.GetBatteryTemperature()
    stats['battery_voltage'] = pijuice.status.GetBatteryVoltage()
    stats['battery_current'] = pijuice.status.GetBatteryCurrent()
    stats['io_voltage'] = pijuice.status.GetIoVoltage()
    stats['io_current'] = pijuice.status.GetIoCurrent()

    for key, value in stats.items():
        stats[key] = check_if_power_management_error_exist(value)

    return stats
    
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

def check_if_power_management_error_exist(reply):
    if "error" not in reply:
        return reply

    if "data" not in reply:
        return reply
        
    if reply['error'] == "NO_ERROR":
        return reply['data']
    else:
        return reply['error']
