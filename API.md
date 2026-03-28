# REST API Reference

This document describes the REST API endpoints exposed by the Dual PSU Controller.

**Base URL:** `http://[DEVICE_IP]:8080/api/`

## Endpoints

### GET Endpoints
- `GET /api/status` — Full status for all PSUs
- `GET /api/psu/{id}` — Full status for a single PSU (readings, settings, protection)
- `GET /api/psu/{id}/readings` — Live readings only
- `GET /api/psu/{id}/settings` — Device settings
- `GET /api/psu/{id}/protection` — Protection thresholds
- `GET /api/snmp` — SNMP agent configuration

### POST Endpoints (Control)
- `POST /api/psu/{id}/output` — Enable/disable output `{ "enabled": true }`
- `POST /api/psu/{id}/voltage` — Set output voltage `{ "voltage": 12.5 }`
- `POST /api/psu/{id}/current` — Set current limit `{ "current": 2.0 }`
- `POST /api/psu/{id}/lock` — Lock/unlock panel `{ "locked": true }`
- `POST /api/psu/{id}/backlight` — Set backlight `{ "level": 3 }`
- `POST /api/psu/{id}/sleep` — Set sleep timeout `{ "minutes": 30 }`
- `POST /api/psu/{id}/beeper` — Enable/disable beeper `{ "enabled": false }`
- `POST /api/psu/{id}/temp_unit` — Set temp unit `{ "fahrenheit": true }`
- `POST /api/psu/{id}/mppt` — MPPT mode `{ "enabled": true, "threshold": 18.0 }`
- `POST /api/psu/{id}/cp` — Constant-power mode `{ "enabled": true, "power": 25.0 }`
- `POST /api/psu/{id}/btf` — Battery full cutoff `{ "current": 0.100 }`
- `POST /api/psu/{id}/data_group` — Data group `{ "group": 3 }`
- `POST /api/psu/{id}/power_on_init` — Power-on output `{ "output_on": true }`

### POST Endpoints (Protection)
- `POST /api/psu/{id}/ovp` — OVP `{ "voltage": 62.0 }`
- `POST /api/psu/{id}/ocp` — OCP `{ "current": 6.100 }`
- `POST /api/psu/{id}/opp` — OPP `{ "power": 360.0 }`
- `POST /api/psu/{id}/otp` — OTP `{ "temperature": 80.0 }`
- `POST /api/psu/{id}/lvp` — LVP `{ "voltage": 10.0 }`
- `POST /api/psu/{id}/ohp` — OHP `{ "hours": 8, "minutes": 30 }`
- `POST /api/psu/{id}/oah` — OAH `{ "mah": 5000 }`
- `POST /api/psu/{id}/owh` — OWH `{ "mwh": 50000 }`
- `POST /api/psu/{id}/temp_cal` — Temp calibration `{ "internal": 0.5, "external": -1.2 }`
- `POST /api/psu/{id}/factory_reset` — Factory reset `{}`

## Notes
- All endpoints return JSON.
- CORS is enabled for browser-based scripting.
- PSU IDs are `a` and `b`.
- See the Web UI (API Docs panel) for detailed payloads and examples.
