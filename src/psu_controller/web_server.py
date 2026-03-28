import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Will be set by psu_controller.py before starting
psus = {}
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
        else:
            self._send_error_json(404, 'Unknown API endpoint')

    # --- POST routes ---

    def do_POST(self):
        path = self.path.split('?')[0]
        if not path.startswith('/api/psu/'):
            self._send_error_json(404, 'Unknown endpoint')
            return

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

        body = self._read_body()
        self._route_api_post(psu, action, body)

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

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def start_web_server(host='0.0.0.0', port=8080, psu_dict=None):
    global psus
    if psu_dict:
        psus = psu_dict
    server = ThreadingHTTPServer((host, port), PSURequestHandler)
    print('[WEB] Listening on %s:%d' % (host, port))
    server.serve_forever()
