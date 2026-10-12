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
      <td>${bar(r.score, max, 'atk')}</td><td>${defenderOf(r.p).rating > 0 ? bar(defenderOf(r.p).rating, maxDef, 'def') : '–'}</td>
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
  view.innerHTML = `<div class="crumbs"><h1>Best gym defenders</h1><span class="muted">${all.length} Pokémon · heuristic: bulk weighted 3:1 over damage · Megas and Mythicals cannot defend</span></div>
    <table class="rk"><thead><tr><th>#</th><th>Pokémon</th><th>Fast</th><th>Charged</th><th>Defend</th></tr></thead><tbody>${body}</tbody></table>`;
}

const SOURCE_LABELS = {wild: 'Wild', eggs: 'Eggs', evolve: 'Evolve', raids: 'Raids', research: 'Research',
                       rocket: 'Team GO Rocket', mega_energy: 'Mega Energy (Mega Raids)'};
const NOW_LABELS = {raid: '⚔️ Raid', egg: '🥚 Egg', research: '🎁 Research'};

function renderDetail(id) {
  const p = BY_ID.get(id);
  if (!p) { view.innerHTML = '<p>Unknown Pokémon.</p>'; return; }
  const msets = legalMovesets(p);
  const hidden = !visible(p);

  const rankings = [];
  for (const t of DATA.types) {
    if (!msets.some(m => m.type === t.id)) continue;
    const rows = rankedForType(t.id, 'attackers');
    const i = rows.findIndex(r => r.p.id === p.id);
    rankings.push({t: t.id, rank: i >= 0 ? i + 1 : null, of: rows.length});
  }
  const gym = rankedGym();
  const gi = gym.findIndex(q => q.id === p.id);
  const d = defenderOf(p);

  const vsOf = t => msets.length ? Math.max(...msets.map(m => m.vs[t])) : 0;
  const vsMax = Math.max(1, ...DATA.types.map(t => vsOf(t.id)));
  const grid = DATA.types.map(t => {
    const v = vsOf(t.id);
    return `<div class="cell ${DARK_TEXT.has(t.id) ? 'dark-text' : ''}" style="background:${TYPE_COLORS[t.id]};opacity:${(0.25 + 0.75 * v / vsMax).toFixed(2)}" title="${esc(typeName(t.id))}: ${v.toFixed(1)}"><span>${esc(typeName(t.id)).slice(0, 4)}</span><b>${v.toFixed(0)}</b></div>`;
  }).join('');

  const forms = p.forms.map(fid => BY_ID.get(fid)).filter(Boolean)
    .map(q => `<a href="#p/${encodeURIComponent(q.id)}">${esc(q.name_fr)}</a>`).join(' · ');
  const msRows = msets.map(m => `<div class="kv"><span>${chip(m.type, 'small')} ${esc(moveName(m.fast))} / ${esc(moveName(m.charged))}${etm(m)}</span><b>${m.rating.toFixed(1)}</b></div>`).join('')
    || '<div class="muted">No damaging moveset.</div>';
  const rankRows = rankings.map(r => `<div class="kv"><span>${esc(typeName(r.t))} attackers</span><b>${r.rank ? `#${r.rank} of ${r.of}` : 'hidden by filters'}</b></div>`).join('');

  const g = p.get;
  const evo = g.evo_line.map((e, i) => {
    const node = `<a class="evo-node ${e.id === p.id ? 'me' : ''}" href="#p/${encodeURIComponent(e.id)}"><img src="${e.sprite || PLACEHOLDER}" alt="" onerror="this.onerror=null;this.src='${PLACEHOLDER}'"><span>${esc(e.name_fr)}</span></a>`;
    const arrow = i < g.evo_line.length - 1 ? `<div class="arrow">${e.candy != null ? e.candy + ' candy' : ''}<br>→</div>` : '';
    return node + arrow;
  }).join('');
  const src = g.sources.map(s => `<span class="src">${SOURCE_LABELS[s] || s}</span>`).join('');
  const megas = g.megas.map(m => BY_ID.get(m)).filter(Boolean)
    .map(q => `<a href="#p/${encodeURIComponent(q.id)}">${esc(q.name_fr)}</a>`).join(', ');
  const now = g.now.length
    ? g.now.map(n => `<div class="kv"><span>${NOW_LABELS[n.kind] || n.kind}: ${esc(n.who)}</span><b>${esc(n.label)}</b></div>`).join('')
    : '<div class="muted">Nothing in the current feed.</div>';

  view.innerHTML = `
    <div class="detail">
      <div class="dp-head">
        <img class="art" src="${p.art}" alt="" onerror="this.onerror=null;this.src='${PLACEHOLDER}'">
        <div>
          <h1>${esc(p.name_fr)} <span class="muted en">${esc(p.name_en)} · #${String(p.dex).padStart(3, '0')}</span></h1>
          <div>${p.types.map(t => chip(t)).join(' ')} ${badges(p)}</div>
          ${forms ? `<div class="muted">Other forms: ${forms}</div>` : ''}
          <div>Attack <b>${p.stats.atk}</b> · Defense <b>${p.stats.def}</b> · Stamina <b>${p.stats.sta}</b>
            <span class="muted">(level 40: ${p.l40.atk} / ${p.l40.def} / ${p.l40.hp} HP)</span></div>
          ${hidden ? '<div class="warn">Hidden from rankings by the current filters.</div>' : ''}
        </div>
      </div>
      <div class="dp-cols">
        <div>
          <div class="panel"><h5>Best movesets</h5>${msRows}</div>
          <div class="panel"><h5>Rankings</h5>${rankRows}
            <div class="kv"><span>Gym defender</span><b>${d.rating ? d.rating.toFixed(1) + (gi >= 0 ? ` · #${gi + 1} of ${gym.length}` : '') : '–'}</b></div>
          </div>
          <div class="panel"><h5>Counter score vs boss type</h5><div class="grid18">${grid}</div>
            <div class="muted small">Best moveset's rating against a single-type boss. Does not model the boss hitting back.</div></div>
        </div>
        <div>
          <div class="panel howto"><h5>How to get it</h5>
            <div class="evo">${evo}</div>
            ${g.buddy_km ? `<div class="kv"><span>Buddy distance</span><b>${g.buddy_km} km</b></div>` : ''}
            <div class="kv"><span>Shadow form</span><b>${g.has_shadow ? 'Yes, from Team GO Rocket' : 'No'}</b></div>
            ${megas ? `<div class="kv"><span>Mega</span><b>${megas} · Mega Energy from Mega Raids</b></div>` : ''}
            <div class="srcs">${src}</div>
            <div class="live"><b>Right now</b> <span class="muted">(LeekDuck feed, data built ${esc(DATA.built)})</span>${now}</div>
          </div>
        </div>
      </div>
    </div>`;
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

function bindSearch() {
  const input = document.getElementById('search');
  const list = document.getElementById('search-results');
  let results = [];
  const hide = () => { list.hidden = true; };
  const show = () => {
    const q = norm(input.value.trim());
    if (!q || !DATA) { hide(); return; }
    const score = p => {
      const fr = norm(p.name_fr), en = norm(p.name_en);
      if (fr.startsWith(q) || en.startsWith(q)) return 0;
      if (fr.includes(q) || en.includes(q)) return 1;
      return -1;
    };
    results = DATA.pokemon.map(p => ({p, s: score(p)})).filter(x => x.s >= 0)
      .sort((a, b) => a.s - b.s || a.p.dex - b.p.dex || a.p.id.localeCompare(b.p.id))
      .slice(0, 8).map(x => x.p);
    list.innerHTML = results.map(p => `<li><a href="#p/${encodeURIComponent(p.id)}">${sprite(p)}<span>${esc(p.name_fr)}</span><span class="muted">${esc(p.name_en)}</span>${badges(p)}</a></li>`).join('')
      || '<li class="muted">No match</li>';
    list.hidden = false;
  };
  input.addEventListener('input', show);
  input.addEventListener('focus', show);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && results.length) { location.hash = '#p/' + encodeURIComponent(results[0].id); input.blur(); hide(); }
    if (e.key === 'Escape') { hide(); input.blur(); }
  });
  list.addEventListener('click', () => { hide(); input.value = ''; });
  document.addEventListener('click', e => { if (!e.target.closest('.search')) hide(); });
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
  bindSearch();
  document.getElementById('built').textContent = `Data built ${DATA.built} · level 40, 15/15/15 IVs · comboDPS-based estimates, not simulations`;
  window.addEventListener('hashchange', route);
  route();
}

init();
