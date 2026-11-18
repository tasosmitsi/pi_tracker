import json
import logging

from pi_tracker import alarm
from pi_tracker.net.modem import get_modem_stats_sync
from pi_tracker.net.mqtt import post_message

log = logging.getLogger(__name__)

def post_battery(mqtt_client, pijuice):
    publish_message = json.dumps(pijuice.status.GetChargeLevel())
    post_message(mqtt_client, 'battery/level', publish_message)
    return True

def post_modem(mqtt_client, modem):
    publish_message = json.dumps(get_modem_stats_sync(modem))
    post_message(mqtt_client, 'modem/stats', publish_message)
    return True

def telemetry(mqtt_client, modem_watcher, pijuice):
    # The alarm state first: it matters most, and a failed PiJuice read below mustn't hold it back
    post_message(mqtt_client, 'telemetry/alarm_state', alarm.current.state)
    post_message(mqtt_client, 'telemetry/modem', json.dumps(get_modem_stats_sync(modem_watcher.modem)))
    post_message(mqtt_client, 'telemetry/power_management', json.dumps(get_power_management_stats_sync(pijuice)))
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

def check_if_power_management_error_exist(reply):
    if "error" not in reply:
        return reply

    if "data" not in reply:
        return reply
        
    if reply['error'] == "NO_ERROR":
        return reply['data']
    else:
        return reply['error']
