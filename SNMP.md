# SNMP OID Reference

This document describes the SNMP agent and OID table for the Dual PSU Controller.

- **Port:** 161/UDP
- **Read community:** `public`
- **Write community:** `private`
- **Base OID:** `1.3.6.1.4.1.99999.1`

## Scalar OIDs
- `.1.0` — `psuCount` (INTEGER): Number of PSU channels

## PSU Table OIDs
Each PSU channel is a row (Row 1 = PSU-A, Row 2 = PSU-B):

| Col | OID Suffix | Name              | Type      | Scale   | RW | Description                       |
|-----|------------|-------------------|-----------|---------|----|-----------------------------------|
| 1   | .2.1.1.{r} | psuIndex          | INT       | --      | RO | Row index (1, 2, ...)             |
| 2   | .2.1.2.{r} | psuName           | STRING    | --      | RO | Channel name                      |
| 3   | .2.1.3.{r} | psuSetVoltage     | INT       | x100    | RW | Voltage setpoint (1250=12.50V)    |
| 4   | .2.1.4.{r} | psuSetCurrent     | INT       | x1000   | RW | Current limit (2000=2.000A)       |
| 5   | .2.1.5.{r} | psuOutputVoltage  | INT       | x100    | RO | Measured output voltage           |
| 6   | .2.1.6.{r} | psuOutputCurrent  | INT       | x1000   | RO | Measured output current           |
| 7   | .2.1.7.{r} | psuOutputPower    | INT       | x100    | RO | Calculated output power           |
| 8   | .2.1.8.{r} | psuInputVoltage   | INT       | x100    | RO | DC input bus voltage              |
| 9   | .2.1.9.{r} | psuInternalTemp   | INT       | x10     | RO | Internal temp sensor (318=31.8C)  |
| 10  | .2.1.10.{r}| psuExternalTemp   | INT       | x10     | RO | External temp sensor (-1=N/A)     |
| 11  | .2.1.11.{r}| psuOutputEnabled  | INT       | 0/1     | RW | 1=output ON, 0=output OFF         |
| 12  | .2.1.12.{r}| psuCVCC           | INT       | 0/1     | RO | 0=CV, 1=CC                        |
| 13  | .2.1.13.{r}| psuProtectStatus  | INT       | --      | RO | Protection status register        |
| 14  | .2.1.14.{r}| psuKeyLock        | INT       | 0/1     | RW | 1=front panel locked              |
| 15  | .2.1.15.{r}| psuBacklight      | INT       | 0-5     | RW | LCD backlight level               |
| 16  | .2.1.16.{r}| psuBeeper         | INT       | 0/1     | RW | 1=beeper enabled                  |
| 17  | .2.1.17.{r}| psuModel          | STRING    | --      | RO | Device model string               |
| 18  | .2.1.18.{r}| psuFirmware       | STRING    | --      | RO | Firmware version                  |
| 19  | .2.1.19.{r}| psuAmpHours       | Counter32 | --      | RO | Accumulated amp-hours (mAh)       |
| 20  | .2.1.20.{r}| psuWattHours      | Counter32 | --      | RO | Accumulated watt-hours (mWh)      |
| 21  | .2.1.21.{r}| psuOutputTimeSec  | Counter32 | --      | RO | Total output ON time (seconds)    |
| 22  | .2.1.22.{r}| psuMPPTEnabled    | INT       | 0/1     | RW | 1=MPPT solar mode ON              |
| 23  | .2.1.23.{r}| psuSleepMin       | INT       | min     | RW | Auto-sleep timeout (0=disabled)   |
| 24  | .2.1.24.{r}| psuOVP            | INT       | x100    | RW | Over-voltage protection (V)       |
| 25  | .2.1.25.{r}| psuOCP            | INT       | x1000   | RW | Over-current protection (A)       |
| 26  | .2.1.26.{r}| psuOPP            | INT       | x10     | RW | Over-power protection (W)         |
| 27  | .2.1.27.{r}| psuOTP            | INT       | x10     | RW | Over-temperature protection (C)   |
| 28  | .2.1.28.{r}| psuLVP            | INT       | x100    | RW | Low-voltage protection (V)        |

## Example SNMP Commands
- Read output voltage of PSU-A:
  `snmpget -v2c -c public [DEVICE_IP] 1.3.6.1.4.1.99999.1.2.1.5.1`
- Set output voltage of PSU-B to 12.50 V:
  `snmpset -v2c -c private [DEVICE_IP] 1.3.6.1.4.1.99999.1.2.1.3.2 i 1250`
- Walk all PSU parameters:
  `snmpwalk -v2c -c public [DEVICE_IP] 1.3.6.1.4.1.99999.1.2`

See the Web UI (SNMP Docs panel) for the full OID table and command reference.
