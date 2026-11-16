"""
The alarm state, kept in a small JSON file so it survives a restart.

Without the file a power cycle would disarm the tracker, which is exactly
what a thief would try. The file is written atomically (temporary file,
fsync, rename), so a power cut while saving leaves either the old or the
new state on disk, never half a file.

States: 0 un-armed, 1 armed, 3 panic. Nothing sets panic yet and 2 is not
assigned.

main.py loads the saved state at start-up into `current`. Other modules use
`alarm.current`; don't use `from alarm import current`, that copy would never
see the loaded state.
"""
import datetime
import json
import logging
import os
import threading

log = logging.getLogger(__name__)

DISARMED = 0
ARMED = 1
PANIC = 3
NAMES = {DISARMED: 'disarmed', ARMED: 'armed', PANIC: 'panic'}

FILE_NAME = 'alarm.json'


class AlarmState:
    """Thread-safe alarm state. With a path it is loaded from and saved to that file."""

    def __init__(self, path=None):
        self.path = path
        self._lock = threading.Lock()
        self._state = self._load() if path else DISARMED

    @property
    def state(self):
        return self._state

    def arm(self):
        """Arm, but only from un-armed. Returns True if the state changed."""
        with self._lock:
            if self._state != DISARMED:
                return False
            self._set(ARMED)
            return True

    def disarm(self):
        """Disarm from any state. Returns True if the state changed."""
        with self._lock:
            if self._state == DISARMED:
                return False
            self._set(DISARMED)
            return True

    def _set(self, state):
        self._state = state
        if self.path:
            self._save()

    def _load(self):
        try:
            with open(self.path) as f:
                saved = json.load(f)['alarm_state']
        except FileNotFoundError:
            log.info("No saved alarm state in %s, starting disarmed", self.path)
            return DISARMED
        except (OSError, ValueError, KeyError, TypeError) as e:
            # The file exists, so the alarm may well have been armed: stay on the safe side
            log.error("Can't read the saved alarm state in %s (%s), starting armed", self.path, e)
            return ARMED

        if type(saved) is not int or saved not in NAMES:
            log.error("Unknown alarm state %r in %s, starting armed", saved, self.path)
            return ARMED
        log.info("Alarm is %s (saved in %s)", NAMES[saved], self.path)
        return saved

    def _save(self):
        data = {
            'alarm_state': self._state,
            'changed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        }
        try:
            _write_atomically(self.path, json.dumps(data) + '\n')
        except OSError as e:
            log.error("Can't save the alarm state to %s: %s. It only holds until the next restart.",
                      self.path, e)


current = AlarmState()


def _write_atomically(path, text):
    directory = os.path.dirname(path) or '.'
    os.makedirs(directory, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    # fsync the directory too, so the rename itself survives a power cut
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
