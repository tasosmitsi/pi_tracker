# TODO: This does not work currently, needs fixing

# from devices.base_sensor_manager import BaseSensorManager
# import time
# from smbus2 import i2c_msg

# SHTC3_ID = 0xEFC8
# CRC_POLYNOMIAL = 0x0131
# SHTC3_WakeUp = 0x3517
# SHTC3_Sleep = 0xB098
# SHTC3_Software_RES = 0x805D
# SHTC3_NM_CD_ReadTH = 0x7866
# SHTC3_NM_CD_ReadRH = 0x58E0


# class SHTC3(BaseSensorManager):
#     def initialize(self):
#         self.SHTC_SOFT_RESET()

#     def shutdown(self):
#         self.SHTC3_SLEEP()

#     def _cmd(self, cmd):
#         msb = (cmd >> 8) & 0xFF
#         lsb = cmd & 0xFF
#         write = i2c_msg.write(self._address, [msb, lsb])
#         self._bus.i2c_rdwr(write)

#     def SHTC3_WAKEUP(self):
#         self._cmd(SHTC3_WakeUp)
#         time.sleep(0.01)

#     def SHTC3_SLEEP(self):
#         self._cmd(SHTC3_Sleep)
#         time.sleep(0.01)

#     def SHTC_SOFT_RESET(self):
#         self._cmd(SHTC3_Software_RES)
#         time.sleep(0.01)

#     def read_temperature(self):
#         self.SHTC3_WAKEUP()
#         self._cmd(SHTC3_NM_CD_ReadTH)
#         time.sleep(0.02)
#         buf = self._bus.read_i2c_block_data(self._address, 0, 3)
#         if not self.SHTC3_CheckCrc(buf, 2, buf[2]):
#             return None
#         raw = (buf[0] << 8) | buf[1]
#         return raw * 175.0 / 65536.0 - 45.0

#     def read_humidity(self):
#         self.SHTC3_WAKEUP()
#         self._cmd(SHTC3_NM_CD_ReadRH)
#         time.sleep(0.02)
#         buf = self._bus.read_i2c_block_data(self._address, 0, 3)
#         if not self.SHTC3_CheckCrc(buf, 2, buf[2]):
#             return None
#         raw = (buf[0] << 8) | buf[1]
#         return raw * 100.0 / 65536.0

#     def SHTC3_CheckCrc(self, data, len, checksum):
#         crc = 0xFF
#         for byteCtr in range(0, len):
#             crc = crc ^ data[byteCtr]
#             for bit in range(0, 8):
#                 if crc & 0x80:
#                     crc = (crc << 1) ^ CRC_POLYNOMIAL
#                 else:
#                     crc = crc << 1
#         if crc == checksum:
#             return True
#         else:
#             return False
