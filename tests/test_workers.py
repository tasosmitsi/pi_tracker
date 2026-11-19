import os
import signal
import threading
import time
import unittest

try:
    import gi
    gi.require_version('GLib', '2.0')
    from gi.repository import GLib
    from pi_tracker import workers
except (ImportError, ValueError):
    GLib = None


def run_loop_until(done, timeout_s=5):
    """Run a GLib main loop until done() is true or timeout_s passes."""
    loop = GLib.MainLoop()

    def check():
        if done():
            loop.quit()
            return False
        return True

    GLib.timeout_add(20, check)
    guard = GLib.timeout_add_seconds(timeout_s, loop.quit)
    loop.run()
    GLib.source_remove(guard)


@unittest.skipIf(GLib is None, 'PyGObject (gi) with GLib is not installed')
class GuardedTimerTest(unittest.TestCase):
    def test_a_failing_target_does_not_stop_the_timer(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) == 1:
                raise OSError(121, 'Remote I/O error')
            return True

        timer = workers.StoppableRestartableGiThread(target=flaky)
        with self.assertLogs('pi_tracker.workers', 'ERROR'):
            timer.start(1)
            run_loop_until(lambda: len(calls) >= 2)
        timer.stop()
        self.assertGreaterEqual(len(calls), 2)

    def test_a_repeated_error_is_logged_once_then_after_10_failures(self):
        def broken():
            raise OSError(121, 'Remote I/O error')

        timer = workers.StoppableRestartableGiThread(target=broken)
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            for _ in range(10):
                self.assertTrue(timer._run())
        self.assertEqual(len(logs.output), 2)
        self.assertIn('Traceback', logs.output[0])
        self.assertIn('10 times in a row', logs.output[1])

    def test_a_different_error_is_logged_again(self):
        errors = [OSError('bus error'), ValueError('bad reply')]

        def broken():
            raise errors.pop(0)

        timer = workers.StoppableRestartableGiThread(target=broken)
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            timer._run()
            timer._run()
        self.assertEqual(len(logs.output), 2)

    def test_recovery_is_logged(self):
        results = [OSError('bus error'), True]

        def sometimes():
            result = results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        timer = workers.StoppableRestartableGiThread(target=sometimes)
        with self.assertLogs('pi_tracker.workers', 'INFO') as logs:
            timer._run()
            self.assertTrue(timer._run())
        self.assertIn('works again after 1 failures', logs.output[-1])

    def test_a_target_returning_false_ends_the_timer_cleanly(self):
        calls = []

        def once():
            calls.append(1)
            return False

        timer = workers.StoppableRestartableGiThread(target=once)
        timer.start(1)
        run_loop_until(lambda: calls)
        self.assertFalse(timer.is_running())
        # GLib already removed the source, so stop() must not try again
        with self.assertLogs('pi_tracker.workers', 'WARNING') as logs:
            timer.stop()
        self.assertIn('already stopped', logs.output[0])



def send(signum, after_s):
    """Send this process `signum` after `after_s`, like Ctrl+C or systemctl stop would."""
    threading.Timer(after_s, os.kill, (os.getpid(), signum)).start()


@unittest.skipIf(GLib is None, 'PyGObject (gi) with GLib is not installed')
class RunWithMainLoopTest(unittest.TestCase):
    def setUp(self):
        self.release = threading.Event()  # lets a stuck worker go at the end of the test
        self.addCleanup(self.release.set)

    def stuck(self, stop_event):
        self.release.wait(10)  # ignores stop_event

    def test_sigterm_stops_the_worker_cleanly(self):
        send(signal.SIGTERM, 0.2)
        with self.assertLogs('pi_tracker.workers', 'INFO') as logs:
            exit_code = workers.run_with_main_loop(lambda stop_event: stop_event.wait(10))
        self.assertEqual(exit_code, 0)
        self.assertIn('SIGTERM received, stopping', logs.output[0])

    def test_ctrl_c_stops_the_worker_cleanly(self):
        send(signal.SIGINT, 0.2)
        with self.assertLogs('pi_tracker.workers', 'INFO'):
            self.assertEqual(workers.run_with_main_loop(lambda stop_event: stop_event.wait(10)), 0)

    def test_a_failing_worker_ends_the_app_with_exit_code_1(self):
        def broken(stop_event):
            raise OSError(121, 'Remote I/O error')
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            self.assertEqual(workers.run_with_main_loop(broken), 1)
        self.assertIn('Worker broken failed', logs.output[0])
        self.assertIn('Remote I/O error', logs.output[0])

    def test_a_worker_that_ends_by_itself_is_a_failure(self):
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            self.assertEqual(workers.run_with_main_loop(lambda stop_event: None), 1)
        self.assertIn('ended without being asked to', logs.output[0])

    def test_a_stuck_worker_is_left_behind_after_the_timeout(self):
        send(signal.SIGTERM, 0.2)
        started = time.monotonic()
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            self.assertEqual(workers.run_with_main_loop(self.stuck, stop_timeout_s=0.5), 1)
        self.assertLess(time.monotonic() - started, 3)
        self.assertIn('Still stopping after 0.5 s', logs.output[0])

    def test_a_second_signal_exits_at_once(self):
        send(signal.SIGINT, 0.2)
        send(signal.SIGINT, 0.4)
        started = time.monotonic()
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            self.assertEqual(workers.run_with_main_loop(self.stuck, stop_timeout_s=30), 1)
        self.assertLess(time.monotonic() - started, 3)
        self.assertIn('SIGINT again', logs.output[0])

    def test_a_signal_stops_every_worker(self):
        stopped = []
        def sensors(stop_event):
            stopped.append('sensors' if stop_event.wait(10) else 'timed out')
        def gps(stop_event):
            stopped.append('gps' if stop_event.wait(10) else 'timed out')
        send(signal.SIGTERM, 0.2)
        with self.assertLogs('pi_tracker.workers', 'INFO'):
            self.assertEqual(workers.run_with_main_loop(sensors, gps), 0)
        self.assertEqual(sorted(stopped), ['gps', 'sensors'])

    def test_one_failing_worker_stops_the_others(self):
        stopped = []
        def gps(stop_event):
            raise OSError(5, 'Input/output error')
        def sensors(stop_event):
            stopped.append(stop_event.wait(10))
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            self.assertEqual(workers.run_with_main_loop(sensors, gps), 1)
        self.assertEqual(stopped, [True])  # asked to stop, not timed out
        self.assertIn('Worker gps failed', logs.output[0])

    def test_a_worker_ending_by_itself_stops_the_others(self):
        def gps(stop_event):
            return
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            self.assertEqual(workers.run_with_main_loop(lambda stop_event: stop_event.wait(10), gps), 1)
        self.assertIn('Worker gps ended without being asked to', logs.output[0])

    def test_a_stuck_worker_is_left_behind_when_another_fails(self):
        def gps(stop_event):
            raise OSError(5, 'Input/output error')
        started = time.monotonic()
        with self.assertLogs('pi_tracker.workers', 'ERROR') as logs:
            self.assertEqual(workers.run_with_main_loop(self.stuck, gps, stop_timeout_s=0.5), 1)
        self.assertLess(time.monotonic() - started, 3)
        self.assertIn('Still stopping after 0.5 s', logs.output[-1])

    def test_threads_are_named_after_their_workers(self):
        names = []
        def sensors(stop_event):
            names.append(threading.current_thread().name)
        def record(stop_event):
            names.append(threading.current_thread().name)
            stop_event.wait(10)
        with self.assertLogs('pi_tracker.workers', 'ERROR'):  # sensors ends by itself
            workers.run_with_main_loop(sensors, lambda stop_event: record(stop_event))
        self.assertEqual(sorted(names), ['sensors', 'worker-2'])

    def test_it_needs_a_worker(self):
        with self.assertRaises(ValueError):
            workers.run_with_main_loop()

    def test_the_signal_handlers_are_put_back(self):
        before = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
        send(signal.SIGTERM, 0.2)
        with self.assertLogs('pi_tracker.workers', 'INFO'):
            workers.run_with_main_loop(lambda stop_event: stop_event.wait(10))
        self.assertEqual((signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)), before)


if __name__ == '__main__':
    unittest.main()
