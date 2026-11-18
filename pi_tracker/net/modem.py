"""
The LTE modem, through ModemManager (libmm-glib).

The modem is optional. ModemWatcher finds it whenever ModemManager reports
one, whatever its number, and follows it when it resets or is unplugged and
comes back as Modem/1, Modem/2... Without ModemManager or without a modem,
the rest of the app runs as usual.
"""
import logging

try:
    import gi
    gi.require_version('ModemManager', '1.0')
    from gi.repository import Gio, ModemManager
except (ImportError, ValueError):  # no PyGObject or no libmm-glib: run without a modem
    Gio = ModemManager = None

log = logging.getLogger(__name__)


class ModemWatcher:
    """The modem and its location interface, or None while there's none."""

    def __init__(self):
        self.modem = None
        self.location = None
        self._path = None

    def start(self, manager=None):
        """Connect to ModemManager and pick a modem. Never raises: the app runs on without one.

        `manager` is for tests; by default it's libmm-glib's MMManager on the system bus.
        """
        try:
            if manager is None:
                manager = _connect()
                if manager is None:
                    return
            # Signals arrive on the GLib main loop, like the telemetry timer that reads self.modem
            manager.connect('object-added', self._on_added)
            manager.connect('object-removed', self._on_removed)
            manager.connect('notify::name-owner', self._on_name_owner)
            if not manager.get_name_owner():
                log.warning("ModemManager isn't running; the modem is picked up when it starts")
            elif not self._pick(manager.get_objects()):
                log.warning("No modem yet; it's picked up when ModemManager reports one")
        except Exception:
            log.exception("Can't look for the modem, running without one")

    def _pick(self, objects):
        """Use the first object that is a modem. True if there was one."""
        for obj in objects:
            modem = obj.get_modem()
            if modem is not None:
                self.modem, self.location, self._path = modem, obj.get_modem_location(), obj.get_object_path()
                log.info("Modem found: %s %s at %s", modem.get_manufacturer(), modem.get_model(), self._path)
                return True
        return False

    def _on_added(self, manager, obj):
        if self.modem is None:
            self._pick([obj])

    def _on_removed(self, manager, obj):
        path = obj.get_object_path()
        if path != self._path:
            return
        log.warning("The modem at %s is gone", path)
        self.modem = self.location = self._path = None
        self._pick(o for o in manager.get_objects() if o.get_object_path() != path)

    def _on_name_owner(self, manager, pspec):
        if manager.get_name_owner():
            log.info("ModemManager is running")
        else:
            log.warning("ModemManager stopped; waiting for it to come back")


def _connect():
    """libmm-glib's MMManager on the system bus, or None when libmm-glib isn't installed."""
    if ModemManager is None:
        log.error("libmm-glib (gir1.2-modemmanager-1.0) isn't installed, running without a modem")
        return None
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    # DO_NOT_AUTO_START: works while ModemManager isn't running, and follows it when it starts
    return ModemManager.Manager.new_sync(connection, Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START, None)


def get_modem_stats_sync(modem):
    """Telemetry for `modem`, or {'present': False} while there's none."""
    if modem is None:
        return {'present': False}
    quality, recent = modem.get_signal_quality()
    return {
        'present': True,
        'signal_quality': quality,
        'signal_recent': recent,
        'primary_port': modem.get_primary_port(),
        'power_state': ModemManager.ModemPowerState.get_string(modem.get_power_state()),
        'current_modes': f"Initial Current Modes: {modem.get_current_modes()}",
    }


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