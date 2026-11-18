"""
The sensor loop: starts the Sense HAT sensors, reads them in turn, logs the
readings at DEBUG and publishes the thermistor.

A sensor that fails to start or to read is logged and skipped for that
round. The other sensors carry on, and the failed one is tried again in the
next round.
"""
import json
import logging
import time

from pi_tracker.failure_log import FailureLog
from pi_tracker.sensors import thermistor

log = logging.getLogger(__name__)


class _Step:
    """One sensor in the loop: whether it has started, and its failures."""

    def __init__(self, name, sensor, read):
        self.name = name
        self.sensor = sensor
        self.read = read
        self.started = False
        self.failures = FailureLog(name, log)


class SensorLoop:
    """Starts and reads each sensor once per round. `publish(topic, payload)` sends an MQTT message."""

    def __init__(self, pressure, light, adc, publish, publish_every_s):
        self._steps = [
            _Step('LPS22HB', pressure, self._read_pressure),
            _Step('TCS34725', light, self._read_light),
            _Step('SGM58031', adc, self._read_adc),
        ]
        self._publish = publish
        self._publish_every_s = publish_every_s
        self._last_thermistor_post = None

    def run(self, stop_event, delay_s):
        """Read round after round until `stop_event` is set, then shut down the sensors that started."""
        try:
            while not stop_event.is_set():
                self.read_all()
                stop_event.wait(delay_s)
        finally:
            self._shutdown()

    def read_all(self):
        for step in self._steps:
            try:
                if not step.started:
                    step.sensor.initialize()
                    step.started = True
                step.read(step.sensor)
            except Exception as e:
                step.failures.failed(e)
            else:
                step.failures.succeeded()

    def _shutdown(self):
        for step in self._steps:
            if step.started:
                try:
                    step.sensor.shutdown()
                except Exception as e:
                    log.warning("%s didn't shut down cleanly: %s", step.name, e)

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
