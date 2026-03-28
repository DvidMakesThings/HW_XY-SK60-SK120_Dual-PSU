# REST API Reference

This document describes the full REST API exposed by the Dual PSU Controller.

**Base URL:** `http://[DEVICE_IP]:8080/api/`
**PSU IDs:** `a` (PSU-A) and `b` (PSU-B)
**Content-Type:** All POST requests must include `Content-Type: application/json`
**CORS:** `Access-Control-Allow-Origin: *` — the API is accessible from any browser origin

---

## Response Format

**GET endpoints** return a JSON object with the requested data.

**POST endpoints** always return:
```json
{ "success": true }
```
or on failure:
```json
{ "success": false, "error": "Human-readable error message" }
```

---

## Status Endpoints

### `GET /api/status`
Full status object for all connected PSUs. Combines readings, settings, and protection data in a single call. Useful for dashboards that need everything at once.

**Response:**
```json
{
  "a": {
    "name": "PSU-A",
    "v_set": 12.50,
    "i_set": 2.000,
    "v_out": 12.48,
    "i_out": 0.312,
    "power": 3.89,
    "v_in": 24.10,
    "ah": 142,
    "wh": 1730,
    "out_hours": 0,
    "out_mins": 12,
    "out_secs": 34,
    "temp_int": 31.8,
    "temp_ext": -1.0,
    "lock": 0,
    "protect": 0,
    "cvcc": 0,
    "output_on": true,
    "backlight": 3,
    "sleep": 0,
    "beeper": 1,
    "f_c": 0,
    "model": 6000,
    "firmware": 130,
    "protection": {
      "ovp": 62.0, "ocp": 6.100, "opp": 360.0,
      "otp": 80.0, "lvp": 10.0,
      "ohp_h": 0, "ohp_m": 0, "oah": 0, "owh": 0,
      "power_on_init": false
    }
  },
  "b": { "..." }
}
```

### `GET /api/psu/{id}`
Full status for a single PSU. Same structure as one entry in `/api/status`.

```bash
curl http://192.168.0.190:8080/api/psu/a
```

### `GET /api/psu/{id}/readings`
Live measurements only. Polled at the PSU background thread rate (~200 ms cycle).

**Response:**
```json
{
  "v_out": 12.48,
  "i_out": 0.312,
  "power": 3.89,
  "v_in": 24.10,
  "v_set": 12.50,
  "i_set": 2.000,
  "ah": 142,
  "wh": 1730,
  "out_hours": 0,
  "out_mins": 12,
  "out_secs": 34,
  "temp_int": 31.8,
  "temp_ext": -1.0,
  "cvcc": 0,
  "output_on": true,
  "protect": 0
}
```

`cvcc`: `0` = constant-voltage mode, `1` = constant-current mode.
`protect`: protection status register bitmask; `0` = no active protection event.
`temp_ext`: `-1.0` indicates no external sensor connected.

```bash
curl http://192.168.0.190:8080/api/psu/a/readings
```

### `GET /api/psu/{id}/settings`
Device configuration settings.

**Response:**
```json
{
  "backlight": 3,
  "sleep": 0,
  "lock": 0,
  "beeper": 1,
  "f_c": 0,
  "model": 6000,
  "firmware": 130,
  "slave_addr": 1,
  "baudrate": 6
}
```

### `GET /api/psu/{id}/protection`
Protection thresholds and accumulated energy limits.

**Response:**
```json
{
  "ovp": 62.0,
  "ocp": 6.100,
  "opp": 360.0,
  "otp": 80.0,
  "lvp": 10.0,
  "ohp_h": 0,
  "ohp_m": 0,
  "oah": 0,
  "owh": 0,
  "power_on_init": false
}
```

### `GET /api/snmp`
SNMP agent configuration (community strings, port, base OID).

```bash
curl http://192.168.0.190:8080/api/snmp
```

---

## Control Endpoints

### `POST /api/psu/{id}/output`
Enable or disable the PSU output.

```json
{ "enabled": true }
```
```bash
curl -X POST -H 'Content-Type: application/json' \
     -d '{"enabled":true}' \
     http://192.168.0.190:8080/api/psu/a/output
```

### `POST /api/psu/{id}/voltage`
Set the output voltage setpoint in volts. The PSU enforces its own OVP limit.

```json
{ "voltage": 12.50 }
```
```bash
curl -X POST -H 'Content-Type: application/json' \
     -d '{"voltage":12.5}' \
     http://192.168.0.190:8080/api/psu/a/voltage
```

### `POST /api/psu/{id}/current`
Set the output current limit in amps.

```json
{ "current": 2.000 }
```

### `POST /api/psu/{id}/lock`
Lock or unlock the front panel keys (prevents physical button presses from changing settings).

```json
{ "locked": true }
```

### `POST /api/psu/{id}/backlight`
Set the LCD backlight level. `0` = off, `5` = maximum brightness.

```json
{ "level": 3 }
```

### `POST /api/psu/{id}/sleep`
Auto-sleep timeout in minutes. `0` disables auto-sleep.

```json
{ "minutes": 30 }
```

### `POST /api/psu/{id}/beeper`
Enable or disable the key press beeper.

```json
{ "enabled": false }
```

### `POST /api/psu/{id}/temp_unit`
Switch the temperature display between Celsius and Fahrenheit.

```json
{ "fahrenheit": true }
```

### `POST /api/psu/{id}/mppt`
Enable MPPT (Maximum Power Point Tracking) solar mode and/or set the input voltage threshold. In MPPT mode, the PSU regulates its input current to keep input voltage at or above the threshold, preventing source collapse.

```json
{ "enabled": true, "threshold": 18.0 }
```

### `POST /api/psu/{id}/cp`
Enable constant-power mode and/or set the power target in watts. The PSU adjusts current to maintain the specified output power.

```json
{ "enabled": true, "power": 25.0 }
```

### `POST /api/psu/{id}/btf`
Battery-full cutoff current threshold in amps. The output turns off automatically when output current drops below this value. Useful for CC/CV battery charging.

```json
{ "current": 0.100 }
```

### `POST /api/psu/{id}/data_group`
Select a preset data group (0–9). Each group stores independent V/I setpoints on the PSU.

```json
{ "group": 3 }
```

### `POST /api/psu/{id}/power_on_init`
Set whether the output is automatically enabled on PSU power-up.

```json
{ "output_on": true }
```

---

## Protection Endpoints

### `POST /api/psu/{id}/ovp`
Over-Voltage Protection threshold in volts. Output shuts off if Vout exceeds this value.

```json
{ "voltage": 62.0 }
```

### `POST /api/psu/{id}/ocp`
Over-Current Protection threshold in amps. Output shuts off if Iout exceeds this value.

```json
{ "current": 6.100 }
```

### `POST /api/psu/{id}/opp`
Over-Power Protection threshold in watts.

```json
{ "power": 360.0 }
```

### `POST /api/psu/{id}/otp`
Over-Temperature Protection threshold in °C. Output shuts off if the internal sensor exceeds this temperature.

```json
{ "temperature": 80.0 }
```

### `POST /api/psu/{id}/lvp`
Low-Voltage Protection threshold on the DC input (volts). Output shuts off if the input bus voltage drops below this level. Useful for protecting battery sources from deep discharge.

```json
{ "voltage": 10.0 }
```

### `POST /api/psu/{id}/ohp`
Over-Hours Protection. Output shuts off after this cumulative run time.

```json
{ "hours": 8, "minutes": 30 }
```

### `POST /api/psu/{id}/oah`
Over Amp-Hours Protection threshold in mAh. Output shuts off after this accumulated charge has been delivered.

```json
{ "mah": 5000 }
```

### `POST /api/psu/{id}/owh`
Over Watt-Hours Protection threshold in mWh. Output shuts off after this accumulated energy has been delivered.

```json
{ "mwh": 50000 }
```

### `POST /api/psu/{id}/temp_cal`
Apply a calibration offset in °C to the internal and/or external temperature sensors. Positive values increase the reported temperature; negative values decrease it.

```json
{ "internal": 0.5, "external": -1.2 }
```

### `POST /api/psu/{id}/factory_reset`
Reset all settings to factory defaults. This cannot be undone.

```json
{}
```
```bash
curl -X POST http://192.168.0.190:8080/api/psu/a/factory_reset
```

---

## Sweep Endpoints

The sweep system executes a timed sequence of voltage and/or output-state changes on a PSU. Each waypoint specifies an elapsed time (ms from sweep start) and at least one action (`voltage` and/or `output`). Waypoints are sorted by `time_ms` server-side and executed at 50 ms resolution. The sweep ends automatically after the last waypoint.

### `GET /api/sweep`
Sweep program and execution status for all PSUs.

**Response:**
```json
{
  "a": {
    "program": [
      { "time_ms": 0,     "voltage": 0.0 },
      { "time_ms": 500,   "output": true  },
      { "time_ms": 1000,  "voltage": 5.0  },
      { "time_ms": 5000,  "voltage": 12.0 },
      { "time_ms": 10000, "output": false }
    ],
    "status": {
      "running": true,
      "elapsed_ms": 3240,
      "current_step": 2
    }
  },
  "b": { "..." }
}
```

`current_step`: index (0-based) of the last applied waypoint. `-1` before any waypoint has been applied.

### `GET /api/sweep/{id}`
Sweep program and status for a single PSU.

```bash
curl http://192.168.0.190:8080/api/sweep/a
```

### `POST /api/sweep/{id}/set`
Upload a sweep program. The existing program is replaced. You can upload a new program while the PSU is idle; the sweep does not start automatically.

Each waypoint must have `time_ms` and at least one of `voltage` (float, volts) or `output` (bool). A single waypoint may contain both.

```json
{
  "points": [
    { "time_ms": 0,     "voltage": 0.0,  "output": true  },
    { "time_ms": 1000,  "voltage": 5.0                   },
    { "time_ms": 3000,  "voltage": 12.0                  },
    { "time_ms": 6000,  "voltage": 3.3                   },
    { "time_ms": 8000,  "output": false                  }
  ]
}
```

```bash
curl -X POST -H 'Content-Type: application/json' \
     -d '{"points":[{"time_ms":0,"voltage":0},{"time_ms":5000,"voltage":12.0}]}' \
     http://192.168.0.190:8080/api/sweep/a/set
```

### `POST /api/sweep/{id}/start`
Start sweep execution. Returns an error if no program is defined or a sweep is already running.

```json
{}
```
```bash
curl -X POST http://192.168.0.190:8080/api/sweep/a/start
```

### `POST /api/sweep/{id}/stop`
Stop sweep execution immediately. The PSU voltage is held at its last-programmed setpoint.

```json
{}
```
```bash
curl -X POST http://192.168.0.190:8080/api/sweep/a/stop
```

---

## Datalogger Endpoints

The datalogger records V/I/P samples from a PSU at a configurable interval. Samples are held in a ring buffer (max 10,000 per channel); when full, the oldest sample is discarded. Logging state (enabled/disabled) survives a `clear` operation.

### `GET /api/datalog`
Logging status for all PSUs (no sample data).

**Response:**
```json
{
  "a": { "enabled": true,  "interval_ms": 500, "samples": 247 },
  "b": { "enabled": false, "interval_ms": 500, "samples": 0   }
}
```

### `GET /api/datalog/{id}`
All logged samples plus status for a single PSU.

**Response:**
```json
{
  "status": { "enabled": true, "interval_ms": 500, "samples": 3 },
  "samples": [
    { "t": 0,    "v": 12.48, "i": 0.312, "p": 3.89 },
    { "t": 500,  "v": 12.47, "i": 0.315, "p": 3.93 },
    { "t": 1000, "v": 12.48, "i": 0.310, "p": 3.87 }
  ]
}
```

`t`: milliseconds since first sample in this log session.
`v`: output voltage (V).
`i`: output current (A).
`p`: output power (W).

```bash
curl http://192.168.0.190:8080/api/datalog/a
```

### `GET /api/datalog/{id}/csv`
Download logged samples as a CSV file. The response has `Content-Disposition: attachment; filename=psu_{id}_log.csv`.

**CSV columns:** `time_ms, voltage_V, current_A, power_W`

```
time_ms,voltage_V,current_A,power_W
0,12.48,0.312,3.89
500,12.47,0.315,3.93
1000,12.48,0.310,3.87
```

```bash
curl -o psu_a_log.csv http://192.168.0.190:8080/api/datalog/a/csv
```

### `POST /api/datalog/{id}/start`
Start logging. If logging is already active, the interval is updated. Minimum `interval_ms` is 100; default is 500.

```json
{ "interval_ms": 500 }
```
```bash
curl -X POST -H 'Content-Type: application/json' \
     -d '{"interval_ms":200}' \
     http://192.168.0.190:8080/api/datalog/a/start
```

### `POST /api/datalog/{id}/stop`
Stop logging. The sample buffer is preserved.

```json
{}
```

### `POST /api/datalog/{id}/clear`
Clear all samples from the buffer. Does not affect the logging state (if logging is running, it continues after the clear).

```json
{}
```

---

## Notes

- **Rate limiting:** There is no enforced rate limit. Polling `/api/psu/{id}/readings` faster than the PSU polling cycle (~200 ms) returns cached data; you will not get newer values by polling faster.
- **Polling the sweep status:** While a sweep is running, poll `GET /api/sweep/{id}` at ~500 ms to track `elapsed_ms` and `current_step`. The sweep ends when `running` becomes `false`.
- **Concurrent sweeps:** Both PSU channels support independent simultaneous sweep execution.
- **Concurrent datalogger and sweep:** The datalogger and sweep can run simultaneously on the same PSU channel.
