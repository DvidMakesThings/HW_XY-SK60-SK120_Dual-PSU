
# Dual PSU Controller: Complete Project Overview

**This project is a complete open-source solution for remote control, monitoring, and automation of two Sinilink XY-SK60/SK120 buck-boost power supplies.**

It combines hardware, firmware, and a modern web interface to turn two programmable PSUs into a networked, rack-mountable, professional-grade power system. Features include:

- Real-time web dashboard for control and telemetry
- SNMP agent for integration with network monitoring tools
- REST API for automation and scripting
- 3D-printable 1U enclosure for 10-inch racks
- One-command deployment scripts for Luckfox and similar Linux SBCs


## Table of Contents

- [Web User Interface (Web UI)](#web-user-interface-web-ui)
- [SNMP Agent](#snmp-agent)
- [REST API](#rest-api)
- [Project Purpose](#project-purpose)
- [Hardware Overview](#hardware-overview)
- [Software Features](#software-features)
- [Typical Use Cases](#typical-use-cases)
- [How It Works](#how-it-works)
- [Enclosure](#enclosure)
- [Hardware & Deployment](#dual-psu-controller-hardware--deployment)
- [Luckfox Device Deployment: Automated Setup Scripts](#luckfox-device-deployment-automated-setup-scripts)
  - [What do these scripts do?](#what-do-these-scripts-do)
  - [Requirements](#requirements)
  - [Step-by-Step Usage](#step-by-step-usage)
  - [Troubleshooting & Tips](#troubleshooting--tips)
- [License](#license)
  - [Software Components](#software-components)
  - [Hardware Components](#hardware-components)
  - [Commercial & Enterprise Use](#commercial--enterprise-use)
- [Contact](#contact)
- [Contributing](#contributing)

---

## Web User Interface (Web UI)
The built-in web dashboard provides real-time control and monitoring of both PSUs from any browser on your network. Features include:

- **Live telemetry:** Voltage, current, power, input voltage, temperature, output state, protection status, and more
- **Channel control:** Turn outputs on/off, set voltage/current, lock panel, enable/disable beeper, MPPT, and more
- **Protection configuration:** Set OVP, OCP, OPP, OTP, LVP, OHP, OAH, OWH thresholds per channel
- **Settings:** Adjust backlight, sleep timeout, temperature units, calibration, and factory reset
- **System info:** View firmware, serial port, SNMP settings, and network status
- **API & SNMP docs:** Built-in reference for REST API and SNMP OIDs/commands

Access the Web UI at:  
`http://[DEVICE_IP]:8080/`

See also: [API.md](API.md) and [SNMP.md](SNMP.md) for full API and SNMP documentation.

---

## SNMP Agent
The controller includes a minimal SNMPv2c agent for integration with network monitoring tools (Zabbix, Nagios, LibreNMS, etc.).

- **Port:** 161/UDP
- **Read community:** `public`
- **Write community:** `private`
- **Base OID:** `1.3.6.1.4.1.99999.1`
- **Supports:** GET, GETNEXT, GETBULK, SET
- **OID Table:** Each PSU channel is a row; all key parameters are exposed as OIDs (see Web UI > SNMP Docs for full table)

See [SNMP.md](SNMP.md) for the full OID table, command reference, and more SNMP usage examples.

### Example SNMP commands
Read output voltage of PSU-A:
```
snmpget -v2c -c public [DEVICE_IP] 1.3.6.1.4.1.99999.1.2.1.5.1
# (raw value x100, e.g. 1250 = 12.50 V)
```
Set output voltage of PSU-B to 12.50 V:
```
snmpset -v2c -c private [DEVICE_IP] 1.3.6.1.4.1.99999.1.2.1.3.2 i 1250
```
Walk all PSU parameters:
```
snmpwalk -v2c -c public [DEVICE_IP] 1.3.6.1.4.1.99999.1.2
```

---

## REST API
The controller exposes a REST API for automation and scripting. All endpoints are documented in the Web UI (API Docs panel).

**Base URL:** `http://[DEVICE_IP]:8080/api/`

See [API.md](API.md) for a full list of endpoints, payloads, and usage notes.

### Example endpoints
- `GET /api/status` — Full status for all PSUs
- `GET /api/psu/a/readings` — Live readings for PSU-A
- `POST /api/psu/a/voltage` — Set output voltage (body: `{ "voltage": 12.5 }`)
- `POST /api/psu/b/output` — Enable/disable output (body: `{ "enabled": true }`)

**CORS is enabled** for browser-based scripting and integration.

---

## Project Purpose
This project delivers a full-featured, open-source remote control and monitoring system for a dual Sinilink XY-SK60/SK120 buck-boost power supply setup. It is designed for makers, lab automation, test benches, and anyone needing reliable, programmable DC power with networked control.

## Hardware Overview
- **Supported Models:** Sinilink XY-SK60 and XY-SK120 buck-boost modules (or compatible)
- **Dual Channel:** Two independent PSUs, each with its own serial (Modbus RTU) interface
- **Connection:** Both PSUs connect to a Linux-based single-board computer (e.g., Luckfox, Raspberry Pi) via UART/USB serial adapters
- **Wiring:**
  - Each PSU’s serial port connects to a separate serial port on the controller device
  - Power and load wiring as per Sinilink documentation
  - No hardware modifications required for basic operation

## Software Features
- **Web Dashboard:** Real-time control and monitoring of both PSUs from any browser
- **SNMP Agent:** Integrates with network monitoring tools (e.g., Zabbix, Nagios)
- **REST API:** For automation, scripting, and integration with other systems
- **Systemd Service:** Runs as a background service, auto-starts on boot
- **Multi-Platform Deployment:** Easy setup scripts for both Windows and Linux/Mac users
- **Live Telemetry:** Voltage, current, power, temperature, output state, and more
- **Safe Operations:** Protection status, lockout, and error reporting

## Typical Use Cases
- Automated test benches for electronics
- Remote-controlled lab power supplies
- Networked power monitoring in IoT setups
- Home automation and smart lab projects
- Educational and research environments

## How It Works
1. **Hardware Setup:** Connect both PSUs to the controller device’s serial ports
2. **Software Deployment:** Use the provided scripts to install and configure the controller software on the device
3. **Operation:**
   - The controller communicates with both PSUs, exposing their controls and telemetry via web and SNMP interfaces
   - Users can access the web UI, automate via API, or monitor via SNMP
   - The system runs headless and auto-starts after power loss or reboot


## Enclosure
This project is designed for a **10-inch rack** and fits a standard **1U** height. The enclosure can be fully **3D printed** using the provided files in the `3D files/` directory.

- Compact 1U form factor for professional rack installations
- 10-inch width fits small lab and telecom racks
- All required STL/3MF files are included for 3D printing
- Front and rear panel designs for easy access and cable management

### Enclosure Renders

<p align="center">
  <img src="img/Front_render.png" alt="Front Render" width="400"/>
  <img src="img/Back_render.png" alt="Back Render" width="400"/>
</p>

### Internal Layout

<p align="center">
  <img src="img/Inside.png" alt="Inside View" width="500"/>
</p>

See the `3D files/` folder for printable models and the `doc/` folder for assembly instructions.

----

# Dual PSU Controller: Hardware & Deployment

This project provides a complete remote-control and monitoring solution for a **dual Sinilink XY-SK60/SK120 buck-boost power supply** setup. It includes:

- **Hardware:** Two independent Sinilink XY-SK60 or SK120 modules, each controllable via serial (Modbus RTU) interface.
- **Controller Software:** Python-based server for remote management, real-time monitoring, and automation of both PSUs. Features include:
  - Web dashboard for live control and status
  - SNMP agent for integration with network monitoring tools
  - REST API for automation and scripting
  - Systemd service for reliable background operation
- **Auto-deployment Scripts:** One-command scripts to install and configure the controller on a Luckfox device (or similar Linux SBC), making setup fast and repeatable.

---

# Luckfox Device Deployment: Automated Setup Scripts

This project includes two scripts to make deploying the PSU Controller server to a Luckfox device as easy and reliable as possible:

- **setup_psu_server.bat** (for Windows users)
- **setup_psu_server.sh** (for Linux/Mac users)

## What do these scripts do?
- **Auto-detect your Luckfox device** on the local network (or use an IP you provide)
- **Copy all project files** from your PC to the device’s `/opt/psu_controller` directory
- **Set up a systemd service** so the server starts automatically on boot
- **Start the server** immediately

---

## Requirements

### For Windows
- [PuTTY tools](https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html) (`plink.exe` and `pscp.exe`) must be in your PATH
- Your Luckfox device must be on the same network as your PC

### For Linux/Mac
- `sshpass`, `ssh`, and `scp` must be installed
- Your Luckfox device must be on the same network as your computer

### Device Credentials
- The default root password is assumed to be `luckfox` (used automatically if you don’t specify one)
- If you changed the password, provide it as the second argument

---

## Step-by-Step Usage

### 1. Prepare your environment
- Place the script (`setup_psu_server.bat` or `setup_psu_server.sh`) in your project root (where all your code is).
- Make sure your Luckfox device is powered on and connected to your network.

### 2. Run the script

**Windows:**
```cmd
setup_psu_server.bat [DEVICE_IP] [PASSWORD]
```
- You can skip `[DEVICE_IP]` to auto-detect your Luckfox device.
- You can skip `[PASSWORD]` to use the default `luckfox`.
- Example (auto-detect, default password):
  ```
  setup_psu_server.bat
  ```
- Example (specify IP):
  ```
  setup_psu_server.bat 192.168.0.190
  ```

**Linux/Mac:**
```bash
bash setup_psu_server.sh [DEVICE_IP] [PASSWORD]
```
- You can skip `[DEVICE_IP]` to auto-detect your Luckfox device.
- You can skip `[PASSWORD]` to use the default `luckfox`.
- Example (auto-detect, default password):
  ```
  bash setup_psu_server.sh
  ```
- Example (specify IP):
  ```
  bash setup_psu_server.sh 192.168.0.190
  ```

### 3. What happens next?
- The script will:
  - Find your Luckfox device (or use the IP you gave)
  - Copy all files from your project folder to `/opt/psu_controller` on the device
  - Create and enable a systemd service so the server runs on every boot
  - Start the server right away

- You can now access the web interface at:
  ```
  http://[DEVICE_IP]:8080/
  ```

---

## Troubleshooting & Tips

- **Device not found?** Make sure it’s powered on and on the same network. Try specifying the IP directly.
- **Wrong password?** If you changed the root password, provide it as the second argument.
- **Windows:** Ensure `plink.exe` and `pscp.exe` are in your PATH (copy them to the same folder as the script if needed).
- **Linux/Mac:** Install `sshpass` if you don’t have it (`sudo apt install sshpass` on Ubuntu/Debian).
- **Service not starting?** You can check logs on the device with:
  ```
  journalctl -u psucontroller -e
  ```

---

**These scripts are designed for a one-command, zero-hassle deployment.**  
If you have special requirements or run into issues, check the comments in the scripts for more details or ask for help!


## License
### Software Components
This project's software is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.
See the [Software License](LICENSE-AGPL) file for details.

#### What AGPL-3.0 means:

- ✅ **You can** freely use, modify, and distribute this software
- ✅ **You can** use this project for personal, educational, or internal purposes
- ✅ **You can** contribute improvements back to this project

- ⚠️ **You must** share any modifications you make if you distribute the software
- ⚠️ **You must** release the source code if you run a modified version on a server that others interact with
- ⚠️ **You must** keep all copyright notices intact

- ❌ **You cannot** incorporate this code into proprietary software without sharing your source code
- ❌ **You cannot** use this project in a commercial product without either complying with AGPL or obtaining a different license

### Hardware Components
Hardware designs, schematics, and related documentation are licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License (CC BY-NC-SA 4.0)**. See the [Hardware License](LICENSE-CC-BY-NC-SA) file for details.

#### What CC BY-NC-SA 4.0 means:

- ✅ **You can** study, modify, and distribute the hardware designs
- ✅ **You can** create derivative works for personal, educational, or non-commercial use
- ✅ **You can** build this project for your own personal use

- ⚠️ **You must** give appropriate credit and indicate if changes were made
- ⚠️ **You must** share any modifications under the same license terms
- ⚠️ **You must** include the original license and copyright notices

- ❌ **You cannot** use the designs for commercial purposes without explicit permission
- ❌ **You cannot** manufacture and sell products based on these designs without a commercial license
- ❌ **You cannot** create closed-source derivatives for commercial purposes
- ❌ **You cannot** use the designer's trademarks without permission

### Commercial & Enterprise Use

Commercial use of this project is prohibited without obtaining a separate commercial license. If you are interested in:

- Manufacturing and selling products based on these designs
- Incorporating these designs into commercial products
- Any other commercial applications

Please contact me through any of the channels listed in the [Contact](#contact) section to discuss commercial licensing arrangements. Commercial licenses are available with reasonable terms to support ongoing development.

## Contact

For questions or feedback:
- **Email:** [dvidmakesthings@gmail.com](mailto:dvidmakesthings@gmail.com)
- **GitHub:** [DvidMakesThings](https://github.com/DvidMakesThings)

## Contributing

Contributions are welcome! As this is an early-stage project, please reach out before 
making substantial changes:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/concept`)
3. Commit your changes (`git commit -m 'Add concept'`)
4. Push to the branch (`git push origin feature/concept`)
5. Open a Pull Request with a detailed description