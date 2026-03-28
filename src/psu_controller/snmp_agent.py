"""
Minimal SNMPv2c agent for PSU monitoring.
Implements GET, GETNEXT, SET over UDP using raw BER/ASN.1 encoding.
No external dependencies.
"""

import socket
import struct
import threading
import time


# --- BER / ASN.1 encoding & decoding ---

TAG_INT       = 0x02
TAG_OCTSTR    = 0x04
TAG_NULL      = 0x05
TAG_OID       = 0x06
TAG_SEQ       = 0x30
TAG_COUNTER32 = 0x41
TAG_GAUGE32   = 0x42
TAG_TIMETICKS = 0x43
TAG_NOSUCHOBJ = 0x80
TAG_NOSUCHINST = 0x81
TAG_ENDOFMIB  = 0x82
TAG_GETREQ    = 0xA0
TAG_GETNEXTREQ = 0xA1
TAG_GETRESP   = 0xA2
TAG_SETREQ    = 0xA3
TAG_GETBULK   = 0xA5


def ber_encode_length(length):
    if length < 0x80:
        return bytes([length])
    if length < 0x100:
        return bytes([0x81, length])
    return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])


def ber_encode_tlv(tag, value):
    return bytes([tag]) + ber_encode_length(len(value)) + value


def ber_encode_int_bytes(val):
    if val == 0:
        return b'\x00'
    negative = val < 0
    if negative:
        # Convert to two's complement
        bit_len = val.bit_length() + 1
        byte_len = (bit_len + 7) // 8
        val = val & ((1 << (byte_len * 8)) - 1)
    result = []
    v = val
    while v > 0:
        result.insert(0, v & 0xFF)
        v >>= 8
    if not result:
        result = [0]
    if not negative and (result[0] & 0x80):
        result.insert(0, 0)
    return bytes(result)


def ber_encode_int(val):
    return ber_encode_tlv(TAG_INT, ber_encode_int_bytes(val))


def ber_encode_str(val):
    if isinstance(val, str):
        val = val.encode('ascii')
    return ber_encode_tlv(TAG_OCTSTR, val)


def ber_encode_null():
    return b'\x05\x00'


def ber_encode_oid(oid_tuple):
    if len(oid_tuple) < 2:
        return ber_encode_tlv(TAG_OID, bytes([0]))
    result = [oid_tuple[0] * 40 + oid_tuple[1]]
    for comp in oid_tuple[2:]:
        if comp < 128:
            result.append(comp)
        else:
            encoded = []
            v = comp
            encoded.append(v & 0x7F)
            v >>= 7
            while v > 0:
                encoded.append((v & 0x7F) | 0x80)
                v >>= 7
            encoded.reverse()
            result.extend(encoded)
    return ber_encode_tlv(TAG_OID, bytes(result))


def ber_encode_seq(items):
    payload = b''.join(items)
    return ber_encode_tlv(TAG_SEQ, payload)


def ber_encode_counter32(val):
    return ber_encode_tlv(TAG_COUNTER32, ber_encode_int_bytes(val & 0xFFFFFFFF))


def ber_encode_gauge32(val):
    return ber_encode_tlv(TAG_GAUGE32, ber_encode_int_bytes(val & 0xFFFFFFFF))


def ber_decode(data, offset=0):
    """Decode one TLV element. Returns (tag, value_bytes, next_offset)."""
    if offset >= len(data):
        return None, b'', offset
    tag = data[offset]
    offset += 1
    if offset >= len(data):
        return tag, b'', offset
    lb = data[offset]
    offset += 1
    if lb < 0x80:
        length = lb
    elif lb == 0x81:
        length = data[offset]
        offset += 1
    elif lb == 0x82:
        length = (data[offset] << 8) | data[offset + 1]
        offset += 2
    else:
        length = 0
    value = data[offset:offset + length]
    return tag, value, offset + length


def ber_decode_int(data):
    """Decode BER integer value bytes."""
    if not data:
        return 0
    val = 0
    for b in data:
        val = (val << 8) | b
    if data[0] & 0x80:
        val -= (1 << (len(data) * 8))
    return val


def ber_decode_oid(data):
    """Decode BER OID value bytes to tuple."""
    if not data:
        return ()
    result = [data[0] // 40, data[0] % 40]
    i = 1
    while i < len(data):
        comp = 0
        while True:
            byte = data[i]
            comp = (comp << 7) | (byte & 0x7F)
            i += 1
            if not (byte & 0x80):
                break
    result.append(comp)
    return tuple(result)


def ber_decode_sequence(data):
    """Decode SEQUENCE contents into list of (tag, value_bytes)."""
    items = []
    offset = 0
    while offset < len(data):
        tag, val, offset = ber_decode(data, offset)
        if tag is None:
            break
        items.append((tag, val))
    return items


# --- SNMP Message parsing / building ---

def parse_snmp_message(data):
    """Parse an SNMP v1/v2c message. Returns dict or None."""
    tag, seq_data, _ = ber_decode(data, 0)
    if tag != TAG_SEQ:
        return None
    items = ber_decode_sequence(seq_data)
    if len(items) < 3:
        return None
    version = ber_decode_int(items[0][1])
    community = items[1][1].decode('ascii', errors='replace')
    pdu_tag = items[2][0]
    pdu_data = items[2][1]
    pdu_items = ber_decode_sequence(pdu_data)
    if len(pdu_items) < 4:
        return None
    request_id = ber_decode_int(pdu_items[0][1])
    error_status = ber_decode_int(pdu_items[1][1])
    error_index = ber_decode_int(pdu_items[2][1])

    # Parse varbind list
    varbinds = []
    vb_list_items = ber_decode_sequence(pdu_items[3][1])
    for vb_tag, vb_data in vb_list_items:
        vb_items = ber_decode_sequence(vb_data)
        if len(vb_items) >= 2:
            oid = ber_decode_oid(vb_items[0][1])
            val_tag = vb_items[1][0]
            val_data = vb_items[1][1]
            varbinds.append((oid, val_tag, val_data))

    return {
        'version': version,
        'community': community,
        'pdu_type': pdu_tag,
        'request_id': request_id,
        'error_status': error_status,
        'error_index': error_index,
        'varbinds': varbinds,
    }


def build_snmp_response(version, community, request_id, error_status,
                        error_index, varbinds):
    """Build SNMP GetResponse message bytes."""
    # Build varbind list
    vb_items = []
    for oid, val_encoded in varbinds:
        vb = ber_encode_seq([ber_encode_oid(oid), val_encoded])
        vb_items.append(vb)
    vb_list = ber_encode_seq(vb_items)

    pdu = ber_encode_tlv(TAG_GETRESP, (
        ber_encode_int(request_id) +
        ber_encode_int(error_status) +
        ber_encode_int(error_index) +
        vb_list
    ))

    msg = ber_encode_seq([
        ber_encode_int(version),
        ber_encode_str(community),
        pdu,
    ])
    return msg


# --- SNMP Agent ---

# OID base: .1.3.6.1.4.1.99999.1
BASE_OID = (1, 3, 6, 1, 4, 1, 99999, 1)


class SNMPAgent:
    """Minimal SNMPv2c agent providing PSU data via SNMP GET/GETNEXT/SET."""

    def __init__(self, psu_dict, community='public', write_community='private',
                 host='0.0.0.0', port=161):
        self.psus = psu_dict
        self.community = community
        self.write_community = write_community
        self.host = host
        self.port = port
        self._oid_tree = []  # sorted list of (oid_tuple, getter, setter)
        self._build_oid_tree()

    def _build_oid_tree(self):
        """Build the OID table mapping OIDs to getter/setter functions."""
        tree = []
        psu_list = sorted(self.psus.keys())

        # .1.0 = psuCount
        count_oid = BASE_OID + (1, 0)
        tree.append((count_oid, lambda: ber_encode_int(len(self.psus)), None))

        # Table: .2.1.<col>.<row>
        columns = [
            # (col_id, name, getter_key, value_encoder, setter_func_name)
            (1, 'psuIndex', None, None, None),
            (2, 'psuName', 'name', 'str', None),
            (3, 'psuSetVoltage', 'v_set_raw', 'int', 'set_voltage_raw'),
            (4, 'psuSetCurrent', 'i_set_raw', 'int', 'set_current_raw'),
            (5, 'psuOutputVoltage', 'v_out_raw', 'int', None),
            (6, 'psuOutputCurrent', 'i_out_raw', 'int', None),
            (7, 'psuOutputPower', 'power_raw', 'int', None),
            (8, 'psuInputVoltage', 'v_in_raw', 'int', None),
            (9, 'psuInternalTemp', 'temp_int_raw', 'int', None),
            (10, 'psuExternalTemp', 'temp_ext_raw', 'int', None),
            (11, 'psuOutputEnabled', 'output_on_int', 'int', 'set_output_snmp'),
            (12, 'psuCVCC', 'cvcc', 'int', None),
            (13, 'psuProtectStatus', 'protect', 'int', None),
            (14, 'psuKeyLock', 'lock_int', 'int', 'set_lock_snmp'),
            (15, 'psuBacklight', 'backlight', 'int', 'set_backlight'),
            (16, 'psuBeeper', 'beeper_int', 'int', 'set_beeper_snmp'),
            (17, 'psuModel', 'model', 'str', None),
            (18, 'psuFirmware', 'version', 'str', None),
            (19, 'psuAmpHours', 'ah', 'counter', None),
            (20, 'psuWattHours', 'wh', 'counter', None),
            (21, 'psuOutputTimeSec', 'out_total_secs', 'counter', None),
            (22, 'psuMPPTEnabled', 'mppt_enabled_int', 'int', 'set_mppt_snmp'),
            (23, 'psuSleepMin', 'sleep_min', 'int', 'set_sleep'),
            (24, 'psuOVP', 'ovp_raw', 'int', 'set_ovp_raw'),
            (25, 'psuOCP', 'ocp_raw', 'int', 'set_ocp_raw'),
            (26, 'psuOPP', 'opp_raw', 'int', 'set_opp_raw'),
            (27, 'psuOTP', 'otp_raw', 'int', 'set_otp_raw'),
            (28, 'psuLVP', 'lvp_raw', 'int', 'set_lvp_raw'),
        ]

        for row_idx, psu_id in enumerate(psu_list, 1):
            for col_id, col_name, key, enc_type, setter_name in columns:
                oid = BASE_OID + (2, 1, col_id, row_idx)

                if col_id == 1:
                    getter = self._make_const_getter(row_idx, 'int')
                else:
                    getter = self._make_getter(psu_id, key, enc_type, row_idx)

                setter = None
                if setter_name:
                    setter = self._make_setter(psu_id, setter_name)

                tree.append((oid, getter, setter))

        tree.sort(key=lambda x: x[0])
        self._oid_tree = tree

    def _get_psu_snmp_data(self, psu_id):
        """Get PSU data with raw register values for SNMP."""
        psu = self.psus.get(psu_id)
        if psu is None:
            return {}
        status = psu.get_full_status()
        prot = status.get('protection', {})
        data = dict(status)
        # Add raw integer versions for SNMP
        data['v_set_raw'] = int(round(status.get('v_set', 0) * 100))
        data['i_set_raw'] = int(round(status.get('i_set', 0) * 1000))
        data['v_out_raw'] = int(round(status.get('v_out', 0) * 100))
        data['i_out_raw'] = int(round(status.get('i_out', 0) * 1000))
        data['power_raw'] = int(round(status.get('power', 0) * 100))
        data['v_in_raw'] = int(round(status.get('v_in', 0) * 100))
        data['temp_int_raw'] = int(round(status.get('temp_int', 0) * 10))
        t_ext = status.get('temp_ext')
        data['temp_ext_raw'] = int(round(t_ext * 10)) if t_ext is not None else -1
        data['output_on_int'] = 1 if status.get('output_on') else 0
        data['lock_int'] = 1 if status.get('lock') else 0
        data['beeper_int'] = 1 if status.get('beeper') else 0
        data['mppt_enabled_int'] = 1 if status.get('mppt_enabled') else 0
        data['ovp_raw'] = int(round(prot.get('ovp', 0) * 100))
        data['ocp_raw'] = int(round(prot.get('ocp', 0) * 1000))
        data['opp_raw'] = int(round(prot.get('opp', 0) * 10))
        data['otp_raw'] = int(round(prot.get('otp', 0) * 10))
        data['lvp_raw'] = int(round(prot.get('lvp', 0) * 100))
        return data

    def _make_const_getter(self, value, enc_type):
        def getter():
            return ber_encode_int(value)
        return getter

    def _make_getter(self, psu_id, key, enc_type, row_idx):
        def getter():
            data = self._get_psu_snmp_data(psu_id)
            val = data.get(key, 0)
            if enc_type == 'str':
                return ber_encode_str(str(val) if val else '')
            elif enc_type == 'counter':
                return ber_encode_counter32(int(val) if val else 0)
            else:
                return ber_encode_int(int(val) if val else 0)
        return getter

    def _make_setter(self, psu_id, method_name):
        def setter(value):
            psu = self.psus.get(psu_id)
            if psu is None:
                return False
            # Dispatch to the right method
            if method_name == 'set_voltage_raw':
                return psu.set_voltage(value / 100.0)
            elif method_name == 'set_current_raw':
                return psu.set_current(value / 1000.0)
            elif method_name == 'set_output_snmp':
                return psu.set_output(bool(value))
            elif method_name == 'set_lock_snmp':
                return psu.set_lock(bool(value))
            elif method_name == 'set_beeper_snmp':
                return psu.set_beeper(bool(value))
            elif method_name == 'set_mppt_snmp':
                return psu.set_mppt(bool(value))
            elif method_name == 'set_backlight':
                return psu.set_backlight(value)
            elif method_name == 'set_sleep':
                return psu.set_sleep(value)
            elif method_name == 'set_ovp_raw':
                return psu.set_ovp(value / 100.0)
            elif method_name == 'set_ocp_raw':
                return psu.set_ocp(value / 1000.0)
            elif method_name == 'set_opp_raw':
                return psu.set_opp(value / 10.0)
            elif method_name == 'set_otp_raw':
                return psu.set_otp(value / 10.0)
            elif method_name == 'set_lvp_raw':
                return psu.set_lvp(value / 100.0)
            return False
        return setter

    def _find_oid(self, oid):
        """Find exact OID match. Returns (getter, setter) or None."""
        for entry_oid, getter, setter in self._oid_tree:
            if entry_oid == oid:
                return getter, setter
        return None

    def _find_next_oid(self, oid):
        """Find next OID after the given one. Returns (oid, getter, setter) or None."""
        for entry_oid, getter, setter in self._oid_tree:
            if entry_oid > oid:
                return entry_oid, getter, setter
        return None

    def _handle_request(self, msg):
        """Process an SNMP request and return response bytes."""
        version = msg['version']
        community = msg['community']
        pdu_type = msg['pdu_type']
        request_id = msg['request_id']
        varbinds = msg['varbinds']

        # Check community for read
        if pdu_type in (TAG_GETREQ, TAG_GETNEXTREQ, TAG_GETBULK):
            if community != self.community and community != self.write_community:
                return None  # wrong community, ignore

        # Check write community
        if pdu_type == TAG_SETREQ:
            if community != self.write_community:
                # Return noAccess error
                resp_vb = [(varbinds[0][0], ber_encode_null())] if varbinds else []
                return build_snmp_response(version, community, request_id, 6, 1, resp_vb)

        result_varbinds = []
        error_status = 0
        error_index = 0

        if pdu_type == TAG_GETREQ:
            for idx, (oid, val_tag, val_data) in enumerate(varbinds, 1):
                match = self._find_oid(oid)
                if match:
                    getter, _ = match
                    try:
                        encoded_val = getter()
                    except Exception:
                        encoded_val = ber_encode_tlv(TAG_NOSUCHINST, b'')
                    result_varbinds.append((oid, encoded_val))
                else:
                    result_varbinds.append((oid, ber_encode_tlv(TAG_NOSUCHINST, b'')))

        elif pdu_type == TAG_GETNEXTREQ:
            for idx, (oid, val_tag, val_data) in enumerate(varbinds, 1):
                match = self._find_next_oid(oid)
                if match:
                    next_oid, getter, _ = match
                    try:
                        encoded_val = getter()
                    except Exception:
                        encoded_val = ber_encode_tlv(TAG_ENDOFMIB, b'')
                    result_varbinds.append((next_oid, encoded_val))
                else:
                    result_varbinds.append((oid, ber_encode_tlv(TAG_ENDOFMIB, b'')))

        elif pdu_type == TAG_SETREQ:
            for idx, (oid, val_tag, val_data) in enumerate(varbinds, 1):
                match = self._find_oid(oid)
                if match:
                    _, setter = match
                    if setter is None:
                        error_status = 17  # notWritable
                        error_index = idx
                        result_varbinds.append((oid, ber_encode_tlv(val_tag, val_data)))
                        break
                    value = ber_decode_int(val_data)
                    try:
                        ok = setter(value)
                    except Exception:
                        ok = False
                    if not ok:
                        error_status = 5  # genErr
                        error_index = idx
                    result_varbinds.append((oid, ber_encode_int(value)))
                else:
                    error_status = 2  # noSuchName (v1) / notWritable
                    error_index = idx
                    result_varbinds.append((oid, ber_encode_null()))
                    break

        elif pdu_type == TAG_GETBULK:
            # Treat as multiple GETNEXT
            non_repeaters = msg.get('error_status', 0)  # overloaded field
            max_repetitions = msg.get('error_index', 10)
            for idx, (oid, val_tag, val_data) in enumerate(varbinds):
                reps = 1 if idx < non_repeaters else max_repetitions
                current_oid = oid
                for _ in range(reps):
                    match = self._find_next_oid(current_oid)
                    if match:
                        next_oid, getter, _ = match
                        try:
                            encoded_val = getter()
                        except Exception:
                            encoded_val = ber_encode_tlv(TAG_ENDOFMIB, b'')
                            result_varbinds.append((current_oid, encoded_val))
                            break
                        result_varbinds.append((next_oid, encoded_val))
                        current_oid = next_oid
                    else:
                        result_varbinds.append((current_oid, ber_encode_tlv(TAG_ENDOFMIB, b'')))
                        break

        else:
            return None

        return build_snmp_response(
            version, community, request_id,
            error_status, error_index, result_varbinds
        )

    def run(self):
        """Run the SNMP agent (blocking)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        print('[SNMP] Listening on %s:%d (community: %s)' % (
            self.host, self.port, self.community))

        while True:
            try:
                data, addr = sock.recvfrom(4096)
                msg = parse_snmp_message(data)
                if msg is None:
                    continue
                response = self._handle_request(msg)
                if response:
                    sock.sendto(response, addr)
            except Exception as e:
                print('[SNMP] Error: %s' % str(e))
                time.sleep(0.1)


def start_snmp_agent(psu_dict, community='public', write_community='private',
                     host='0.0.0.0', port=161):
    agent = SNMPAgent(psu_dict, community, write_community, host, port)
    agent.run()
