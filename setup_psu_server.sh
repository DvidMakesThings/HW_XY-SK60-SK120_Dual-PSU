#!/bin/bash
# setup_psu_server.sh - Automate PSU server deployment to Luckfox device
# Usage: ./setup_psu_server.sh [DEVICE_IP] [PASSWORD]

set -e

# --- CONFIG ---
REMOTE_DIR="/opt/psu_controller"
SERVICE_NAME="psucontroller"
PYTHON_FILE="web_server.py"

# --- DETECT LUCKFOX DEVICE ---
find_luckfox() {
    echo "[INFO] Scanning for Luckfox device on local network..."
    for ip in 192.168.0.{2..254}; do
        if timeout 1 bash -c "</dev/tcp/$ip/22" 2>/dev/null; then
            hostinfo=$(sshpass -p "$2" ssh -o StrictHostKeyChecking=no root@$ip 'uname -a 2>/dev/null')
            if echo "$hostinfo" | grep -qi luckfox; then
                echo "$ip"
                return 0
            fi
        fi
    done
    return 1
}

# --- MAIN ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVICE_IP="$1"
PASSWORD="$2"

if [ -z "$PASSWORD" ]; then
    PASSWORD="luckfox"
fi

if [ -z "$DEVICE_IP" ]; then
    DEVICE_IP=$(find_luckfox "$PASSWORD")
    if [ -z "$DEVICE_IP" ]; then
        echo "[ERROR] Could not auto-detect Luckfox device. Specify IP as first argument." >&2
        exit 1
    fi
    echo "[INFO] Luckfox device found at $DEVICE_IP"
fi

# --- UPLOAD FILES ---
echo "[INFO] Uploading files to $DEVICE_IP:$REMOTE_DIR ..."
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@$DEVICE_IP "mkdir -p $REMOTE_DIR"
sshpass -p "$PASSWORD" scp -r $SCRIPT_DIR/* root@$DEVICE_IP:$REMOTE_DIR/

# --- SETUP SYSTEMD SERVICE ---
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
SERVICE_CONTENT="[Unit]\nDescription=PSU Controller Web Server\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory=$REMOTE_DIR\nExecStart=/usr/bin/python3 $REMOTE_DIR/$PYTHON_FILE\nRestart=always\nUser=root\n\n[Install]\nWantedBy=multi-user.target\n"

sshpass -p "$PASSWORD" ssh root@$DEVICE_IP "echo -e '$SERVICE_CONTENT' > $SERVICE_FILE && systemctl daemon-reload && systemctl enable $SERVICE_NAME && systemctl restart $SERVICE_NAME"

echo "[INFO] Setup complete. Service '$SERVICE_NAME' is running on $DEVICE_IP."
