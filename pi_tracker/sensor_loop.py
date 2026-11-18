"""
The sensor loop: reads the Sense HAT sensors in turn, logs the readings at
DEBUG and publishes the thermistor.

A read that fails is logged and skipped for that round. The other sensors
carry on, and the failed one is read again in the next round.
"""
import json
import logging
import time

from pi_tracker.failure_log import FailureLog
from pi_tracker.sensors import thermistor

log = logging.getLogger(__name__)


class SensorLoop:
    """Reads each sensor once per round. `publish(topic, payload)` sends an MQTT message."""

    def __init__(self, pressure, light, adc, publish, publish_every_s):
        self._steps = [
            (pressure, self._read_pressure, FailureLog('LPS22HB read', log)),
            (light, self._read_light, FailureLog('TCS34725 read', log)),
            (adc, self._read_adc, FailureLog('SGM58031 read', log)),
        ]
        self._publish = publish
        self._publish_every_s = publish_every_s
        self._last_thermistor_post = None

    def run(self, stop_event, delay_s):
        """Read round after round until `stop_event` is set."""
        while not stop_event.is_set():
            self.read_all()
            stop_event.wait(delay_s)

    def read_all(self):
        for sensor, read, failures in self._steps:
            try:
                read(sensor)
            except Exception as e:
                failures.failed(e)
            else:
                failures.succeeded()

    def _read_pressure(self, sensor):
        log.debug("LPS22HB %s", sensor.read_data())

    def _read_light(self, sensor):
        data = sensor.read_data()
        log.debug("TCS34725 R: %d G: %d B: %d C: %#x RGB565: %#x RGB888: %#x LUX: %d CT: %dK INT: %d",
                  data['R'], data['G'], data['B'], data['C'], data['RGB565'],
                  data['RGB888'], data['LUX'], data['CT'], data['INT'])

    def _read_adc(self, sensor):
        adc = sensor.read_data()
        log.debug("SGM58031 %s", adc)
        self._thermistor(adc)

    def _thermistor(self, adc):
        # Thermistor experiment: wiring and circuit values are in pi_tracker/sensors/thermistor.py
        channel, millivolts = thermistor.CHANNEL, adc[thermistor.CHANNEL]
        volts = millivolts / 1000
        ohms = thermistor.resistance(volts)
        if ohms is None:
            log.debug("Thermistor: %s at %.1f mV, open or shorted?", channel, millivolts)
            return
        temp_c = thermistor.temperature_c(ohms)
        log.debug("Thermistor %.2f °C (%s %.1f mV, %.0f ohm)", temp_c, channel, millivolts, ohms)
        now = time.monotonic()
        if self._last_thermistor_post is None or now - self._last_thermistor_post >= self._publish_every_s:
            self._publish('telemetry/thermistor', json.dumps({
                'temperature_c': round(temp_c, 2),
                'voltage_v': round(volts, 4),
                'resistance_ohm': round(ohms),
            }))
            self._last_thermistor_post = now
