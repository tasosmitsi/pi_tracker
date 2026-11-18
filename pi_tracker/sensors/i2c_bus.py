class I2CBusManager:
    """
    Manages a single open SMBus object and shares it among sensors.
    """

    def __init__(self, smbus_module, bus_number):
        self._smbus_module = smbus_module
        self._bus_number = bus_number
        self._bus = None

    def __enter__(self):
        # Open the bus once
        self._bus = self._smbus_module.SMBus(self._bus_number)
        return self._bus  # return the SMBus instance to sensors

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close the bus cleanly
        if self._bus is not None:
            self._bus.close()
        return False  # do not suppress exceptions
