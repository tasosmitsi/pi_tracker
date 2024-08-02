import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import time

class ModemSignalHandler:
    def __init__(self):
        self.signal_quality = None
        self.current_modes = None
        self.packet_service_state = None
        self.state = None
        self.access_technologies = None
        self.location = None
        
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        
        self.bus.add_signal_receiver(self.signal_handler, dbus_interface="org.freedesktop.DBus.Properties", signal_name="PropertiesChanged", path="/org/freedesktop/ModemManager1/Modem/0")

    def signal_handler(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, dbus.Dictionary):
                for key, value in arg.items():
                    if key == "SignalQuality":
                        self.signal_quality = value[0]
                    elif key == "CurrentModes":
                        self.current_modes = value[0]
                    elif key == "PacketServiceState":
                        self.packet_service_state = value
                    elif key == "State":
                        self.state = value
                    elif key == "AccessTechnologies":
                        self.access_technologies = value
                    elif key == "Location":
                        self.location = value

    # Getter and setter methods
    def get_signal_quality(self):
        return self.signal_quality
    
    def set_signal_quality(self, signal_quality):
        self.signal_quality = signal_quality
    
    def get_current_modes(self):
        return self.current_modes
    
    def set_current_modes(self, current_modes):
        self.current_modes = current_modes
    
    def get_packet_service_state(self):
        return self.packet_service_state
    
    def set_packet_service_state(self, packet_service_state):
        self.packet_service_state = packet_service_state
    
    def get_state(self):
        return self.state
    
    def set_state(self, state):
        self.state = state
    
    def get_access_technologies(self):
        return self.access_technologies
    
    def set_access_technologies(self, access_technologies):
        self.access_technologies = access_technologies
    
    def get_location(self):
        return self.location
    
    def set_location(self, location):
        self.location = location

    def print_all(self):
        print("Modem Information:")
        print(f"Signal Quality: {self.signal_quality}")
        print(f"Current Modes: {self.current_modes}")
        print(f"Packet Service State: {self.packet_service_state}")
        print(f"State: {self.state}")
        print(f"Access Technologies: {self.access_technologies}")
        print(f"Location: {self.location}")