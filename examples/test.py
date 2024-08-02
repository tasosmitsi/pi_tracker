import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib, Gio, ModemManager
import time
# DBusGMainLoop(set_as_default=True)

class ModemHandler:
    def __init__(self, modem):
        self.modem = modem

    def property_changed(self, interface_name, changed_properties, invalidated_properties):
        path = '/org/freedesktop/ModemManager1/Modem/0'
        if interface_name == "org.freedesktop.ModemManager1.Modem":
            for property_name, property_value in changed_properties.items():
                print(f"Property '{property_name}' changed to: {property_value}")

            # Update properties using the modem object
            print(f"Updated Signal Quality: {self.modem.get_signal_quality()}")
            print(f"Updated Primary Port: {self.modem.get_primary_port()}")
            print(f"Updated Power State: {ModemManager.ModemPowerState.get_string(self.modem.get_power_state())}")
            print(f"Updated Current Modes: {self.modem.get_current_modes()}")

def periodic_print(modem):
    print(f"Initial Signal Quality: {modem.get_signal_quality()}")
    print(f"Initial Primary Port: {modem.get_primary_port()}")
    print(f"Initial Power State: {ModemManager.ModemPowerState.get_string(modem.get_power_state())}")
    print(f"Initial Current Modes: {modem.get_current_modes()}")
    return True



def main():
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    manager = ModemManager.Manager.new_sync(
        connection, Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START, None)

    if not manager.get_name_owner():
        print('ModemManager not found in bus')
        return

    # Find the modem by name or iterate
    obj = manager.get_object('/org/freedesktop/ModemManager1/Modem/0')
    modem = obj.get_modem()
    
    # handler = ModemHandler(modem)


    # Connect to the PropertiesChanged signal using dbus
    # bus = dbus.SystemBus()
    # bus.add_signal_receiver(
    #     handler.property_changed,
    #     dbus_interface="org.freedesktop.DBus.Properties",
    #     signal_name="PropertiesChanged",
    #     path="/org/freedesktop/ModemManager1/Modem/0",
    #     arg0="org.freedesktop.ModemManager1.Modem"
    # )

    GLib.timeout_add_seconds(2, periodic_print, modem)
    
    loop = GLib.MainLoop()
    loop.run()

if __name__ == '__main__':
    main()
