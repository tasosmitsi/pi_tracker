import types
import unittest
from unittest import mock

from pi_tracker.net import modem as modem_module
from pi_tracker.net.modem import ModemWatcher, get_modem_stats_sync

PATH = '/org/freedesktop/ModemManager1/Modem/%d'


class FakeModem:
    def get_manufacturer(self):
        return 'SIMCOM'

    def get_model(self):
        return 'SIM7600E-H'

    def get_signal_quality(self):
        return 67, True

    def get_primary_port(self):
        return 'ttyUSB2'

    def get_power_state(self):
        return 3

    def get_current_modes(self):
        return 'modes'


class FakeObject:
    """A ModemManager object at Modem/<number>."""

    def __init__(self, number):
        self.path = PATH % number
        self.modem = FakeModem()

    def get_object_path(self):
        return self.path

    def get_modem(self):
        return self.modem

    def get_modem_location(self):
        return 'location of ' + self.path


class FakeManager:
    """Stands in for libmm-glib's MMManager: a D-Bus object manager with signals."""

    def __init__(self, *objects, running=True):
        self.objects = list(objects)
        self.owner = ':1.7' if running else None
        self.handlers = {}

    def get_name_owner(self):
        return self.owner

    def get_objects(self):
        return list(self.objects)

    def connect(self, signal, handler):
        self.handlers[signal] = handler

    def add(self, obj):
        self.objects.append(obj)
        self.handlers['object-added'](self, obj)

    def remove(self, obj):
        self.objects.remove(obj)
        self.handlers['object-removed'](self, obj)

    def start_modemmanager(self):
        self.owner = ':1.9'
        self.handlers['notify::name-owner'](self, None)


def watching(manager):
    watcher = ModemWatcher()
    watcher.start(manager)
    return watcher


class ModemWatcherTest(unittest.TestCase):
    def test_the_modem_is_found_whatever_its_number(self):
        modem3 = FakeObject(3)
        with self.assertLogs('pi_tracker.net.modem', 'INFO') as logs:
            watcher = watching(FakeManager(modem3))
        self.assertIs(watcher.modem, modem3.modem)
        self.assertEqual(watcher.location, 'location of ' + PATH % 3)
        self.assertIn('Modem found: SIMCOM SIM7600E-H at ' + PATH % 3, logs.output[0])

    def test_a_modem_that_appears_later_is_picked_up(self):
        manager = FakeManager()
        with self.assertLogs('pi_tracker.net.modem', 'WARNING') as logs:
            watcher = watching(manager)
        self.assertIn('No modem yet', logs.output[0])
        self.assertIsNone(watcher.modem)
        modem0 = FakeObject(0)
        manager.add(modem0)
        self.assertIs(watcher.modem, modem0.modem)

    def test_a_reset_modem_is_followed_to_its_new_number(self):
        old, new = FakeObject(0), FakeObject(1)
        manager = FakeManager(old)
        watcher = watching(manager)
        with self.assertLogs('pi_tracker.net.modem', 'WARNING') as logs:
            manager.remove(old)
        self.assertIsNone(watcher.modem)
        self.assertIn('The modem at %s is gone' % (PATH % 0), logs.output[0])
        manager.add(new)
        self.assertIs(watcher.modem, new.modem)

    def test_another_modem_coming_or_going_changes_nothing(self):
        ours, other = FakeObject(0), FakeObject(1)
        manager = FakeManager(ours)
        watcher = watching(manager)
        manager.add(other)
        manager.remove(other)
        self.assertIs(watcher.modem, ours.modem)

    def test_when_ours_goes_the_other_modem_takes_over(self):
        ours, other = FakeObject(0), FakeObject(1)
        manager = FakeManager(ours, other)
        watcher = watching(manager)
        with self.assertLogs('pi_tracker.net.modem', 'INFO'):
            manager.remove(ours)
        self.assertIs(watcher.modem, other.modem)

    def test_modemmanager_starting_later_is_fine(self):
        manager = FakeManager(running=False)
        with self.assertLogs('pi_tracker.net.modem', 'WARNING') as logs:
            watcher = watching(manager)
        self.assertIn("ModemManager isn't running", logs.output[0])
        with self.assertLogs('pi_tracker.net.modem', 'INFO') as logs:
            manager.start_modemmanager()
            manager.add(FakeObject(0))
        self.assertIn('ModemManager is running', logs.output[0])
        self.assertIsNotNone(watcher.modem)

    def test_without_libmm_glib_the_app_runs_without_a_modem(self):
        with mock.patch.object(modem_module, 'ModemManager', None), \
                self.assertLogs('pi_tracker.net.modem', 'ERROR') as logs:
            watcher = ModemWatcher()
            watcher.start()
        self.assertIsNone(watcher.modem)
        self.assertIn("libmm-glib", logs.output[0])

    def test_a_failure_while_looking_for_the_modem_is_logged_not_raised(self):
        manager = FakeManager()
        manager.get_objects = mock.Mock(side_effect=RuntimeError('D-Bus went away'))
        with self.assertLogs('pi_tracker.net.modem', 'ERROR') as logs:
            watcher = watching(manager)
        self.assertIsNone(watcher.modem)
        self.assertIn('D-Bus went away', logs.output[0])


class ModemStatsTest(unittest.TestCase):
    def test_no_modem(self):
        self.assertEqual(get_modem_stats_sync(None), {'present': False})

    def test_a_modem(self):
        fake_mm = types.SimpleNamespace(ModemPowerState=types.SimpleNamespace(get_string=lambda state: 'on'))
        with mock.patch.object(modem_module, 'ModemManager', fake_mm):
            stats = get_modem_stats_sync(FakeModem())
        self.assertEqual(stats, {'present': True, 'signal_quality': 67, 'signal_recent': True,
                                 'primary_port': 'ttyUSB2', 'power_state': 'on',
                                 'current_modes': 'Initial Current Modes: modes'})


if __name__ == '__main__':
    unittest.main()
