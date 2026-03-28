"""
Sweep Manager - Automated timed voltage sweep sequences for PSU channels.
Each PSU can have an independent program: a sorted list of (time_ms, voltage)
waypoints. When started, the sweep steps through the waypoints in order,
applying the voltage setpoint at each timestamp. The sweep ends automatically
when the last waypoint time is reached.
"""

import threading
import time


class SweepManager:
    """Manages timed voltage sweep sequences for PSU channels."""

    def __init__(self):
        self._programs = {}     # psu_id -> list of {'time_ms': int, 'voltage': float}
        self._status = {}       # psu_id -> {'running': bool, 'elapsed_ms': int, 'current_step': int}
        self._threads = {}
        self._stop_events = {}
        self._lock = threading.Lock()
        self._psus = {}

    def set_psus(self, psus):
        self._psus = psus
        for psu_id in psus:
            if psu_id not in self._programs:
                self._programs[psu_id] = []
            if psu_id not in self._status:
                self._status[psu_id] = {
                    'running': False,
                    'elapsed_ms': 0,
                    'current_step': -1,
                }

    def set_program(self, psu_id, points):
        """Set sweep program.

        Each waypoint is a dict with 'time_ms' and at least one of:
          'voltage': float  — set output voltage at this time
          'output':  bool   — enable (True) or disable (False) output at this time
        Both fields may be present in a single waypoint.
        """
        if psu_id not in self._psus:
            return False, 'Unknown PSU'
        try:
            validated = []
            for p in points:
                wp = {'time_ms': int(p['time_ms'])}
                if 'voltage' in p and p['voltage'] is not None:
                    wp['voltage'] = float(p['voltage'])
                if 'output' in p and p['output'] is not None:
                    wp['output'] = bool(p['output'])
                if 'voltage' not in wp and 'output' not in wp:
                    raise ValueError('Waypoint must have voltage or output field')
                validated.append(wp)
            validated.sort(key=lambda p: p['time_ms'])
        except (KeyError, TypeError, ValueError) as exc:
            return False, 'Invalid point: %s' % exc
        with self._lock:
            self._programs[psu_id] = validated
        return True, None

    def start(self, psu_id):
        """Start sweep execution for a PSU."""
        if psu_id not in self._psus:
            return False, 'Unknown PSU'
        with self._lock:
            if self._status.get(psu_id, {}).get('running'):
                return False, 'Sweep already running'
            if not self._programs.get(psu_id):
                return False, 'No sweep program defined'
        self._cancel(psu_id)
        ev = threading.Event()
        self._stop_events[psu_id] = ev
        t = threading.Thread(target=self._run, args=(psu_id, ev), daemon=True)
        self._threads[psu_id] = t
        with self._lock:
            self._status[psu_id] = {
                'running': True,
                'elapsed_ms': 0,
                'current_step': -1,
            }
        t.start()
        return True, None

    def stop(self, psu_id):
        """Stop sweep execution for a PSU."""
        if psu_id not in self._psus:
            return False, 'Unknown PSU'
        self._cancel(psu_id)
        with self._lock:
            if psu_id in self._status:
                self._status[psu_id]['running'] = False
        return True, None

    def _cancel(self, psu_id):
        ev = self._stop_events.pop(psu_id, None)
        if ev:
            ev.set()
        t = self._threads.pop(psu_id, None)
        if t and t.is_alive():
            t.join(timeout=2.0)

    def _run(self, psu_id, stop_event):
        psu = self._psus[psu_id]
        with self._lock:
            program = list(self._programs[psu_id])

        start_t = time.monotonic()
        last_step = -1

        while not stop_event.is_set():
            elapsed_ms = int((time.monotonic() - start_t) * 1000)

            # Current step: last waypoint whose time_ms <= elapsed_ms
            step = -1
            for i, pt in enumerate(program):
                if pt['time_ms'] <= elapsed_ms:
                    step = i

            with self._lock:
                self._status[psu_id]['elapsed_ms'] = elapsed_ms
                self._status[psu_id]['current_step'] = step

            # Apply actions on step change
            if step != last_step and step >= 0:
                wp = program[step]
                if 'voltage' in wp:
                    psu.set_voltage(wp['voltage'])
                if 'output' in wp:
                    psu.set_output(wp['output'])
                last_step = step

            # Finish when past the last waypoint
            if program and elapsed_ms >= program[-1]['time_ms']:
                break

            stop_event.wait(timeout=0.05)   # 50 ms resolution

        with self._lock:
            self._status[psu_id]['running'] = False

    def get_status(self, psu_id=None):
        """Return sweep status (and program) for one or all PSUs."""
        with self._lock:
            if psu_id is not None:
                return {
                    'program': list(self._programs.get(psu_id, [])),
                    'status': dict(self._status.get(psu_id, {})),
                }
            return {
                pid: {
                    'program': list(self._programs.get(pid, [])),
                    'status': dict(self._status.get(pid, {})),
                }
                for pid in self._psus
            }
