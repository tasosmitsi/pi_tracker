"""
NTC thermistor in a voltage divider: divider voltage -> resistance -> temperature.

Wiring: 3.3 V -- 10 kΩ -- node -- NTC -- GND, with the node going to the ADC
input CHANNEL through a 10 kΩ / 100 nF filter, which doesn't change the maths.
"""
import math

CHANNEL = 'AIN3'            # SGM58031 input the divider is wired to
SUPPLY_V = 3.286            # the Sense HAT's 3V3, read on AIN3 with the NTC unplugged (2026-11-14)
FIXED_OHM = 10000.0         # divider resistor between 3.3 V and the node
THERMISTOR_TO_GROUND = True
R25_OHM = 10000.0           # NTC resistance at 25 °C
BETA = 3950.0               # B value from the NTC's datasheet
RAIL_MARGIN = 0.01          # within 1 % of 0 V or the supply means open or shorted (beyond about -52 and +183 °C)

KELVIN = 273.15


def resistance(volts, supply_v=SUPPLY_V, fixed_ohm=FIXED_OHM, to_ground=THERMISTOR_TO_GROUND):
    """Thermistor resistance in ohms, or None if the voltage is too close to a rail: open or shorted."""
    margin = supply_v * RAIL_MARGIN
    if not margin < volts < supply_v - margin:
        return None
    if to_ground:
        return fixed_ohm * volts / (supply_v - volts)
    return fixed_ohm * (supply_v - volts) / volts


def temperature_c(ohms, r25_ohm=R25_OHM, beta=BETA):
    """Beta equation: 1/T = 1/T25 + ln(R/R25)/B, with T in kelvin."""
    return 1 / (1 / (25 + KELVIN) + math.log(ohms / r25_ohm) / beta) - KELVIN
