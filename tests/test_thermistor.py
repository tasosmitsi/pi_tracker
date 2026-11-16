import math
import unittest

from devices import thermistor


def beta_resistance(temp_c, r25=10000.0, beta=3950.0):
    return r25 * math.exp(beta * (1 / (temp_c + 273.15) - 1 / 298.15))


class ThermistorTest(unittest.TestCase):
    def test_rated_resistance_is_25_degrees(self):
        self.assertAlmostEqual(thermistor.temperature_c(10000, 10000, 3950), 25.0, places=6)

    def test_beta_equation_round_trip(self):
        for temp in (-20, 0, 50, 80):
            with self.subTest(temp=temp):
                ohms = beta_resistance(temp)
                self.assertAlmostEqual(thermistor.temperature_c(ohms, 10000, 3950), temp, places=6)

    def test_known_value(self):
        # A 10k B3950 thermistor is about 3588 ohm at 50 °C
        self.assertAlmostEqual(thermistor.temperature_c(3588, 10000, 3950), 50.0, delta=0.05)

    def test_resistance_with_the_thermistor_to_ground(self):
        # NTC at 5k: 3.3 V * 5k / (10k + 5k) = 1.1 V
        self.assertAlmostEqual(thermistor.resistance(1.1, 3.3, 10000, True), 5000, places=6)

    def test_resistance_with_the_thermistor_to_the_supply(self):
        # NTC at 5k: 3.3 V * 10k / (5k + 10k) = 2.2 V
        self.assertAlmostEqual(thermistor.resistance(2.2, 3.3, 10000, False), 5000, places=6)

    def test_the_defaults_match_the_saddle_circuit(self):
        # 10k divider, NTC to ground: half the supply is 25 °C
        self.assertAlmostEqual(thermistor.temperature_c(thermistor.resistance(1.65)), 25.0, places=6)

    def test_open_or_shorted_gives_none(self):
        for volts in (-0.01, 0, 3.3, 3.4):
            with self.subTest(volts=volts):
                self.assertIsNone(thermistor.resistance(volts, 3.3, 10000, True))

    def test_divider_voltage_to_temperature(self):
        ohms = beta_resistance(10)
        volts = 3.3 * ohms / (ohms + 10000)
        measured = thermistor.resistance(volts, 3.3, 10000, True)
        self.assertAlmostEqual(thermistor.temperature_c(measured, 10000, 3950), 10, places=6)


if __name__ == '__main__':
    unittest.main()
