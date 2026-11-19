"""
Logging

Every record goes to logs/pi_tracker.log in the folder the app runs in, with a
timestamp, rotated by size. Run by hand, it's also printed to stderr. Under
systemd (JOURNAL_STREAM is set) it goes to the file only, or to the journal if
the file can't be written. The level applies to both.
"""
import logging
import logging.handlers
import os
import sys

LOG_FILE = os.path.join('logs', 'pi_tracker.log')
FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'

_console = None
_file = None


def setup(level='INFO', max_kb=1024, backups=5):
    """Log at `level` to the rotating file and, run by hand, to stderr. Call again to change the settings."""
    global _console, _file
    root = logging.getLogger()
    under_systemd = bool(os.environ.get('JOURNAL_STREAM'))

    file_error = None
    if _file is None:
        try:
            os.makedirs(os.path.dirname(LOG_FILE) or '.', exist_ok=True)
            _file = logging.handlers.RotatingFileHandler(LOG_FILE, encoding='utf-8')
            _file.setFormatter(logging.Formatter(FORMAT))
            root.addHandler(_file)
        except OSError as e:
            file_error = e
    if _file is not None:
        _file.maxBytes = max_kb * 1024
        _file.backupCount = backups

    if _console is None and (not under_systemd or _file is None):
        _console = logging.StreamHandler(sys.stderr)
        # the journal adds its own timestamps
        _console.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s' if under_systemd else FORMAT))
        root.addHandler(_console)
    if file_error:
        logging.getLogger(__name__).warning("Can't write the log file %s (%s), logging to stderr only",
                                            LOG_FILE, file_error)

    # getLevelName() maps a known name to its number and anything else to a string
    numeric = logging.getLevelName(str(level).upper())
    if isinstance(numeric, int):
        root.setLevel(numeric)
    else:
        root.setLevel(logging.INFO)
        logging.getLogger(__name__).warning("Unknown log level %r, using INFO", level)
