"""
NTC thermistor in a voltage divider: divider voltage -> resistance -> temperature.

Wiring: 3.3 V -- 10 kΩ -- node -- NTC -- GND, with the node going to AIN0
through a 10 kΩ / 100 nF filter, which doesn't change the maths.
"""
import math

SUPPLY_V = 3.3              # 3V3 from the Sense HAT; measure it for better accuracy
FIXED_OHM = 10000.0         # divider resistor between 3.3 V and the node
THERMISTOR_TO_GROUND = True
R25_OHM = 10000.0           # NTC resistance at 25 °C
BETA = 3950.0               # B value from the NTC's datasheet

KELVIN = 273.15


def resistance(volts, supply_v=SUPPLY_V, fixed_ohm=FIXED_OHM, to_ground=THERMISTOR_TO_GROUND):
    """Thermistor resistance in ohms, or None if the voltage says open or shorted."""
    if not 0 < volts < supply_v:
        return None
    if to_ground:
        return fixed_ohm * volts / (supply_v - volts)
    return fixed_ohm * (supply_v - volts) / volts


def temperature_c(ohms, r25_ohm=R25_OHM, beta=BETA):
    """Beta equation: 1/T = 1/T25 + ln(R/R25)/B, with T in kelvin."""
    return 1 / (1 / (25 + KELVIN) + math.log(ohms / r25_ohm) / beta) - KELVIN
