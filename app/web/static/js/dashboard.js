/**
 * dashboard.js \u2014 Telemetry Data Platform v3
 * Wires KPI cards, scenario doughnut, hourly speed chart, and events table
 * to the existing FastAPI analytics API endpoints.
 */

'use strict';

// &#9472;&#9472; Palette (matches app.css) &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
const SCENARIO_COLORS = {
  hard_brake:           '#EB0A1E',
  rapid_acceleration:   '#D97706',
  over_speeding:        '#1A6FD4',
  low_battery:          '#EA580C',
  risky_weather_event:  '#7C3AED',
};

const DEFAULT_COLOR = '#94A3B8';

// &#9472;&#9472; Chart instances (module-level for destroy/rebuild) &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
let doughnutChart = null;
let speedChart    = null;

// &#9472;&#9472; State &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
let currentHours = 24;

// &#9472;&#9472; DOM refs &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
const $ = (id) => document.getElementById(id);

const btnRefresh      = $('btn-refresh');
const refreshIcon     = $('refresh-icon');
const lastUpdatedEl   = $('last-updated');
const dataStatusEl    = $('data-status');
const fleetInput      = $('fleet-id-input');
const vehicleInput    = $('vehicle-id-input');
const btnLoadEvents   = $('btn-load-events');
const scenarioFilter  = $('scenario-filter');
const eventsTableWrap = $('events-table-wrap');
const hoursToggle     = $('hours-toggle');

// &#9472;&#9472; Helpers &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
function fleetId()   { return fleetInput.value.trim(); }
function vehicleId() { return vehicleInput.value.trim(); }

function setStatus(msg, cls) {
  dataStatusEl.textContent = msg;
  dataStatusEl.className = 'tdp-data-status ' + (cls || '');
}

function kpiSkeleton() {
  ['kpi-v-total','kpi-v-active','kpi-v-speed','kpi-v-battery']
    .forEach(id => {
      const el = $(id);
      el.textContent = '&#8211;';
      el.classList.add('loading');
    });
}

function kpiSet(id, value) {
  const el = $(id);
  el.classList.remove('loading');
  el.textContent = value !== null && value !== undefined ? value : '\u2014';
}

async function apiFetch(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status} \u2014 ${path}`);
  return res.json();
}

function formatDatetime(iso) {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

function batteryClass(level) {
  if (level < 15)  return 'tdp-battery-low';
  if (level < 30)  return 'tdp-battery-mid';
  return 'tdp-battery-high';
}

// &#9472;&#9472; KPI Load &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
async function loadKPIs(fid) {
  kpiSkeleton();
  const data = await apiFetch(`/api/v1/analytics/fleet/${fid}/summary`);

  kpiSet('kpi-v-total',   data.total_vehicles ?? '\u2014');
  kpiSet('kpi-v-active',  data.active_vehicles_last_hour ?? '\u2014');
  kpiSet('kpi-v-speed',
    data.avg_speed_last_hour != null
      ? parseFloat(data.avg_speed_last_hour).toFixed(1)
      : '\u2014'
  );
  kpiSet('kpi-v-battery', data.low_battery_count ?? '\u2014');
}

// &#9472;&#9472; Scenario Doughnut &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
async function loadScenarioDoughnut(fid) {
  const legendEl = $('scenario-legend');
  const totalEl  = $('doughnut-total');

  legendEl.innerHTML = `
    <div class="tdp-legend-loading">
      <div class="tdp-spinner"></div><span>Loading scenarios&#8230;</span>
    </div>`;
  totalEl.innerHTML = `<span class="tdp-doughnut-num">\u2014</span><span class="tdp-doughnut-lbl">total</span>`;

  const fromEl = $('scenario-from');
  const toEl   = $('scenario-to');

  let url = `/api/v1/analytics/fleet/${fid}/scenario-summary`;
  const params = [];
  if (fromEl.value) params.push(`from_date=${fromEl.value}T00:00:00`);
  if (toEl.value)   params.push(`to_date=${toEl.value}T23:59:59`);
  if (params.length) url += '?' + params.join('&');

  const data = await apiFetch(url);
  const summary = data.summary || {};
  const labels  = Object.keys(summary);
  const counts  = Object.values(summary);
  const total   = counts.reduce((a, b) => a + b, 0);

  totalEl.innerHTML = `<span class="tdp-doughnut-num">${total.toLocaleString()}</span><span class="tdp-doughnut-lbl">events</span>`;

  const colors = labels.map(l => SCENARIO_COLORS[l] || DEFAULT_COLOR);

  if (doughnutChart) { doughnutChart.destroy(); doughnutChart = null; }

  if (labels.length === 0) {
    legendEl.innerHTML = '<p style="font-size:0.78rem;color:var(--text-muted);padding:8px 0;">No scenario events in selected range.</p>';
    return;
  }

  const ctx = document.getElementById('scenarioDoughnut').getContext('2d');
  doughnutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: counts,
        backgroundColor: colors,
        borderColor: '#FFFFFF',
        borderWidth: 2,
        hoverBorderWidth: 3,
        hoverOffset: 6,
      }],
    },
    options: {
      cutout: '70%',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} (${((ctx.parsed/total)*100).toFixed(1)}%)`,
          },
          backgroundColor: '#0D0D0D',
          titleColor: '#FFFFFF',
          bodyColor: '#D4D4D4',
          borderColor: '#2A2A2A',
          borderWidth: 1,
          padding: 10,
        },
      },
      animation: { animateRotate: true, duration: 600 },
    },
  });

  // Custom legend
  legendEl.innerHTML = labels.map((label, i) => `
    <div class="tdp-legend-item">
      <div class="tdp-legend-left">
        <div class="tdp-legend-dot" style="background:${colors[i]};"></div>
        <span class="tdp-legend-label">${label.replace(/_/g,' ')}</span>
      </div>
      <span class="tdp-legend-count">${counts[i].toLocaleString()}</span>
    </div>
  `).join('');
}

// &#9472;&#9472; Speed Chart &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
async function loadSpeedChart(fid, vid, hours) {
  const placeholder = $('speed-chart-placeholder');
  const canvas      = $('speedLineChart');

  if (!vid) {
    placeholder.style.display = '';
    canvas.style.display = 'none';
    return;
  }

  placeholder.style.display = 'none';
  canvas.style.display = 'block';

  const data = await apiFetch(
    `/api/v1/analytics/vehicle/${fid}/${vid}/hourly?hours=${hours}`
  );

  if (!data || data.length === 0) {
    placeholder.innerHTML = `
      <i class="bi bi-info-circle tdp-placeholder-icon"></i>
      <p>No speed data for this vehicle in the last ${hours}h window.</p>`;
    placeholder.style.display = '';
    canvas.style.display = 'none';
    return;
  }

  const sorted    = [...data].sort((a, b) => new Date(a.hour_bucket) - new Date(b.hour_bucket));
  const hourLabels = sorted.map(r => {
    const d = new Date(r.hour_bucket);
    return d.toLocaleString('en-GB', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
  });
  const avgSpeeds = sorted.map(r => parseFloat(r.avg_speed) || 0);
  const maxSpeeds = sorted.map(r => parseFloat(r.max_speed) || 0);

  if (speedChart) { speedChart.destroy(); speedChart = null; }

  const ctx = canvas.getContext('2d');

  // Gradient fill for avg speed
  const grad = ctx.createLinearGradient(0, 0, 0, 260);
  grad.addColorStop(0,   'rgba(235, 10, 30, 0.20)');
  grad.addColorStop(1,   'rgba(235, 10, 30, 0.00)');

  speedChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: hourLabels,
      datasets: [
        {
          label: 'Avg Speed (km/h)',
          data: avgSpeeds,
          borderColor: '#EB0A1E',
          backgroundColor: grad,
          borderWidth: 2.5,
          pointRadius: avgSpeeds.length > 72 ? 0 : 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35,
        },
        {
          label: 'Max Speed (km/h)',
          data: maxSpeeds,
          borderColor: '#1A6FD4',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          borderDash: [5, 4],
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: false,
          tension: 0.35,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            font: { family: "'Barlow', sans-serif", size: 11 },
            color: '#5A6070',
            boxWidth: 12,
            boxHeight: 2,
            padding: 16,
          },
        },
        tooltip: {
          backgroundColor: '#0D0D0D',
          titleColor: '#FFFFFF',
          bodyColor: '#D4D4D4',
          borderColor: '#2A2A2A',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} km/h`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,0.04)', drawBorder: false },
          ticks: {
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            color: '#8A92A0',
            maxTicksLimit: 12,
            maxRotation: 40,
          },
        },
        y: {
          grid: { color: 'rgba(0,0,0,0.05)', drawBorder: false },
          ticks: {
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            color: '#8A92A0',
            callback: (v) => `${v} km/h`,
          },
          beginAtZero: true,
        },
      },
      animation: { duration: 500 },
    },
  });
}

// &#9472;&#9472; Events Table &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
async function loadEventsTable(fid, scenario) {
  eventsTableWrap.innerHTML = `
    <div class="tdp-table-placeholder">
      <div class="tdp-spinner" style="width:24px;height:24px;border-width:3px;"></div>
      <span style="font-size:0.82rem;color:var(--text-muted);margin-left:10px;">Querying events&#8230;</span>
    </div>`;

  const data = await apiFetch(
    `/api/v1/analytics/fleet/${fid}/scenarios?scenario=${encodeURIComponent(scenario)}&limit=50`
  );

  const rows  = data.results || [];
  const total = data.total   || 0;

  if (rows.length === 0) {
    eventsTableWrap.innerHTML = `
      <div class="tdp-table-placeholder">
        <i class="bi bi-inbox tdp-placeholder-icon"></i>
        <p>No events found for scenario <strong>${scenario}</strong>.</p>
      </div>`;
    return;
  }

  const tbodyRows = rows.map(r => {
    const chips = (r.scenarios || []).map(s =>
      `<span class="tdp-chip tdp-chip-${s}">${s.replace(/_/g,' ')}</span>`
    ).join('');

    const batClass = batteryClass(r.battery_level);

    return `<tr>
      <td class="mono">${r.event_id.slice(0,8)}&#8230;</td>
      <td class="mono">${r.vehicle_id.slice(0,8)}&#8230;</td>
      <td>${formatDatetime(r.recorded_at)}</td>
      <td class="speed-val">${parseFloat(r.speed).toFixed(1)}</td>
      <td class="battery-val ${batClass}">${r.battery_level}%</td>
      <td>${r.acceleration != null ? parseFloat(r.acceleration).toFixed(3) : '\u2014'}</td>
      <td>${r.weather || '\u2014'}</td>
      <td><div class="tdp-scenario-chips">${chips}</div></td>
    </tr>`;
  }).join('');

  eventsTableWrap.innerHTML = `
    <div style="overflow-x:auto;">
      <table class="tdp-events-table">
        <thead>
          <tr>
            <th>Event ID</th>
            <th>Vehicle ID</th>
            <th>Recorded At</th>
            <th>Speed (km/h)</th>
            <th>Battery</th>
            <th>Accel (m/s&#178;)</th>
            <th>Weather</th>
            <th>Scenarios</th>
          </tr>
        </thead>
        <tbody>${tbodyRows}</tbody>
      </table>
    </div>
    <div class="tdp-table-footer">
      <span class="tdp-table-count">
        Showing <strong>${rows.length}</strong> of <strong>${total.toLocaleString()}</strong> events
      </span>
      <span style="font-size:0.75rem;color:var(--text-muted);">
        Scenario: <strong style="color:var(--text-primary);">${scenario}</strong>
      </span>
    </div>`;
}

// &#9472;&#9472; Full Refresh &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
async function doRefresh() {
  const fid = fleetId();
  if (!fid) {
    setStatus('Enter a Fleet ID', 'error');
    return;
  }

  btnRefresh.classList.add('spinning');
  btnRefresh.disabled = true;
  setStatus('Loading&#8230;', 'loading');

  try {
    await Promise.all([
      loadKPIs(fid),
      loadScenarioDoughnut(fid),
      loadSpeedChart(fid, vehicleId(), currentHours),
    ]);

    lastUpdatedEl.textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });
    setStatus('Data current', 'ok');
  } catch (err) {
    console.error('Refresh error:', err);
    setStatus('API error \u2014 check console', 'error');

    ['kpi-v-total','kpi-v-active','kpi-v-speed','kpi-v-battery'].forEach(id => {
      const el = $(id);
      el.classList.remove('loading');
      el.textContent = 'ERR';
    });
  } finally {
    btnRefresh.classList.remove('spinning');
    btnRefresh.disabled = false;
  }
}

// &#9472;&#9472; Hours Toggle &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
hoursToggle.addEventListener('click', (e) => {
  const btn = e.target.closest('.tdp-toggle-btn');
  if (!btn) return;
  currentHours = parseInt(btn.dataset.hours, 10);
  hoursToggle.querySelectorAll('.tdp-toggle-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const fid = fleetId();
  const vid = vehicleId();
  if (fid && vid) loadSpeedChart(fid, vid, currentHours).catch(console.error);
});

// &#9472;&#9472; Date range triggers re-fetch of doughnut &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
['scenario-from', 'scenario-to'].forEach(id => {
  $(id).addEventListener('change', () => {
    const fid = fleetId();
    if (fid) loadScenarioDoughnut(fid).catch(console.error);
  });
});

// &#9472;&#9472; Events button &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
btnLoadEvents.addEventListener('click', () => {
  const fid = fleetId();
  if (!fid) { alert('Please enter a Fleet ID first.'); return; }
  loadEventsTable(fid, scenarioFilter.value).catch(err => {
    console.error(err);
    eventsTableWrap.innerHTML = `
      <div class="tdp-table-placeholder" style="color:var(--red);">
        <i class="bi bi-exclamation-triangle tdp-placeholder-icon"></i>
        <p>Failed to load events: ${err.message}</p>
      </div>`;
  });
});

// &#9472;&#9472; Main refresh button &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
btnRefresh.addEventListener('click', doRefresh);

// &#9472;&#9472; Init on page load &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
(function init() {
  // Kick off initial load if a fleet_id was pre-filled by the template
  if (fleetId()) {
    doRefresh();
  } else {
    setStatus('Enter a Fleet ID and click Refresh', '');
  }
})();
