import types
import unittest
from unittest import mock

from pi_tracker.sensors import lps22hb
from pi_tracker.sensors.lps22hb import LPS22HB

# 1013.25 hPa is 4150272 counts (x 4096), 25.00 °C is 2500 (x 100)
REGISTERS = {0x27: 0x03,                              # STATUS: new pressure and temperature
             0x28: 0x00, 0x29: 0x54, 0x2A: 0x3F,      # PRESS_OUT_XL, _L, _H
             0x2B: 0xC4, 0x2C: 0x09}                  # TEMP_OUT_L, _H


class FakeBus:
    def __init__(self, error=None):
        self.error = error

    def read_byte_data(self, address, register):
        if self.error:
            raise self.error
        return REGISTERS.get(register, 0)

    def write_byte_data(self, address, register, value):
        pass


class ReadDataTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(lps22hb, 'time', types.SimpleNamespace(sleep=lambda s: None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_reading(self):
        self.assertEqual(LPS22HB(FakeBus(), 0x5C).read_data(), {'pressure_hPa': 1013.25, 'temperature_C': 25.0})

    def test_an_i2c_error_is_raised_for_the_sensor_loop(self):
        # It used to be printed and replaced by zeros
        with self.assertRaises(OSError):
            LPS22HB(FakeBus(OSError(121, 'Remote I/O error')), 0x5C).read_data()


if __name__ == '__main__':
    unittest.main()
