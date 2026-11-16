import importlib.util
import types
import unittest
from unittest import mock

# The driver imports gpiozero for its interrupt pin.
HAVE_GPIOZERO = importlib.util.find_spec('gpiozero') is not None

ENABLE, ATIME, ID, STATUS = 0x00, 0x01, 0x12, 0x13
AEN, AVALID = 0x02, 0x01
DATA = {0x14: 'C', 0x16: 'R', 0x18: 'G', 0x1A: 'B'}


class FakeTCS34725:
    """Registers on a fake clock: after AEN is set, the data read 0 until the first integration has ended."""

    def __init__(self, C, R, G, B, stuck=False):
        self.counts = {'C': C, 'R': R, 'G': G, 'B': B}
        self.stuck = stuck
        self.now = 0.0
        self.atime = 0xFF
        self.enable = 0
        self.started = None

    def sleep(self, seconds):
        self.now += seconds

    def valid(self):
        # 2.4 ms start-up, then (256 - ATIME) steps of 2.4 ms
        return (not self.stuck and self.started is not None
                and self.now - self.started >= 0.0024 * (257 - self.atime))

    def write_byte_data(self, address, command, value):
        register = command & 0x1F
        if command & 0x60 == 0x60:  # special function: clear interrupt
            return
        if register == ATIME:
            self.atime = value
        elif register == ENABLE:
            if value & AEN and not self.enable & AEN:
                self.started = self.now
            self.enable = value

    def read_byte_data(self, address, command):
        register = command & 0x1F
        if register == ID:
            return 0x44
        if register == STATUS:
            return AVALID if self.valid() else 0
        return self.enable if register == ENABLE else 0

    def read_word_data(self, address, command):
        return self.counts[DATA[command & 0x1F]] if self.valid() else 0


def first_reading(chip):
    """Start the driver the way main.py does and return its first reading."""
    from devices.TCS34725 import TCS34725_manager as driver
    with mock.patch.object(driver, 'time', types.SimpleNamespace(sleep=chip.sleep)), \
            mock.patch.object(driver, 'DigitalInputDevice'):
        with driver.TCS34725(chip, 0x29) as sensor:
            return sensor.read_data()


@unittest.skipUnless(HAVE_GPIOZERO, 'gpiozero is not installed')
class FirstReadingTest(unittest.TestCase):
    def test_the_first_reading_after_power_up_is_real(self):
        data = first_reading(FakeTCS34725(C=3000, R=1000, G=1200, B=500))
        self.assertEqual(data['C'], 3000)
        self.assertAlmostEqual(data['CT'], 3296.0)  # 3810 * 500 / 1000 + 1391

    def test_no_colour_temperature_without_red_light(self):
        for counts in (dict(C=0, R=0, G=0, B=0),          # dark
                       dict(C=0, R=1, G=1, B=1),          # red cancels out with the IR estimate
                       dict(C=900, R=10, G=500, B=500)):  # less red than IR
            with self.subTest(**counts):
                self.assertEqual(first_reading(FakeTCS34725(**counts))['CT'], 0)

    def test_a_sensor_that_never_finishes_a_reading_only_warns(self):
        with self.assertLogs('devices.TCS34725.TCS34725_manager', 'WARNING'):
            data = first_reading(FakeTCS34725(C=3000, R=1000, G=1200, B=500, stuck=True))
        self.assertEqual(data['CT'], 0)


if __name__ == '__main__':
    unittest.main()
