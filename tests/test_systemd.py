import os
import socket
import tempfile
import unittest
from unittest import mock

from pi_tracker import systemd


def unix_sockets_allowed():
    try:
        socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM).close()
        return True
    except OSError:  # some sandboxes forbid them
        return False


class FakeSocket:
    """Records what notify() does with its socket."""
    calls = []

    def __init__(self, family, kind):
        self.calls.append(('socket', family, kind))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def connect(self, address):
        self.calls.append(('connect', address))

    def sendall(self, data):
        self.calls.append(('sendall', data))


class NotifyTest(unittest.TestCase):
    def listen(self, address):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.bind(address)
        sock.settimeout(2)
        self.addCleanup(sock.close)
        return sock

    def test_run_by_hand_it_does_nothing(self):
        with mock.patch.dict(os.environ, clear=True):
            self.assertFalse(systemd.notify('READY=1'))

    def test_what_is_sent_where(self):
        FakeSocket.calls = []
        with mock.patch.dict(os.environ, {'NOTIFY_SOCKET': '@/org/freedesktop/systemd1/notify'}), \
                mock.patch.object(systemd.socket, 'socket', FakeSocket):
            self.assertTrue(systemd.notify('READY=1'))
        self.assertEqual(FakeSocket.calls, [('socket', socket.AF_UNIX, socket.SOCK_DGRAM),
                                            ('connect', '\0/org/freedesktop/systemd1/notify'),
                                            ('sendall', b'READY=1')])

    @unittest.skipUnless(unix_sockets_allowed(), 'Unix sockets are not allowed here')
    def test_the_message_reaches_the_notify_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'notify')
            sock = self.listen(path)
            with mock.patch.dict(os.environ, {'NOTIFY_SOCKET': path}):
                self.assertTrue(systemd.notify('READY=1'))
            self.assertEqual(sock.recv(100), b'READY=1')

    @unittest.skipUnless(unix_sockets_allowed(), 'Unix sockets are not allowed here')
    def test_an_abstract_notify_socket_works_too(self):
        name = 'pi_tracker-test-%d' % os.getpid()
        sock = self.listen('\0' + name)
        with mock.patch.dict(os.environ, {'NOTIFY_SOCKET': '@' + name}):
            self.assertTrue(systemd.notify('WATCHDOG=1'))
        self.assertEqual(sock.recv(100), b'WATCHDOG=1')

    def test_a_missing_socket_is_logged_not_raised(self):
        with mock.patch.dict(os.environ, {'NOTIFY_SOCKET': '/nonexistent/notify'}), \
                self.assertLogs('pi_tracker.systemd', 'WARNING'):
            self.assertFalse(systemd.notify('READY=1'))


class WatchdogIntervalTest(unittest.TestCase):
    def test_half_of_watchdog_sec(self):
        with mock.patch.dict(os.environ, {'WATCHDOG_USEC': '60000000', 'WATCHDOG_PID': str(os.getpid())}):
            self.assertEqual(systemd.watchdog_interval_s(), 30)

    def test_no_watchdog(self):
        with mock.patch.dict(os.environ, clear=True):
            self.assertIsNone(systemd.watchdog_interval_s())

    def test_a_watchdog_meant_for_another_process(self):
        with mock.patch.dict(os.environ, {'WATCHDOG_USEC': '60000000', 'WATCHDOG_PID': '1'}):
            self.assertIsNone(systemd.watchdog_interval_s())


class WatchdogTest(unittest.TestCase):
    def test_it_is_fed_while_the_sensor_loop_keeps_going(self):
        watchdog = systemd.Watchdog(max_round_age_s=30)
        watchdog.round_done()
        with mock.patch.object(systemd, 'notify') as notify:
            self.assertTrue(watchdog.feed())
        notify.assert_called_once_with('WATCHDOG=1')

    def test_it_is_not_fed_when_the_sensor_loop_is_stuck(self):
        watchdog = systemd.Watchdog(max_round_age_s=30)
        watchdog.last_round -= 31
        with mock.patch.object(systemd, 'notify') as notify, \
                self.assertLogs('pi_tracker.systemd', 'ERROR') as logs:
            self.assertTrue(watchdog.feed())  # the timer keeps running; systemd does the rest
        notify.assert_not_called()
        self.assertIn('No sensor round for 31 s', logs.output[0])


if __name__ == '__main__':
    unittest.main()
