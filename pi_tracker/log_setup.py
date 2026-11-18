"""
Logging

Everything goes to stderr. When run by hand each line gets a timestamp; under
systemd the journal adds its own, so it is left out there.
"""
import logging
import os
import sys

_handler = None


def setup(level='INFO'):
    """Send log records to stderr at `level`. Call again to change the level."""
    global _handler
    root = logging.getLogger()

    if _handler is None:
        _handler = logging.StreamHandler(sys.stderr)
        if os.environ.get('JOURNAL_STREAM'):
            fmt = '%(levelname)s %(name)s: %(message)s'
        else:
            fmt = '%(asctime)s %(levelname)s %(name)s: %(message)s'
        _handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(_handler)

    # getLevelName() maps a known name to its number and anything else to a string
    numeric = logging.getLevelName(str(level).upper())
    if isinstance(numeric, int):
        root.setLevel(numeric)
    else:
        root.setLevel(logging.INFO)
        logging.getLogger(__name__).warning("Unknown log level %r, using INFO", level)
