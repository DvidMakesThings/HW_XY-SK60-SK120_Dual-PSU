#!/usr/bin/env python3
"""
PSU Controller - Main entry point.
Starts web server and SNMP agent for XY-SK60 buck-boost converter control.
"""

import json
import os
import sys
import threading

from modbus_psu import ModbusPSU
from web_server import start_web_server
import web_server
from snmp_agent import start_snmp_agent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config():
    config_path = os.path.join(BASE_DIR, 'config.json')
    if not os.path.isfile(config_path):
        print('[ERROR] config.json not found at %s' % config_path)
        sys.exit(1)
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    config = load_config()

    # Initialize PSU connections
    psus = {}
    for psu_id, psu_cfg in config['psus'].items():
        print('[INIT] Connecting to %s on %s at %d baud...' % (
            psu_cfg['name'], psu_cfg['port'], psu_cfg['baudrate']))
        psu = ModbusPSU(
            port=psu_cfg['port'],
            baudrate=psu_cfg['baudrate'],
            address=psu_cfg['address'],
            name=psu_cfg['name'],
        )
        if psu.connected:
            print('[INIT] %s connected OK' % psu_cfg['name'])
        else:
            print('[INIT] WARNING: %s failed to connect on %s' % (
                psu_cfg['name'], psu_cfg['port']))
        psus[psu_id] = psu

    # Quick connectivity test
    for psu_id, psu in psus.items():
        readings = psu.get_readings()
        if readings:
            print('[INIT] %s: Vin=%.2fV, Vset=%.2fV, Iset=%.3fA, Output=%s' % (
                psu.name,
                readings['v_in'],
                readings['v_set'],
                readings['i_set'],
                'ON' if readings['output_on'] else 'OFF',
            ))
        else:
            print('[INIT] %s: No response from device' % psu.name)

    web_cfg = config.get('web', {})
    snmp_cfg = config.get('snmp', {})

    # Set PSU references in web server module
    web_server.psus = psus

    # Start SNMP agent in background thread
    snmp_thread = threading.Thread(
        target=start_snmp_agent,
        args=(psus,),
        kwargs={
            'community': snmp_cfg.get('community', 'public'),
            'write_community': snmp_cfg.get('write_community', 'private'),
            'host': snmp_cfg.get('host', '0.0.0.0'),
            'port': snmp_cfg.get('port', 161),
        },
        daemon=True,
    )
    snmp_thread.start()

    # Start web server (blocking, main thread)
    print('[INIT] Starting PSU Controller')
    print('[INIT] Web UI: http://0.0.0.0:%d/' % web_cfg.get('port', 8080))
    print('[INIT] SNMP:   %s:%d community=%s' % (
        snmp_cfg.get('host', '0.0.0.0'),
        snmp_cfg.get('port', 161),
        snmp_cfg.get('community', 'public'),
    ))

    try:
        start_web_server(
            host=web_cfg.get('host', '0.0.0.0'),
            port=web_cfg.get('port', 8080),
        )
    except KeyboardInterrupt:
        print('\n[SHUTDOWN] Stopping...')
    finally:
        for psu in psus.values():
            psu.close()
        print('[SHUTDOWN] Done.')


if __name__ == '__main__':
    main()
