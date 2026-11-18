import sys
import logging
import gi
gi.require_version('ModemManager', '1.0')
from gi.repository import Gio, GLib, GObject, ModemManager

log = logging.getLogger(__name__)

def modem_init():
    global manager
    # Connection to ModemManager    
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    manager = ModemManager.Manager.new_sync(
    connection, Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START, None)
    
    if not manager.get_name_owner():
        log.error('ModemManager not found in bus')
        sys.exit(2)
        
    # find the modem by name or iterate
    obj =  manager.get_object('/org/freedesktop/ModemManager1/Modem/0')
    #	test = manager.get_interfaces()
    #	print(test)

    modem = obj.get_modem()
    modem_location = obj.get_modem_location()
    
    modem_state = modem.get_state()
    if modem_state == ModemManager.ModemState.ENABLED:
        log.info('Modem enabled')
    
    elif modem_state == ModemManager.ModemState.CONNECTED:
        log.info('Modem connected')

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
        log.warning("None of the desired location sources are supported by the modem")
        return

    return modem_location.setup_sync(ModemManager.ModemLocationSource(desired_sources), False, None)

def stop_gps_all(modem_location):
    supported_sources = modem_location.get_capabilities()
    desired_sources = 0
    
    if supported_sources & ModemManager.ModemLocationSource(0):
            desired_sources |= ModemManager.ModemLocationSource(0)
    
    return modem_location.setup_sync(ModemManager.ModemLocationSource(desired_sources), False, None)