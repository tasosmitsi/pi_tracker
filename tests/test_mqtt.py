import importlib.util
import types
import unittest
from unittest import mock

from pi_tracker import alarm, settings
from pi_tracker.failure_log import FailureLog

# pi_tracker/net/mqtt.py needs paho-mqtt.
HAVE_PAHO = importlib.util.find_spec('paho') is not None

SUCCESS = types.SimpleNamespace(is_failure=False)
FAILURE = types.SimpleNamespace(is_failure=True)


class FakeClient:
    def __init__(self):
        self.published = []
        self.subscribed = []
        self.calls = []  # in order: publish, wait, disconnect, loop_stop
        self.connected = True

    def is_connected(self):
        return self.connected

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))
        self.calls.append('publish %s %s' % (topic, payload))
        return FakeMessageInfo(self.calls)

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)
        return 0, len(self.subscribed)  # like paho: (MQTT_ERR_SUCCESS, message id)

    def disconnect(self):
        self.calls.append('disconnect')

    def loop_stop(self):
        self.calls.append('loop_stop')


class FakeMessageInfo:
    def __init__(self, calls):
        self.calls = calls

    def wait_for_publish(self, timeout=None):
        self.calls.append('wait')


class FakeMessage:
    def __init__(self, topic, payload, qos=1):
        self.topic = topic
        self.payload = payload if isinstance(payload, bytes) else payload.encode()
        self.qos = qos


@unittest.skipUnless(HAVE_PAHO, 'paho-mqtt is not installed')
class MqttTestCase(unittest.TestCase):
    def setUp(self):
        from pi_tracker.net import mqtt
        self.mqtt = mqtt
        self.saved = settings.current, alarm.current, mqtt._connection
        settings.current = settings.Settings(mqtt=settings.MqttSettings(client_id='bike1', qos=0))
        alarm.current = alarm.AlarmState()
        mqtt._connection = FailureLog('MQTT connect', mqtt.log)
        self.client = FakeClient()

    def tearDown(self):
        settings.current, alarm.current, self.mqtt._connection = self.saved


class TopicsFollowTheSettingsTest(MqttTestCase):
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
        self.mqtt.on_connect(self.client, None, None, SUCCESS, None)
        self.assertEqual(self.client.subscribed, ['bike1/command/#'])


class ConnectionTest(MqttTestCase):
    def test_starting_does_not_wait_for_the_broker(self):
        with mock.patch.object(self.mqtt.mqtt, 'Client') as client_class:
            client = self.mqtt.mqtt_ini()
        self.assertIs(client, client_class.return_value)
        client.reconnect_delay_set.assert_called_once_with(min_delay=1, max_delay=120)
        client.connect_async.assert_called_once_with('192.168.178.203', 4433, 60)
        client.loop_start.assert_called_once_with()
        client.connect.assert_not_called()

    def test_nothing_is_published_while_disconnected(self):
        self.client.connected = False
        self.mqtt.post_message(self.client, 'telemetry/x', 'v')
        self.assertEqual(self.client.published, [])

    def test_failed_connections_are_logged_once_then_after_10(self):
        with self.assertLogs('pi_tracker.net.mqtt', 'ERROR') as logs:
            for _ in range(10):
                self.mqtt.on_connect_fail(self.client, None)
        self.assertEqual(len(logs.output), 2)
        self.assertIn("can't reach 192.168.178.203:4433", logs.output[0])
        self.assertIn('10 times in a row', logs.output[1])

    def test_a_refused_connection_is_logged_and_nothing_is_subscribed(self):
        with self.assertLogs('pi_tracker.net.mqtt', 'ERROR') as logs:
            self.mqtt.on_connect(self.client, None, None, FAILURE, None)
        self.assertIn('the broker refused', logs.output[0])
        self.assertEqual(self.client.subscribed, [])

    def test_connecting_after_failures_is_logged(self):
        with self.assertLogs('pi_tracker.net.mqtt', 'INFO') as logs:
            self.mqtt.on_connect_fail(self.client, None)
            self.mqtt.on_connect(self.client, None, None, SUCCESS, None)
        self.assertIn('works again after 1 failures', logs.output[-2])
        self.assertIn('Connected to the MQTT broker at 192.168.178.203:4433', logs.output[-1])

    def test_a_lost_connection_is_logged(self):
        with self.assertLogs('pi_tracker.net.mqtt', 'WARNING') as logs:
            self.mqtt.on_disconnect(self.client, None, None, FAILURE, None)
        self.assertIn('Lost the connection', logs.output[0])


class StatusTest(MqttTestCase):
    def test_the_last_will_says_offline_and_is_set_before_connecting(self):
        with mock.patch.object(self.mqtt.mqtt, 'Client'):
            client = self.mqtt.mqtt_ini()
        client.will_set.assert_called_once_with('bike1/status', 'offline', qos=1, retain=True)
        calls = [name for name, args, kwargs in client.method_calls]
        self.assertLess(calls.index('will_set'), calls.index('connect_async'))

    def test_connecting_says_online(self):
        self.mqtt.on_connect(self.client, None, None, SUCCESS, None)
        self.assertIn(('bike1/status', 'online', 1, True), self.client.published)

    def test_stopping_says_offline_before_disconnecting(self):
        self.mqtt.mqtt_stop(self.client)
        self.assertEqual(self.client.calls, ['publish bike1/status offline', 'wait', 'disconnect', 'loop_stop'])
        self.assertEqual(self.client.published, [('bike1/status', 'offline', 1, True)])

    def test_stopping_while_not_connected_just_stops(self):
        self.client.connected = False
        self.mqtt.mqtt_stop(self.client)
        self.assertEqual(self.client.calls, ['disconnect', 'loop_stop'])


class CallbackErrorsTest(MqttTestCase):
    def test_every_callback_is_wrapped(self):
        with mock.patch.object(self.mqtt.mqtt, 'Client'):
            client = self.mqtt.mqtt_ini()
        for name in ('on_connect', 'on_connect_fail', 'on_disconnect', 'on_subscribe', 'on_unsubscribe', 'on_message'):
            with self.subTest(name):
                self.assertIs(getattr(client, name).__wrapped__, getattr(self.mqtt, name))

    def test_a_failing_callback_is_logged_instead_of_raised(self):
        # The command that stopped paho's network thread: a payload that isn't UTF-8
        on_message = self.mqtt._log_errors(self.mqtt.on_message)
        with self.assertLogs('pi_tracker.net.mqtt', 'ERROR') as logs:
            on_message(self.client, None, FakeMessage('bike1/command', b'\xff\xfe'))
        self.assertIn('MQTT on_message failed', logs.output[0])
        self.assertIn('UnicodeDecodeError', logs.output[0])


if __name__ == '__main__':
    unittest.main()
