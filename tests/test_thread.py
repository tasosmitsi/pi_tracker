import unittest

try:
    import gi
    gi.require_version('GLib', '2.0')
    from gi.repository import GLib
    import Thread
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

        timer = Thread.StoppableRestartableGiThread(target=flaky)
        with self.assertLogs('Thread', 'ERROR'):
            timer.start(1)
            run_loop_until(lambda: len(calls) >= 2)
        timer.stop()
        self.assertGreaterEqual(len(calls), 2)

    def test_a_repeated_error_is_logged_once_then_after_10_failures(self):
        def broken():
            raise OSError(121, 'Remote I/O error')

        timer = Thread.StoppableRestartableGiThread(target=broken)
        with self.assertLogs('Thread', 'ERROR') as logs:
            for _ in range(10):
                self.assertTrue(timer._run())
        self.assertEqual(len(logs.output), 2)
        self.assertIn('Traceback', logs.output[0])
        self.assertIn('10 times in a row', logs.output[1])

    def test_a_different_error_is_logged_again(self):
        errors = [OSError('bus error'), ValueError('bad reply')]

        def broken():
            raise errors.pop(0)

        timer = Thread.StoppableRestartableGiThread(target=broken)
        with self.assertLogs('Thread', 'ERROR') as logs:
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

        timer = Thread.StoppableRestartableGiThread(target=sometimes)
        with self.assertLogs('Thread', 'INFO') as logs:
            timer._run()
            self.assertTrue(timer._run())
        self.assertIn('works again after 1 failures', logs.output[-1])

    def test_a_target_returning_false_ends_the_timer_cleanly(self):
        calls = []

        def once():
            calls.append(1)
            return False

        timer = Thread.StoppableRestartableGiThread(target=once)
        timer.start(1)
        run_loop_until(lambda: calls)
        self.assertFalse(timer.is_running())
        # GLib already removed the source, so stop() must not try again
        with self.assertLogs('Thread', 'WARNING') as logs:
            timer.stop()
        self.assertIn('already stopped', logs.output[0])


if __name__ == '__main__':
    unittest.main()
