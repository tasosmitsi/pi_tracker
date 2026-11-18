import importlib.util
import json
import types
import unittest

from pi_tracker import alarm, settings

# telemetry.py publishes through pi_tracker/net/mqtt.py, which needs paho-mqtt.
HAVE_PAHO = importlib.util.find_spec('paho') is not None


class FakeClient:
    def __init__(self):
        self.published = []

    def is_connected(self):
        return True

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload))


class FakePiJuice:
    """Every status call answers like the PiJuice library, or raises `error` when given one."""

    def __init__(self, error=None):
        def answer(*args):
            if error:
                raise error
            return {'data': 1, 'error': 'NO_ERROR'}
        self.status = types.SimpleNamespace(**{name: answer for name in (
            'GetStatus', 'GetChargeLevel', 'GetFaultStatus', 'GetButtonEvents', 'GetBatteryTemperature',
            'GetBatteryVoltage', 'GetBatteryCurrent', 'GetIoVoltage', 'GetIoCurrent')})


@unittest.skipUnless(HAVE_PAHO, 'paho-mqtt is not installed')
class TelemetryTest(unittest.TestCase):
    def setUp(self):
        from pi_tracker import telemetry
        self.telemetry = telemetry.telemetry
        self.saved = settings.current, alarm.current
        settings.current = settings.Settings(mqtt=settings.MqttSettings(client_id='bike1'))
        alarm.current = alarm.AlarmState()
        self.client = FakeClient()
        self.no_modem = types.SimpleNamespace(modem=None)

    def tearDown(self):
        settings.current, alarm.current = self.saved

    def test_without_a_modem_telemetry_still_goes_out(self):
        self.assertTrue(self.telemetry(self.client, self.no_modem, FakePiJuice()))
        topics = [topic for topic, payload in self.client.published]
        self.assertEqual(topics, ['bike1/telemetry/alarm_state', 'bike1/telemetry/modem',
                                  'bike1/telemetry/power_management'])
        self.assertEqual(json.loads(self.client.published[1][1]), {'present': False})

    def test_the_alarm_state_goes_out_even_when_the_pijuice_fails(self):
        with self.assertRaises(OSError):  # the GLib timer logs it and runs again
            self.telemetry(self.client, self.no_modem, FakePiJuice(OSError(121, 'Remote I/O error')))
        self.assertEqual(self.client.published[0], ('bike1/telemetry/alarm_state', 0))


if __name__ == '__main__':
    unittest.main()
