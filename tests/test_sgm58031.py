import unittest

from devices.SGM58031.SGM58031_manager import SGM58031


class FakeADC:
    """Register file behind a pointer, like the SGM58031: register reads start with the MSB."""

    def __init__(self, conversion):
        self.registers = {0: conversion, 1: 0x8583, 2: 0x8000, 3: 0x7FFF}

    def write_word_data(self, address, register, value):
        # SMBus sends the low byte first, so the driver swaps the bytes before writing
        self.registers[register] = ((value & 0xFF) << 8) | (value >> 8)

    def read_byte_data(self, address, register):
        return self.registers[register] >> 8

    def read_i2c_block_data(self, address, register, length):
        value = self.registers[register]
        return [value >> 8, value & 0xFF][:length]


def adc_reading(conversion):
    adc = SGM58031(FakeADC(conversion), 0x48)
    adc.initialize()
    return adc


class ReadTest(unittest.TestCase):
    def test_both_bytes_come_from_the_conversion_register(self):
        self.assertEqual(adc_reading(0x5A3C).SGM58031_SINGLE_READ(0), 0x5A3C)

    def test_a_reading_below_zero_is_negative(self):
        self.assertEqual(adc_reading(0xFFF0).SGM58031_SINGLE_READ(0), -16)

    def test_millivolts(self):
        self.assertEqual(adc_reading(22000).read_data()['AIN0'], 2750.0)  # 22000 * 0.125 mV


if __name__ == '__main__':
    unittest.main()
