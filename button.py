"""
The PiJuice SW1 button: a single press arms the alarm.

The button can only arm, never disarm, so whoever has the bike in their hands
can't switch the alarm off. Disarming is done remotely over MQTT.
"""
import logging

from actions import arm_alarm

log = logging.getLogger(__name__)

_last_error = None  # last error the PiJuice reported, so it is logged only once


def check_button(pijuice):
    """Read the button events once and act on them. Runs from a GLib timer, so it must not block."""
    global _last_error
    events = pijuice.status.GetButtonEvents()

    error = events.get('error')
    if error != 'NO_ERROR':
        if error != _last_error:
            log.warning("Can't read the PiJuice button events: %s", error)
            _last_error = error
        return True
    if _last_error is not None:
        log.info("PiJuice button events can be read again")
        _last_error = None

    if events.get('data', {}).get('SW1') == 'SINGLE_PRESS':
        log.info("SW1 pressed")
        arm_alarm()  # only does something while the alarm is un-armed
        pijuice.status.AcceptButtonEvent('SW1')

    # Other SW1 events are left alone: the PiJuice software uses long presses
    # to halt or power off the Pi.
    return True
