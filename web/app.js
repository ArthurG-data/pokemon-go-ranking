'use strict';

const TYPE_COLORS = {BUG:'#a8b820',DARK:'#705848',DRAGON:'#7038f8',ELECTRIC:'#f8d030',FAIRY:'#ee99ac',FIGHTING:'#c03028',FIRE:'#f08030',FLYING:'#a890f0',GHOST:'#705898',GRASS:'#78c850',GROUND:'#e0c068',ICE:'#98d8d8',NORMAL:'#a8a878',POISON:'#a040a0',PSYCHIC:'#f85888',ROCK:'#b8a038',STEEL:'#b8b8d0',WATER:'#6890f0'};
const DARK_TEXT = new Set(['ELECTRIC', 'ICE', 'GROUND', 'STEEL', 'FAIRY']);
const STORAGE_KEY = 'goraid.settings';
const PLACEHOLDER = 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><circle cx="20" cy="20" r="14" fill="#ddd"/></svg>');

let DATA = null;
const BY_ID = new Map();
const state = {
  filters: {legendary: false, mythical: false, mega: false, shadow: false, elite: false},
  mode: 'attackers',
  topn: 25,
  sort: null,   // {key, dir}
};
const view = document.getElementById('view');

// ---------- settings persistence (per-viewer convenience; page works without it) ----------
function loadSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (s && s.filters) Object.assign(state.filters, s.filters);
    if (s && (s.mode === 'attackers' || s.mode === 'counters')) state.mode = s.mode;
    if (s && typeof s.topn === 'number') state.topn = s.topn;
  } catch (e) { /* private mode / blocked storage: defaults */ }
}
function saveSettings() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({filters: state.filters, mode: state.mode, topn: state.topn})); } catch (e) { /* ignore */ }
}

// ---------- helpers ----------
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])); }
function norm(s) { return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
function typeName(t) { const x = DATA.types.find(y => y.id === t); return x ? x.name_fr : t; }
function chip(t, extra) { return `<span class="chip ${DARK_TEXT.has(t) ? 'dark-text' : ''} ${extra || ''}" style="background:${TYPE_COLORS[t]}">${esc(typeName(t))}</span>`; }
function moveName(id) { const m = DATA.moves[id]; return m ? m.name_fr : (id || '–'); }
function sprite(p, cls) {
  return `<img class="sprite ${cls || ''} ${p.flags.shadow ? 'is-shadow' : ''}" src="${p.flags.mega ? p.art : p.sprite}" alt="" loading="lazy" onerror="this.onerror=null;this.src='${PLACEHOLDER}'">`;
}
function badges(p) {
  let b = '';
  if (p.flags.mega) b += '<span class="tag mega">MEGA</span>';
  if (p.flags.shadow) b += '<span class="tag shadow">SHADOW</span>';
  if (p.flags.mythical) b += '<span class="tag leg">MYTH</span>';
  else if (p.flags.legendary) b += '<span class="tag leg">LEG</span>';
  return b;
}
function etm(ms) { return ms.elite_tm ? ' <span class="tag etm" title="Needs an Elite TM">ETM</span>' : ''; }
function bar(value, max, cls) {
  const w = max > 0 ? Math.round(value / max * 80) : 0;
  return `<span class="bar ${cls || ''}" style="width:${w}px"></span>${value.toFixed(1)}`;
}
function nameCell(p) { return `<a class="pname" href="#p/${encodeURIComponent(p.id)}">${sprite(p)}<span>${esc(p.name_fr)}</span>${badges(p)}</a>`; }

// ---------- ranking logic (all filtering happens here) ----------
function visible(p) {
  const f = state.filters;
  if (f.mega && p.flags.mega) return false;
  if (f.shadow && p.flags.shadow) return false;
  if (f.mythical && p.flags.mythical) return false;
  if (f.legendary && p.flags.legendary) return false;
  return true;
}
function legalMovesets(p) { return state.filters.elite ? p.movesets.filter(m => !m.elite_tm) : p.movesets; }
function defenderOf(p) { return state.filters.elite ? p.defender_no_elite : p.defender; }
function bestMoveset(p, typeId, mode) {
  let best = null, score = 0;
  for (const m of legalMovesets(p)) {
    if (mode === 'attackers' && m.type !== typeId) continue;
    const s = mode === 'attackers' ? m.rating : m.vs[typeId];
    if (s > score) { score = s; best = m; }
  }
  return best ? {ms: best, score} : null;
}
function rankedForType(typeId, mode) {
  mode = mode || state.mode;
  const rows = [];
  for (const p of DATA.pokemon) {
    if (!visible(p)) continue;
    const b = bestMoveset(p, typeId, mode);
    if (b) rows.push({p, ms: b.ms, score: b.score});
  }
  rows.sort((a, b) => b.score - a.score);
  return rows;
}
function rankedGym() {
  return DATA.pokemon.filter(p => visible(p) && defenderOf(p).rating > 0)
    .sort((a, b) => defenderOf(b).rating - defenderOf(a).rating);
}
function topSlice(rows) { return state.topn > 0 ? rows.slice(0, state.topn) : rows; }
function applySort(rows) {
  if (!state.sort) return rows;
  const {key, dir} = state.sort;
  const val = r => key === 'name' ? r.p.name_fr : key === 'dps' ? r.ms.dps : key === 'tdo' ? r.ms.tdo : key === 'defend' ? defenderOf(r.p).rating : r.score;
  return rows.slice().sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * dir; });
}

// ---------- views ----------
function renderLanding() {
  const cards = DATA.types.map(t => {
    const top = rankedForType(t.id).slice(0, 3);
    const rows = top.map(r => `<a class="r" href="#p/${encodeURIComponent(r.p.id)}">${sprite(r.p)}<span>${esc(r.p.name_fr)}</span><b>${r.score.toFixed(0)}</b></a>`).join('');
    return `<div class="tcard" data-type="${t.id}">
      <a class="hd ${DARK_TEXT.has(t.id) ? 'dark-text' : ''}" style="background:${TYPE_COLORS[t.id]}" href="#type/${t.id}">${esc(t.name_fr)}</a>
      ${rows || '<div class="r muted">nothing with current filters</div>'}
      <a class="more" href="#type/${t.id}">see all →</a>
    </div>`;
  }).join('');
  view.innerHTML = `<h1 class="sr-only">Types</h1><div class="tgrid">${cards}</div>`;
}

function renderType(typeId) {
  if (!TYPE_COLORS[typeId]) { view.innerHTML = '<p>Unknown type.</p>'; return; }
  const all = rankedForType(typeId);
  const rows = topSlice(applySort(all));
  const max = all.length ? all[0].score : 0;
  const maxDef = Math.max(0, ...all.map(r => defenderOf(r.p).rating));
  const title = state.mode === 'attackers' ? `Best ${esc(typeName(typeId))} attackers` : `Best counters vs ${esc(typeName(typeId))}`;
  const th = (key, label) => `<th data-sort="${key}" class="${state.sort && state.sort.key === key ? (state.sort.dir > 0 ? 'asc' : 'desc') : ''}">${label}</th>`;
  const body = rows.map((r, i) => `<tr>
      <td>${i + 1}</td><td>${nameCell(r.p)}</td>
      <td>${esc(moveName(r.ms.fast))}</td>
      <td>${esc(moveName(r.ms.charged))}${etm(r.ms)}</td>
      <td>${r.ms.dps.toFixed(1)}</td><td>${Math.round(r.ms.tdo)}</td>
      <td>${bar(r.score, max, 'atk')}</td><td>${bar(defenderOf(r.p).rating, maxDef, 'def')}</td>
    </tr>`).join('');
  view.innerHTML = `
    <div class="crumbs"><a href="#">← All types</a> ${chip(typeId, 'big')} <h1>${title}</h1><span class="muted">${all.length} Pokémon</span></div>
    <table class="rk"><thead><tr><th>#</th>${th('name', 'Pokémon')}<th>Fast</th><th>Charged</th>${th('dps', 'DPS')}${th('tdo', 'TDO')}${th('score', state.mode === 'attackers' ? 'Attack' : 'Score')}${th('defend', 'Defend')}</tr></thead><tbody>${body}</tbody></table>`;
  view.querySelectorAll('th[data-sort]').forEach(h => h.addEventListener('click', () => {
    const key = h.dataset.sort;
    state.sort = state.sort && state.sort.key === key ? {key, dir: -state.sort.dir} : {key, dir: key === 'name' ? 1 : -1};
    renderType(typeId);
  }));
}

function renderGym() {
  const all = rankedGym();
  const rows = topSlice(all);
  const max = all.length ? defenderOf(all[0]).rating : 0;
  const body = rows.map((p, i) => {
    const d = defenderOf(p);
    return `<tr><td>${i + 1}</td><td>${nameCell(p)}</td><td>${esc(moveName(d.fast))}</td><td>${esc(moveName(d.charged))}</td><td>${bar(d.rating, max, 'def')}</td></tr>`;
  }).join('');
  view.innerHTML = `<div class="crumbs"><h1>Best gym defenders</h1><span class="muted">${all.length} Pokémon · heuristic: defender DPS × bulk</span></div>
    <table class="rk"><thead><tr><th>#</th><th>Pokémon</th><th>Fast</th><th>Charged</th><th>Defend</th></tr></thead><tbody>${body}</tbody></table>`;
}

function renderDetail(id) {   // replaced in Task 9
  view.innerHTML = `<p class="muted">Detail page for ${esc(id)} is not built yet.</p>`;
}

// ---------- routing & controls ----------
function route() {
  if (!DATA) return;
  const [kind, arg] = location.hash.replace(/^#/, '').split('/');
  const tab = kind === 'gym' ? 'gym' : 'types';
  document.querySelectorAll('.tabs a').forEach(a => a.classList.toggle('on', a.dataset.tab === tab));
  if (kind === 'type' && arg) renderType(arg);
  else if (kind === 'p' && arg) renderDetail(decodeURIComponent(arg));
  else if (kind === 'gym') renderGym();
  else renderLanding();
  window.scrollTo(0, 0);
}

function bindControls() {
  document.querySelectorAll('input[data-filter]').forEach(cb => {
    cb.checked = !!state.filters[cb.dataset.filter];
    cb.addEventListener('change', () => { state.filters[cb.dataset.filter] = cb.checked; saveSettings(); route(); });
  });
  const modeBtns = document.querySelectorAll('#mode button');
  const paintMode = () => modeBtns.forEach(b => b.classList.toggle('on', b.dataset.mode === state.mode));
  modeBtns.forEach(b => b.addEventListener('click', () => { state.mode = b.dataset.mode; paintMode(); saveSettings(); route(); }));
  paintMode();
  const topn = document.getElementById('topn');
  topn.value = String(state.topn);
  topn.addEventListener('change', () => { state.topn = Number(topn.value); saveSettings(); route(); });
}

async function init() {
  loadSettings();
  bindControls();
  try {
    const resp = await fetch('data.json');
    if (!resp.ok) throw new Error(resp.status + ' ' + resp.statusText);
    DATA = await resp.json();
  } catch (e) {
    view.innerHTML = `<p class="error">Could not load data.json (${esc(e.message)}). Run <code>uv run python -m pipeline.build</code> and serve the <code>web/</code> folder over HTTP.</p>`;
    return;
  }
  for (const p of DATA.pokemon) BY_ID.set(p.id, p);
  document.getElementById('built').textContent = `Data built ${DATA.built} · level 40, 15/15/15 IVs · comboDPS-based estimates, not simulations`;
  window.addEventListener('hashchange', route);
  route();
}

init();
