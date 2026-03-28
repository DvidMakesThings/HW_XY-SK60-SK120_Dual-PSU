# SNMP Reference

The PSU controller includes a built-in SNMPv2c agent. This document describes the OID structure, data types, scaling, and command examples.

---

## Agent Configuration

| Parameter | Value |
|---|---|
| Protocol | SNMPv2c |
| Transport | UDP |
| Port | 161 |
| Read community | `public` |
| Write community | `private` |
| Base OID | `1.3.6.1.4.1.99999.1` |
| Operations | GET, GETNEXT, GETBULK, SET |

---

## OID Structure

```
1.3.6.1.4.1.99999.1
│
├── .1.0          ─ Scalar: psuCount
│
└── .2.1.{col}.{row}   ─ PSU Table
         │       │
         │       └── Row: 1 = PSU-A,  2 = PSU-B
         └────────── Column: 1–28 (see table below)
```

---

## Scalar OIDs

| OID | Name | Type | Description |
|---|---|---|---|
| `...1.0` | `psuCount` | INTEGER | Number of connected PSU channels |

```bash
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.1.0
```

---

## PSU Table OIDs

OID format: `1.3.6.1.4.1.99999.1.2.1.{column}.{row}`

Row 1 = PSU-A, Row 2 = PSU-B.

All integer values are raw register values. Divide by the **Divisor** to obtain engineering units. For example, a raw voltage value of `1250` with divisor 100 represents **12.50 V**.

To write a value, multiply the desired engineering value by the divisor and send as an INTEGER. For example, to set 5.00 V: `5.00 × 100 = 500`.

| Col | OID Suffix | Name | Type | Divisor | Units | Access | Description |
|---|---|---|---|---|---|---|---|
| 1 | `.2.1.1.{r}` | `psuIndex` | INTEGER | — | — | RO | Row index (1, 2, …) |
| 2 | `.2.1.2.{r}` | `psuName` | STRING | — | — | RO | Channel name (PSU-A, PSU-B) |
| 3 | `.2.1.3.{r}` | `psuSetVoltage` | INTEGER | 100 | V | **RW** | Voltage setpoint |
| 4 | `.2.1.4.{r}` | `psuSetCurrent` | INTEGER | 1000 | A | **RW** | Current limit |
| 5 | `.2.1.5.{r}` | `psuOutputVoltage` | INTEGER | 100 | V | RO | Measured output voltage |
| 6 | `.2.1.6.{r}` | `psuOutputCurrent` | INTEGER | 1000 | A | RO | Measured output current |
| 7 | `.2.1.7.{r}` | `psuOutputPower` | INTEGER | 100 | W | RO | Calculated output power |
| 8 | `.2.1.8.{r}` | `psuInputVoltage` | INTEGER | 100 | V | RO | DC input bus voltage |
| 9 | `.2.1.9.{r}` | `psuInternalTemp` | INTEGER | 10 | °C | RO | Internal temperature sensor |
| 10 | `.2.1.10.{r}` | `psuExternalTemp` | INTEGER | 10 | °C | RO | External temperature sensor (−10 = not present) |
| 11 | `.2.1.11.{r}` | `psuOutputEnabled` | INTEGER | — | 0/1 | **RW** | 1 = output ON, 0 = output OFF |
| 12 | `.2.1.12.{r}` | `psuCVCC` | INTEGER | — | 0/1 | RO | 0 = CV mode, 1 = CC mode |
| 13 | `.2.1.13.{r}` | `psuProtectStatus` | INTEGER | — | bitmask | RO | Protection status register (0 = no event) |
| 14 | `.2.1.14.{r}` | `psuKeyLock` | INTEGER | — | 0/1 | **RW** | 1 = front panel keys locked |
| 15 | `.2.1.15.{r}` | `psuBacklight` | INTEGER | — | 0–5 | **RW** | LCD backlight level |
| 16 | `.2.1.16.{r}` | `psuBeeper` | INTEGER | — | 0/1 | **RW** | 1 = key beeper enabled |
| 17 | `.2.1.17.{r}` | `psuModel` | STRING | — | — | RO | Device model string |
| 18 | `.2.1.18.{r}` | `psuFirmware` | STRING | — | — | RO | Firmware version |
| 19 | `.2.1.19.{r}` | `psuAmpHours` | Counter32 | — | mAh | RO | Accumulated amp-hours |
| 20 | `.2.1.20.{r}` | `psuWattHours` | Counter32 | — | mWh | RO | Accumulated watt-hours |
| 21 | `.2.1.21.{r}` | `psuOutputTimeSec` | Counter32 | — | s | RO | Total output ON time |
| 22 | `.2.1.22.{r}` | `psuMPPTEnabled` | INTEGER | — | 0/1 | **RW** | 1 = MPPT solar mode ON |
| 23 | `.2.1.23.{r}` | `psuSleepMin` | INTEGER | — | min | **RW** | Auto-sleep timeout (0 = disabled) |
| 24 | `.2.1.24.{r}` | `psuOVP` | INTEGER | 100 | V | **RW** | Over-voltage protection threshold |
| 25 | `.2.1.25.{r}` | `psuOCP` | INTEGER | 1000 | A | **RW** | Over-current protection threshold |
| 26 | `.2.1.26.{r}` | `psuOPP` | INTEGER | 10 | W | **RW** | Over-power protection threshold |
| 27 | `.2.1.27.{r}` | `psuOTP` | INTEGER | 10 | °C | **RW** | Over-temperature protection threshold |
| 28 | `.2.1.28.{r}` | `psuLVP` | INTEGER | 100 | V | **RW** | Low-voltage (input) protection threshold |

---

## Value Scaling

Integer OIDs store values as scaled integers to avoid floating-point in the base SNMP protocol.

**Reading:** `engineering_value = raw_integer / divisor`

| Raw value | Divisor | Result |
|---|---|---|
| 1250 | 100 | 12.50 V |
| 2000 | 1000 | 2.000 A |
| 3890 | 100 | 38.90 W |
| 318 | 10 | 31.8 °C |

**Writing:** `raw_integer = round(engineering_value × divisor)`

| Desired | Divisor | Raw to send |
|---|---|---|
| 5.00 V | 100 | 500 |
| 3.300 A | 1000 | 3300 |
| 62.0 V (OVP) | 100 | 6200 |
| 80.0 °C (OTP) | 10 | 800 |

---

## Command Reference

Replace `192.168.0.190` with your device IP. For PSU-B substitute row `2` for `1`.

### Read Operations

```bash
# Scalar: number of channels
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.1.0

# Walk all PSU table entries (both channels, all columns)
snmpwalk -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2

# Bulk-get all 28 columns for PSU-A in a single UDP packet
snmpbulkget -v2c -c public -Cr28 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.0.1

# Individual reads — PSU-A (row 1)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.1.1   # psuIndex
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.2.1   # psuName
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.3.1   # psuSetVoltage  (raw ÷100 → V)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.4.1   # psuSetCurrent  (raw ÷1000 → A)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.5.1   # psuOutputVoltage
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.6.1   # psuOutputCurrent
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.7.1   # psuOutputPower
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.8.1   # psuInputVoltage
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.9.1   # psuInternalTemp  (raw ÷10 → °C)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.10.1  # psuExternalTemp
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.11.1  # psuOutputEnabled (0/1)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.12.1  # psuCVCC (0=CV, 1=CC)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.13.1  # psuProtectStatus
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.14.1  # psuKeyLock
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.15.1  # psuBacklight (0-5)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.16.1  # psuBeeper (0/1)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.17.1  # psuModel
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.18.1  # psuFirmware
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.19.1  # psuAmpHours (mAh)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.20.1  # psuWattHours (mWh)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.21.1  # psuOutputTimeSec
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.22.1  # psuMPPTEnabled
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.23.1  # psuSleepMin
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.24.1  # psuOVP  (raw ÷100 → V)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.25.1  # psuOCP  (raw ÷1000 → A)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.26.1  # psuOPP  (raw ÷10 → W)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.27.1  # psuOTP  (raw ÷10 → °C)
snmpget -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.28.1  # psuLVP  (raw ÷100 → V)
```

### Write Operations

```bash
# Set PSU-A voltage to 12.50 V  (12.50 × 100 = 1250)
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.3.1 i 1250

# Set PSU-B voltage to 5.00 V
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.3.2 i 500

# Set PSU-A current limit to 2.000 A  (2.000 × 1000 = 2000)
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.4.1 i 2000

# Turn PSU-A output ON
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.11.1 i 1

# Turn PSU-B output OFF
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.11.2 i 0

# Lock PSU-A front panel
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.14.1 i 1

# Set PSU-A backlight to level 2
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.15.1 i 2

# Set PSU-A OVP to 62.00 V  (62.00 × 100 = 6200)
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.24.1 i 6200

# Set PSU-A OCP to 6.100 A  (6.100 × 1000 = 6100)
snmpset -v2c -c private 192.168.0.190 1.3.6.1.4.1.99999.1.2.1.25.1 i 6100
```

---

## Monitoring Integration

### Zabbix

Add the PSU controller as a host with SNMPv2 interface, community `public`, port 161.

Example item configuration for PSU-A output voltage:
- **OID:** `1.3.6.1.4.1.99999.1.2.1.5.1`
- **Type:** SNMPv2 agent
- **Value type:** Numeric (float)
- **Preprocessing:** Multiply by `0.01` (divisor 100)
- **Units:** V

Recommended trigger for protection event:
- `{HOST:1.3.6.1.4.1.99999.1.2.1.13.1.last()} <> 0` → PROBLEM

### LibreNMS / Nagios

Use the OID table to build custom checks or templates. `snmpwalk` the base OID to discover all values automatically:

```bash
snmpwalk -v2c -c public 192.168.0.190 1.3.6.1.4.1.99999.1
```

### Python (pysnmp)

```python
from pysnmp.hlapi import *

B = '1.3.6.1.4.1.99999.1'

# Read PSU-A output voltage
for (errorIndication, errorStatus, errorIndex, varBinds) in getCmd(
        SnmpEngine(),
        CommunityData('public', mpModel=1),
        UdpTransportTarget(('192.168.0.190', 161)),
        ContextData(),
        ObjectType(ObjectIdentity(B + '.2.1.5.1'))):
    if not errorIndication and not errorStatus:
        raw = int(varBinds[0][1])
        print(f'PSU-A output voltage: {raw / 100:.2f} V')
```
