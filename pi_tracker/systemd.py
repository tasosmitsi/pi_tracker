"""
Talking to systemd when it runs the tracker (deploy/pi-tracker@.service).

notify() tells systemd the app has started, and Watchdog keeps systemd's
watchdog fed. Run by hand there's no NOTIFY_SOCKET, and both do nothing.
"""
import logging
import os
import socket
import time

log = logging.getLogger(__name__)


def notify(message):
    """Send `message`, e.g. 'READY=1', to systemd's notify socket. False when not run by systemd."""
    address = os.environ.get('NOTIFY_SOCKET')
    if not address:
        return False
    if address.startswith('@'):  # abstract socket
        address = '\0' + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(message.encode())
        return True
    except OSError as e:
        log.warning("Can't notify systemd: %s", e)
        return False


def watchdog_interval_s():
    """How often to feed systemd's watchdog (half its WatchdogSec), or None when there's no watchdog."""
    usec = os.environ.get('WATCHDOG_USEC')
    pid = os.environ.get('WATCHDOG_PID')
    if not usec or (pid and int(pid) != os.getpid()):
        return None
    return int(usec) / 1e6 / 2


class Watchdog:
    """Feeds systemd's watchdog from a GLib timer, but only while the sensor loop keeps finishing rounds.

    A stuck GLib loop stops the timer and a stuck sensor loop stops the rounds;
    either way the feeding stops and systemd restarts the app.
    """

    def __init__(self, max_round_age_s):
        self.max_round_age_s = max_round_age_s
        self.last_round = time.monotonic()

    def round_done(self):
        self.last_round = time.monotonic()

    def feed(self):
        age = time.monotonic() - self.last_round
        if age <= self.max_round_age_s:
            notify('WATCHDOG=1')
        else:
            log.error("No sensor round for %.0f s, so the watchdog isn't fed; systemd will restart the app", age)
        return True  # keep the timer
