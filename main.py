import sys
import time
import signal
import logging
import os
import config

from Thread import StoppableRestartableThread
from Thread import StoppableRestartableGiThread
from threads import *
from mqtt import *
from modem import *
from pijuice import PiJuice
from helpers import *

import smbus2
from i2c_bus_manager import I2CBusManager
from devices.LPS22HB.LPS22HB_manager import LPS22HB
from devices.TCS34725.TCS34725_manager import TCS34725
from devices.SGM58031.SGM58031_manager import SGM58031
import log_setup

log = logging.getLogger('main')

SHTC3_I2C_ADDRESS   = 0x70
LPS22HB_I2C_ADDRESS = 0x5C
TCS34725_I2C_ADDRESS = 0x29
SGM_I2C_ADDRESS = 0x48
PI_JUICE_I2C_ADDRESS = 0x14

def signal_handler(sig, frame):
    log.info("Interrupt received, stopping the idle and main loop...")
    idle.stop()
    loop.quit()

def idle_function(delay, stop_event):
    try:
        modem, modem_location = modem_init()
    except Exception as e:
        log.warning("Modem could be disconnected: %s", e)
        
    with PiJuice(1, PI_JUICE_I2C_ADDRESS) as pijuice:
        mqtt_client = mqtt_ini()
        config.mqtt_client = mqtt_client
        started_threads = []

        # thread_post_modem = StoppableRestartableGiThread(target=post_modem, args=(mqtt_client, modem))
        # thread_post_battery = StoppableRestartableGiThread(target=post_battery, args=(mqtt_client, pijuice)).start(60)
        # started_threads.append(thread_post_battery)

        # Initiate the change_alarm_state thread and start it imediately, it will always be on.
        thread_change_alarm_state = StoppableRestartableGiThread(target=change_alarm_state, args=(pijuice, )).start(2)
        started_threads.append(thread_change_alarm_state)
        
        # Initiate the telemetry thread and start it imediately, it will always be on.
        thread_telemetry = StoppableRestartableGiThread(target=telemetry, args=(mqtt_client, modem, pijuice)).start(5)
        started_threads.append(thread_telemetry)

        with I2CBusManager(smbus2, 1) as bus, \
            LPS22HB(bus, LPS22HB_I2C_ADDRESS) as pressure_sensor, \
            TCS34725(bus, TCS34725_I2C_ADDRESS) as light_sensor, \
            SGM58031(bus, SGM_I2C_ADDRESS) as adc_sensor:

            while not stop_event.is_set():
                # main loop!
                log.debug("LPS22HB %s", pressure_sensor.read_data())
                data = light_sensor.read_data()
                log.debug("TCS34725 R: %d G: %d B: %d C: %#x RGB565: %#x RGB888: %#x LUX: %d CT: %dK INT: %d",
                          data['R'], data['G'], data['B'], data['C'], data['RGB565'],
                          data['RGB888'], data['LUX'], data['CT'], data['INT'])
                log.debug("SGM58031 %s", adc_sensor.read_data())
                time.sleep(delay)

        # Stop all started threads
        for thread in started_threads:
            thread.stop()
            
        log.info("Stopping mqtt...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        
def main():
    global loop
    global idle

    log_setup.setup(os.environ.get('PI_TRACKER_LOG_LEVEL', 'INFO'))
    
    # 0 for un-armed, 1 for armed, 3 panic
    # assume we start with alarm un-armed. In reality this value will be read
    # from the config file
    config.alarm_state = 0

    # config.btn_state = {'data': {'SW1': 'NO_EVENT'}, 'error': 'NO_ERROR'}
    
    
    loop = GLib.MainLoop() # Init the GLib main loop
    signal.signal(signal.SIGINT, signal_handler) # Set up the signal handler for SIGINT (Ctrl+C)
    # Start the idle thread
    idle = StoppableRestartableThread(target=idle_function, args=(), kwargs={'delay': 0.5}).start()

    loop.run() # Start the main loop
    log.info("Exiting the application...")

    
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




