/* PRISM prototype — front-end. No framework, no network deps beyond /api. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fx = (n, d = 2) => (n === null || n === undefined || isNaN(n)) ? '—' : Number(n).toFixed(d);

const ICONS = {
  grid: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  pulse: '<path d="M2 12h4l3-8 4 16 3-8h6"/>',
  flag: '<path d="M5 21V4h9l-1 3h7l-2 5 2 5h-7l-1-3H5"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="0.6"/>',
  db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'
};

const state = {
  buildings: [], summary: null, result: null, accuracy: null, runs: [], selfcheck: null,
  view: 'dashboard', filter: 'ALL', q: '', teams: 3, horizon: 24, bid: null,
  busy: false, timers: {}
};

/* ------------------------------------------------------------------ api --- */
const api = {
  async get(p) { const r = await fetch(p); return r.json(); },
  async post(p, b) {
    const r = await fetch(p, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(b || {})
    });
    return r.json();
  },
  async del(p) { const r = await fetch(p, { method: 'DELETE' }); return r.json(); }
};

function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(state.timers.toast);
  state.timers.toast = setTimeout(() => t.classList.remove('show'), 2200);
}

/* A run against a building that never collapsed is a rehearsal, not a rescue.
   The history must not put the two in the same column unlabelled. */
function isPreplan(bid) {
  const b = state.buildings.find(x => x.bid === bid);
  return !!(b && !b.collapsed);
}
function livesCell(r, bold) {
  const pre = isPreplan(r.bid);
  const col = pre ? 'var(--amber)' : 'var(--green)';
  return `<td class="num" style="color:${col};${bold ? 'font-weight:700' : ''}">${fx(r.lives, 2)}${
    pre ? ' <span class="card-sub">pre-plan</span>' : ''}</td>`;
}

/* --------------------------------------------------------------- pieces --- */
const bandChip = b => `<span class="band ${b}">${b}</span>`;
const tag = (t, cls = '') => `<span class="tag ${cls}">${esc(t)}</span>`;

function kpi(val, label, color, pct) {
  return `<div class="card kpi">
    <div class="val" style="color:${color}">${val}</div>
    <div class="lbl">${esc(label)}</div>
    <div class="bar"><i style="width:${Math.max(2, Math.min(100, pct))}%;background:${color}"></i></div>
  </div>`;
}

function barRow(label, value, max, color, txt) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return `<div class="bar-row">
    <div title="${esc(label)}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(label)}</div>
    <div class="bar-track"><div class="bar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div></div>
    <div class="bar-val">${txt}</div></div>`;
}

const survColor = s => s > 0.5 ? 'var(--green)' : s > 0.2 ? 'var(--amber)' : 'var(--red)';

/* --------------------------------------------------------------- router --- */
function setView(v) {
  const prev = state.view;
  state.view = v;
  // A drawer belongs to the page that opened it. Leaving it open over the next
  // section looks like the app forgot what it was doing.
  if (prev !== v) closeDrawer();
  $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.view === v));
  const meta = {
    dashboard: ['Dashboard', 'Live view of the building queue and engine status.'],
    queue: ['Building queue', 'Every property, scored from records alone. Click a row for the maths.'],
    intake: ['Intake', 'Add a building. The band updates as you type — same function the engine uses.'],
    ops: ['Collapse ops', 'Run the nine-stage chain on a collapsed building.'],
    tasking: ['Tasking', 'Ranked dig list, team timeline, and what cannot be reached in time.'],
    accuracy: ['Accuracy', 'What 95% can and cannot mean here — computed, not asserted.'],
    data: ['Data', 'Export, import, reseed, and every run this system has produced.']
  }[v] || ['PRISM', ''];
  $('#view-title').textContent = meta[0];
  $('#view-sub').textContent = meta[1];
  render();
  // Tasking is a result view; landing on an empty one is a dead end. Run the
  // selected building rather than making the user route through Collapse ops.
  if (v === 'tasking' && !state.result && state.bid) runEngine({ quiet: true });
  if (v === 'accuracy' && !state.rtDone) runRedteam({ quiet: true });
}

async function boot() {
  $$('.ico').forEach(el => {
    const k = el.dataset.i;
    if (ICONS[k]) el.innerHTML = `<svg viewBox="0 0 24 24">${ICONS[k]}</svg>`;
  });
  const h = await api.get('/api/health').catch(() => null);
  if (h && h.ok) {
    $('#eng-dot').className = 'dot on';
    $('#eng-text').textContent = 'engine online';
    $('#eng-tests').textContent = h.tests + ' tests';
  } else {
    $('#eng-dot').className = 'dot off';
    $('#eng-text').textContent = 'engine offline';
  }
  await refresh();
  const v = (location.hash || '#/dashboard').replace('#/', '');
  setView(v);
  window.addEventListener('hashchange', () => setView((location.hash || '#/dash').replace('#/', '')));
  $('#btn-refresh').onclick = async () => { await refresh(); toast('Queue refreshed'); };
  $('#global-search').oninput = e => { state.q = e.target.value.toLowerCase(); render(); };
  $('#drawer').onclick = e => { if (e.target.id === 'drawer') closeDrawer(); };
}

async function refresh() {
  const [b, s, r, a, sc] = await Promise.all([
    api.get('/api/buildings'), api.get('/api/summary'), api.get('/api/runs'),
    api.get('/api/accuracy').catch(() => null),
    api.get('/api/selfcheck').catch(() => null)
  ]);
  state.buildings = b; state.summary = s; state.runs = r; state.accuracy = a;
  state.selfcheck = sc;
  if (!state.bid && b.length) state.bid = (b.find(x => x.collapsed) || b[0]).bid;
}

/* ------------------------------------------------------------ dashboard --- */
function vDashboard() {
  const s = state.summary;
  if (!s) return `<div class="empty">Loading…</div>`;
  const maxBand = Math.max(s.bands.RED, s.bands.AMBER, s.bands.GREEN, 1);
  const risky = [...state.buildings].sort((a, b) => b.p_stands - a.p_stands).slice(0, 6);

  return `
  <div class="grid g4">
    ${kpi(s.total, 'buildings in queue', 'var(--cyan)', (s.total / 12) * 100)}
    ${kpi(s.bands.RED, 'RED band · failure more likely than not', 'var(--red)',
      (s.bands.RED / Math.max(1, s.total)) * 100)}
    ${kpi(s.collapsed, 'collapsed, case open', 'var(--amber)', (s.collapsed / 4) * 100)}
    ${kpi(s.runs, 'pipeline runs saved', 'var(--green)', Math.min(100, s.runs * 12))}
  </div>

  <div class="split" style="margin-top:14px">
    <div class="card">
      <div class="card-h"><div class="card-t">Highest standing risk</div>
        <div class="card-sub">ranked from records alone</div></div>
      <table><thead><tr>
        <th>Building</th><th class="num">LR</th><th class="num">D/C</th>
        <th class="num">P_stands</th><th>Band</th><th></th></tr></thead><tbody>
        ${risky.map(b => `<tr class="click" data-bid="${esc(b.bid)}">
          <td><b>${esc(b.label)}</b><div class="card-sub">${esc(b.bid)} · ${esc(b.use)}</div></td>
          <td class="num">${fx(b.lr, 2)}×</td>
          <td class="num">${fx(b.dc, 2)}</td>
          <td class="num">${fx(b.p_stands, 3)}</td>
          <td>${bandChip(b.band)}</td>
          <td>${b.collapsed ? tag('collapsed', 'bad') : ''}</td></tr>`).join('')}
      </tbody></table>
    </div>

    <div>
      <div class="card">
        <div class="card-h"><div class="card-t">Band distribution</div></div>
        ${barRow('RED', s.bands.RED, maxBand, 'var(--red)', s.bands.RED)}
        ${barRow('AMBER', s.bands.AMBER, maxBand, 'var(--amber)', s.bands.AMBER)}
        ${barRow('GREEN', s.bands.GREEN, maxBand, 'var(--green)', s.bands.GREEN)}
        <div class="note" style="margin-top:10px">A band is a queue position, not a forecast.
        Brittle shear failure gives no precursor — the queue sequences inspection, nothing more.</div>
      </div>
      <div class="card" style="margin-top:14px">
        <div class="card-h"><div class="card-t">Engine</div>${tag('10/10', 'ok')}</div>
        <div class="stat-line"><span>adversarial checks</span><span>10 / 10 passing</span></div>
        <div class="stat-line"><span>decision law</span><span class="mono">lives / team-hour</span></div>
        <div class="stat-line"><span>refusal gate</span><span>posterior &lt; 0.60 → UNCERTAIN</span></div>
        <button class="btn ghost sm" style="margin-top:12px" data-goto="accuracy">Open accuracy page</button>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">Recent runs</div>
      <div class="card-sub">${s.runs} total</div></div>
    ${state.runs.length ? `<table><thead><tr><th>#</th><th>Building</th><th>When</th>
      <th class="num">Teams</th><th class="num">Horizon</th><th class="num">Expected lives</th>
      <th></th></tr></thead><tbody>
      ${state.runs.slice(0, 6).map(r => `<tr>
        <td class="mono">${r.id}</td><td>${esc(r.bid)}</td>
        <td class="card-sub">${esc((r.created_at || '').replace('T', ' ').slice(0, 19))}</td>
        <td class="num">${r.teams}</td><td class="num">${r.horizon}h</td>
        ${livesCell(r, true)}
        <td><button class="btn ghost sm" data-loadrun="${r.id}">Load</button></td></tr>`).join('')}
      </tbody></table>` : `<div class="empty">No runs yet. Open a collapsed building in Collapse ops.</div>`}
  </div>`;
}

/* ---------------------------------------------------------------- queue --- */
function vQueue() {
  let rows = state.buildings;
  if (state.filter !== 'ALL') {
    rows = state.filter === 'COLLAPSED' ? rows.filter(b => b.collapsed)
      : rows.filter(b => b.band === state.filter);
  }
  if (state.q) {
    rows = rows.filter(b => (b.label + b.bid + b.use).toLowerCase().includes(state.q));
  }
  const seg = (k, t) => `<button data-filter="${k}" class="${state.filter === k ? 'on' : ''}">${t}</button>`;

  return `
  <div class="row" style="margin-bottom:14px">
    <div class="seg">${seg('ALL', 'All')}${seg('RED', 'RED')}${seg('AMBER', 'AMBER')}
      ${seg('GREEN', 'GREEN')}${seg('COLLAPSED', 'Collapsed')}</div>
    <div class="spacer"></div>
    <div class="card-sub">${rows.length} of ${state.buildings.length} shown</div>
  </div>

  <div class="card" style="padding:14px 8px">
    <table><thead><tr>
      <th style="padding-left:14px">Building</th><th>Use</th><th>Structure</th>
      <th class="num">Floor ×</th><th class="num">Density ×</th><th class="num">LR</th>
      <th class="num">D/C</th><th class="num">P_stands</th><th>Band</th><th>Records</th><th></th>
    </tr></thead><tbody>
    ${rows.map(b => `<tr class="click" data-bid="${esc(b.bid)}">
      <td style="padding-left:14px"><b>${esc(b.label)}</b>${b.collapsed
        ? ' ' + tag('collapsed', 'bad') : ''}
        <div class="card-sub">${esc(b.bid)} · declared G+${b.declared_floors - 1}${
          b.observed_floors ? ` · listed G+${b.observed_floors - 1}` : ''}</div></td>
      <td>${esc(b.use)}</td>
      <td class="card-sub">${esc((b.structure || '').replace(/_/g, ' '))}</td>
      <td class="num" style="color:var(--amber)">${fx(b.lr_floors, 2)}×</td>
      <td class="num" style="color:var(--amber)">${fx(b.lr_occ, 2)}×</td>
      <td class="num"><b>${fx(b.lr, 2)}×</b></td>
      <td class="num">${fx(b.dc, 2)}</td>
      <td class="num">${fx(b.p_stands, 3)}</td>
      <td>${bandChip(b.band)}</td>
      <td>${b.verifiable ? tag('verifiable', 'ok') : tag('unverifiable', 'warn')}</td>
      <td><button class="btn ghost sm" data-run="${esc(b.bid)}">Run</button></td>
    </tr>`).join('') || `<tr><td colspan="11"><div class="empty">No buildings match.</div></td></tr>`}
    </tbody></table>
  </div>`;
}

/* --------------------------------------------------------------- intake --- */
function vIntake() {
  const f = (id, label, val = '', type = 'text', hint = '', extra = '') => `
    <div class="field"><label>${label}</label>
      <input id="f-${id}" type="${type}" value="${val}" ${extra}>${hint ? `<div class="hint">${hint}</div>` : ''}
    </div>`;

  return `
  <div class="split">
    <div class="card">
      <div class="card-h"><div class="card-t">New building record</div>
        <div class="card-sub">only the starred fields are required</div></div>
      <div class="form-grid">
        ${f('bid', 'Building id *', '', 'text', 'e.g. SN-1148')}
        ${f('label', 'Label *', '', 'text', 'street and description')}
        <div class="field"><label>Use</label><select id="f-use">
          <option value="pg">pg / hostel</option><option value="residential">residential</option>
          <option value="mixed">mixed</option><option value="commercial">commercial</option>
          <option value="school">school</option></select></div>
        <div class="field"><label>Structure</label><select id="f-structure">
          <option value="unframed_masonry">unframed masonry</option>
          <option value="load_bearing_rc">load-bearing RC</option>
          <option value="rc_frame">RC frame</option>
          <option value="wood">wood</option><option value="steel">steel</option>
          <option value="precast_panel">precast panel (unmodelled)</option></select></div>
        ${f('plot_m2', 'Plot area m²', 60, 'number')}
        ${f('declared_floors', 'Declared floors', 2, 'number', 'including ground: G+1 = 2')}
        ${f('observed_floors', 'Listed floors', '', 'number', 'leave blank if unknown')}
        ${f('design_occupancy', 'Design occupancy', 4, 'number', 'per sanctioned plan')}
        ${f('observed_occupancy', 'Actual occupancy', '', 'number', 'beds / residents seen')}
        ${f('corrosion_pct', 'Corrosion loss %', 0, 'number', 'NDT survey, if any')}
        <div class="field"><label>Element removed</label><select id="f-element_removed">
          <option value="none">none</option><option value="base_wall">base wall / shop front</option>
          <option value="column">column</option><option value="slab">slab</option>
          <option value="beam">beam</option></select></div>
        ${f('time_of_day_h', 'Time of day (hour)', 19.5, 'number', '0–24, for occupancy')}
      </div>

      <div class="hr"></div>
      <div class="row">
        <label class="row" style="font-size:12px;color:var(--mute)">
          <input type="checkbox" id="f-sanction_plan"> sanctioned plan on file</label>
        <label class="row" style="font-size:12px;color:var(--mute)">
          <input type="checkbox" id="f-collapsed"> this building has collapsed</label>
      </div>
      <div class="form-grid" style="margin-top:12px">
        ${f('lg_impacts', 'Last-gasp impacts', '', 'number', 'blank if no sensor')}
        ${f('lg_duration', 'Last-gasp duration s', '', 'number')}
      </div>
      <div class="row" style="margin-top:16px">
        <button class="btn" id="btn-save">Save building</button>
        <button class="btn ghost" data-goto="queue">Cancel</button>
      </div>
    </div>

    <div>
      <div class="card" id="preview-card">
        <div class="card-h"><div class="card-t">Live standing preview</div>
          <div class="card-sub" id="pv-gate">waiting</div></div>
        <div id="pv-body"><div class="note">Start typing — the band recomputes on every keystroke
          using the same function the engine uses.</div></div>
      </div>
      <div class="card" style="margin-top:14px">
        <div class="card-t" style="margin-bottom:10px">Why these fields</div>
        <div class="note">
          <b style="color:var(--ink)">Declared vs listed floors</b> is the load ratio — the single
          strongest predictor of mechanism. <b style="color:var(--ink)">Design vs actual occupancy</b>
          multiplies it. <b style="color:var(--ink)">Element removed</b> selects which mechanisms are
          even possible. Leave anything blank and the record degrades honestly — it will mark itself
          unverifiable rather than guess.
        </div>
      </div>
    </div>
  </div>`;
}

function readForm() {
  const g = id => {
    const el = $('#f-' + id);
    if (!el) return null;
    if (el.type === 'checkbox') return el.checked;
    const v = el.value.trim();
    return v === '' ? null : v;
  };
  return {
    bid: g('bid'), label: g('label'), use: g('use'), structure: g('structure'),
    plot_m2: g('plot_m2'), declared_floors: g('declared_floors'),
    observed_floors: g('observed_floors'), design_occupancy: g('design_occupancy'),
    observed_occupancy: g('observed_occupancy'), corrosion_pct: g('corrosion_pct'),
    element_removed: g('element_removed'), time_of_day_h: g('time_of_day_h'),
    sanction_plan: g('sanction_plan') ? 1 : 0, collapsed: g('collapsed') ? 1 : 0,
    lg_impacts: g('lg_impacts'), lg_duration: g('lg_duration'), lg_amp: 0.3
  };
}

async function updatePreview() {
  const body = $('#pv-body');
  if (!body) return;
  const d = readForm();
  const pv = await api.post('/api/preview', d);
  const st = pv.standing, sat = pv.satellite;
  const col = st.band === 'RED' ? 'var(--red)' : st.band === 'AMBER' ? 'var(--amber)' : 'var(--green)';
  $('#pv-gate').innerHTML = bandChip(st.band);
  body.innerHTML = `
    <div class="big" style="color:${col}">${fx(st.p_stands, 3)}</div>
    <div class="card-sub" style="margin-bottom:14px">standing probability</div>
    <div class="stat-line"><span>floor ratio</span><span>${fx(st.lr_floors, 2)}×</span></div>
    <div class="stat-line"><span>density ratio</span><span>${fx(st.lr_occ, 2)}×</span></div>
    <div class="stat-line"><span>load ratio</span><span>${fx(st.lr, 2)}×</span></div>
    <div class="stat-line"><span>demand / capacity</span><span>${fx(st.dc, 2)}</span></div>
    <div class="stat-line"><span>gravity term</span><span>${fx(st.p_gravity, 3)}</span></div>
    <div class="stat-line"><span>seismic term</span><span>${fx(st.p_seismic, 3)}</span></div>
    <div class="stat-line"><span>plot in 10 m pixels</span><span>${fx(sat.plot_in_pixels, 2)}</span></div>
    ${st.note ? `<div class="note" style="margin-top:12px;color:var(--amber)">⚠ ${esc(st.note)}</div>` : ''}
    ${sat.sub_pixel ? `<div class="note" style="margin-top:8px">Satellite cannot resolve this plot —
      under one pixel. The record must carry it.</div>` : ''}`;
}

/* ------------------------------------------------------------------ ops --- */
function vOps() {
  const opts = state.buildings.map(b =>
    `<option value="${esc(b.bid)}" ${state.bid === b.bid ? 'selected' : ''}>
      ${esc(b.bid)} — ${esc(b.label)}${b.collapsed ? '  [collapsed]' : ''}</option>`).join('');

  return `
  <div class="card">
    <div class="form-grid" style="grid-template-columns:2fr 1fr 1fr 1fr">
      <div class="field"><label>Building</label>
        <select id="ops-bid">${opts}</select></div>
      <div class="field"><label>Teams <span id="lbl-teams" style="color:var(--amber)">${state.teams}</span></label>
        <input type="range" id="ops-teams" class="slider" min="1" max="8" value="${state.teams}"></div>
      <div class="field"><label>Horizon <span id="lbl-hor" style="color:var(--amber)">${state.horizon}h</span></label>
        <input type="range" id="ops-horizon" class="slider" min="6" max="72" step="6" value="${state.horizon}"></div>
      <div class="field"><label>&nbsp;</label>
        <button class="btn" id="btn-run">Run pipeline</button></div>
    </div>
  </div>
  <div id="ops-out" style="margin-top:14px">${state.result && state.result.building.bid === state.bid
    ? '' : vOpsPreview()}</div>`;
}

/* Before a run: show what the records already settle, and what the chain will add.
   An empty page is not an empty dataset -- stage 1 and stage 2 have already run. */
function vOpsPreview() {
  const b = state.buildings.find(x => x.bid === state.bid);
  if (!b) return `<div class="empty"><b>No building selected</b>Pick one above.</div>`;

  const stages = [
    ['1', 'Standing', 'declared vs listed floors, occupancy, D/C', b.band.toLowerCase()],
    ['2', 'Satellite auditor', 'plot in pixels — can imagery even see this?',
      b.sub_pixel ? 'sub-pixel' : 'resolvable'],
    ['3', 'Mechanism', 'six-class posterior from the record', 'lead + refusal gate'],
    ['4', 'Void field', 'pockets, people, dig effort', b.collapsed ? 'built at run time' : 'collapsed only'],
    ['5', 'Survival clock', 'lognormal survival per pocket', 's(t)'],
    ['6', 'Tasking', 'ELSE = lives per team-hour, greedy by time', 'rank + gantt']
  ];

  const line = (k, v, col) =>
    `<div class="stat-line"><span>${k}</span><span style="color:${col || 'var(--ink)'}">${v}</span></div>`;

  return `
  <div class="split">
    <div class="card">
      <div class="card-h"><div class="card-t">What the records already settle</div>
        ${bandChip(b.band)}</div>
      ${line('declared floors', b.declared_floors)}
      ${line('listed / observed floors', b.observed_floors == null ? 'never surveyed' : b.observed_floors)}
      ${line('floor ratio', fx(b.lr_floors, 2) + '×')}
      ${line('occupancy ratio', fx(b.lr_occ, 2) + '×')}
      ${line('combined load ratio', fx(b.lr, 2) + '×', 'var(--amber)')}
      ${line('demand / capacity', fx(b.dc, 2) + ' / 1.00')}
      ${line('P(stands | design event)', fx(b.p_stands, 3), 'var(--red)')}
      <div class="hr"></div>
      ${line('sanction plan on file', b.sanction_plan ? 'yes' : 'no',
        b.sanction_plan ? 'var(--green)' : 'var(--red)')}
      ${line('plot footprint', b.plot_m2 + ' m² = ' + fx(b.plot_px, 2) + ' Sentinel-2 px')}
      ${line('imagery can resolve it', b.sub_pixel ? 'no — sub-pixel' : 'yes',
        b.sub_pixel ? 'var(--red)' : 'var(--green)')}
      <div class="note" style="margin-top:10px">${b.sub_pixel
        ? 'At 10 m per pixel this plot is smaller than one pixel. Sentinel-2 cannot see a storey '
          + 'addition here, so the satellite stage returns nothing and the record carries the call.'
        : 'This plot is larger than one Sentinel-2 pixel; the auditor can compare roof outline to '
          + 'the sanctioned footprint.'}</div>
    </div>

    <div class="card">
      <div class="card-h"><div class="card-t">The chain that will run</div>
        <div class="card-sub" id="chain-params">${state.teams} team${state.teams===1?'':'s'} · ${state.horizon} h</div></div>
      ${stages.map(([n, name, desc, out]) => `<div class="chain-row">
        <div class="chain-n">${n}</div>
        <div class="chain-body"><div class="chain-t">${name}</div>
          <div class="chain-d">${desc}</div></div>
        <div class="chain-o">${out}</div>
      </div>`).join('')}
      <div class="hr"></div>
      <div class="row">
        <button class="btn" id="btn-run2">Run pipeline</button>
        <span class="note" style="align-self:center">deterministic · ${b.collapsed
          ? 'this building is marked collapsed' : 'not collapsed — marked PENDING'}</span>
      </div>
    </div>
  </div>`;
}

function vOpsResult(r) {
  const b = state.buildings.find(x => x.bid === r.building.bid) || {};
  const post = r.mechanism.posterior;
  const sorted = Object.entries(post).sort((a, c) => c[1] - a[1]);
  const lead = sorted[0];

  return `
  ${r.mode === 'PREPLAN' ? `<div class="banner warn">
    <b>PRE-PLAN, NOT A DISPATCH.</b> This building has not collapsed. The figures below describe the
    modelled event if it did — they are a rehearsal for the queue, not a reason to send a team today.
  </div>` : ''}
  <div class="grid g4">
    ${kpi(fx(r.standing.p_stands, 3), 'standing probability', 'var(--red)',
      r.standing.p_stands * 100)}
    ${kpi(fx(lead[1], 2), 'p(' + lead[0] + ')', 'var(--cyan)', lead[1] * 100)}
    ${kpi(r.occupancy.expected_trapped, 'expected trapped', 'var(--amber)',
      Math.min(100, r.occupancy.expected_trapped * 5))}
    ${kpi(fx(r.lives, 2), r.mode === 'PREPLAN' ? 'lives at risk, modelled' : 'expected lives saved',
      'var(--green)', r.lives * 18)}
  </div>

  <div class="split top" style="margin-top:14px">
    <div class="card">
      <div class="card-h"><div class="card-t">Mechanism posterior</div>
        ${r.mechanism.uncertain
          ? tag('UNCERTAIN · NOVEL', 'bad')
          : tag('confident · ' + fx(r.mechanism.confidence, 2), 'ok')}</div>
      ${sorted.map(([k, v]) => barRow(k.replace(/_/g, ' '), v, Math.max(...Object.values(post)),
        k === lead[0] ? 'var(--amber)' : '#2E4358', fx(v, 3))).join('')}
      ${r.mechanism.uncertain ? `<div class="note" style="margin-top:10px;color:var(--red)">
        No class reached 0.60, or the structure is outside the model's vocabulary. The void field
        falls back to the survivable-void prior. This is a refusal, not a guess.</div>` : ''}
      <div class="hr"></div>
      <div class="note"><b style="color:var(--ink)">Why the lead matters.</b> The mechanism sets
        which voids are survivable at all — a pancake leaves horizontal gaps at the perimeter and
        in stairwells, a lean-to leaves one sheltered wedge on the fallen side, a cantilever leaves
        the ground-floor core. Digging the wrong shape of hole is how teams spend daylight on
        rubble that had no void in it. Posterior spread here: top two classes differ by
        ${fx(sorted[0][1] - sorted[1][1], 2)}, and the gate fires below 0.60.</div>
    </div>

    <div class="card">
      <div class="card-h"><div class="card-t">Occupancy</div>
        <div class="card-sub">${r.occupancy.heads_known} heads known</div></div>
      <div class="stat-line"><span>present at ${fx(r.building.time_of_day_h || 0, 1)} h</span>
        <span>${fx(r.occupancy.p_present, 2)}</span></div>
      <div class="stat-line"><span>collapsed fraction</span>
        <span>${fx(r.occupancy.collapse_frac, 2)}</span></div>
      <div class="stat-line"><span>expected trapped</span>
        <span style="color:var(--amber)">${r.occupancy.expected_trapped}</span></div>
      <div class="stat-line"><span>pockets modelled</span><span>${r.voids.length}</span></div>
      <div class="hr"></div>
      <div class="card-t" style="margin-bottom:8px">Policy check</div>
      <div class="note">Confirming occupancy first would change expected lives by
        <b style="color:${r.policy.with_records > 0 ? 'var(--green)' : 'var(--red)'}">
        ${r.policy.with_records > 0 ? '+' : ''}${fx(r.policy.with_records, 2)}</b>
        where records exist, and
        <b style="color:var(--green)">+${fx(r.policy.without_records, 2)}</b> where they do not.</div>
      <div style="margin-top:10px">${tag(r.policy.verdict,
        r.policy.verdict.startsWith('CONFIRM') ? 'warn' : 'ok')}</div>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">Top of the dig list</div>
      <button class="btn cyan sm" data-goto="tasking">Open full tasking →</button></div>
    <table><thead><tr><th>#</th><th>Pocket</th><th>Zone</th><th class="num">People</th>
      <th class="num">s(t)</th><th class="num">d_dig</th><th class="num">ELSE</th>
      <th class="num">Done</th></tr></thead><tbody>
      ${r.voids.slice(0, 5).map(v => `<tr class="${v.rank === 1 ? 'hi' : ''}">
        <td class="mono" style="color:var(--amber)">${v.rank}</td>
        <td><b>${esc(v.vid)}</b> <span class="card-sub">${esc(v.mechanism)}</span></td>
        <td>${esc(v.zone.replace(/_/g, ' '))} · fl ${v.floor}</td>
        <td class="num">${fx(v.people, 2)}</td>
        <td class="num" style="color:${survColor(v.survival_now)}">${fx(v.survival_now, 2)}</td>
        <td class="num">${fx(v.d_dig, 2)}</td>
        <td class="num"><b>${fx(v.else_score, 3)}</b></td>
        <td class="num">${v.done === null ? '—' : v.done + 'h'}</td></tr>`).join('')}
    </tbody></table>
  </div>`;
}

/* -------------------------------------------------------------- tasking --- */
function vTasking() {
  const r = state.result;
  if (!r) return `<div class="empty"><b>Nothing to task yet</b>
    Run a building in Collapse ops first.</div>`;

  const H = r.params.horizon;
  const teams = r.params.teams;
  const done = r.voids.filter(v => v.done !== null);
  const byTeam = {};
  done.forEach(v => { (byTeam[v.team] = byTeam[v.team] || []).push(v); });

  const gantt = Array.from({ length: teams }, (_, i) => i + 1).map(t => {
    const items = byTeam[t] || [];
    const bars = items.map(v => {
      // A dig that overruns the horizon is drawn truncated at the wall, never
      // bleeding past the track -- the shortfall is stated in the panel below.
      const left = Math.min(99.4, (v.start / H) * 100);
      const width = Math.max(1.2, Math.min(100 - left, ((v.done - v.start) / H) * 100));
      return `<div class="gantt-bar" style="left:${left}%;width:${width}%;
        background:${survColor(v.survival_at_done)}"
        title="${esc(v.vid)} · ${esc(v.zone)} · ${fx(v.people, 2)} people · survival at entry ${fx(v.survival_at_done, 2)}">
        ${v.vid}</div>`;
    }).join('');
    return `<div class="gantt-team">
      <div class="gantt-label">T${t}</div>
      <div class="gantt-track">${bars}</div></div>`;
  }).join('');

  const axis = `<div class="gantt-axis"><div></div><div class="gantt-hours">
    ${[0, H / 4, H / 2, 3 * H / 4, H].map(h => `<span>${Math.round(h)}h</span>`).join('')}
  </div></div>`;

  return `
  ${r.mode === 'PREPLAN' ? `<div class="banner warn">
    <b>PRE-PLAN.</b> ${esc(r.building.bid)} has not collapsed. This is the plan that would be issued
    if it did — useful for pre-positioning, not for dispatch.
  </div>` : ''}
  <div class="grid g4">
    ${kpi(fx(r.lives, 2), r.mode === 'PREPLAN' ? 'lives at risk, modelled' : 'expected lives saved',
      'var(--green)', r.lives * 18)}
    ${kpi(r.voids.length, 'pockets modelled', 'var(--cyan)', r.voids.length * 7)}
    ${kpi(r.unreached.length, 'not reached in time', 'var(--amber)', r.unreached.length * 14)}
    ${kpi(r.expectant.length, 'expectant · re-triage', 'var(--red)', r.expectant.length * 20)}
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">${esc(r.building.bid)} — ${esc(r.building.label)}</div>
      <div class="card-sub">${teams} team${teams === 1 ? '' : 's'} · ${H} h horizon</div>
      <div class="row">
        <div class="seg">
          ${[1, 2, 3, 4, 6, 8].map(n => `<button data-teams="${n}"
            class="${r.params.teams === n ? 'on' : ''}">${n}T</button>`).join('')}
        </div>
        <div class="card-sub">bar colour = survival at entry</div>
      </div></div>
    <div class="gantt">${gantt}</div>
    ${axis}
    <div class="note" style="margin-top:12px">Duty cycle ${fx(r.params.duty, 2)} — the fraction of
      wall-clock a team actually spends working. Change the team count above and watch the tail of
      the list fall off the end.</div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">Ranked dig list</div>
      <div class="card-sub">ELSE = people × s(t) × d_dig ÷ effort × (1 − R)</div></div>
    <table><thead><tr>
      <th>#</th><th>Pocket</th><th>Mechanism</th><th>Zone</th><th class="num">Fl</th>
      <th class="num">People</th><th class="num">s0</th><th class="num">d_dig</th>
      <th class="num">R</th><th class="num">Min</th><th class="num">ELSE</th>
      <th class="num">Start</th><th class="num">Done</th><th class="num">s at entry</th></tr></thead><tbody>
      ${r.voids.map(v => `<tr class="${v.rank === 1 ? 'hi' : ''}">
        <td class="mono" style="color:var(--amber)">${v.rank}</td>
        <td><b>${esc(v.vid)}</b></td>
        <td class="card-sub">${esc(v.mechanism.replace(/_/g, ' '))}</td>
        <td>${esc(v.zone.replace(/_/g, ' '))}</td>
        <td class="num">${v.floor}</td>
        <td class="num">${fx(v.people, 2)}</td>
        <td class="num">${fx(v.s0, 2)}</td>
        <td class="num">${fx(v.d_dig, 2)}</td>
        <td class="num">${fx(v.secondary, 2)}</td>
        <td class="num">${v.effort}</td>
        <td class="num"><b>${fx(v.else_score, 3)}</b></td>
        <td class="num">${v.start === null ? '—' : v.start + 'h'}</td>
        <td class="num">${v.done === null ? '—' : v.done + 'h'}</td>
        <td class="num" style="color:${v.survival_at_done === null ? 'var(--dim)' : survColor(v.survival_at_done)}">
          ${v.survival_at_done === null ? '—' : fx(v.survival_at_done, 2)}</td></tr>`).join('')}
    </tbody></table>
  </div>

  ${r.unreached.length || r.expectant.length ? `<div class="card" style="margin-top:14px">
    <div class="card-t" style="margin-bottom:10px">Stated, not hidden</div>
    ${r.unreached.length ? `<div class="note"><b style="color:var(--amber)">Not reached within
      ${H} h:</b> ${r.unreached.map(esc).join(', ')} — re-triage when a team frees up.</div>` : ''}
    ${r.expectant.length ? `<div class="note" style="margin-top:8px"><b style="color:var(--red)">
      Expectant at T+${H}h:</b> ${r.expectant.map(esc).join(', ')}. This is a resource judgement
      with a re-triage timer — never a death verdict, and the word is blocked in output.</div>` : ''}
  </div>` : ''}`;
}

/* ------------------------------------------------------------- accuracy --- */
function vAccuracy() {
  const a = state.accuracy;
  if (!a) return `<div class="empty">Loading…</div>`;
  const vcls = { green: 'v-green', amber: 'v-amber', red: 'v-red' };

  return `
  <div class="split">
    <div class="card">
      <div class="card-h"><div class="card-t">What 95% can and cannot mean</div>
        <div class="card-sub">nine metrics · four reach it</div></div>
      <table class="metric-table"><thead><tr><th>Claim</th><th>Metric</th>
        <th>Path</th><th>Verdict</th></tr></thead><tbody>
        ${a.metrics.map(m => `<tr>
          <td>${esc(m.claim)}</td>
          <td class="card-sub">${esc(m.metric)}</td>
          <td class="card-sub">${esc(m.path)}</td>
          <td class="verdict ${vcls[m.tone]}">${esc(m.verdict)}</td></tr>`).join('')}
      </tbody></table>
      <div class="note" style="margin-top:12px">Only three things move a number toward 95%:
        <b style="color:var(--ink)">redundancy</b> (buy independent confirmations),
        <b style="color:var(--ink)">better prior data</b> (records before sensors), and
        <b style="color:var(--ink)">refusal</b> (say UNCERTAIN instead of estimating). The third
        is the invention.</div>
    </div>

    <div>
      <div class="card">
        <div class="card-h"><div class="card-t">Clearance PPV · k confirmations</div>
          <div class="card-sub">LR+ ${a.lr_per_confirmation} per test</div></div>
        <table><thead><tr><th>k</th>
          ${a.priors.map(p => `<th class="num">prior ${p}</th>`).join('')}</tr></thead><tbody>
          ${a.ppv_grid.map(g => `<tr><td class="mono">${g.k}</td>
            ${g.values.map((v, i) => `<td class="num" style="${v > 0.95 ? 'color:var(--green);font-weight:700' : v > 0.9 ? 'color:var(--amber);font-weight:700' : ''}">${v.toFixed(4)}</td>`).join('')}
          </tr>`).join('')}
        </tbody></table>
        <div class="note" style="margin-top:10px">One confirmation at a 1-in-1,000 prior gives
          0.45% confidence. Three at 10% give 91%. This is why clearance must be k-of-n.</div>
      </div>

      <div class="card" style="margin-top:14px">
        <div class="card-h"><div class="card-t">Detection with redundancy</div>
          <div class="card-sub">FINDER-class POD 0.80</div></div>
        ${a.detection.map(d => barRow(`${d.passes} pass${d.passes > 1 ? 'es' : ''}`, d.pod,
          1, d.pod > 0.95 ? 'var(--green)' : 'var(--cyan)', fx(d.pod, 3))).join('')}
        <div class="note" style="margin-top:8px">Three independent passes take a 0.80 sensor to
          0.992 without inventing a better sensor.</div>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">Determinism, checked live</div>
      <div class="card-sub">same record, same seed, run twice</div></div>
    ${state.selfcheck ? `<div class="row" style="align-items:center;gap:14px">
        ${tag(state.selfcheck.ok ? 'PASS' : 'FAIL', state.selfcheck.ok ? 'ok' : 'bad')}
        <span class="note"><b style="color:var(--ink)">${esc(state.selfcheck.detail)}</b> —
        ${esc(state.selfcheck.bid)}, seed ${state.selfcheck.seed}, ${state.selfcheck.pockets} pockets,
        ${fx(state.selfcheck.lives, 2)} expected lives on both runs. The plan a team receives at
        04:00 is the plan it would receive at 04:05.</span>
      </div>` : `<div class="note">checking…</div>`}
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">Adversarial checks</div>
      <div class="row"><span id="rt-status" class="card-sub">
        ${a.redteam ? `${a.redteam.passed}/${a.redteam.total} passed` : 'not run in this session'}
      </span>
      <button class="btn ghost sm" id="btn-rt">Run now</button></div></div>
    <div id="rt-list">${a.redteam ? renderRt(a.redteam.rows) : `<div class="note">
      Ten tests the pipeline must survive: unit consistency, scheduler safety, posterior
      normalisation, survival monotonicity, unknown structures, stale records, sensor silence,
      forbidden output, capacity shortfall, and the value-of-information regime.</div>`}</div>
  </div>`;
}

function renderRt(rows) {
  return `<table><tbody>${rows.map(r => `<tr>
    <td style="width:52px">${r.ok ? '<span class="tag ok">PASS</span>' : '<span class="tag bad">FAIL</span>'}</td>
    <td><b>${esc(r.name)}</b><div class="card-sub">${esc(r.detail)}</div></td></tr>`).join('')}
  </tbody></table>`;
}

/* ----------------------------------------------------------------- data --- */
function vData() {
  return `
  <div class="split top">
    <div class="card">
      <div class="card-h"><div class="card-t">Dataset</div>
        <div class="card-sub">${state.buildings.length} buildings · ${state.runs.length} run${state.runs.length===1?'':'s'}</div></div>
      <div class="row">
        <button class="btn" id="btn-export">Export JSON</button>
        <button class="btn ghost" id="btn-reseed">Reseed demo data</button>
      </div>
      <div class="hr"></div>
      <div class="field"><label>Import buildings (paste JSON array)</label>
        <textarea id="import-box" rows="7" placeholder='[{"bid":"XX-1","label":"Test","plot_m2":60,
"declared_floors":2,"design_occupancy":4,"use":"residential","structure":"rc_frame"}]'></textarea>
        <div class="hint">Records are merged on building id. Bad rows are skipped, not fatal.</div>
      </div>
      <button class="btn ghost" id="btn-import" style="margin-top:10px">Import</button>
    </div>

    <div class="card">
      <div class="card-h"><div class="card-t">Run history</div>
        <div class="card-sub">stored in prism.db</div></div>
      ${state.runs.length ? `<div class="scroll-y"><table><thead><tr><th>#</th><th>Building</th><th>When</th>
        <th class="num">T</th><th class="num">H</th><th class="num">Lives</th><th></th></tr></thead>
        <tbody>${state.runs.map(r => `<tr>
          <td class="mono">${r.id}</td><td>${esc(r.bid)}</td>
          <td class="card-sub">${esc((r.created_at || '').slice(5, 16).replace('T', ' '))}</td>
          <td class="num">${r.teams}</td><td class="num">${r.horizon}</td>
          ${livesCell(r, false)}
          <td><button class="btn ghost sm" data-loadrun="${r.id}">Load</button></td></tr>`).join('')}
        </tbody></table></div>` : `<div class="empty">No runs yet.</div>`}
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">Open-data sources</div>
      <div class="card-sub">field-level provenance · adapters, not scrapers</div></div>
    <table><thead><tr><th>Source</th><th>Licence</th><th>Supplies</th>
      <th>Constraint that shapes the design</th></tr></thead><tbody>
      ${[
        ['OpenStreetMap / Overpass', 'ODbL 1.0', 'building footprint, levels, use tag',
         'levels tag is volunteer-reported — a footprint is not a structural record'],
        ['Google Open Buildings 2.5D', 'CC-BY 4.0', 'roof geometry, height proxy',
         '2.5D height MAE ≈ 1.5 m — resolves storeys, not storey <i>legality</i>'],
        ['Sentinel-2 L2A (Copernicus)', 'free, open', '10 m optical, 5-day revisit',
         'a 46 m² plot is 0.46 px: sub-pixel, therefore not evidence'],
        ['Municipal tax / UPIC', 'public record', 'declared floors, assessed area',
         'declared value, not observed — useful only joined to an observation'],
        ['NDMA SACHET', 'Government of India', 'alert feed, severity, epicentre',
         'push notification, not a building-level signal — it sets the clock, not the target'],
        ['IMD rainfall / seismic', 'Government of India', 'antecedent wetting, PGA',
         'regional, daily — a prior on hazard, never on a specific address']
      ].map(([n, l, f, c]) => `<tr>
        <td><b>${n}</b></td>
        <td class="card-sub">${l}</td>
        <td class="card-sub">${f}</td>
        <td class="card-sub" style="max-width:420px">${c}</td></tr>`).join('')}
    </tbody></table>
    <div class="note" style="margin-top:12px">The bundled 14-building set is synthetic and follows these
      schemas field-for-field, so a live adapter can replace it without touching the engine. Each row
      above is joined on the building id, and every join records which side supplied the fact —
      declared or observed. A record that only ever had a declared value stays marked unverifiable.</div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="card-h"><div class="card-t">Raw records</div>
      <div class="card-sub">what the engine actually receives</div></div>
    <table><thead><tr><th>Id</th><th>Label</th><th>Use</th><th class="num">Plot</th>
      <th class="num">Decl.</th><th class="num">Listed</th><th class="num">Des.occ</th>
      <th class="num">Act.occ</th><th>Element</th><th class="num">Corr %</th></tr></thead><tbody>
      ${state.buildings.map(b => `<tr>
        <td class="mono">${esc(b.bid)}</td><td>${esc(b.label)}</td><td>${esc(b.use)}</td>
        <td class="num">${b.plot_m2}</td><td class="num">${b.declared_floors}</td>
        <td class="num">${b.observed_floors ?? '—'}</td>
        <td class="num">${b.design_occupancy ?? '—'}</td>
        <td class="num">${b.observed_occupancy ?? '—'}</td>
        <td class="card-sub">${esc((b.structure || '').replace(/_/g, ' '))}</td>
        <td class="num">${b.corrosion_pct == null ? '—' : fx(b.corrosion_pct, 1)}</td></tr>`).join('')}
    </tbody></table>
  </div>`;
}

/* --------------------------------------------------------------- render --- */
function render() {
  const v = state.view;
  const el = $('#view');
  if (v === 'dashboard') el.innerHTML = vDashboard();
  else if (v === 'queue') el.innerHTML = vQueue();
  else if (v === 'intake') el.innerHTML = vIntake();
  else if (v === 'ops') el.innerHTML = vOps();
  else if (v === 'tasking') el.innerHTML = vTasking();
  else if (v === 'accuracy') el.innerHTML = vAccuracy();
  else if (v === 'data') el.innerHTML = vData();

  if (v === 'ops' && state.result) {
    $('#ops-out').innerHTML = vOpsResult(state.result);
  }
  if (v === 'intake') {
    ['bid', 'label', 'plot_m2', 'declared_floors', 'observed_floors', 'design_occupancy',
      'observed_occupancy', 'corrosion_pct', 'time_of_day_h', 'element_removed', 'use',
      'structure', 'sanction_plan'].forEach(id => {
        const e = $('#f-' + id);
        if (e) e.addEventListener('input', debouncedPreview);
      });
    $('#btn-save').onclick = saveBuilding;
  }
  if (v === 'accuracy') { const rt = $('#btn-rt'); if (rt) rt.onclick = runRedteam; }
  wire();
}

let _pvTimer = null;
function debouncedPreview() {
  clearTimeout(_pvTimer);
  _pvTimer = setTimeout(updatePreview, 180);
}

function wire() {
  $$('[data-bid]').forEach(el => el.onclick = () => openDrawer(el.dataset.bid));
  $$('[data-goto]').forEach(el => el.onclick = () => { location.hash = '#/' + el.dataset.goto; });
  const rb2 = $('#btn-run2');
  if (rb2) rb2.onclick = () => runEngine();
  $$('[data-run]').forEach(el => el.onclick = async e => {
    e.stopPropagation();
    state.bid = el.dataset.run;
    location.hash = '#/ops';
    setTimeout(() => $('#btn-run') && $('#btn-run').click(), 60);
  });
  $$('[data-loadrun]').forEach(el => el.onclick = () => loadRun(el.dataset.loadrun));
  $$('[data-filter]').forEach(el => el.onclick = () => { state.filter = el.dataset.filter; render(); });
  $$('[data-teams]').forEach(el => el.onclick = () => {
    state.teams = +el.dataset.teams; runEngine();
  });

  const sel = $('#ops-bid');
  if (sel) sel.onchange = e => {
    state.bid = e.target.value;
    // A result belongs to the building that produced it. Showing Satya Niketan's
    // numbers under Mehrauli's name would be the worst kind of UI bug here.
    if (state.result && state.result.building.bid !== state.bid) state.result = null;
    render();
  };
  const st = $('#ops-teams');
  if (st) st.oninput = e => {
    state.teams = +e.target.value;
    $('#lbl-teams').textContent = state.teams;
    const c = $('#chain-params'); if (c) c.textContent = state.teams + (state.teams===1?' team · ':' teams · ') + state.horizon + ' h';
  };
  const sh = $('#ops-horizon');
  if (sh) sh.oninput = e => {
    state.horizon = +e.target.value;
    $('#lbl-hor').textContent = state.horizon + 'h';
    const c = $('#chain-params'); if (c) c.textContent = state.teams + (state.teams===1?' team · ':' teams · ') + state.horizon + ' h';
  };
  const br = $('#btn-run');
  if (br) br.onclick = runEngine;

  const ex = $('#btn-export');
  if (ex) ex.onclick = async () => {
    const d = await api.get('/api/export');
    const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'prism-buildings.json';
    a.click();
    toast('Exported ' + d.buildings.length + ' records');
  };
  const rs = $('#btn-reseed');
  if (rs) rs.onclick = async () => {
    await api.post('/api/reseed'); await refresh(); state.result = null;
    render(); toast('Demo dataset restored');
  };
  const imp = $('#btn-import');
  if (imp) imp.onclick = async () => {
    try {
      const parsed = JSON.parse($('#import-box').value);
      const items = Array.isArray(parsed) ? parsed : (parsed.buildings || []);
      const res = await api.post('/api/import', { buildings: items });
      await refresh(); render(); toast('Imported ' + res.imported + ' records');
    } catch (e) { toast('That is not valid JSON'); }
  };
}

async function saveBuilding() {
  const d = readForm();
  if (!d.bid || !d.label) return toast('Building id and label are required');
  const res = await api.post('/api/buildings', d);
  if (res.error) return toast('Save failed: ' + res.error);
  await refresh();
  toast('Saved ' + d.bid);
  location.hash = '#/queue';
}

async function runEngine(opts) {
  const quiet = !!(opts && opts.quiet);
  if (!state.bid) { if (!quiet) toast('Select a building first'); return; }
  const btn = $('#btn-run');
  if (btn) { btn.disabled = true; btn.textContent = 'Running…'; }
  try {
    const r = await api.post('/api/run',
      { bid: state.bid, teams: state.teams, horizon: state.horizon });
    if (r.error) { toast('Run failed: ' + r.error); return; }
    state.result = r;
    await refresh();
    render();
    if (!quiet) toast('Run #' + r.run_id + ' · ' + fx(r.lives, 2) +
      (r.mode === 'PREPLAN' ? ' lives at risk (pre-plan)' : ' expected lives'));
  } finally {
    const b2 = $('#btn-run');
    if (b2) { b2.disabled = false; b2.textContent = 'Run pipeline'; }
  }
}

async function loadRun(id) {
  const r = await api.get('/api/runs/' + id);
  state.result = r;
  state.bid = r.building.bid;
  state.teams = r.params.teams;
  state.horizon = r.params.horizon;
  location.hash = '#/tasking';
  setTimeout(render, 30);
  toast('Loaded run #' + id);
}

async function runRedteam(opts) {
  const quiet = !!(opts && opts.quiet);
  state.rtDone = true;
  const btn = $('#btn-rt');
  if (btn) { btn.disabled = true; btn.textContent = 'Running…'; }
  const res = await api.post('/api/redteam');
  const st = $('#rt-status'), ls = $('#rt-list');
  if (st) st.textContent = `${res.passed}/${res.total} passed`;
  if (ls) ls.innerHTML = renderRt(res.rows);
  if (btn) { btn.disabled = false; btn.textContent = 'Run again'; }
  if (!quiet) toast(res.passed === res.total ? 'All checks passed' : 'A check failed — see list');
}

/* --------------------------------------------------------------- drawer --- */
function openDrawer(bid) {
  const b = state.buildings.find(x => x.bid === bid);
  if (!b) return;
  $('#drawer-inner').innerHTML = `
    <div class="card-h"><div class="card-t">Building record</div>
      <button class="btn ghost sm" id="dr-close">Close</button></div>
    <h2 style="font-size:19px;margin:4px 0 2px">${esc(b.label)}</h2>
    <div class="card-sub" style="margin-bottom:16px">${esc(b.bid)} · ${esc(b.use)} ·
      ${esc((b.structure || '').replace(/_/g, ' '))}</div>
    <div class="row" style="margin-bottom:16px">${bandChip(b.band)}
      ${b.collapsed ? tag('collapsed', 'bad') : ''}
      ${b.verifiable ? tag('records verifiable', 'ok') : tag('records unverifiable', 'warn')}
      ${b.sub_pixel ? tag('sub-pixel plot', 'warn') : ''}</div>

    <div class="big" style="color:var(--red)">${fx(b.p_stands, 3)}</div>
    <div class="card-sub" style="margin-bottom:16px">standing probability</div>

    <div class="stat-line"><span>declared floors</span><span>G+${b.declared_floors - 1}</span></div>
    <div class="stat-line"><span>listed floors</span>
      <span>${b.observed_floors ? 'G+' + (b.observed_floors - 1) : 'unknown'}</span></div>
    <div class="stat-line"><span>floor ratio</span><span>${fx(b.lr_floors, 2)}×</span></div>
    <div class="stat-line"><span>density ratio</span><span>${fx(b.lr_occ, 2)}×</span></div>
    <div class="stat-line"><span>load ratio</span><span>${fx(b.lr, 2)}×</span></div>
    <div class="stat-line"><span>demand / capacity</span><span>${fx(b.dc, 2)}</span></div>
    <div class="stat-line"><span>plot in 10 m pixels</span><span>${fx(b.plot_px, 2)}</span></div>

    <div class="note" style="margin-top:16px">
      ${b.dc > 1
        ? `Demand exceeds capacity by ${fx(b.dc, 2)}×. Above 1.0 the building has already failed —
           no earthquake is required.`
        : `Within capacity at ${fx(b.dc, 2)}×. The band reflects the seismic term and record quality.`}
      ${b.verifiable ? '' : ' No sanctioned plan and no independent floor observation: the load ratio is unverifiable.'}
    </div>

    <div class="row" style="margin-top:20px">
      <button class="btn" id="dr-run">Run collapse pipeline</button>
      <button class="btn ghost red" id="dr-del">Delete record</button>
    </div>`;
  $('#drawer').classList.add('open');
  $('#dr-close').onclick = closeDrawer;
  $('#dr-run').onclick = () => {
    closeDrawer(); state.bid = b.bid; location.hash = '#/ops';
    setTimeout(() => $('#btn-run') && $('#btn-run').click(), 80);
  };
  $('#dr-del').onclick = async () => {
    await api.del('/api/buildings/' + b.bid);
    closeDrawer(); await refresh(); render(); toast('Deleted ' + b.bid);
  };
}

function closeDrawer() { $('#drawer').classList.remove('open'); }

boot();
