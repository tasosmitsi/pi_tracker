# pi_tracker

Anti-theft GPS tracker for an electric fatbike: a Raspberry Pi Zero W with a
PiJuice, a Waveshare Sense HAT (B) and an LTE modem, reporting over MQTT.

## Run
On the Pi, from the repo root (`config.yml` and `certs/` are read from there):

    python3 main.py

`PI_TRACKER_LOG_LEVEL=DEBUG python3 main.py` also logs the sensor readings.

Everything is logged to `logs/pi_tracker.log` in the folder the app runs in, and
run by hand it's printed as well. The file rotates at 1 MB and keeps 5 old ones
(`log` in `config.yml`). If you sync with autosync, exclude `logs/` from its rsync
(`--exclude 'logs/'`), or its `--delete` removes the Pi's logs.

## Run as a service
`deploy/pi-tracker@.service` starts the tracker at boot, as your user, from
`~/pi_tracker` with the venv in `~/pi_tracker/.venv`. It restarts the tracker
when it fails or hangs:

    sudo cp deploy/pi-tracker@.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now pi-tracker@$USER

- Log: `tail -f ~/pi_tracker/logs/pi_tracker.log`. systemd's own lines (starts, restarts,
  watchdog timeouts) are in `journalctl -u pi-tracker@$USER`. State: `systemctl status pi-tracker@$USER`.
- After autosync has brought new code: `sudo systemctl restart pi-tracker@$USER`.
- Stop the service before running `python3 main.py` by hand. Two copies share the
  MQTT client id and keep pushing each other off the broker, and both drive the sensors.
- No venv? Change `ExecStart` in the unit to `/usr/bin/python3 main.py`.
- pip packages are in `requirements.txt`. PyGObject, libmm-glib
  (`gir1.2-modemmanager-1.0`), the PiJuice software and lgpio come from apt, so
  make the venv with `--system-site-packages`.

## Test
From the repo root, on the laptop or the Pi:

    python3 -m unittest discover -s tests -t .

Tests that need paho-mqtt, PyGObject or gpiozero skip themselves where those
aren't installed.

## Layout
    main.py              entry point: wiring and the GLib main loop
    config.yml           settings; anything left out falls back to pi_tracker/settings.py
    requirements.txt     pip packages for the venv
    logs/                pi_tracker.log and its rotated copies (not in git)
    deploy/
      pi-tracker@.service  the systemd service
    pi_tracker/
      alarm.py           alarm state, saved to alarm.json on every change
      actions.py         arm_alarm / disarm_alarm
      button.py          PiJuice SW1: a single press arms
      telemetry.py       the telemetry callback and the stats it publishes
      sensor_loop.py     starts and reads the sensors; one that fails is tried again next round
      workers.py         the GLib timer wrapper, and running the worker threads until SIGINT/SIGTERM
      failure_log.py     logs a job that keeps failing without flooding the log
      systemd.py         tells systemd the app is ready, and feeds its watchdog
      settings.py        settings from config.yml, with a default for each
      log_setup.py       logging to logs/pi_tracker.log, and to the terminal when run by hand
      net/
        mqtt.py          MQTT client, publishing, commands
        modem.py         ModemManager: finds the modem and follows it, GPS on/off
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
