import json
import unittest

from pi_tracker.sensor_loop import SensorLoop

PRESSURE = {'pressure_hPa': 1017.37, 'temperature_C': 28.74}
LIGHT = {'R': 253, 'G': 251, 'B': 196, 'C': 0xbbce, 'RGB565': 0xffd8, 'RGB888': 0xfdfbc4,
         'LUX': 415, 'CT': 4441, 'INT': 0}
ADC = {'AIN0': 120.125, 'AIN1': 120.375, 'AIN2': 120.125, 'AIN3': 1574.625}  # your log of 2026-11-14: 27.07 °C
I2C_ERROR = OSError(121, 'Remote I/O error')


class FakeSensor:
    """Gives the readings in turn, then keeps giving the last one. A reading that is an exception is raised."""

    def __init__(self, *readings):
        self.readings = list(readings)
        self.reads = 0

    def read_data(self):
        self.reads += 1
        reading = self.readings.pop(0) if len(self.readings) > 1 else self.readings[0]
        if isinstance(reading, Exception):
            raise reading
        return reading


class Rounds:
    """Stands in for the stop event: lets run() go round `n` times without waiting."""

    def __init__(self, n):
        self.left = n

    def is_set(self):
        self.left -= 1
        return self.left < 0

    def wait(self, timeout):
        pass


class SensorLoopTest(unittest.TestCase):
    def setUp(self):
        self.pressure, self.light, self.adc = FakeSensor(PRESSURE), FakeSensor(LIGHT), FakeSensor(ADC)
        self.published = []

    def sensor_loop(self):
        return SensorLoop(self.pressure, self.light, self.adc,
                          publish=lambda topic, payload: self.published.append((topic, json.loads(payload))),
                          publish_every_s=5)

    def test_a_failing_sensor_does_not_stop_the_others(self):
        self.pressure = FakeSensor(I2C_ERROR)
        with self.assertLogs('pi_tracker.sensor_loop', 'ERROR') as logs:
            self.sensor_loop().read_all()
        self.assertEqual((self.light.reads, self.adc.reads), (1, 1))
        self.assertIn('LPS22HB read failed', logs.output[0])
        self.assertIn('Remote I/O error', logs.output[0])

    def test_the_loop_goes_on_after_a_failure_and_logs_the_recovery(self):
        self.light = FakeSensor(ZeroDivisionError('float division by zero'), LIGHT)
        with self.assertLogs('pi_tracker.sensor_loop', 'INFO') as logs:
            self.sensor_loop().run(Rounds(3), 0.5)
        self.assertEqual((self.pressure.reads, self.light.reads, self.adc.reads), (3, 3, 3))
        self.assertIn('TCS34725 read works again after 1 failures', logs.output[-1])

    def test_a_repeated_error_is_logged_once_then_after_10_failures(self):
        self.light = FakeSensor(I2C_ERROR)
        with self.assertLogs('pi_tracker.sensor_loop', 'ERROR') as logs:
            self.sensor_loop().run(Rounds(10), 0.5)
        self.assertEqual(len(logs.output), 2)
        self.assertIn('Traceback', logs.output[0])
        self.assertIn('10 times in a row', logs.output[1])

    def test_the_thermistor_is_published_once_per_interval(self):
        sensor_loop = self.sensor_loop()
        sensor_loop.read_all()
        sensor_loop.read_all()
        self.assertEqual(self.published, [('telemetry/thermistor',
                                           {'temperature_c': 27.07, 'voltage_v': 1.5746, 'resistance_ohm': 9126})])

    def test_no_thermistor_message_when_the_adc_read_fails(self):
        self.adc = FakeSensor(I2C_ERROR)
        with self.assertLogs('pi_tracker.sensor_loop', 'ERROR'):
            self.sensor_loop().read_all()
        self.assertEqual(self.published, [])


if __name__ == '__main__':
    unittest.main()
