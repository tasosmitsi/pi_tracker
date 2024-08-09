import sys
import time
import signal

from Thread import StoppableRestartableThread
from Thread import StoppableRestartableGiThread
from threads import *
from mqtt import *
from modem import *
from pi_juice import *
from helpers import *

def signal_handler(sig, frame):
    print("Interrupt received, stopping the idle and main loop...")
    idle.stop()
    loop.quit()

def idle_function(delay, stop_event):    
    modem, modem_location = modem_init()
    pijuice = init_pijuice()
    mqtt_client = mqtt_ini()

    thread_post_modem = StoppableRestartableGiThread(target=post_modem, args=(mqtt_client, modem))
    thread_post_battery = StoppableRestartableGiThread(target=post_battery, args=(mqtt_client, pijuice))
    thread_print_btn = StoppableRestartableGiThread(target=print_btn, args=(pijuice, ))

    # Initiate the telemetry thread and start it imediately, it will always be on.
    thread_telemetry = StoppableRestartableGiThread(target=telemetry, args=(mqtt_client, modem, pijuice))
    thread_telemetry.start(1)

    i = 0
    while not stop_event.is_set():
        # main loop!
        if i == 0:
            i = 1
            # thread_post_modem.start(2)
            # thread_post_battery.start(2)
            thread_print_btn.start(2)
        time.sleep(delay)

    # thread_post_modem.stop()
    # thread_post_battery.stop()
    thread_print_btn.stop()
    thread_telemetry.stop()
    print("Stopping mqtt...")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
        
def main():
    global loop
    global idle
    global alarm_state # 0 for un-armed, 1 for armed, 3 panic
    
    loop = GLib.MainLoop() # Init the GLib main loop
    signal.signal(signal.SIGINT, signal_handler) # Set up the signal handler for SIGINT (Ctrl+C)
    # Start the idle thread
    idle = StoppableRestartableThread(target=idle_function, args=(), kwargs={'delay': 0.5}).start()  
    loop.run() # Start the main loop
    print("Exiting the application...")

    
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




