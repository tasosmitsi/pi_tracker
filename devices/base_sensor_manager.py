class BaseSensorManager:
    """
    Base class for I²C sensors using a shared SMBus instance.
    """

    def __init__(self, bus, address, **kwargs):
        """
        bus: SMBus object (shared)
        address: I2C device address
        kwargs: sensor-specific options like debug, mode, etc.
        """
        self._bus = bus
        self._address = address
        self._options = kwargs  # store for subclasses

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.shutdown()
        except Exception:
            pass
        return False  # do not suppress exceptions

    # Methods sensors override
    def initialize(self):
        pass

    def shutdown(self):
        pass
