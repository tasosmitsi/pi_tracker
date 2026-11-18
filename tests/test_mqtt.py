import importlib.util
import types
import unittest

from pi_tracker import alarm, settings

# pi_tracker/net/mqtt.py needs paho-mqtt.
HAVE_PAHO = importlib.util.find_spec('paho') is not None


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
        from pi_tracker.net import mqtt
        self.mqtt = mqtt
        self.saved = settings.current, alarm.current
        settings.current = settings.Settings(mqtt=settings.MqttSettings(client_id='bike1', qos=0))
        alarm.current = alarm.AlarmState()
        self.client = FakeClient()

    def tearDown(self):
        settings.current, alarm.current = self.saved

    def test_published_topics_start_with_the_configured_client_id(self):
        self.mqtt.post_message(self.client, 'telemetry/x', 'v')
        self.assertEqual(self.client.published, [('bike1/telemetry/x', 'v', 0, False)])

    def test_commands_are_taken_from_the_configured_topic(self):
        self.mqtt.on_message(self.client, None, FakeMessage('bike1/command', 'arm_alarm'))
        self.assertEqual(alarm.current.state, alarm.ARMED)
        self.assertIn(('bike1/telemetry/alarm_state', 1, 0, False), self.client.published)

    def test_disarm_command_disarms(self):
        alarm.current.arm()
        self.mqtt.on_message(self.client, None, FakeMessage('bike1/command', 'disarm_alarm'))
        self.assertEqual(alarm.current.state, alarm.DISARMED)
        self.assertIn(('bike1/telemetry/alarm_state', 0, 0, False), self.client.published)

    def test_commands_on_another_prefix_are_rejected(self):
        with self.assertLogs('pi_tracker.net.mqtt', 'WARNING'):
            self.mqtt.on_message(self.client, None, FakeMessage('pi0w/command', 'arm_alarm'))
        self.assertEqual(alarm.current.state, alarm.DISARMED)
        self.assertEqual(self.client.published[0][0], 'bike1/errors')

    def test_subscribes_under_the_configured_client_id(self):
        reason = types.SimpleNamespace(is_failure=False)
        self.mqtt.on_connect(self.client, None, None, reason, None)
        self.assertEqual(self.client.subscribed, ['bike1/command/#'])


if __name__ == '__main__':
    unittest.main()
