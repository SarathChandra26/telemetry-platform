/**
 * telemetry.js &#8212; Telemetry Ingestion UI
 * Handles form submission, client-side scenario preview,
 * battery indicator, and API response rendering.
 */

'use strict';

// &#9472;&#9472; DOM refs &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
const form            = document.getElementById('telemetry-form');
const btnSubmit       = document.getElementById('btn-submit');
const btnSubmitText   = document.getElementById('btn-submit-text');
const btnSubmitSpinner = document.getElementById('btn-submit-spinner');
const btnReset        = document.getElementById('btn-reset-form');
const btnPopulate     = document.getElementById('btn-populate-sample');
const btnCopy         = document.getElementById('btn-copy-response');

const responseBody    = document.getElementById('response-body');
const detectedCard    = document.getElementById('detected-card');
const detectedTags    = document.getElementById('detected-tags');
const scenarioTags    = document.getElementById('scenario-tags');

const batteryInput    = document.getElementById('f-battery');
const batteryBar      = document.getElementById('battery-bar');
const speedInput      = document.getElementById('f-speed');
const accelInput      = document.getElementById('f-acceleration');
const weatherSelect   = document.getElementById('f-weather');

// &#9472;&#9472; Scenario Colours &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
const SCENARIO_STYLE = {
  hard_brake:           { bg: 'rgba(235,10,30,0.1)',   color: '#EB0A1E' },
  rapid_acceleration:   { bg: 'rgba(217,119,6,0.1)',   color: '#D97706' },
  over_speeding:        { bg: 'rgba(26,111,212,0.1)',  color: '#1A6FD4' },
  low_battery:          { bg: 'rgba(234,88,12,0.1)',   color: '#EA580C' },
  risky_weather_event:  { bg: 'rgba(124,58,237,0.1)',  color: '#7C3AED' },
};

// &#9472;&#9472; Battery indicator &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
function updateBatteryBar() {
  const val = parseInt(batteryInput.value, 10);
  if (isNaN(val) || val < 0 || val > 100) {
    batteryBar.style.width = '0%';
    return;
  }
  batteryBar.style.width = val + '%';
  if (val < 15)      batteryBar.style.background = '#EB0A1E';
  else if (val < 30) batteryBar.style.background = '#D97706';
  else               batteryBar.style.background = '#0D9E64';
}

batteryInput.addEventListener('input', updateBatteryBar);

// &#9472;&#9472; Client-side scenario preview &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
const RISKY_WEATHER = new Set(['rain', 'snow', 'fog']);

function previewScenarios() {
  const speed   = parseFloat(speedInput.value);
  const battery = parseInt(batteryInput.value, 10);
  const accel   = accelInput.value !== '' ? parseFloat(accelInput.value) : null;
  const weather = weatherSelect.value;

  const predicted = [];

  if (accel !== null && accel < -7)              predicted.push('hard_brake');
  if (accel !== null && accel > 7)               predicted.push('rapid_acceleration');
  if (!isNaN(speed)   && speed > 100)            predicted.push('over_speeding');
  if (!isNaN(battery) && battery < 15)           predicted.push('low_battery');
  if (predicted.includes('hard_brake') && RISKY_WEATHER.has(weather)) {
    predicted.push('risky_weather_event');
  }

  if (predicted.length === 0) {
    scenarioTags.innerHTML = '<span class="tdp-scenario-tag-empty">No scenarios predicted with current values.</span>';
  } else {
    scenarioTags.innerHTML = predicted.map(s => {
      const style = SCENARIO_STYLE[s] || { bg: '#f0f0f0', color: '#333' };
      return `<span class="tdp-scenario-badge" style="background:${style.bg};color:${style.color};">${s.replace(/_/g,' ')}</span>`;
    }).join('');
  }
}

[speedInput, batteryInput, accelInput, weatherSelect].forEach(el => {
  el.addEventListener('input', previewScenarios);
  el.addEventListener('change', previewScenarios);
});

// &#9472;&#9472; UUID generator &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
function uuid4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

// &#9472;&#9472; Sample data population &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
const SAMPLE_DATASETS = [
  {
    fleet_id:      '3fa85f64-5717-4562-b3fc-2c963f66afa6',
    vehicle_id:    uuid4(),
    speed:         '112.50',
    latitude:      '35.6762',
    longitude:     '139.6503',
    battery_level: '12',
    acceleration:  '-8.200',
    weather:       'rain',
    engine_on:     'true',
  },
  {
    fleet_id:      '3fa85f64-5717-4562-b3fc-2c963f66afa6',
    vehicle_id:    uuid4(),
    speed:         '68.00',
    latitude:      '35.6895',
    longitude:     '139.6917',
    battery_level: '78',
    acceleration:  '7.500',
    weather:       'clear',
    engine_on:     'true',
  },
  {
    fleet_id:      '3fa85f64-5717-4562-b3fc-2c963f66afa6',
    vehicle_id:    uuid4(),
    speed:         '42.00',
    latitude:      '35.6580',
    longitude:     '139.7016',
    battery_level: '55',
    acceleration:  '',
    weather:       'fog',
    engine_on:     'false',
  },
];

let sampleIndex = 0;

btnPopulate.addEventListener('click', () => {
  const s = SAMPLE_DATASETS[sampleIndex % SAMPLE_DATASETS.length];
  sampleIndex++;

  document.getElementById('f-fleet-id').value     = s.fleet_id;
  document.getElementById('f-vehicle-id').value   = s.vehicle_id;
  document.getElementById('f-speed').value         = s.speed;
  document.getElementById('f-lat').value           = s.latitude;
  document.getElementById('f-lon').value           = s.longitude;
  document.getElementById('f-battery').value       = s.battery_level;
  document.getElementById('f-acceleration').value  = s.acceleration;
  document.getElementById('f-weather').value       = s.weather;
  document.getElementById('f-engine-on').value     = s.engine_on;

  // Default recorded_at to now
  const now = new Date();
  now.setSeconds(0, 0);
  document.getElementById('f-recorded-at').value = now.toISOString().slice(0,16);

  updateBatteryBar();
  previewScenarios();
});

// &#9472;&#9472; Build API payload &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
function buildPayload() {
  const get = (id) => document.getElementById(id).value.trim();

  const payload = {
    fleet_id:      get('f-fleet-id'),
    vehicle_id:    get('f-vehicle-id'),
    speed:         parseFloat(get('f-speed')),
    latitude:      parseFloat(get('f-lat')),
    longitude:     parseFloat(get('f-lon')),
    battery_level: parseInt(get('f-battery'), 10),
  };

  const accel     = get('f-acceleration');
  const weather   = get('f-weather');
  const engineOn  = get('f-engine-on');
  const recordedAt = get('f-recorded-at');

  if (accel)     payload.acceleration = parseFloat(accel);
  if (weather)   payload.weather      = weather;
  if (engineOn)  payload.engine_on    = engineOn === 'true';
  if (recordedAt) payload.recorded_at = new Date(recordedAt).toISOString();

  return payload;
}

// &#9472;&#9472; Validation &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function validate(payload) {
  const errors = [];
  if (!UUID_RE.test(payload.fleet_id))   errors.push('fleet_id must be a valid UUID v4');
  if (!UUID_RE.test(payload.vehicle_id)) errors.push('vehicle_id must be a valid UUID v4');
  if (isNaN(payload.speed))             errors.push('speed is required and must be a number');
  if (isNaN(payload.latitude))          errors.push('latitude is required and must be a number');
  if (isNaN(payload.longitude))         errors.push('longitude is required and must be a number');
  if (isNaN(payload.battery_level))     errors.push('battery_level is required and must be an integer');
  return errors;
}

// &#9472;&#9472; Response rendering &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
let lastResponseText = '';

function showResponse(status, data, ok) {
  lastResponseText = JSON.stringify(data, null, 2);

  const statusLine = `<div class="tdp-response-status ${ok ? 'tdp-status-ok' : 'tdp-status-err'}">
    <i class="bi bi-${ok ? 'check-circle' : 'x-circle'}"></i>
    HTTP ${status} &#183; ${ok ? 'Success' : 'Error'} &#183; ${new Date().toLocaleTimeString('en-GB', {hour12:false})}
  </div>`;

  // Syntax-highlight the JSON
  const highlighted = lastResponseText
    .replace(/("[\w_]+")\s*:/g, '<span style="color:#9CDCFE;">$1</span>:')
    .replace(/:\s*(".*?")/g, ': <span style="color:#CE9178;">$1</span>')
    .replace(/:\s*(\d+\.?\d*)/g, ': <span style="color:#B5CEA8;">$1</span>')
    .replace(/:\s*(true|false)/g, ': <span style="color:#569CD6;">$1</span>');

  responseBody.innerHTML = `<pre class="tdp-json">${highlighted}</pre>${statusLine}`;
  btnCopy.style.display = 'block';

  // Show detected scenarios if success
  if (ok && data.scenarios) {
    detectedCard.style.display = 'block';
    if (data.scenarios.length === 0) {
      detectedTags.innerHTML = '<span style="font-size:0.8rem;color:var(--text-muted);">No scenarios triggered.</span>';
    } else {
      detectedTags.innerHTML = data.scenarios.map(s => {
        const style = SCENARIO_STYLE[s] || { bg: '#f0f0f0', color: '#333' };
        return `<span class="tdp-scenario-badge" style="background:${style.bg};color:${style.color};font-size:0.78rem;padding:4px 10px;">
          <i class="bi bi-lightning-charge"></i> ${s.replace(/_/g,' ')}
        </span>`;
      }).join('');
    }
  } else {
    detectedCard.style.display = 'none';
  }
}

function showValidationErrors(errors) {
  const html = errors.map(e => `<li>${e}</li>`).join('');
  responseBody.innerHTML = `
    <div style="padding:16px;">
      <div style="display:flex;align-items:center;gap:8px;color:#EB0A1E;margin-bottom:10px;font-weight:600;font-size:0.82rem;">
        <i class="bi bi-exclamation-triangle"></i> Validation Errors
      </div>
      <ul style="font-size:0.8rem;color:#D4D4D4;padding-left:18px;line-height:2;">${html}</ul>
    </div>`;
  btnCopy.style.display = 'none';
  detectedCard.style.display = 'none';
}

// &#9472;&#9472; Form submit &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const payload = buildPayload();
  const errors  = validate(payload);

  if (errors.length > 0) {
    showValidationErrors(errors);
    return;
  }

  // Loading state
  btnSubmit.disabled = true;
  btnSubmitText.textContent = 'Submitting&#8230;';
  btnSubmitSpinner.style.display = 'inline-flex';

  responseBody.innerHTML = `
    <div class="tdp-response-idle">
      <div class="tdp-spinner" style="width:24px;height:24px;border-width:3px;margin-bottom:12px;"></div>
      <p>Sending to API&#8230;</p>
    </div>`;
  btnCopy.style.display = 'none';
  detectedCard.style.display = 'none';

  try {
    const res = await fetch('/api/v1/telemetry', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    const data = await res.json();
    showResponse(res.status, data, res.ok);
  } catch (err) {
    showResponse(0, { error: err.message }, false);
  } finally {
    btnSubmit.disabled = false;
    btnSubmitText.textContent = 'Submit Event';
    btnSubmitSpinner.style.display = 'none';
  }
});

// &#9472;&#9472; Reset &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
btnReset.addEventListener('click', () => {
  form.reset();
  updateBatteryBar();
  previewScenarios();
  responseBody.innerHTML = `
    <div class="tdp-response-idle">
      <i class="bi bi-hourglass tdp-response-idle-icon"></i>
      <p>Awaiting submission&#8230;</p>
      <p class="tdp-response-idle-sub">The API response will appear here.</p>
    </div>`;
  btnCopy.style.display = 'none';
  detectedCard.style.display = 'none';
  sampleIndex = 0;
});

// &#9472;&#9472; Copy &#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;
btnCopy.addEventListener('click', async () => {
  if (!lastResponseText) return;
  try {
    await navigator.clipboard.writeText(lastResponseText);
    btnCopy.innerHTML = '<i class="bi bi-clipboard-check"></i>';
    setTimeout(() => { btnCopy.innerHTML = '<i class="bi bi-clipboard"></i>'; }, 2000);
  } catch (_) {
    // fallback silent fail
  }
});
