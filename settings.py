"""
Settings for pi_tracker, read from config.yml.

Every setting has a default below, so config.yml only needs the values that
differ. A missing or unreadable config.yml, an unknown key or a value of the
wrong type is logged and the default is used instead.
"""
import dataclasses
import logging

import yaml

log = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class MqttSettings:
    host: str = '192.168.178.203'
    port: int = 4433
    path: str = '/ws'                   # WebSocket path
    client_id: str = 'pi0w'             # also the first level of every topic
    keepalive_s: int = 60
    qos: int = 1
    retain: bool = False
    ca_certs: str = 'certs/ca_certificate.crt'
    certfile: str = 'certs/client_certificate.crt'
    keyfile: str = 'certs/client_private.key'


@dataclasses.dataclass(frozen=True)
class IntervalSettings:
    telemetry_s: int = 5                # GLib timers only take whole seconds
    button_poll_s: int = 2
    sensor_loop_s: float = 0.5


@dataclasses.dataclass(frozen=True)
class LogSettings:
    level: str = 'INFO'


@dataclasses.dataclass(frozen=True)
class Settings:
    mqtt: MqttSettings = dataclasses.field(default_factory=MqttSettings)
    intervals: IntervalSettings = dataclasses.field(default_factory=IntervalSettings)
    log: LogSettings = dataclasses.field(default_factory=LogSettings)


current = Settings()


def load(path):
    """Read `path` and return a Settings, using defaults for anything missing or wrong."""
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        log.warning("%s not found, using the default settings", path)
        raw = None
    except (OSError, yaml.YAMLError) as e:
        log.error("Can't read %s, using the default settings: %s", path, e)
        raw = None

    if raw is None:  # also what an empty file gives
        raw = {}
    return _build(Settings, raw, path, '')


def _build(cls, raw, path, prefix):
    if not isinstance(raw, dict):
        log.error("%s: %s should be a mapping, using its defaults", path, prefix.rstrip('.') or 'the file')
        raw = {}

    names = [f.name for f in dataclasses.fields(cls)]
    for key in raw:
        if key not in names:
            log.warning("%s: unknown setting %s%s, ignored", path, prefix, key)

    defaults = cls()
    values = {}
    for name in names:
        if name not in raw:
            continue
        default = getattr(defaults, name)
        value = raw[name]
        if dataclasses.is_dataclass(default):
            values[name] = _build(type(default), value, path, prefix + name + '.')
        elif _same_type(value, default):
            values[name] = type(default)(value)
        else:
            log.warning("%s: %s%s should be %s, not %r; using %r",
                        path, prefix, name, type(default).__name__, value, default)
    return cls(**values)


def _same_type(value, default):
    # bool is a subclass of int, so true/false must not pass as numbers
    if isinstance(default, bool) or isinstance(value, bool):
        return isinstance(default, bool) and isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float))  # 1 is fine where 1.0 is expected
    return type(value) is type(default)
