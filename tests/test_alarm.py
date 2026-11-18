import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from pi_tracker import alarm


class AlarmStateTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        # The 'state' directory doesn't exist yet; saving has to create it
        self.path = os.path.join(self.dir.name, 'state', 'alarm.json')

    def tearDown(self):
        self.dir.cleanup()

    def write(self, text):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w') as f:
            f.write(text)

    def saved(self):
        with open(self.path) as f:
            return json.load(f)

    def test_first_start_without_a_file_is_disarmed(self):
        with self.assertLogs('pi_tracker.alarm', 'INFO'):
            state = alarm.AlarmState(self.path)
        self.assertEqual(state.state, alarm.DISARMED)
        self.assertFalse(os.path.exists(self.path))

    def test_arming_is_saved_and_survives_a_restart(self):
        state = alarm.AlarmState(self.path)
        self.assertTrue(state.arm())
        self.assertEqual(self.saved()['alarm_state'], alarm.ARMED)
        self.assertIn('changed_at', self.saved())
        self.assertEqual(alarm.AlarmState(self.path).state, alarm.ARMED)

    def test_arming_only_works_from_disarmed(self):
        state = alarm.AlarmState(self.path)
        state.arm()
        self.assertFalse(state.arm())

        self.write('{"alarm_state": 3}')
        panic = alarm.AlarmState(self.path)
        self.assertFalse(panic.arm())
        self.assertEqual(panic.state, alarm.PANIC)

    def test_disarming_works_from_any_state_and_is_saved(self):
        self.write('{"alarm_state": 3}')
        state = alarm.AlarmState(self.path)
        self.assertTrue(state.disarm())
        self.assertEqual(self.saved()['alarm_state'], alarm.DISARMED)
        self.assertFalse(state.disarm())

    def test_a_file_that_cant_be_understood_starts_armed(self):
        for text in ('{not json', '[]', '{}', '{"alarm_state": "armed"}',
                     '{"alarm_state": 2}', '{"alarm_state": true}', '{"alarm_state": 1.0}'):
            with self.subTest(text=text):
                self.write(text)
                with self.assertLogs('pi_tracker.alarm', 'ERROR'):
                    self.assertEqual(alarm.AlarmState(self.path).state, alarm.ARMED)

    def test_a_failed_save_keeps_the_new_state_until_restart(self):
        state = alarm.AlarmState(self.path)
        with mock.patch('pi_tracker.alarm._write_atomically', side_effect=OSError(30, 'Read-only file system')):
            with self.assertLogs('pi_tracker.alarm', 'ERROR'):
                self.assertTrue(state.arm())
        self.assertEqual(state.state, alarm.ARMED)

    def test_no_temporary_file_is_left_behind(self):
        state = alarm.AlarmState(self.path)
        state.arm()
        state.disarm()
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ['alarm.json'])

    def test_without_a_path_nothing_is_saved(self):
        state = alarm.AlarmState()
        self.assertTrue(state.arm())
        self.assertEqual(state.state, alarm.ARMED)
        self.assertFalse(os.path.exists(self.path))

    def test_changes_from_several_threads_leave_file_and_memory_in_step(self):
        state = alarm.AlarmState(self.path)

        def flip():
            for _ in range(20):
                state.arm()
                state.disarm()

        threads = [threading.Thread(target=flip) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.saved()['alarm_state'], state.state)


if __name__ == '__main__':
    unittest.main()
