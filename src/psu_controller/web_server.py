import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Will be set by psu_controller.py before starting
psus = {}
sweep_manager = None
datalogger = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')

MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
}


class PSURequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default logging

    def _send_csv(self, csv_data, filename='data.csv'):
        body = csv_data.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv')
        self.send_header('Content-Disposition', 'attachment; filename="%s"' % filename)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=None, separators=(',', ':')).encode('ascii')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status, message):
        self._send_json({'error': message}, status)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _serve_file(self, path):
        full_path = os.path.join(WEB_DIR, path.lstrip('/'))
        full_path = os.path.normpath(full_path)
        if not full_path.startswith(os.path.normpath(WEB_DIR)):
            self.send_error(403)
            return
        if not os.path.isfile(full_path):
            self.send_error(404)
            return
        ext = os.path.splitext(full_path)[1]
        mime = MIME_TYPES.get(ext, 'application/octet-stream')
        with open(full_path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _get_psu(self, psu_id):
        psu_id = psu_id.lower()
        if psu_id in psus:
            return psus[psu_id]
        return None

    # --- GET routes ---

    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/' or path == '/index.html':
            self._serve_file('index.html')
        elif path.startswith('/api/'):
            self._route_api_get(path)
        elif path.startswith('/'):
            self._serve_file(path)
        else:
            self.send_error(404)

    def _route_api_get(self, path):
        if path == '/api/status':
            result = {}
            for psu_id, psu in psus.items():
                result[psu_id] = psu.get_full_status()
            self._send_json(result)

        elif path == '/api/readings':
            result = {}
            for psu_id, psu in psus.items():
                r = psu.get_readings_cached()
                if r:
                    r['name'] = psu.name
                result[psu_id] = r or {}
            self._send_json(result)

        elif path.startswith('/api/psu/'):
            parts = path.split('/')
            if len(parts) >= 4:
                psu_id = parts[3]
                psu = self._get_psu(psu_id)
                if psu is None:
                    self._send_error_json(404, 'PSU not found')
                    return
                if len(parts) == 4 or (len(parts) == 5 and parts[4] == ''):
                    self._send_json(psu.get_full_status())
                elif len(parts) == 5 and parts[4] == 'readings':
                    r = psu.get_readings()
                    self._send_json(r if r else {'error': 'read failed'})
                elif len(parts) == 5 and parts[4] == 'settings':
                    s = psu.get_settings()
                    self._send_json(s if s else {'error': 'read failed'})
                elif len(parts) == 5 and parts[4] == 'protection':
                    p = psu.get_protection()
                    self._send_json(p if p else {'error': 'read failed'})
                else:
                    self._send_error_json(404, 'Unknown endpoint')
            else:
                self._send_error_json(404, 'Unknown endpoint')

        elif path == '/api/snmp':
            self._send_json({
                'community': 'public',
                'write_community': 'private',
                'port': 161,
                'base_oid': '1.3.6.1.4.1.99999.1',
            })

        elif path == '/api/sweep':
            if sweep_manager:
                self._send_json(sweep_manager.get_status())
            else:
                self._send_error_json(503, 'Sweep manager not available')

        elif path.startswith('/api/sweep/'):
            parts = path.split('/')
            if len(parts) >= 4:
                psu_id = parts[3]
                if sweep_manager:
                    self._send_json(sweep_manager.get_status(psu_id))
                else:
                    self._send_error_json(503, 'Sweep manager not available')
            else:
                self._send_error_json(400, 'Missing PSU id')

        elif path == '/api/datalog':
            if datalogger:
                self._send_json(datalogger.get_all_status())
            else:
                self._send_error_json(503, 'Datalogger not available')

        elif path.startswith('/api/datalog/'):
            parts = path.split('/')
            if len(parts) >= 4:
                psu_id = parts[3]
                sub = parts[4] if len(parts) >= 5 else ''
                if not datalogger:
                    self._send_error_json(503, 'Datalogger not available')
                    return
                if sub == 'csv':
                    csv_data, err = datalogger.get_csv(psu_id)
                    if err:
                        self._send_error_json(404, err)
                    else:
                        self._send_csv(csv_data, 'psu_%s_log.csv' % psu_id)
                else:
                    result, err = datalogger.get_data(psu_id)
                    if err:
                        self._send_error_json(404, err)
                    else:
                        self._send_json(result)
            else:
                self._send_error_json(400, 'Missing PSU id')

        else:
            self._send_error_json(404, 'Unknown API endpoint')

    # --- POST routes ---

    def do_POST(self):
        path = self.path.split('?')[0]
        body = self._read_body()

        if path.startswith('/api/psu/'):
            parts = path.split('/')
            if len(parts) < 5:
                self._send_error_json(400, 'Missing action')
                return
            psu_id = parts[3]
            action = parts[4]
            psu = self._get_psu(psu_id)
            if psu is None:
                self._send_error_json(404, 'PSU not found')
                return
            self._route_api_post(psu, action, body)

        elif path.startswith('/api/sweep/'):
            parts = path.split('/')
            if len(parts) < 5:
                self._send_error_json(400, 'Missing action')
                return
            psu_id = parts[3]
            action = parts[4]
            self._route_sweep_post(psu_id, action, body)

        elif path.startswith('/api/datalog/'):
            parts = path.split('/')
            if len(parts) < 5:
                self._send_error_json(400, 'Missing action')
                return
            psu_id = parts[3]
            action = parts[4]
            self._route_datalog_post(psu_id, action, body)

        else:
            self._send_error_json(404, 'Unknown endpoint')

    def _route_api_post(self, psu, action, body):
        ok = False

        if action == 'output':
            val = body.get('enabled')
            if val is None:
                self._send_error_json(400, 'Missing "enabled"')
                return
            ok = psu.set_output(bool(val))

        elif action == 'voltage':
            val = body.get('voltage')
            if val is None:
                self._send_error_json(400, 'Missing "voltage"')
                return
            ok = psu.set_voltage(float(val))

        elif action == 'current':
            val = body.get('current')
            if val is None:
                self._send_error_json(400, 'Missing "current"')
                return
            ok = psu.set_current(float(val))

        elif action == 'lock':
            ok = psu.set_lock(bool(body.get('locked', False)))

        elif action == 'backlight':
            ok = psu.set_backlight(int(body.get('level', 5)))

        elif action == 'sleep':
            ok = psu.set_sleep(int(body.get('minutes', 0)))

        elif action == 'beeper':
            ok = psu.set_beeper(bool(body.get('enabled', True)))

        elif action == 'temp_unit':
            ok = psu.set_temp_unit(body.get('fahrenheit', False))

        elif action == 'mppt':
            if 'enabled' in body:
                ok = psu.set_mppt(bool(body['enabled']))
            if 'threshold' in body:
                ok = psu.set_mppt_threshold(float(body['threshold']))

        elif action == 'cp':
            if 'enabled' in body:
                ok = psu.set_cp_enabled(bool(body['enabled']))
            if 'power' in body:
                ok = psu.set_cp_power(float(body['power']))

        elif action == 'btf':
            ok = psu.set_btf(float(body.get('current', 0)))

        elif action == 'data_group':
            ok = psu.set_data_group(int(body.get('group', 0)))

        elif action == 'power_on_init':
            ok = psu.set_power_on_init(bool(body.get('output_on', False)))

        elif action == 'ovp':
            ok = psu.set_ovp(float(body.get('voltage', 0)))

        elif action == 'ocp':
            ok = psu.set_ocp(float(body.get('current', 0)))

        elif action == 'opp':
            ok = psu.set_opp(float(body.get('power', 0)))

        elif action == 'otp':
            ok = psu.set_otp(float(body.get('temperature', 0)))

        elif action == 'lvp':
            ok = psu.set_lvp(float(body.get('voltage', 0)))

        elif action == 'ohp':
            ok = psu.set_ohp(int(body.get('hours', 0)), int(body.get('minutes', 0)))

        elif action == 'oah':
            ok = psu.set_oah(int(body.get('mah', 0)))

        elif action == 'owh':
            ok = psu.set_owh(int(body.get('mwh', 0)))

        elif action == 'temp_cal':
            if 'internal' in body:
                ok = psu.set_temp_cal_int(float(body['internal']))
            if 'external' in body:
                ok = psu.set_temp_cal_ext(float(body['external']))

        elif action == 'factory_reset':
            ok = psu.factory_reset()

        else:
            self._send_error_json(404, 'Unknown action: %s' % action)
            return

        self._send_json({'success': ok})

    def _route_sweep_post(self, psu_id, action, body):
        if not sweep_manager:
            self._send_error_json(503, 'Sweep manager not available')
            return
        if action == 'set':
            points = body.get('points')
            if points is None or not isinstance(points, list):
                self._send_error_json(400, 'Missing "points" list')
                return
            ok, err = sweep_manager.set_program(psu_id, points)
        elif action == 'start':
            ok, err = sweep_manager.start(psu_id)
        elif action == 'stop':
            ok, err = sweep_manager.stop(psu_id)
        else:
            self._send_error_json(404, 'Unknown sweep action: %s' % action)
            return
        if err:
            self._send_json({'success': False, 'error': err})
        else:
            self._send_json({'success': ok})

    def _route_datalog_post(self, psu_id, action, body):
        if not datalogger:
            self._send_error_json(503, 'Datalogger not available')
            return
        if action == 'start':
            interval_ms = int(body.get('interval_ms', 500))
            ok, err = datalogger.start(psu_id, interval_ms)
        elif action == 'stop':
            ok, err = datalogger.stop(psu_id)
        elif action == 'clear':
            ok, err = datalogger.clear(psu_id)
        else:
            self._send_error_json(404, 'Unknown datalog action: %s' % action)
            return
        if err:
            self._send_json({'success': False, 'error': err})
        else:
            self._send_json({'success': ok})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def start_web_server(host='0.0.0.0', port=8080, psu_dict=None,
                     sweep_mgr=None, data_logger=None):
    global psus, sweep_manager, datalogger
    if psu_dict:
        psus = psu_dict
    if sweep_mgr:
        sweep_manager = sweep_mgr
    if data_logger:
        datalogger = data_logger
    server = ThreadingHTTPServer((host, port), PSURequestHandler)
    print('[WEB] Listening on %s:%d' % (host, port))
    server.serve_forever()
