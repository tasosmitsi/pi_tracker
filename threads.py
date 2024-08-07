import json
import gi
gi.require_version('ModemManager', '1.0')
from gi.repository import ModemManager

from mqtt import *

def post_battery(mqtt_client, pijuice):
    publish_message = json.dumps(pijuice.status.GetChargeLevel())
    post_message(mqtt_client, 'battery/level', publish_message)
    return True

def post_modem(mqtt_client, modem):
    publish_message = json.dumps(get_modem_stats_sync(modem))
    post_message(mqtt_client, 'modem/stats', publish_message)
    return True

def print_btn(pijuice):
    btn_events = pijuice.status.GetButtonEvents()

    if btn_events['error'] != 'NO_ERROR':
        print("Button events reported:" + btn_events['error'])

    if 'data' in btn_events:
        if btn_events['data']['SW1'] == 'SINGLE_PRESS':
            print(btn_events)
            pijuice.status.AcceptButtonEvent('SW1')
            print(pijuice.status.GetButtonEvents())
    return True


    
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