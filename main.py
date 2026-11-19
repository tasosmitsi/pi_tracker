import sys
import functools
import logging
import os

import smbus2
from pijuice import PiJuice

from pi_tracker import alarm, log_setup, settings, systemd
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

def sensor_worker(mqtt_client, watchdog, stop_event):
    """The worker thread: the sensor loop, until stop_event is set. Everything else is set up by main()."""
    intervals = settings.current.intervals
    with I2CBusManager(smbus2, 1) as bus:
        # The loop starts the sensors itself. One that fails to start or to read
        # is skipped for that round and tried again; see pi_tracker/sensor_loop.py
        sensor_loop = SensorLoop(LPS22HB(bus, LPS22HB_I2C_ADDRESS),
                                 TCS34725(bus, TCS34725_I2C_ADDRESS),
                                 SGM58031(bus, SGM_I2C_ADDRESS),
                                 publish=functools.partial(post_message, mqtt_client),
                                 publish_every_s=intervals.telemetry_s,
                                 on_round=watchdog.round_done if watchdog else None)
        sensor_loop.run(stop_event, intervals.sensor_loop_s)

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

    intervals = settings.current.intervals

    # The modem is optional: picked up whenever ModemManager reports one, and
    # followed through resets; see pi_tracker/net/modem.py
    modem = ModemWatcher()
    modem.start()

    mqtt_client = mqtt_ini()
    timers = []  # GLib timers: their callbacks run on the main loop, one at a time
    try:
        # Under systemd with WatchdogSec (deploy/pi-tracker@.service): fed from a GLib
        # timer while the sensor loop keeps finishing rounds, so a hang in either one
        # gets the app restarted. Run by hand there's no watchdog.
        watchdog = None
        interval_s = systemd.watchdog_interval_s()
        if interval_s:
            watchdog = systemd.Watchdog(max_round_age_s=interval_s)
            timers.append(StoppableRestartableGiThread(target=watchdog.feed).start(max(1, int(interval_s))))

        # The workers: blocking loops, each in a thread of its own; the thread takes the
        # function's name. Add more by passing them to run_with_main_loop() too.
        def sensors(stop_event):
            sensor_worker(mqtt_client, watchdog, stop_event)

        # The PiJuice is open only around what uses it: its two timers, and the main
        # loop that runs them. run_with_main_loop() blocks until the app stops.
        with PiJuice(1, PI_JUICE_I2C_ADDRESS) as pijuice:
            # thread_post_modem = StoppableRestartableGiThread(target=post_modem, args=(mqtt_client, modem))
            # thread_post_battery = StoppableRestartableGiThread(target=post_battery, args=(mqtt_client, pijuice)).start(60)

            # A single press on SW1 arms the alarm.
            timers.append(StoppableRestartableGiThread(target=check_button, args=(pijuice, )).start(intervals.button_poll_s))
            timers.append(StoppableRestartableGiThread(target=telemetry, args=(mqtt_client, modem, pijuice)).start(intervals.telemetry_s))

            # Run the GLib main loop, with the workers next to it. Ctrl+C and SIGTERM
            # (systemctl stop) stop them cleanly. If one fails, the others stop too and
            # the exit code is 1, so systemd can restart the tracker; see pi_tracker/workers.py
            systemd.notify('READY=1')  # everything is up; MQTT and the modem connect in the background
            exit_code = run_with_main_loop(sensors)
    finally:
        # Also when something failed or got stuck: the timers stop and the status says offline.
        # The loop has stopped by now, so no timer fires on the closed PiJuice in between.
        for timer in timers:
            timer.stop()

        log.info("Stopping mqtt...")
        mqtt_stop(mqtt_client)

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




