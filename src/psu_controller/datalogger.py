"""
Data Logger - Time-series logging of PSU voltage, current, and power readings.
Each PSU can be logged independently. Samples are kept in memory (ring buffer,
max 10000 entries per channel). Data can be retrieved as JSON or exported as CSV.
"""

import csv
import io
import threading
import time


class DataLogger:
    """Logs PSU readings over time for analysis and CSV export."""

    MAX_SAMPLES = 10000

    def __init__(self):
        self._logs = {}         # psu_id -> list of {'t', 'v', 'i', 'p'}
        self._status = {}       # psu_id -> {'enabled', 'interval_ms', 'samples'}
        self._threads = {}
        self._stop_events = {}
        self._lock = threading.Lock()
        self._psus = {}

    def set_psus(self, psus):
        self._psus = psus
        for psu_id in psus:
            if psu_id not in self._logs:
                self._logs[psu_id] = []
            if psu_id not in self._status:
                self._status[psu_id] = {
                    'enabled': False,
                    'interval_ms': 500,
                    'samples': 0,
                }

    def start(self, psu_id, interval_ms=500):
        """Start logging for a PSU."""
        if psu_id not in self._psus:
            return False, 'Unknown PSU'
        with self._lock:
            if self._status.get(psu_id, {}).get('enabled'):
                return False, 'Already logging'
        self._cancel(psu_id)
        ev = threading.Event()
        self._stop_events[psu_id] = ev
        with self._lock:
            self._status[psu_id]['enabled'] = True
            self._status[psu_id]['interval_ms'] = max(100, int(interval_ms))
        t = threading.Thread(
            target=self._run,
            args=(psu_id, max(100, int(interval_ms)), ev),
            daemon=True,
        )
        self._threads[psu_id] = t
        t.start()
        return True, None

    def stop(self, psu_id):
        """Stop logging for a PSU."""
        if psu_id not in self._psus:
            return False, 'Unknown PSU'
        self._cancel(psu_id)
        with self._lock:
            if psu_id in self._status:
                self._status[psu_id]['enabled'] = False
        return True, None

    def clear(self, psu_id):
        """Clear all logged samples for a PSU."""
        if psu_id not in self._psus:
            return False, 'Unknown PSU'
        with self._lock:
            self._logs[psu_id] = []
            if psu_id in self._status:
                self._status[psu_id]['samples'] = 0
        return True, None

    def _cancel(self, psu_id):
        ev = self._stop_events.pop(psu_id, None)
        if ev:
            ev.set()
        t = self._threads.pop(psu_id, None)
        if t and t.is_alive():
            t.join(timeout=2.0)

    def _run(self, psu_id, interval_ms, stop_event):
        psu = self._psus[psu_id]
        start_t = time.monotonic()
        interval_s = interval_ms / 1000.0

        while not stop_event.is_set():
            r = psu.get_readings_cached()
            if r:
                sample = {
                    't': int((time.monotonic() - start_t) * 1000),
                    'v': round(float(r.get('v_out', 0)), 3),
                    'i': round(float(r.get('i_out', 0)), 4),
                    'p': round(float(r.get('power', 0)), 3),
                }
                with self._lock:
                    logs = self._logs[psu_id]
                    if len(logs) >= self.MAX_SAMPLES:
                        logs.pop(0)
                    logs.append(sample)
                    self._status[psu_id]['samples'] = len(logs)
            stop_event.wait(timeout=interval_s)

    def get_data(self, psu_id):
        """Return logged samples + status for a PSU."""
        if psu_id not in self._psus:
            return None, 'Unknown PSU'
        with self._lock:
            return {
                'samples': list(self._logs[psu_id]),
                'status': dict(self._status[psu_id]),
            }, None

    def get_csv(self, psu_id):
        """Return logged samples as a CSV string."""
        if psu_id not in self._psus:
            return None, 'Unknown PSU'
        with self._lock:
            logs = list(self._logs[psu_id])
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['time_ms', 'voltage_V', 'current_A', 'power_W'])
        for s in logs:
            writer.writerow([s['t'], s['v'], s['i'], s['p']])
        return buf.getvalue(), None

    def get_all_status(self):
        """Return status for all PSUs."""
        with self._lock:
            return {pid: dict(self._status[pid]) for pid in self._psus}
