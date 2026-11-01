import os
import tempfile
import unittest

import settings

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, 'config.yml')

    def tearDown(self):
        self.dir.cleanup()

    def write(self, text):
        with open(self.path, 'w') as f:
            f.write(text)

    def test_missing_file_gives_the_defaults(self):
        with self.assertLogs('settings', 'WARNING'):
            loaded = settings.load(self.path)
        self.assertEqual(loaded, settings.Settings())

    def test_given_values_override_and_the_rest_keep_their_defaults(self):
        self.write('mqtt:\n  host: example.duckdns.org\n  port: 8883\n')
        loaded = settings.load(self.path)
        self.assertEqual(loaded.mqtt.host, 'example.duckdns.org')
        self.assertEqual(loaded.mqtt.port, 8883)
        self.assertEqual(loaded.mqtt.client_id, 'pi0w')
        self.assertEqual(loaded.intervals, settings.IntervalSettings())

    def test_unknown_key_is_reported_and_ignored(self):
        self.write('mqtt:\n  hots: typo\n')
        with self.assertLogs('settings', 'WARNING') as logs:
            loaded = settings.load(self.path)
        self.assertIn('mqtt.hots', logs.output[0])
        self.assertEqual(loaded.mqtt, settings.MqttSettings())

    def test_wrong_type_keeps_the_default(self):
        self.write('mqtt:\n  port: "4433"\n  retain: 1\n')
        with self.assertLogs('settings', 'WARNING') as logs:
            loaded = settings.load(self.path)
        self.assertEqual(len(logs.output), 2)
        self.assertEqual(loaded.mqtt.port, 4433)
        self.assertIs(loaded.mqtt.retain, False)

    def test_true_is_not_accepted_as_a_number(self):
        self.write('intervals:\n  telemetry_s: true\n')
        with self.assertLogs('settings', 'WARNING'):
            loaded = settings.load(self.path)
        self.assertEqual(loaded.intervals.telemetry_s, 5)

    def test_whole_number_is_accepted_where_a_float_is_expected(self):
        self.write('intervals:\n  sensor_loop_s: 2\n')
        loaded = settings.load(self.path)
        self.assertEqual(loaded.intervals.sensor_loop_s, 2.0)
        self.assertIsInstance(loaded.intervals.sensor_loop_s, float)

    def test_broken_yaml_gives_the_defaults(self):
        self.write('mqtt: [unclosed\n')
        with self.assertLogs('settings', 'ERROR'):
            loaded = settings.load(self.path)
        self.assertEqual(loaded, settings.Settings())

    def test_empty_file_gives_the_defaults(self):
        self.write('')
        self.assertEqual(settings.load(self.path), settings.Settings())

    def test_section_that_is_not_a_mapping_gives_its_defaults(self):
        self.write('mqtt: 42\nintervals:\n  telemetry_s: 10\n')
        with self.assertLogs('settings', 'ERROR'):
            loaded = settings.load(self.path)
        self.assertEqual(loaded.mqtt, settings.MqttSettings())
        self.assertEqual(loaded.intervals.telemetry_s, 10)

    def test_the_config_yml_in_the_repo_loads_without_complaints(self):
        with self.assertNoLogs('settings', 'WARNING'):
            settings.load(os.path.join(REPO, 'config.yml'))


if __name__ == '__main__':
    unittest.main()
