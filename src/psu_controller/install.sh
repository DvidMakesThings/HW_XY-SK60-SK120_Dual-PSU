#!/bin/sh
# PSU Controller - Install Script for Luckfox Pico Plus
# Installs to /opt/psu_controller/ and sets up systemd service
# Also ensures UART3 + UART4 are enabled via device tree overlay

set -e

INSTALL_DIR="/opt/psu_controller"
SERVICE_NAME="psu-controller"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== PSU Controller Installer ==="
echo ""

# --- Install files ---
echo "[1/4] Installing files to ${INSTALL_DIR} ..."
mkdir -p "${INSTALL_DIR}/web"

for f in psu_controller.py modbus_psu.py web_server.py snmp_agent.py sweep_manager.py datalogger.py config.json; do
    cp "${SCRIPT_DIR}/${f}" "${INSTALL_DIR}/${f}"
done
for f in index.html style.css app.js; do
    cp "${SCRIPT_DIR}/web/${f}" "${INSTALL_DIR}/web/${f}"
done

echo "   Files installed."

# --- Check pyserial ---
echo "[2/4] Checking Python dependencies ..."
if python3 -c "import serial" 2>/dev/null; then
    echo "   pyserial found."
else
    echo "   WARNING: pyserial not found. Attempting install ..."
    if command -v pip3 >/dev/null 2>&1; then
        pip3 install pyserial
    elif command -v pip >/dev/null 2>&1; then
        pip install pyserial
    else
        echo "   ERROR: pip not found. Install pyserial manually."
        echo "   Download from https://pypi.org/project/pyserial/"
        exit 1
    fi
fi

# --- Enable UARTs ---
echo "[3/4] Checking UART device nodes ..."

# UART4 (ttyS4) - usually enabled by boot overlay
if [ ! -e /dev/ttyS4 ]; then
    echo "   ttyS4 not found - creating device node ..."
    mknod /dev/ttyS4 c 4 68 2>/dev/null || true
fi

# UART3 (ttyS3) - often needs manual creation
if [ ! -e /dev/ttyS3 ]; then
    echo "   ttyS3 not found - creating device node ..."
    mknod /dev/ttyS3 c 4 67 2>/dev/null || true
fi

# Load DT overlays if configfs is available
if [ -d /sys/kernel/config/device-tree/overlays ]; then
    echo "   Applying device tree overlays for UART3/UART4 ..."

    # Check if overlays already applied
    if [ ! -d /sys/kernel/config/device-tree/overlays/uart3 ]; then
        # Get phandles from live DT
        PINS_DIR="/proc/device-tree/pinctrl/rockchip,pins"
        if [ -d "$PINS_DIR" ]; then
            PHANDLE_UART3=""
            PHANDLE_UART4=""
            for node_dir in "$PINS_DIR"/*/; do
                node_name=$(basename "$node_dir")
                case "$node_name" in
                    *uart3m1-xfer*)
                        if [ -f "${node_dir}phandle" ]; then
                            PHANDLE_UART3=$(hexdump -e '4/1 "%02x"' "${node_dir}phandle" 2>/dev/null | sed 's/^0*//')
                            PHANDLE_UART3=$((0x${PHANDLE_UART3}))
                        fi
                        ;;
                    *uart4m1-xfer*)
                        if [ -f "${node_dir}phandle" ]; then
                            PHANDLE_UART4=$(hexdump -e '4/1 "%02x"' "${node_dir}phandle" 2>/dev/null | sed 's/^0*//')
                            PHANDLE_UART4=$((0x${PHANDLE_UART4}))
                        fi
                        ;;
                esac
            done

            if [ -n "$PHANDLE_UART3" ]; then
                mkdir -p /tmp/dtbo
                cat > /tmp/dtbo/uart3.dts << DTEOF
/dts-v1/;
/plugin/;
/ {
    fragment@0 {
        target-path = "/serial@ff590000";
        __overlay__ {
            status = "okay";
            pinctrl-names = "default";
            pinctrl-0 = <${PHANDLE_UART3}>;
        };
    };
};
DTEOF
                dtc -I dts -O dtb -o /tmp/dtbo/uart3.dtbo /tmp/dtbo/uart3.dts 2>/dev/null
                mkdir -p /sys/kernel/config/device-tree/overlays/uart3
                cat /tmp/dtbo/uart3.dtbo > /sys/kernel/config/device-tree/overlays/uart3/dtbo
                echo "   UART3 overlay applied (phandle ${PHANDLE_UART3})"
            fi

            if [ -n "$PHANDLE_UART4" ]; then
                cat > /tmp/dtbo/uart4.dts << DTEOF
/dts-v1/;
/plugin/;
/ {
    fragment@0 {
        target-path = "/serial@ff5a0000";
        __overlay__ {
            status = "okay";
            pinctrl-names = "default";
            pinctrl-0 = <${PHANDLE_UART4}>;
        };
    };
};
DTEOF
                dtc -I dts -O dtb -o /tmp/dtbo/uart4.dtbo /tmp/dtbo/uart4.dts 2>/dev/null
                mkdir -p /sys/kernel/config/device-tree/overlays/uart4
                cat /tmp/dtbo/uart4.dtbo > /sys/kernel/config/device-tree/overlays/uart4/dtbo
                echo "   UART4 overlay applied (phandle ${PHANDLE_UART4})"
            fi
        fi
    else
        echo "   UART3 overlay already active."
    fi
else
    echo "   Configfs DT overlays not available - UARTs must be enabled in base DT."
fi

# Verify
for dev in /dev/ttyS3 /dev/ttyS4; do
    if [ -e "$dev" ]; then
        echo "   OK: $dev present"
    else
        echo "   WARNING: $dev missing - PSU on this port will not work"
    fi
done

# --- Install systemd service ---
echo "[4/4] Installing systemd service ..."
cp "${SCRIPT_DIR}/psu-controller.service" /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

echo ""
echo "=== Installation complete ==="
echo "   Web UI:  http://$(hostname -I | awk '{print $1}'):8080/"
echo "   SNMP:    port 161, community 'public'"
echo "   Service: systemctl status ${SERVICE_NAME}"
echo ""
