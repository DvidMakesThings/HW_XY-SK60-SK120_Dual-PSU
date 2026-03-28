import struct
import serial
import threading
import time


class ModbusPSU:
    """Driver for Sinilink XY-SK60/SK120 buck-boost converter via Modbus RTU."""

    # Register map: name -> (address, decimals_divisor)
    # Divisor: 100 means value/100 (e.g. 2400 -> 24.00V)
    REG_V_SET       = 0x0000
    REG_I_SET       = 0x0001
    REG_VOUT        = 0x0002
    REG_IOUT        = 0x0003
    REG_POWER       = 0x0004
    REG_UIN         = 0x0005
    REG_AH_LOW      = 0x0006
    REG_AH_HIGH     = 0x0007
    REG_WH_LOW      = 0x0008
    REG_WH_HIGH     = 0x0009
    REG_OUT_H       = 0x000A
    REG_OUT_M       = 0x000B
    REG_OUT_S       = 0x000C
    REG_T_IN        = 0x000D
    REG_T_EX        = 0x000E
    REG_LOCK        = 0x000F
    REG_PROTECT     = 0x0010
    REG_CVCC        = 0x0011
    REG_ONOFF       = 0x0012
    REG_F_C         = 0x0013
    REG_B_LED       = 0x0014
    REG_SLEEP       = 0x0015
    REG_MODEL       = 0x0016
    REG_VERSION     = 0x0017
    REG_SLAVE_ADDR  = 0x0018
    REG_BAUDRATE    = 0x0019
    REG_T_IN_CAL    = 0x001A
    REG_T_EXT_CAL   = 0x001B
    REG_BEEPER      = 0x001C
    REG_EXTRACT_M   = 0x001D
    REG_SYS_STATUS  = 0x001E
    REG_MPPT_ENABLE = 0x001F
    REG_MPPT_THRESH = 0x0020
    REG_BTF         = 0x0021
    REG_CP_ENABLE   = 0x0022
    REG_CP_SET      = 0x0023
    REG_FACTORY_RST = 0x0025

    # Protection registers
    REG_S_OVP       = 0x0053
    REG_S_OCP       = 0x0054
    REG_S_OPP       = 0x0055
    REG_S_OHP_H     = 0x0056
    REG_S_OHP_M     = 0x0057
    REG_S_OAH_L     = 0x0058
    REG_S_OAH_H     = 0x0059
    REG_S_OWH_L     = 0x005A
    REG_S_OWH_H     = 0x005B
    REG_S_OTP       = 0x005C
    REG_S_INI       = 0x005D
    REG_S_LVP       = 0x0052

    BAUD_MAP = {
        0: 9600, 1: 14400, 2: 19200, 3: 38400,
        4: 56000, 5: 57600, 6: 115200, 7: 2400, 8: 4800
    }

    def __init__(self, port, baudrate=115200, address=1, name="PSU"):
        self.port_path = port
        self.baudrate = baudrate
        self.address = address
        self.name = name
        self.lock = threading.Lock()
        self._ser = None
        self._cache = {}
        self._cache_time = 0
        self._cache_ttl = 5.0
        self._readings_cache = {}
        self._readings_cache_time = 0
        self._readings_cache_ttl = 0.2
        self._connect()

    def _connect(self):
        try:
            self._ser = serial.Serial(
                self.port_path, self.baudrate, timeout=0.15,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
        except Exception:
            self._ser = None

    @property
    def connected(self):
        return self._ser is not None and self._ser.is_open

    @staticmethod
    def _crc16(data):
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return struct.pack('<H', crc)

    def _build_read_frame(self, start_reg, count):
        frame = struct.pack('>BBHH', self.address, 0x03, start_reg, count)
        return frame + self._crc16(frame)

    def _build_write_frame(self, reg, value):
        frame = struct.pack('>BBHH', self.address, 0x06, reg, value & 0xFFFF)
        return frame + self._crc16(frame)

    def _send_recv(self, frame, expect_len=None):
        if not self.connected:
            self._connect()
            if not self.connected:
                return None
        try:
            self._ser.reset_input_buffer()
            self._ser.write(frame)
            # Read expected bytes using serial timeout (0.15s)
            n = expect_len or 64
            resp = self._ser.read(n)
            if len(resp) < 5:
                return None
            return resp
        except Exception:
            self._ser = None
            return None

    def read_registers(self, start, count):
        """Read count holding registers starting at start. Returns list of uint16 or None."""
        with self.lock:
            frame = self._build_read_frame(start, count)
            expect = 5 + count * 2
            resp = self._send_recv(frame, expect)
            if resp is None or len(resp) < expect:
                return None
            if resp[0] != self.address or resp[1] != 0x03:
                return None
            byte_count = resp[2]
            if byte_count != count * 2:
                return None
            values = []
            for i in range(count):
                val = struct.unpack('>H', resp[3 + i*2 : 5 + i*2])[0]
                values.append(val)
            return values

    def write_register(self, reg, value):
        """Write a single holding register. Returns True on success."""
        with self.lock:
            frame = self._build_write_frame(reg, value)
            resp = self._send_recv(frame, 8)
            self._cache_time = 0  # invalidate cache
            if resp is None or len(resp) < 8:
                return False
            if resp[0] != self.address or resp[1] != 0x06:
                return False
            return True

    def get_readings(self):
        """Read live measurements and basic status. Returns dict or None."""
        # Chunk 1: regs 0x00-0x09
        c1 = self.read_registers(0x00, 10)
        if c1 is None:
            return None
        # Chunk 2: regs 0x0A-0x13
        c2 = self.read_registers(0x0A, 10)
        if c2 is None:
            return None

        t_ex = c2[4]
        ext_temp = None if t_ex == 8888 else t_ex / 10.0
        ah = (c1[7] << 16) | c1[6]
        wh = (c1[9] << 16) | c1[8]
        out_secs = c2[0] * 3600 + c2[1] * 60 + c2[2]

        return {
            'v_set': c1[0] / 100.0,
            'i_set': c1[1] / 1000.0,
            'v_out': c1[2] / 100.0,
            'i_out': c1[3] / 1000.0,
            'power': c1[4] / 100.0,
            'v_in': c1[5] / 100.0,
            'ah': ah,
            'wh': wh,
            'out_hours': c2[0],
            'out_mins': c2[1],
            'out_secs': c2[2],
            'out_total_secs': out_secs,
            'temp_int': c2[3] / 10.0,
            'temp_ext': ext_temp,
            'lock': bool(c2[5]),
            'protect': c2[6],
            'cvcc': c2[7],  # 0=CV, 1=CC
            'output_on': bool(c2[8]),
            'temp_unit': 'F' if c2[9] else 'C',
        }

    def get_settings(self):
        """Read device settings. Returns dict or None."""
        c3 = self.read_registers(0x14, 10)
        if c3 is None:
            return None
        c4 = self.read_registers(0x1E, 6)
        if c4 is None:
            return None

        baud_idx = c3[5]
        model_raw = c3[2]
        model_str = struct.pack('>H', model_raw).decode('ascii', errors='replace')

        return {
            'backlight': c3[0],
            'sleep_min': c3[1],
            'model_raw': model_raw,
            'model': model_str,
            'version_raw': c3[3],
            'version': '%d.%02d' % (c3[3] // 100, c3[3] % 100),
            'slave_addr': c3[4],
            'baud_index': baud_idx,
            'baudrate': self.BAUD_MAP.get(baud_idx, 0),
            'temp_cal_int': c3[6] / 10.0,
            'temp_cal_ext': c3[7] / 10.0,
            'beeper': bool(c3[8]),
            'data_group': c3[9],
            'sys_status': c4[0],
            'mppt_enabled': bool(c4[1]),
            'mppt_threshold': c4[2] / 100.0,
            'btf': c4[3] / 1000.0,
            'cp_enabled': bool(c4[4]),
            'cp_set': c4[5] / 10.0,
        }

    def get_protection(self):
        """Read protection settings. Returns dict or None."""
        c5 = self.read_registers(0x50, 10)
        if c5 is None:
            return None
        c6 = self.read_registers(0x5A, 4)
        if c6 is None:
            return None
        oah = (c5[9] << 16) | c5[8]
        owh = (c6[1] << 16) | c6[0]
        return {
            'cv_set': c5[0] / 100.0,
            'cc_set': c5[1] / 1000.0,
            'lvp': c5[2] / 100.0,
            'ovp': c5[3] / 100.0,
            'ocp': c5[4] / 1000.0,
            'opp': c5[5] / 10.0,
            'ohp_h': c5[6],
            'ohp_m': c5[7],
            'oah': oah,
            'owh': owh,
            'otp': c6[2] / 10.0,
            'power_on_init': bool(c6[3]),
        }

    def get_readings_cached(self):
        """Get readings with a short-lived cache for fast polling."""
        now = time.time()
        if self._readings_cache and (now - self._readings_cache_time) < self._readings_cache_ttl:
            return self._readings_cache
        r = self.get_readings()
        if r is not None:
            self._readings_cache = r
            self._readings_cache_time = now
        return self._readings_cache or r

    def get_full_status(self, use_cache=True):
        """Get complete device status. Uses cache if recent enough."""
        now = time.time()
        if use_cache and self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        readings = self.get_readings()
        if readings is None:
            return self._cache or {'error': 'Communication failed'}

        settings = self.get_settings()
        protection = self.get_protection()

        status = {'name': self.name, 'port': self.port_path, 'connected': True}
        status.update(readings)
        if settings:
            status.update(settings)
        if protection:
            status['protection'] = protection

        self._cache = status
        self._cache_time = now
        return status

    # --- Write methods ---

    def set_voltage(self, volts):
        """Set output voltage in volts (e.g. 12.00)."""
        raw = int(round(volts * 100))
        return self.write_register(self.REG_V_SET, raw)

    def set_current(self, amps):
        """Set output current limit in amps (e.g. 1.500)."""
        raw = int(round(amps * 1000))
        return self.write_register(self.REG_I_SET, raw)

    def set_output(self, on):
        return self.write_register(self.REG_ONOFF, 1 if on else 0)

    def set_lock(self, locked):
        return self.write_register(self.REG_LOCK, 1 if locked else 0)

    def set_backlight(self, level):
        level = max(0, min(5, int(level)))
        return self.write_register(self.REG_B_LED, level)

    def set_sleep(self, minutes):
        return self.write_register(self.REG_SLEEP, int(minutes))

    def set_beeper(self, on):
        return self.write_register(self.REG_BEEPER, 1 if on else 0)

    def set_temp_unit(self, fahrenheit):
        return self.write_register(self.REG_F_C, 1 if fahrenheit else 0)

    def set_mppt(self, enabled):
        return self.write_register(self.REG_MPPT_ENABLE, 1 if enabled else 0)

    def set_mppt_threshold(self, ratio):
        raw = int(round(ratio * 100))
        return self.write_register(self.REG_MPPT_THRESH, raw)

    def set_btf(self, amps):
        raw = int(round(amps * 1000))
        return self.write_register(self.REG_BTF, raw)

    def set_cp_enabled(self, on):
        return self.write_register(self.REG_CP_ENABLE, 1 if on else 0)

    def set_cp_power(self, watts):
        raw = int(round(watts * 10))
        return self.write_register(self.REG_CP_SET, raw)

    def set_power_on_init(self, output_on):
        return self.write_register(self.REG_S_INI, 1 if output_on else 0)

    def set_ovp(self, volts):
        raw = int(round(volts * 100))
        return self.write_register(self.REG_S_OVP, raw)

    def set_ocp(self, amps):
        raw = int(round(amps * 1000))
        return self.write_register(self.REG_S_OCP, raw)

    def set_opp(self, watts):
        raw = int(round(watts * 10))
        return self.write_register(self.REG_S_OPP, raw)

    def set_otp(self, temp_c):
        raw = int(round(temp_c * 10))
        return self.write_register(self.REG_S_OTP, raw)

    def set_lvp(self, volts):
        raw = int(round(volts * 100))
        return self.write_register(self.REG_S_LVP, raw)

    def set_ohp(self, hours, minutes):
        ok1 = self.write_register(self.REG_S_OHP_H, int(hours))
        ok2 = self.write_register(self.REG_S_OHP_M, int(minutes))
        return ok1 and ok2

    def set_oah(self, mah):
        low = int(mah) & 0xFFFF
        high = (int(mah) >> 16) & 0xFFFF
        ok1 = self.write_register(self.REG_S_OAH_L, low)
        ok2 = self.write_register(self.REG_S_OAH_H, high)
        return ok1 and ok2

    def set_owh(self, mwh):
        low = int(mwh) & 0xFFFF
        high = (int(mwh) >> 16) & 0xFFFF
        ok1 = self.write_register(self.REG_S_OWH_L, low)
        ok2 = self.write_register(self.REG_S_OWH_H, high)
        return ok1 and ok2

    def set_data_group(self, group):
        group = max(0, min(9, int(group)))
        return self.write_register(self.REG_EXTRACT_M, group)

    def set_temp_cal_int(self, offset_c):
        raw = int(round(offset_c * 10))
        return self.write_register(self.REG_T_IN_CAL, raw)

    def set_temp_cal_ext(self, offset_c):
        raw = int(round(offset_c * 10))
        return self.write_register(self.REG_T_EXT_CAL, raw)

    def factory_reset(self):
        return self.write_register(self.REG_FACTORY_RST, 1)

    def close(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
