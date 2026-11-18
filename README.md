# pi_tracker

Anti-theft GPS tracker for an electric fatbike: a Raspberry Pi Zero W with a
PiJuice, a Waveshare Sense HAT (B) and an LTE modem, reporting over MQTT.

## Run
On the Pi, from the repo root (`config.yml` and `certs/` are read from there):

    python3 main.py

`PI_TRACKER_LOG_LEVEL=DEBUG python3 main.py` also logs the sensor readings.

## Test
From the repo root, on the laptop or the Pi:

    python3 -m unittest discover -s tests -t .

Tests that need paho-mqtt, PyGObject or gpiozero skip themselves where those
aren't installed.

## Layout
    main.py              entry point: wiring and the GLib main loop
    config.yml           settings; anything left out falls back to pi_tracker/settings.py
    pi_tracker/
      alarm.py           alarm state, saved to alarm.json on every change
      actions.py         arm_alarm / disarm_alarm
      button.py          PiJuice SW1: a single press arms
      telemetry.py       the telemetry callback and the stats it publishes
      sensor_loop.py     reads the sensors in turn; one that fails is skipped for that round
      workers.py         the sensor-loop thread and the GLib timer wrapper
      failure_log.py     logs a job that keeps failing without flooding the log
      settings.py        settings from config.yml, with a default for each
      log_setup.py       logging to stderr
      net/
        mqtt.py          MQTT client, publishing, commands
        modem.py         ModemManager: the modem and its GPS
        modem_signals.py D-Bus signal listener (unused)
      sensors/
        base.py          base class for the I2C sensor drivers
        i2c_bus.py       the shared I2C bus
        lps22hb.py       pressure and temperature
        sgm58031.py      4-channel ADC
        tcs34725.py      colour and light
        shtc3.py         humidity and temperature (not working yet)
        thermistor.py    NTC maths: ADC voltage to temperature
    tests/               unit tests, no hardware needed
    docs/                datasheets and the Sense HAT schematic
    examples/            Waveshare demo code, for reference only

New code goes in `pi_tracker/`, with absolute imports
(`from pi_tracker.net import mqtt`) and no `import *`. A new folder only once
there are a few modules for it.
