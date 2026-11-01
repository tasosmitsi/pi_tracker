import importlib.util
import sys
import types
import unittest

import settings

# mqtt.py needs paho-mqtt. actions.py imports a module called `config`,
# which isn't in the repo, so stand in for it when it can't be found.
HAVE_PAHO = importlib.util.find_spec('paho') is not None
if 'config' not in sys.modules and importlib.util.find_spec('config') is None:
    sys.modules['config'] = types.ModuleType('config')


class FakeClient:
    def __init__(self):
        self.published = []
        self.subscribed = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)


class FakeMessage:
    def __init__(self, topic, payload, qos=1):
        self.topic = topic
        self.payload = payload.encode()
        self.qos = qos


@unittest.skipUnless(HAVE_PAHO, 'paho-mqtt is not installed')
class TopicsFollowTheSettingsTest(unittest.TestCase):
    def setUp(self):
        import config
        import mqtt
        self.config = config
        self.mqtt = mqtt
        self.saved = settings.current
        settings.current = settings.Settings(mqtt=settings.MqttSettings(client_id='bike1', qos=0))
        self.client = FakeClient()
        config.mqtt_client = self.client
        config.alarm_state = 0

    def tearDown(self):
        settings.current = self.saved

    def test_published_topics_start_with_the_configured_client_id(self):
        self.mqtt.post_message(self.client, 'telemetry/x', 'v')
        self.assertEqual(self.client.published, [('bike1/telemetry/x', 'v', 0, False)])

    def test_commands_are_taken_from_the_configured_topic(self):
        self.mqtt.on_message(self.client, None, FakeMessage('bike1/command', 'arm_alarm'))
        self.assertEqual(self.config.alarm_state, 1)
        self.assertIn(('bike1/telemetry/alarm_state', 1, 0, False), self.client.published)

    def test_commands_on_another_prefix_are_rejected(self):
        with self.assertLogs('mqtt', 'WARNING'):
            self.mqtt.on_message(self.client, None, FakeMessage('pi0w/command', 'arm_alarm'))
        self.assertEqual(self.config.alarm_state, 0)
        self.assertEqual(self.client.published[0][0], 'bike1/errors')

    def test_subscribes_under_the_configured_client_id(self):
        reason = types.SimpleNamespace(is_failure=False)
        self.mqtt.on_connect(self.client, None, None, reason, None)
        self.assertEqual(self.client.subscribed, ['bike1/command/#'])


if __name__ == '__main__':
    unittest.main()
