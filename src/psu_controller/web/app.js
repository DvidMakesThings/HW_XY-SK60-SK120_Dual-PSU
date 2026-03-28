/* PSU Controller - Professional Dashboard Application */
(function () {
    'use strict';

    var $ = function (sel, root) { return (root || document).querySelector(sel); };
    var $$ = function (sel, root) { return Array.from((root || document).querySelectorAll(sel)); };
    var fmt = function (n, d) { if (n === undefined || n === null) return '--'; return Number(n).toFixed(d === undefined ? 2 : d); };
    var pad2 = function (n) { return n < 10 ? '0' + n : String(n); };
    var uptimeStr = function (sec) {
        sec = Math.max(0, Math.floor(sec));
        var h = Math.floor(sec / 3600); var m = Math.floor((sec % 3600) / 60); var s = sec % 60;
        return pad2(h) + ':' + pad2(m) + ':' + pad2(s);
    };

    var refreshTimer = null;
    var fullRefreshTimer = null;
    var refreshInterval = 300;
    var psuIds = [];
    var lastData = null;
    var startTime = Date.now();

    // SVG icons
    var chevSvg = '<div class="chev" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="rgba(234,240,255,.85)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>';

    // ==================== ROUTES ====================

    var routes = {
        outputs: { title: 'Outputs', crumb: 'PSU Controller / Outputs' },
        protection: { title: 'Protection', crumb: 'PSU Controller / Protection' },
        settings: { title: 'Settings', crumb: 'PSU Controller / Settings' },
        info: { title: 'System', crumb: 'PSU Controller / System' },
        'api-docs': { title: 'API Documentation', crumb: 'PSU Controller / API Docs' },
        'snmp-docs': { title: 'SNMP Documentation', crumb: 'PSU Controller / SNMP Docs' }
    };

    function setRoute(route) {
        $$('.nav button').forEach(function (b) { b.classList.toggle('active', b.getAttribute('data-route') === route); });
        $$('.panel').forEach(function (p) { p.classList.toggle('active', p.id === 'panel-' + route); });
        var t = $('#pageTitle'); var c = $('#pageCrumb');
        if (t) t.textContent = routes[route].title;
        if (c) c.textContent = routes[route].crumb;
        var sb = $('#sidebar'); if (sb) sb.classList.remove('open');
        // Re-render panels that need data
        if (lastData) {
            if (route === 'protection') renderProtection(lastData);
            if (route === 'settings') renderSettings(lastData);
            if (route === 'info') renderInfo(lastData);
        }
        if (route === 'api-docs') renderApiDocs();
        if (route === 'snmp-docs') renderSnmpDocs();
    }

    // ==================== KPI CARDS ====================

    function renderKpis(data) {
        var grid = $('#kpiGrid'); if (!grid) return;
        var totalP = 0; var onCount = 0; var total = 0; var anyFault = false;
        Object.keys(data).forEach(function (id) {
            var d = data[id]; total++;
            if (d.output_on) { onCount++; totalP += d.power || 0; }
            if (d.protect && d.protect !== 0) anyFault = true;
        });
        var first = data[Object.keys(data)[0]] || {};

        grid.innerHTML =
            '<div class="card kpi"><div class="inner">' +
            '<div class="label"><span class="dot ' + (anyFault ? 'warn' : 'good') + '"></span> System</div>' +
            '<div class="value">' + (anyFault ? 'Attention' : 'Stable') + '</div>' +
            '<div class="hint">' + (anyFault ? 'Protection flag active' : 'All channels nominal') + '</div>' +
            '</div></div>' +

            '<div class="card kpi"><div class="inner">' +
            '<div class="label"><span class="dot ' + (onCount > 0 ? 'good' : '') + '"></span> Channels active</div>' +
            '<div class="value">' + onCount + ' / ' + total + '</div>' +
            '<div class="hint">Total output: <span style="font-family:var(--mono);">' + fmt(totalP, 1) + ' W</span></div>' +
            '</div></div>' +

            '<div class="card kpi"><div class="inner">' +
            '<div class="label"><span class="dot good"></span> Input supply</div>' +
            '<div class="value">' + fmt(first.v_in, 2) + ' V</div>' +
            '<div class="hint">Shared DC input bus</div>' +
            '</div></div>' +

            '<div class="card kpi"><div class="inner">' +
            '<div class="label"><span class="dot good"></span> Temperature</div>' +
            '<div class="value">' + fmt(first.temp_int, 1) + ' C</div>' +
            '<div class="hint">Internal sensor</div>' +
            '</div></div>';
    }

    // ==================== PSU CHANNEL CARDS ====================

    function psuCard(id, d) {
        var on = d.output_on;
        var v = fmt(d.v_out, 2); var i = fmt(d.i_out, 3); var p = fmt(d.power, 2);
        var isCC = d.cvcc === 1;
        var modeStr = isCC ? 'CC' : 'CV';
        var modeClass = isCC ? 'i-color' : 'v-color';
        var stateDot = on ? (d.protect ? 'warn' : 'good') : '';
        var upSec = (d.out_hours || 0) * 3600 + (d.out_mins || 0) * 60 + (d.out_secs || 0);

        return '<div class="channel-card" data-psu="' + id + '">' +
            // Header row: name + power button
            '<div class="ch-header">' +
            '<div class="ch-name"><span class="dot ' + stateDot + '"></span>' +
            '<div class="title"><strong>' + (d.name || ('PSU-' + id.toUpperCase())) + '</strong>' +
            '<span>' + (on ? modeStr + ' mode' : 'Standby') + ' &middot; ' + uptimeStr(upSec) + '</span></div></div>' +
            '<button class="pwr-btn ' + (on ? 'on' : '') + '" data-act="toggle-output" data-psu="' + id + '">' + (on ? 'ON' : 'OFF') + '</button>' +
            '</div>' +
            // Big readings row
            '<div class="ch-readings">' +
            '<div class="ch-big"><div class="ch-big-val v-color">' + v + '</div><div class="ch-big-unit">V</div><div class="ch-big-label">Output</div></div>' +
            '<div class="ch-big"><div class="ch-big-val i-color">' + i + '</div><div class="ch-big-unit">A</div><div class="ch-big-label">Current</div></div>' +
            '<div class="ch-big"><div class="ch-big-val p-color">' + p + '</div><div class="ch-big-unit">W</div><div class="ch-big-label">Power</div></div>' +
            '</div>' +
            // Quick controls row - always visible
            '<div class="ch-controls">' +
            '<div class="ch-ctrl">' +
            '<label>Set Voltage (V)</label>' +
            '<div class="input-row-inline"><input type="number" step="0.01" min="0" max="60" data-inp="voltage" data-psu="' + id + '" placeholder="' + fmt(d.v_set, 2) + '"/>' +
            '<button class="btn" data-act="set-voltage" data-psu="' + id + '">Set</button></div>' +
            '</div>' +
            '<div class="ch-ctrl">' +
            '<label>Set Current (A)</label>' +
            '<div class="input-row-inline"><input type="number" step="0.001" min="0" max="6" data-inp="current" data-psu="' + id + '" placeholder="' + fmt(d.i_set, 3) + '"/>' +
            '<button class="btn" data-act="set-current" data-psu="' + id + '">Set</button></div>' +
            '</div>' +
            '</div>' +
            // Secondary info chips
            '<div class="ch-info">' +
            '<span class="chip"><b>Vin</b> <span class="tag">' + fmt(d.v_in, 2) + ' V</span></span>' +
            '<span class="chip"><b>Temp</b> <span class="tag">' + fmt(d.temp_int, 1) + ' C</span></span>' +
            '<span class="chip"><b>Lock</b> <span class="tag">' + (d.lock ? 'ON' : 'off') + '</span></span>' +
            '<span class="chip"><b>Energy</b> <span class="tag">' + (d.ah || 0) + 'mAh / ' + (d.wh || 0) + 'mWh</span></span>' +
            (d.protect ? '<span class="chip" style="border-color:rgba(255,77,109,.35);color:var(--bad);"><b>PROTECT</b> <span class="tag">' + d.protect + '</span></span>' : '') +
            '</div>' +
            '</div>';
    }

    function renderChannels(data) {
        var grid = $('#psuGrid'); if (!grid) return;
        var html = '';
        Object.keys(data).forEach(function (id) { html += psuCard(id, data[id]); });
        // Save focused input before replacing DOM
        var focused = document.activeElement;
        var focusInp = focused && focused.getAttribute('data-inp');
        var focusPsu = focused && focused.getAttribute('data-psu');
        var focusVal = focused && focused.value;
        grid.innerHTML = html;
        // Restore focus and value if user was typing
        if (focusInp && focusPsu) {
            var el = grid.querySelector('[data-inp="' + focusInp + '"][data-psu="' + focusPsu + '"]');
            if (el) { el.value = focusVal || ''; el.focus(); }
        }
    }

    // ==================== PROTECTION PANEL ====================

    function renderProtection(data) {
        var grid = $('#protGrid'); if (!grid) return;
        var html = '';
        Object.keys(data).forEach(function (id) {
            var d = data[id]; var prot = d.protection || {};
            html += '<div style="grid-column:span 12;margin-bottom:4px;">' +
                '<div class="section-title" style="margin-top:8px;"><h2>' + (d.name || ('PSU-' + id.toUpperCase())) + '</h2></div></div>';
            html += fieldNum('OVP - Over Voltage (V)', fmt(prot.ovp, 2), 'ovp', id, 'set-ovp');
            html += fieldNum('OCP - Over Current (A)', fmt(prot.ocp, 3), 'ocp', id, 'set-ocp');
            html += fieldNum('OPP - Over Power (W)', fmt(prot.opp, 1), 'opp', id, 'set-opp');
            html += fieldNum('OTP - Over Temp (C)', fmt(prot.otp, 1), 'otp', id, 'set-otp');
            html += fieldNum('LVP - Low Input Voltage (V)', fmt(prot.lvp, 2), 'lvp', id, 'set-lvp');
            // OHP (two inputs)
            html += '<div class="field"><label>OHP - Over Hours</label>' +
                '<div class="input-row"><input type="number" step="1" min="0" data-inp="ohp_h" data-psu="' + id + '" placeholder="' + (prot.ohp_h || 0) + '" style="width:45%"/>' +
                '<input type="number" step="1" min="0" max="59" data-inp="ohp_m" data-psu="' + id + '" placeholder="' + (prot.ohp_m || 0) + '" style="width:45%"/>' +
                '<button class="btn" data-act="set-ohp" data-psu="' + id + '">Set</button></div>' +
                '<div class="help">hours : minutes</div></div>';
            html += fieldNum('OAH - Over Amp-Hours (mAh)', String(prot.oah || 0), 'oah', id, 'set-oah');
            html += fieldNum('OWH - Over Watt-Hours (mWh)', String(prot.owh || 0), 'owh', id, 'set-owh');
            html += toggleRow('Power-On Output', 'power_on_init', id, prot.power_on_init);
            html += '<div class="field"><label>Protection Status</label>' +
                '<div style="font-family:var(--mono);font-size:14px;color:' + ((d.protect) ? 'var(--bad)' : 'var(--good)') + ';">' + (d.protect || '0 (clear)') + '</div></div>';
        });
        grid.innerHTML = html;
    }

    // ==================== SETTINGS PANEL ====================

    function renderSettings(data) {
        var grid = $('#settingsGrid'); if (!grid) return;
        var html = '';
        Object.keys(data).forEach(function (id) {
            var d = data[id];
            html += '<div style="grid-column:span 12;margin-bottom:4px;">' +
                '<div class="section-title" style="margin-top:8px;"><h2>' + (d.name || ('PSU-' + id.toUpperCase())) + '</h2></div></div>';
            html += toggleRow('Lock Panel', 'lock', id, d.lock);
            html += toggleRow('Beeper', 'beeper', id, d.beeper);
            html += toggleRow('Temp: Fahrenheit', 'temp_unit', id, d.temp_unit === 'F');
            html += toggleRow('MPPT Solar Mode', 'mppt', id, d.mppt_enabled);
            html += toggleRow('Constant Power Mode', 'cp', id, d.cp_enabled);
            html += fieldNum('Backlight (0-5)', String(d.backlight || 5), 'backlight', id, 'set-backlight');
            html += fieldNum('Sleep Timeout (min, 0=off)', String(d.sleep_min || 0), 'sleep', id, 'set-sleep');
            html += fieldNum('MPPT Threshold', fmt(d.mppt_threshold, 2), 'mppt_threshold', id, 'set-mppt-threshold');
            html += fieldNum('Constant Power (W)', fmt(d.cp_set, 1), 'cp_set', id, 'set-cp-power');
            html += fieldNum('Battery Full Cutoff (A)', fmt(d.btf, 3), 'btf', id, 'set-btf');
            html += fieldNum('Data Group (0-9)', String(d.data_group || 0), 'data_group', id, 'set-data-group');
            html += fieldNum('Int Temp Cal (C)', fmt(d.temp_cal_int, 1), 'temp_cal_int', id, 'set-temp-cal-int');
            html += fieldNum('Ext Temp Cal (C)', fmt(d.temp_cal_ext, 1), 'temp_cal_ext', id, 'set-temp-cal-ext');
            html += '<div class="field"><label>Factory Reset</label>' +
                '<button class="btn danger" data-act="factory-reset" data-psu="' + id + '">Reset to Defaults</button>' +
                '<div class="help">Erases all settings on this PSU. Cannot be undone.</div></div>';
        });
        grid.innerHTML = html;
    }

    // ==================== INFO PANEL ====================

    function renderInfo(data) {
        var grid = $('#infoGrid'); if (!grid) return;
        var html = '';
        Object.keys(data).forEach(function (id) {
            var d = data[id];
            html += '<div class="info-card"><h3>' + (d.name || ('PSU-' + id.toUpperCase())) + '</h3>' +
                '<table class="info-table">' +
                infoRow('Model', d.model || '--') +
                infoRow('Firmware', 'v' + (d.version || '--')) +
                infoRow('Slave Address', String(d.slave_addr || '--')) +
                infoRow('Baud Rate', String(d.baudrate || '--')) +
                infoRow('Serial Port', d.port || '--') +
                infoRow('Internal Temp', fmt(d.temp_int, 1) + ' C') +
                infoRow('External Temp', (d.temp_ext !== null && d.temp_ext !== undefined ? fmt(d.temp_ext, 1) + ' C' : 'N/A')) +
                '</table></div>';
        });
        html += '<div class="info-card"><h3>Network / SNMP</h3>' +
            '<table class="info-table">' +
            infoRow('Web UI', 'http://' + location.host + '/') +
            infoRow('SNMP Port', '161') +
            infoRow('Read Community', 'public') +
            infoRow('Write Community', 'private') +
            infoRow('Base OID', '1.3.6.1.4.1.99999.1') +
            '</table></div>';
        grid.innerHTML = html;
    }

    function infoRow(k, v) { return '<tr><td>' + k + '</td><td>' + v + '</td></tr>'; }

    // ==================== DOCS PANEL ====================

    var apiDocsRendered = false;
    var snmpDocsRendered = false;

    function renderApiDocs() {
        if (apiDocsRendered) return;
        var el = $('#apiDocsContent'); if (!el) return;
        apiDocsRendered = true;

        var host = location.hostname || '192.168.0.190';
        var port = location.port || '8080';
        var base = 'http://' + host + ':' + port;

        var h = '';

        h += '<div class="card"><div class="inner">';
        h += '<p class="note">All endpoints are served from <code>' + base + '</code>. '
            + 'GET endpoints return JSON. POST endpoints accept a JSON body and return <code>{"success": true/false}</code>. '
            + 'CORS is enabled (Access-Control-Allow-Origin: *). PSU IDs are <code>a</code> and <code>b</code>.</p>';
        h += '</div></div>';

        // -- GET endpoints --
        h += '<div style="height:12px;"></div>';
        h += '<div class="section-title"><h2>GET Endpoints</h2></div>';

        h += docEndpoint('GET', '/api/status',
            'Returns full status for all connected PSUs.',
            null,
            'curl ' + base + '/api/status');

        h += docEndpoint('GET', '/api/psu/{id}',
            'Full status for a single PSU (readings + settings + protection).',
            null,
            'curl ' + base + '/api/psu/a');

        h += docEndpoint('GET', '/api/psu/{id}/readings',
            'Live readings only: voltage, current, power, input voltage, temperature, etc.',
            null,
            'curl ' + base + '/api/psu/a/readings');

        h += docEndpoint('GET', '/api/psu/{id}/settings',
            'Device settings: backlight, sleep, lock, beeper, MPPT, constant-power, etc.',
            null,
            'curl ' + base + '/api/psu/b/settings');

        h += docEndpoint('GET', '/api/psu/{id}/protection',
            'Protection thresholds: OVP, OCP, OPP, OTP, LVP, OHP, OAH, OWH.',
            null,
            'curl ' + base + '/api/psu/a/protection');

        h += docEndpoint('GET', '/api/snmp',
            'SNMP agent configuration (community strings, port, base OID).',
            null,
            'curl ' + base + '/api/snmp');

        // -- POST endpoints --
        h += '<div style="height:12px;"></div>';
        h += '<div class="section-title"><h2>POST Endpoints -- Control</h2></div>';

        h += docEndpoint('POST', '/api/psu/{id}/output',
            'Enable or disable the PSU output.',
            '{"enabled": true}',
            'curl -X POST -H "Content-Type: application/json" -d \'{"enabled":true}\' ' + base + '/api/psu/a/output');

        h += docEndpoint('POST', '/api/psu/{id}/voltage',
            'Set the output voltage setpoint (V).',
            '{"voltage": 12.50}',
            'curl -X POST -H "Content-Type: application/json" -d \'{"voltage":12.5}\' ' + base + '/api/psu/a/voltage');

        h += docEndpoint('POST', '/api/psu/{id}/current',
            'Set the output current limit (A).',
            '{"current": 2.000}',
            'curl -X POST -H "Content-Type: application/json" -d \'{"current":2.0}\' ' + base + '/api/psu/a/current');

        h += docEndpoint('POST', '/api/psu/{id}/lock',
            'Lock or unlock the front panel keys.',
            '{"locked": true}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/backlight',
            'Set LCD backlight level (0 = off, 5 = max).',
            '{"level": 3}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/sleep',
            'Auto-sleep timeout in minutes (0 = disabled).',
            '{"minutes": 30}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/beeper',
            'Enable or disable the key beeper.',
            '{"enabled": false}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/temp_unit',
            'Switch temperature display between Celsius and Fahrenheit.',
            '{"fahrenheit": true}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/mppt',
            'Enable MPPT solar mode and/or set the threshold voltage.',
            '{"enabled": true, "threshold": 18.0}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/cp',
            'Enable constant-power mode and/or set the power target (W).',
            '{"enabled": true, "power": 25.0}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/btf',
            'Battery-full cutoff current (A). Output turns off when current drops below this.',
            '{"current": 0.100}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/data_group',
            'Select preset data group (0-9).',
            '{"group": 3}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/power_on_init',
            'Restore output state on power-up.',
            '{"output_on": true}',
            null);

        // -- POST protection --
        h += '<div style="height:12px;"></div>';
        h += '<div class="section-title"><h2>POST Endpoints -- Protection</h2></div>';

        h += docEndpoint('POST', '/api/psu/{id}/ovp',
            'Over-Voltage Protection threshold (V).',
            '{"voltage": 62.0}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/ocp',
            'Over-Current Protection threshold (A).',
            '{"current": 6.100}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/opp',
            'Over-Power Protection threshold (W).',
            '{"power": 360.0}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/otp',
            'Over-Temperature Protection threshold (C).',
            '{"temperature": 80.0}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/lvp',
            'Low-Voltage Protection on input (V). Shuts off output if DC input drops below.',
            '{"voltage": 10.0}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/ohp',
            'Over-Hours Protection. Shuts off after specified run time.',
            '{"hours": 8, "minutes": 30}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/oah',
            'Over Amp-Hours Protection (mAh).',
            '{"mah": 5000}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/owh',
            'Over Watt-Hours Protection (mWh).',
            '{"mwh": 50000}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/temp_cal',
            'Temperature sensor calibration offset (C). Can set internal and/or external.',
            '{"internal": 0.5, "external": -1.2}',
            null);

        h += docEndpoint('POST', '/api/psu/{id}/factory_reset',
            'Reset all settings to factory defaults. Cannot be undone.',
            '{}',
            'curl -X POST ' + base + '/api/psu/a/factory_reset');

        el.innerHTML = h;
    }

    function renderSnmpDocs() {
        if (snmpDocsRendered) return;
        var el = $('#snmpDocsContent'); if (!el) return;
        snmpDocsRendered = true;

        var host = location.hostname || '192.168.0.190';
        var B = '1.3.6.1.4.1.99999.1';

        var h = '';

        h += '<div class="card"><div class="inner">';
        h += '<p class="note">The built-in SNMP agent listens on <b>UDP port 161</b>. '
            + 'Read community: <code>public</code>. Write community: <code>private</code>.<br>'
            + 'Base OID: <code>' + B + '</code><br>'
            + 'Supports GET, GETNEXT, GETBULK, and SET operations.<br>'
            + 'Integer values are raw register values (see scale column). '
            + 'For example, voltage 12.50 V is stored as 1250 (x100).</p>';
        h += '</div></div>';

        // -- Scalar --
        h += '<div style="height:12px;"></div>';
        h += '<div class="section-title"><h2>Scalar OIDs</h2></div>';
        h += '<div class="card"><div class="inner">';
        h += '<table class="info-table">';
        h += '<tr><td style="color:var(--muted);width:50%">OID</td><td style="font-family:var(--mono)">' + B + '.1.0</td></tr>';
        h += '<tr><td style="color:var(--muted)">Name</td><td>psuCount</td></tr>';
        h += '<tr><td style="color:var(--muted)">Type</td><td>INTEGER</td></tr>';
        h += '<tr><td style="color:var(--muted)">Description</td><td>Number of connected PSU channels</td></tr>';
        h += '</table>';
        h += '<div style="margin-top:10px;"><code class="doc-cmd">snmpget -v2c -c public ' + host + ' ' + B + '.1.0</code></div>';
        h += '</div></div>';

        // -- Table --
        h += '<div style="height:12px;"></div>';
        h += '<div class="section-title"><h2>PSU Table OIDs</h2></div>';

        h += '<div class="card"><div class="inner">';
        h += '<p class="note">Table OID format: <code>' + B + '.2.1.&lt;column&gt;.&lt;row&gt;</code><br>'
            + 'Row 1 = PSU-A, Row 2 = PSU-B. Writable columns accept SNMP SET with the raw integer value.</p>';
        h += '</div></div>';

        h += '<div style="height:8px;"></div>';
        h += '<div class="card"><div class="inner" style="overflow-x:auto;">';
        h += '<table class="doc-table">';
        h += '<thead><tr><th>Col</th><th>OID Suffix</th><th>Name</th><th>Type</th><th>Scale</th><th>RW</th><th>Description</th></tr></thead>';
        h += '<tbody>';

        var cols = [
            [1, 'psuIndex', 'INT', '--', 'RO', 'Row index (1, 2, ...)'],
            [2, 'psuName', 'STRING', '--', 'RO', 'Channel name (PSU-A, PSU-B)'],
            [3, 'psuSetVoltage', 'INT', 'x100', 'RW', 'Voltage setpoint. 1250 = 12.50 V'],
            [4, 'psuSetCurrent', 'INT', 'x1000', 'RW', 'Current limit. 2000 = 2.000 A'],
            [5, 'psuOutputVoltage', 'INT', 'x100', 'RO', 'Measured output voltage'],
            [6, 'psuOutputCurrent', 'INT', 'x1000', 'RO', 'Measured output current'],
            [7, 'psuOutputPower', 'INT', 'x100', 'RO', 'Calculated output power'],
            [8, 'psuInputVoltage', 'INT', 'x100', 'RO', 'DC input bus voltage'],
            [9, 'psuInternalTemp', 'INT', 'x10', 'RO', 'Internal temp sensor. 318 = 31.8 C'],
            [10, 'psuExternalTemp', 'INT', 'x10', 'RO', 'External temp sensor (-1 = N/A)'],
            [11, 'psuOutputEnabled', 'INT', '0/1', 'RW', '1 = output ON, 0 = output OFF'],
            [12, 'psuCVCC', 'INT', '0/1', 'RO', '0 = CV (constant voltage), 1 = CC (constant current)'],
            [13, 'psuProtectStatus', 'INT', '--', 'RO', 'Protection status register (0 = clear)'],
            [14, 'psuKeyLock', 'INT', '0/1', 'RW', '1 = front panel locked'],
            [15, 'psuBacklight', 'INT', '0-5', 'RW', 'LCD backlight level (0=off, 5=max)'],
            [16, 'psuBeeper', 'INT', '0/1', 'RW', '1 = beeper enabled'],
            [17, 'psuModel', 'STRING', '--', 'RO', 'Device model string'],
            [18, 'psuFirmware', 'STRING', '--', 'RO', 'Firmware version'],
            [19, 'psuAmpHours', 'Counter32', '--', 'RO', 'Accumulated amp-hours (mAh)'],
            [20, 'psuWattHours', 'Counter32', '--', 'RO', 'Accumulated watt-hours (mWh)'],
            [21, 'psuOutputTimeSec', 'Counter32', '--', 'RO', 'Total output ON time (seconds)'],
            [22, 'psuMPPTEnabled', 'INT', '0/1', 'RW', '1 = MPPT solar mode ON'],
            [23, 'psuSleepMin', 'INT', 'min', 'RW', 'Auto-sleep timeout (0 = disabled)'],
            [24, 'psuOVP', 'INT', 'x100', 'RW', 'Over-voltage protection (V)'],
            [25, 'psuOCP', 'INT', 'x1000', 'RW', 'Over-current protection (A)'],
            [26, 'psuOPP', 'INT', 'x10', 'RW', 'Over-power protection (W)'],
            [27, 'psuOTP', 'INT', 'x10', 'RW', 'Over-temperature protection (C)'],
            [28, 'psuLVP', 'INT', 'x100', 'RW', 'Low-voltage protection on input (V)']
        ];

        for (var ci = 0; ci < cols.length; ci++) {
            var c = cols[ci];
            var rwClass = c[4] === 'RW' ? ' style="color:var(--good);"' : '';
            h += '<tr><td>' + c[0] + '</td><td style="font-family:var(--mono);">.2.1.' + c[0] + '.{row}</td>' +
                '<td>' + c[1] + '</td><td>' + c[2] + '</td><td style="font-family:var(--mono);">' + c[3] + '</td>' +
                '<td' + rwClass + '>' + c[4] + '</td><td>' + c[5] + '</td></tr>';
        }

        h += '</tbody></table>';
        h += '</div></div>';

        // -- SNMP Command Reference --
        h += '<div style="height:12px;"></div>';
        h += '<div class="section-title"><h2>SNMP Command Examples -- PSU-A (Row 1)</h2></div>';

        h += '<div class="card"><div class="inner">';
        h += '<p class="note">Replace <code>' + host + '</code> with your device IP. For PSU-B use row <code>2</code> instead of <code>1</code>.</p>';
        h += '<div style="height:8px;"></div>';

        var cmds = [
            ['# --- Read operations (GET) ---', ''],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.1.0', 'psuCount'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.1.1', 'psuIndex (row 1)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.2.1', 'psuName'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.3.1', 'psuSetVoltage (raw x100)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.4.1', 'psuSetCurrent (raw x1000)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.5.1', 'psuOutputVoltage (raw x100)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.6.1', 'psuOutputCurrent (raw x1000)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.7.1', 'psuOutputPower (raw x100)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.8.1', 'psuInputVoltage (raw x100)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.9.1', 'psuInternalTemp (raw x10)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.10.1', 'psuExternalTemp (raw x10, -1=N/A)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.11.1', 'psuOutputEnabled (0/1)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.12.1', 'psuCVCC (0=CV, 1=CC)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.13.1', 'psuProtectStatus'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.14.1', 'psuKeyLock (0/1)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.15.1', 'psuBacklight (0-5)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.16.1', 'psuBeeper (0/1)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.17.1', 'psuModel'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.18.1', 'psuFirmware'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.19.1', 'psuAmpHours (mAh)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.20.1', 'psuWattHours (mWh)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.21.1', 'psuOutputTimeSec'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.22.1', 'psuMPPTEnabled (0/1)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.23.1', 'psuSleepMin'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.24.1', 'psuOVP (raw x100)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.25.1', 'psuOCP (raw x1000)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.26.1', 'psuOPP (raw x10)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.27.1', 'psuOTP (raw x10)'],
            ['snmpget -v2c -c public ' + host + ' ' + B + '.2.1.28.1', 'psuLVP (raw x100)'],
            ['', ''],
            ['# --- Walk entire table ---', ''],
            ['snmpwalk -v2c -c public ' + host + ' ' + B + '.2', 'walk all PSU table entries'],
            ['snmpbulkget -v2c -c public -Cr28 ' + host + ' ' + B + '.2.1.0.1', 'bulk-get all 28 cols for PSU-A'],
            ['', ''],
            ['# --- Write operations (SET) ---', ''],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.3.1 i 1250', 'set voltage to 12.50 V'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.4.1 i 2000', 'set current limit to 2.000 A'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.11.1 i 1', 'turn output ON'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.11.1 i 0', 'turn output OFF'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.14.1 i 1', 'lock front panel'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.15.1 i 3', 'set backlight to level 3'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.16.1 i 0', 'disable beeper'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.22.1 i 1', 'enable MPPT mode'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.23.1 i 30', 'set auto-sleep to 30 min'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.24.1 i 6200', 'set OVP to 62.00 V'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.25.1 i 6100', 'set OCP to 6.100 A'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.26.1 i 3600', 'set OPP to 360.0 W'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.27.1 i 800', 'set OTP to 80.0 C'],
            ['snmpset -v2c -c private ' + host + ' ' + B + '.2.1.28.1 i 1000', 'set LVP to 10.00 V']
        ];

        h += '<pre class="doc-pre">';
        for (var i = 0; i < cmds.length; i++) {
            var cmd = cmds[i][0];
            var comment = cmds[i][1];
            if (cmd === '' && comment === '') { h += '\n'; continue; }
            if (cmd.indexOf('# ') === 0) { h += '<span class="doc-comment">' + cmd + '</span>\n'; continue; }
            h += cmd;
            if (comment) h += '   <span class="doc-comment"># ' + comment + '</span>';
            h += '\n';
        }
        h += '</pre>';

        h += '</div></div>';

        // -- PSU-B note --
        h += '<div style="height:12px;"></div>';
        h += '<div class="card"><div class="inner">';
        h += '<p class="note"><b>PSU-B (Row 2):</b> Replace the trailing <code>.1</code> with <code>.2</code> in all table OIDs above. '
            + 'For example, PSU-B output voltage: <code>' + B + '.2.1.5.2</code></p>';
        h += '</div></div>';

        el.innerHTML = h;
    }

    function docEndpoint(method, path, desc, bodyExample, curlExample) {
        var mClass = method === 'GET' ? 'v-color' : 'i-color';
        var h = '<div style="height:8px;"></div>';
        h += '<div class="card"><div class="inner">';
        h += '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">';
        h += '<span class="pill" style="font-weight:700;font-family:var(--mono);color:' + (method === 'GET' ? 'var(--voltage)' : 'var(--current)') + ';">' + method + '</span>';
        h += '<code style="font-size:14px;">' + path + '</code>';
        h += '</div>';
        h += '<p class="note" style="margin-top:8px;">' + desc + '</p>';
        if (bodyExample) {
            h += '<div style="margin-top:8px;"><span style="font-size:11px;color:var(--muted);">Request body:</span>';
            h += '<pre class="doc-pre" style="margin-top:4px;">' + bodyExample + '</pre></div>';
        }
        if (curlExample) {
            h += '<div style="margin-top:8px;"><span style="font-size:11px;color:var(--muted);">Example:</span>';
            h += '<pre class="doc-pre" style="margin-top:4px;">' + curlExample + '</pre></div>';
        }
        h += '</div></div>';
        return h;
    }

    // ==================== HELPERS ====================

    function fieldNum(label, placeholder, inputName, psuId, action) {
        return '<div class="field"><label>' + label + '</label>' +
            '<div class="input-row"><input type="number" step="any" data-inp="' + inputName + '" data-psu="' + psuId + '" placeholder="' + placeholder + '"/>' +
            '<button class="btn" data-act="' + action + '" data-psu="' + psuId + '">Set</button></div></div>';
    }

    function toggleRow(label, toggleName, psuId, checked) {
        return '<div class="toggle-row">' +
            '<div><div class="t-label">' + label + '</div></div>' +
            '<div class="switch' + (checked ? ' on' : '') + '" data-tog="' + toggleName + '" data-psu="' + psuId + '"><span class="knob"></span></div>' +
            '</div>';
    }

    // ==================== SIDEBAR ====================

    function updateSidebar(data) {
        var connected = !!data;
        var conn = $('#sideConn');
        if (conn) { conn.textContent = connected ? 'Online' : 'Offline'; conn.className = 'conn-badge ' + (connected ? 'online' : 'offline'); }
        var up = $('#sideUptime');
        if (up) up.textContent = uptimeStr(Math.floor((Date.now() - startTime) / 1000));
        var pill = $('#sideFaultPill');
        if (pill && data) {
            var anyFault = false;
            Object.keys(data).forEach(function (id) { if (data[id].protect) anyFault = true; });
            if (anyFault) { pill.textContent = 'Fault active'; pill.style.borderColor = 'rgba(255,77,109,.35)'; pill.style.background = 'rgba(255,77,109,.12)'; pill.style.color = 'rgba(255,77,109,.9)'; }
            else { pill.textContent = 'No faults'; pill.style.borderColor = 'rgba(62,245,154,.25)'; pill.style.background = 'rgba(62,245,154,.08)'; pill.style.color = 'rgba(234,240,255,.82)'; }
        }
        var statusPill = $('#pillStatus');
        if (statusPill) statusPill.textContent = connected ? 'LIVE' : 'OFFLINE';
    }

    // ==================== MASTER SWITCH ====================

    function updateMasterSwitch(data) {
        var sw = $('#masterSwitch'); if (!sw || !data) return;
        var anyOn = false;
        Object.keys(data).forEach(function (id) { if (data[id].output_on) anyOn = true; });
        sw.classList.toggle('on', anyOn);
    }

    function handleMasterSwitch(data) {
        if (!data) return;
        var anyOn = false;
        Object.keys(data).forEach(function (id) { if (data[id].output_on) anyOn = true; });
        var newState = !anyOn;
        var ids = Object.keys(data);
        var done = 0;
        ids.forEach(function (id) {
            apiPost(id, 'output', { enabled: newState }, function () {
                done++; if (done >= ids.length) refreshNow();
            });
        });
    }

    // ==================== EVENT DELEGATION ====================

    document.addEventListener('click', function (e) {
        // Buttons with data-act
        var btn = e.target.closest('[data-act]');
        if (!btn) return;
        var act = btn.getAttribute('data-act');
        var psu = btn.getAttribute('data-psu');
        if (!psu) return;

        e.preventDefault(); e.stopPropagation();

        if (act === 'toggle-output') {
            var d = lastData && lastData[psu];
            apiPost(psu, 'output', { enabled: !(d && d.output_on) }, function (ok) { if (ok) refreshNow(); });
            return;
        }

        if (act === 'set-voltage') {
            var v = getInp('voltage', psu); if (v === '') return;
            apiPost(psu, 'voltage', { voltage: parseFloat(v) }, ack('Voltage')); return;
        }
        if (act === 'set-current') {
            var c = getInp('current', psu); if (c === '') return;
            apiPost(psu, 'current', { current: parseFloat(c) }, ack('Current')); return;
        }
        if (act === 'set-ovp') { apiPost(psu, 'ovp', { voltage: pf('ovp', psu) }, ack('OVP')); return; }
        if (act === 'set-ocp') { apiPost(psu, 'ocp', { current: pf('ocp', psu) }, ack('OCP')); return; }
        if (act === 'set-opp') { apiPost(psu, 'opp', { power: pf('opp', psu) }, ack('OPP')); return; }
        if (act === 'set-otp') { apiPost(psu, 'otp', { temperature: pf('otp', psu) }, ack('OTP')); return; }
        if (act === 'set-lvp') { apiPost(psu, 'lvp', { voltage: pf('lvp', psu) }, ack('LVP')); return; }
        if (act === 'set-ohp') {
            apiPost(psu, 'ohp', { hours: pi('ohp_h', psu), minutes: pi('ohp_m', psu) }, ack('OHP')); return;
        }
        if (act === 'set-oah') { apiPost(psu, 'oah', { mah: pi('oah', psu) }, ack('OAH')); return; }
        if (act === 'set-owh') { apiPost(psu, 'owh', { mwh: pi('owh', psu) }, ack('OWH')); return; }
        if (act === 'set-backlight') { apiPost(psu, 'backlight', { level: pi('backlight', psu) }, ack('Backlight')); return; }
        if (act === 'set-sleep') { apiPost(psu, 'sleep', { minutes: pi('sleep', psu) }, ack('Sleep')); return; }
        if (act === 'set-mppt-threshold') { apiPost(psu, 'mppt', { threshold: pf('mppt_threshold', psu) }, ack('MPPT threshold')); return; }
        if (act === 'set-cp-power') { apiPost(psu, 'cp', { power: pf('cp_set', psu) }, ack('CP power')); return; }
        if (act === 'set-btf') { apiPost(psu, 'btf', { current: pf('btf', psu) }, ack('BTF')); return; }
        if (act === 'set-data-group') { apiPost(psu, 'data_group', { group: pi('data_group', psu) }, ack('Data group')); return; }
        if (act === 'set-temp-cal-int') { apiPost(psu, 'temp_cal', { internal: pf('temp_cal_int', psu) }, ack('Int temp cal')); return; }
        if (act === 'set-temp-cal-ext') { apiPost(psu, 'temp_cal', { external: pf('temp_cal_ext', psu) }, ack('Ext temp cal')); return; }
        if (act === 'factory-reset') {
            if (confirm('Factory reset this PSU? All settings will be lost.')) {
                apiPost(psu, 'factory_reset', {}, function (ok) { if (ok) { showToast('Factory reset sent', 'success'); refreshNow(); } });
            }
            return;
        }
    });

    // Toggle switches
    document.addEventListener('click', function (e) {
        var sw = e.target.closest('.switch[data-tog]');
        if (!sw) return;
        e.preventDefault();
        var tog = sw.getAttribute('data-tog');
        var psu = sw.getAttribute('data-psu');
        var isOn = sw.classList.contains('on');
        var newVal = !isOn;

        var bodyMap = {
            lock: function (v) { return { locked: v }; },
            beeper: function (v) { return { enabled: v }; },
            temp_unit: function (v) { return { fahrenheit: v }; },
            mppt: function (v) { return { enabled: v }; },
            cp: function (v) { return { enabled: v }; },
            power_on_init: function (v) { return { output_on: v }; }
        };
        var fn = bodyMap[tog]; if (!fn) return;
        sw.classList.toggle('on');
        apiPost(psu, tog, fn(newVal), function (ok) { if (ok) refreshNow(); });
    });

    // Master switch
    (function () {
        var ms = $('#masterSwitch');
        if (ms) ms.addEventListener('click', function () { handleMasterSwitch(lastData); });
    })();

    // Factory reset button on settings header
    (function () {
        var btn = $('#btnFactoryReset');
        if (btn) btn.addEventListener('click', function () {
            if (!lastData) return;
            if (!confirm('Factory reset ALL PSUs?')) return;
            Object.keys(lastData).forEach(function (id) {
                apiPost(id, 'factory_reset', {}, function () { });
            });
            showToast('Factory reset sent to all PSUs', 'success');
            setTimeout(refreshNow, 1500);
        });
    })();

    // ==================== INPUT HELPERS ====================

    function getInp(name, psu) {
        var el = document.querySelector('[data-inp="' + name + '"][data-psu="' + psu + '"]');
        return el ? el.value : '';
    }
    function pf(name, psu) { return parseFloat(getInp(name, psu)) || 0; }
    function pi(name, psu) { return parseInt(getInp(name, psu), 10) || 0; }
    function ack(label) { return function (ok) { if (ok) { showToast(label + ' set', 'success'); refreshNow(); } }; }

    // ==================== DATA REFRESH ====================

    function updateAll(data) {
        lastData = data;
        updateSidebar(data);
        if (!data) return;
        renderKpis(data);
        renderChannels(data);
        updateMasterSwitch(data);
    }

    function updateReadings(data) {
        if (!data) return;
        // Merge fast readings into lastData so UI stays complete
        if (!lastData) { lastData = data; }
        else {
            Object.keys(data).forEach(function (id) {
                if (!lastData[id]) { lastData[id] = data[id]; }
                else {
                    var r = data[id];
                    for (var k in r) { lastData[id][k] = r[k]; }
                }
            });
        }
        updateSidebar(lastData);
        renderKpis(lastData);
        renderChannels(lastData);
        updateMasterSwitch(lastData);
    }

    function fetchReadings(cb) {
        fetch('/api/readings').then(function (r) { return r.json(); }).then(function (d) { cb(d); }).catch(function () { cb(null); });
    }

    function fetchStatus(cb) {
        fetch('/api/status').then(function (r) { return r.json(); }).then(function (d) { cb(d); }).catch(function () { cb(null); });
    }

    function apiPost(psuId, action, body, cb) {
        fetch('/api/psu/' + psuId + '/' + action, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
        }).then(function (r) { return r.json(); }).then(function (d) {
            if (d.error) { showToast(d.error, 'error'); cb(false); } else { cb(d.success !== false); }
        }).catch(function (err) { showToast('Request failed: ' + err.message, 'error'); cb(false); });
    }

    function startRefresh() {
        if (refreshTimer) clearTimeout(refreshTimer);
        if (fullRefreshTimer) clearInterval(fullRefreshTimer);
        if (refreshInterval > 0) {
            // Chained fast poll: wait for response before scheduling next
            (function poll() {
                refreshTimer = setTimeout(function () {
                    fetchReadings(function (d) { updateReadings(d); poll(); });
                }, refreshInterval);
            })();
            fullRefreshTimer = setInterval(function () { fetchStatus(updateAll); }, 5000);
        }
    }

    function refreshNow() { setTimeout(function () { fetchReadings(updateReadings); }, 150); }

    // ==================== TOAST ====================

    var toastTimeout;
    function showToast(msg, type) {
        var el = $('#toast'); if (!el) return;
        el.textContent = msg; el.className = 'toast ' + (type || 'success');
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(function () { el.classList.add('hidden'); }, 3000);
    }

    // ==================== INIT ====================

    function init() {
        // Sidebar nav
        $$('.nav button').forEach(function (b) { b.addEventListener('click', function () { setRoute(b.getAttribute('data-route')); }); });
        // Hamburger
        var hamb = $('#hamb'); if (hamb) hamb.addEventListener('click', function () { $('#sidebar').classList.toggle('open'); });
        // Refresh rate
        var rr = $('#refresh-rate'); if (rr) rr.addEventListener('change', function () { refreshInterval = parseInt(this.value, 10); startRefresh(); });
        // Initial fetch
        fetchStatus(function (data) { updateAll(data); });
        startRefresh();
    }

    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }

})();
