import sys
import functools
import logging
import os

import smbus2
from pijuice import PiJuice

from pi_tracker import alarm, log_setup, settings
from pi_tracker.button import check_button
from pi_tracker.net.modem import ModemWatcher
from pi_tracker.net.mqtt import mqtt_ini, mqtt_stop, post_message
from pi_tracker.sensor_loop import SensorLoop
from pi_tracker.sensors.i2c_bus import I2CBusManager
from pi_tracker.sensors.lps22hb import LPS22HB
from pi_tracker.sensors.sgm58031 import SGM58031
from pi_tracker.sensors.tcs34725 import TCS34725
from pi_tracker.telemetry import telemetry
from pi_tracker.workers import StoppableRestartableGiThread, run_with_main_loop

log = logging.getLogger('main')

CONFIG_FILE = 'config.yml'

SHTC3_I2C_ADDRESS   = 0x70
LPS22HB_I2C_ADDRESS = 0x5C
TCS34725_I2C_ADDRESS = 0x29
SGM_I2C_ADDRESS = 0x48
PI_JUICE_I2C_ADDRESS = 0x14

def idle_function(delay, stop_event):
    intervals = settings.current.intervals
    # The modem is optional: picked up whenever ModemManager reports one, and
    # followed through resets; see pi_tracker/net/modem.py
    modem = ModemWatcher()
    modem.start()

    with PiJuice(1, PI_JUICE_I2C_ADDRESS) as pijuice:
        mqtt_client = mqtt_ini()
        started_threads = []
        try:
            # thread_post_modem = StoppableRestartableGiThread(target=post_modem, args=(mqtt_client, modem))
            # thread_post_battery = StoppableRestartableGiThread(target=post_battery, args=(mqtt_client, pijuice)).start(60)
            # started_threads.append(thread_post_battery)

            # Initiate the button thread and start it imediately, it will always be on.
            # A single press on SW1 arms the alarm.
            thread_check_button = StoppableRestartableGiThread(target=check_button, args=(pijuice, )).start(intervals.button_poll_s)
            started_threads.append(thread_check_button)

            # Initiate the telemetry thread and start it imediately, it will always be on.
            thread_telemetry = StoppableRestartableGiThread(target=telemetry, args=(mqtt_client, modem, pijuice)).start(intervals.telemetry_s)
            started_threads.append(thread_telemetry)

            with I2CBusManager(smbus2, 1) as bus:
                # The loop starts the sensors itself. One that fails to start or to read
                # is skipped for that round and tried again; see pi_tracker/sensor_loop.py
                sensor_loop = SensorLoop(LPS22HB(bus, LPS22HB_I2C_ADDRESS),
                                         TCS34725(bus, TCS34725_I2C_ADDRESS),
                                         SGM58031(bus, SGM_I2C_ADDRESS),
                                         publish=functools.partial(post_message, mqtt_client),
                                         publish_every_s=intervals.telemetry_s)
                sensor_loop.run(stop_event, delay)
        finally:
            # Also when something above failed: the timers stop and the status says offline
            for thread in started_threads:
                thread.stop()

            log.info("Stopping mqtt...")
            mqtt_stop(mqtt_client)

def main():
    # Log at INFO while reading the settings, then switch to the configured level.
    # PI_TRACKER_LOG_LEVEL overrides the level in config.yml.
    log_setup.setup(os.environ.get('PI_TRACKER_LOG_LEVEL', 'INFO'))
    settings.current = settings.load(CONFIG_FILE)
    log_setup.setup(os.environ.get('PI_TRACKER_LOG_LEVEL') or settings.current.log.level)
    
    # 0 for un-armed, 1 for armed, 3 panic. The state is saved on every change and
    # read back here, so a restart doesn't disarm the tracker.
    state_dir = os.path.expanduser(settings.current.state.directory)
    alarm.current = alarm.AlarmState(os.path.join(state_dir, alarm.FILE_NAME))

    # config.btn_state = {'data': {'SW1': 'NO_EVENT'}, 'error': 'NO_ERROR'}
    
    
    # Run the GLib main loop, with idle_function in a thread next to it. Ctrl+C and
    # SIGTERM (systemctl stop) stop it cleanly. If it fails, the exit code is 1, so
    # systemd can restart the tracker; see pi_tracker/workers.py
    delay = settings.current.intervals.sensor_loop_s
    exit_code = run_with_main_loop(lambda stop_event: idle_function(delay, stop_event))
    log.info("Exiting the application...")
    sys.exit(exit_code)

    
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




