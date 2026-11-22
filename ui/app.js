'use strict';
/* MTAI - front end. Talks to local_ai_chat.py over /api (token protected). */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const TOKEN = $('meta[name=token]').content;
const nativeApi = () => (window.pywebview && window.pywebview.api) || null;

/* ------------------------------------------------------------------ icons */
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  sidebar: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4.2 7.6L12 12l7.8-4.4M12 12v9"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  refresh: '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v5h-5"/>',
  edit: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/>',
  trash: '<path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 12.5h9l1-12.5"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  chev: '<path d="M6 9l6 6 6-6"/>',
  spark: '<path d="M12 3l1.9 5.6L19.5 10.5l-5.6 1.9L12 18l-1.9-5.6L4.5 10.5l5.6-1.9z"/><path d="M19 17l.7 1.8 1.8.7-1.8.7L19 22l-.7-1.8-1.8-.7 1.8-.7z"/>',
  brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V5a2 2 0 0 0-3-1z"/><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  tool: '<path d="M14.5 6.5a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3z"/><path d="M14.5 6.5L17 4"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  power: '<path d="M12 3v8"/><path d="M6.4 6.6a8 8 0 1 0 11.2 0"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  bolt: '<path d="M13 3L5 13h6l-1 8 8-10h-6z"/>',
  code: '<path d="M9 8l-4 4 4 4M15 8l4 4-4 4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z"/>',
  bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V16h7v-2.1A6 6 0 0 0 12 3z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  alert: '<path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17h.01"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="2"/>',
  memory: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>',
  play: '<path d="M7 5l12 7-12 7z"/>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  tablet: '<rect x="5" y="3" width="14" height="18" rx="2.5"/><path d="M11 18h2"/>',
  phone: '<rect x="7.5" y="3" width="9" height="18" rx="2.5"/><path d="M11 18h2"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M7 9l3 3-3 3M12.5 15H17"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  wrap: '<path d="M4 6h16M4 12h13a3 3 0 0 1 0 6h-4M4 18h5"/><path d="M15 16l-2 2 2 2"/>',
  clip: '<path d="M20.5 11.5l-8.3 8.3a5.2 5.2 0 0 1-7.4-7.4l8.6-8.6a3.5 3.5 0 0 1 5 5l-8.6 8.6a1.7 1.7 0 0 1-2.5-2.5l7.9-7.9"/>',
  wand: '<path d="M4 20L14.5 9.5M17 3v3M15.5 4.5h3M20 8v2M19 9h2M12 4v1.5M11.25 4.75h1.5"/><path d="M13 8l3 3"/>',
  keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><path d="M6.5 10h.01M10 10h.01M14 10h.01M17.5 10h.01M7.5 14h9"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.6-.8 1.6-1.6 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-.9.7-1.6 1.6-1.6H16a5 5 0 0 0 5-5c0-4.1-4-7.4-9-7.4z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="14.5" cy="7" r="1"/>',
};

/* ------------------------------------------------------------------ theme */
const THEMES = [
  { id: 'amethyst', name: 'Amethyst', accent: '#8b5cf6', accent2: '#c084fc', bg: '#07060b' },
  { id: 'ocean', name: 'Ocean', accent: '#3b82f6', accent2: '#22d3ee', bg: '#05080e' },
  { id: 'sakura', name: 'Sakura', accent: '#ec4899', accent2: '#f9a8d4', bg: '#0c0609' },
  { id: 'emerald', name: 'Emerald', accent: '#10b981', accent2: '#a3e635', bg: '#040a08' },
  { id: 'sunset', name: 'Sunset', accent: '#f97316', accent2: '#facc15', bg: '#0c0805' },
  { id: 'crimson', name: 'Crimson', accent: '#e11d48', accent2: '#fb7185', bg: '#0c0506' },
  { id: 'aurora', name: 'Aurora', accent: '#14b8a6', accent2: '#a78bfa', bg: '#05090b' },
  { id: 'mono', name: 'Graphite', accent: '#9ca3af', accent2: '#e5e7eb', bg: '#080809' },
];
const DEFAULT_THEME = { preset: 'amethyst', accent: '#8b5cf6', accent2: '#c084fc', bg: '#07060b', glow: 1, motion: true, anim: 'medium' };
const ANIM_LEVELS = ['none', 'reduced', 'medium', 'high'];
// theme.anim was a true/false switch before 2026-11-14: true becomes medium (or reduced when Windows asks for less motion), false becomes none
function animOf(a) {
  if (ANIM_LEVELS.includes(a)) return a;
  if (a === false) return 'none';
  return matchMedia('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'medium';
}
// 0 none, 1 reduced, 2 medium, 3 high (motion.js, extras.js and privacy.js ask this)
function animLevel() { return Math.max(0, ANIM_LEVELS.indexOf(document.body.dataset.anim || 'medium')); }
const hexOk = h => /^#[0-9a-f]{6}$/i.test(h || '');
const hex2rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const rgb2hex = c => '#' + c.map(v => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('');
const mix = (a, b, t) => { const x = hex2rgb(a), y = hex2rgb(b); return rgb2hex(x.map((v, i) => v + (y[i] - v) * t)); };
const trip = h => hex2rgb(h).join(' ');
function themeOf(raw) {
  const t = { ...DEFAULT_THEME, ...(raw || {}) };
  for (const k of ['accent', 'accent2', 'bg']) if (!hexOk(t[k])) t[k] = DEFAULT_THEME[k];
  t.anim = animOf(raw && raw.anim);
  return t;
}
function applyTheme(raw) {
  const t = themeOf(raw), A = t.accent, B = t.accent2, G = t.bg, W = '#ffffff', K = '#000000';
  const v = {
    '--accent': A, '--acc': trip(A), '--accent-l': mix(A, W, .3), '--acc-l': trip(mix(A, W, .3)),
    '--accent2': B, '--acc2': trip(B), '--accent2-l': mix(B, W, .45), '--accent2-d': mix(B, K, .35), '--accent-mid': mix(A, B, .5),
    '--deep': mix(A, K, .2), '--deep-rgb': trip(mix(A, K, .5)), '--deep-2': mix(A, K, .5), '--tint': mix(A, W, .8),
    '--bg': G, '--bg-rgb': trip(G), '--bg-glow': mix(G, A, .14),
    '--glass-rgb': trip(mix(G, A, .11)), '--glass2-rgb': trip(mix(G, A, .17)), '--glass3-rgb': trip(mix(G, A, .14)),
    '--text': mix(W, A, .06), '--muted': mix('#a1a1aa', A, .2), '--dim': mix('#6b6b78', A, .18), '--glow': String(t.glow),
  };
  const root = document.documentElement.style;
  for (const [k, val] of Object.entries(v)) root.setProperty(k, val);
  document.body.classList.toggle('no-motion', !t.motion);
  document.body.dataset.anim = document.documentElement.dataset.anim = t.anim;
  document.body.classList.toggle('no-anim', t.anim === 'none');
  document.body.classList.toggle('anim-reduced', t.anim === 'reduced');
  document.body.classList.toggle('anim-high', t.anim === 'high');
  try { localStorage.setItem('mtai-theme', JSON.stringify(t)); } catch {}
  const nat = nativeApi();
  if (nat && nat.set_caption) nat.set_caption(G, v['--text']).catch(() => {});
}
// apply the last theme at once, before settings arrive, so the window never flashes purple
try { const t = JSON.parse(localStorage.getItem('mtai-theme') || 'null'); if (t) applyTheme(t); } catch {}
window.addEventListener('pywebviewready', () => applyTheme(S.settings.theme));
function icon(name, size = 18) {
  return `<svg class="i" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ''}</svg>`;
}
function hydrateIcons(root = document) {
  $$('[data-icon]', root).forEach(el => {
    el.insertAdjacentHTML('afterbegin', icon(el.dataset.icon, +el.dataset.size || 18));
    el.removeAttribute('data-icon');
  });
}

/* ---------------------------------------------------------------- helpers */
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
function fmtSize(b) {
  if (!b) return '';
  const u = ['B', 'KB', 'MB', 'GB', 'TB']; let i = 0;
  while (b >= 1024 && i < 4) { b /= 1024; i++; }
  return (i >= 3 ? b.toFixed(1) : Math.round(b)) + ' ' + u[i];
}
function fmtDur(s) {
  if (s == null) return '';
  if (s < 1) return s.toFixed(1) + 's';
  if (s < 60) return Math.round(s) + 's';
  return Math.floor(s / 60) + 'm ' + Math.round(s % 60) + 's';
}
const fmtCtx = n => !n ? '' : n >= 1024 ? Math.round(n / 1024) + 'K' : String(n);
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

async function api(path, body, opts = {}) {
  // every "open in browser" goes through here: none in privacy mode, the system browser is outside MTAI's block
  if (path === 'open' && body && privacyOn()) { privacyBlocked('link'); return { blocked: true }; }
  const r = await fetch('/api/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Token': TOKEN, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: opts.signal,
  });
  if (opts.stream) {
    if (!r.ok) throw new Error((await r.text()) || r.statusText);
    return r;
  }
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.error) throw new Error(j.error || r.statusText);
  return j;
}
async function* ndjson(resp) {
  const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
      if (line) { try { yield JSON.parse(line); } catch {} }
    }
  }
  if (buf.trim()) { try { yield JSON.parse(buf); } catch {} }
}

function toast(text, kind = 'info', ms = 3200) {
  const ic = kind === 'ok' ? 'check' : kind === 'err' ? 'alert' : 'info';
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.innerHTML = icon(ic, 17) + `<span>${esc(text)}</span>`;
  $('#toasts').append(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 300); }, ms);
}

function confirmDialog({ title, text, ok = 'Delete', danger = true }) {
  return new Promise(res => {
    const d = $('#dialog');
    d.innerHTML = `<div class="dialog"><h3>${esc(title)}</h3><p>${esc(text)}</p><div class="d-acts">
      <button class="btn ghost" data-r="0">Cancel</button><button class="btn ${danger ? 'danger' : 'primary'}" data-r="1">${esc(ok)}</button></div></div>`;
    d.hidden = false;
    const done = v => { d.hidden = true; d.onclick = null; document.removeEventListener('keydown', key, true); res(v); };
    const key = e => { if (e.key === 'Escape') { e.stopPropagation(); done(false); } if (e.key === 'Enter') { e.stopPropagation(); done(true); } };
    document.addEventListener('keydown', key, true);
    d.onclick = e => { const b = e.target.closest('[data-r]'); if (b) done(b.dataset.r === '1'); else if (e.target === d) done(false); };
    setTimeout(() => d.querySelector('[data-r="1"]').focus(), 20);
  });
}

// big picture view: click outside or Esc closes it; generated pictures get Download and Show in folder
function lightbox(src, label = '') {
  const d = $('#dialog');
  const gen = (src.match(/\/img\/([\w.-]+)$/) || [])[1] || '';
  d.innerHTML = `<div class="lightbox"><img src="${esc(src)}" alt="${esc(label)}">
    <div class="lb-bar">
      <button class="btn primary small" data-lb="download">${icon('download', 15)}Download</button>
      ${gen ? `<button class="btn ghost small" data-lb="folder">${icon('folder', 15)}Show in folder</button>` : ''}
      <button class="btn ghost small" data-lb="close">${icon('x', 15)}Close</button>
    </div></div>`;
  d.hidden = false;
  const close = () => { d.hidden = true; d.onclick = null; };
  d.onclick = async e => {
    const b = e.target.closest('[data-lb]');
    if (!b) { if (!e.target.closest('.lightbox img')) close(); return; }
    e.stopPropagation();
    if (b.dataset.lb === 'close') return close();
    if (b.dataset.lb === 'folder') { api('images/reveal', { name: gen }).catch(() => {}); return; }
    // download: Save As through the app window; in a browser (or for attached pictures) a normal download
    const nat = nativeApi();
    if (gen && nat && nat.save_image) {
      try { const p = await nat.save_image(gen, label.slice(0, 60)); if (p) toast('Saved to ' + p, 'ok'); } catch (err) { toast('Save failed: ' + err, 'err'); }
      return;
    }
    const a = document.createElement('a');
    a.href = src; a.download = gen || ('mtai-picture.' + ((src.match(/^data:image\/(\w+)/) || [])[1] || 'png'));
    document.body.append(a); a.click(); a.remove();
  };
}

/* --------------------------------------------------------------- markdown */
const KW = new Set(('if else elif for while do return function def class import from as export default const let var new this self ' +
  'try except catch finally raise throw with yield async await lambda in of is not and or None null undefined true false True False nil ' +
  'pub fn struct enum impl use mod match loop break continue switch case public private protected static void int float double char bool ' +
  'string long short byte unsigned signed using namespace package interface extends implements type func go defer select chan map range ' +
  'local then end elseif repeat until begin echo print pass global nonlocal assert del sizeof typedef template typename auto mut ref ' +
  'override virtual final abstract sealed readonly get set where SELECT FROM WHERE INSERT INTO VALUES UPDATE DELETE CREATE TABLE JOIN ON ' +
  'GROUP BY ORDER LIMIT AS AND OR NOT NULL PRIMARY KEY').split(' '));
const PLAIN_LANGS = new Set(['', 'text', 'txt', 'plain', 'plaintext', 'markdown', 'md', 'output', 'console', 'log']);

function highlight(code, lang) {
  lang = (lang || '').toLowerCase();
  if (PLAIN_LANGS.has(lang)) return esc(code);
  const hash = /^(py|python|sh|bash|shell|zsh|ps1|powershell|pwsh|rb|ruby|r|yaml|yml|toml|ini|perl|make|makefile|dockerfile|conf|cmake|nim|elixir|ex)$/.test(lang);
  const slash = !/^(py|python|sh|bash|shell|zsh|yaml|yml|toml|ini|r|rb|ruby)$/.test(lang);
  const dash = /^(sql|lua|haskell|hs)$/.test(lang);
  const parts = [];
  if (slash) parts.push('\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*');
  if (hash) parts.push('#[^\\n]*');
  if (dash) parts.push('--[^\\n]*');
  const comment = parts.length ? '(' + parts.join('|') + ')' : '(\\b\\B)';
  const re = new RegExp(comment +
    '|("""[\\s\\S]*?"""|\'\'\'[\\s\\S]*?\'\'\'|"(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\'|`(?:\\\\.|[^`\\\\])*`)' +
    '|(\\b0x[0-9a-fA-F]+\\b|\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)' +
    '|([A-Za-z_$][\\w$]*)', 'g');
  let out = '', last = 0, m;
  while ((m = re.exec(code))) {
    out += esc(code.slice(last, m.index));
    const t = esc(m[0]);
    if (m[1]) out += `<span class="tk-c">${t}</span>`;
    else if (m[2]) out += `<span class="tk-s">${t}</span>`;
    else if (m[3]) out += `<span class="tk-n">${t}</span>`;
    else if (KW.has(m[4])) out += `<span class="tk-k">${t}</span>`;
    else if (code[re.lastIndex] === '(') out += `<span class="tk-f">${t}</span>`;
    else if (/^[A-Z][a-z]/.test(m[4])) out += `<span class="tk-t">${t}</span>`;
    else out += t;
    last = re.lastIndex;
  }
  return out + esc(code.slice(last));
}

function inline(s) {
  const codes = [];
  s = s.replace(/`([^`\n]+)`/g, (_, c) => { codes.push(c); return '\u0000' + (codes.length - 1) + '\u0000'; });
  s = esc(s);
  s = s.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>');
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>');
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s<]+[^\s<.,;:!?)\]'"])/g, '$1<a href="$2">$2</a>');
  s = s.replace(/\*\*\*(?!\s)(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
       .replace(/\*\*(?!\s)(.+?)\*\*/g, '<strong>$1</strong>')
       .replace(/(^|[^\w])__(?!\s)(.+?)__(?!\w)/g, '$1<strong>$2</strong>')
       .replace(/(^|[^*\w])\*(?![\s*])(.+?)\*(?!\*)/g, '$1<em>$2</em>')
       .replace(/(^|[^_\w])_(?![\s_])(.+?)_(?!\w)/g, '$1<em>$2</em>')
       .replace(/~~(.+?)~~/g, '<del>$1</del>');
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => '<code>' + esc(codes[+i]) + '</code>');
}

const RUNNABLE = { python: 'python', py: 'python', python3: 'python', javascript: 'javascript', js: 'javascript', node: 'javascript',
  mjs: 'javascript', powershell: 'powershell', ps1: 'powershell', pwsh: 'powershell' };
const RUN_NAMES = { python: 'Python', javascript: 'JavaScript (Node)', powershell: 'PowerShell' };
const isHtmlCode = (code, lang) => ['html', 'htm', 'xhtml', 'svg'].includes(lang) ||
  (!lang || lang === 'xml') && /^\s*(<!doctype html|<html[\s>]|<svg[\s>])/i.test(code);

function codeBlock(code, lang) {
  code = code.replace(/\n$/, '');
  const l = (lang || '').toLowerCase(), n = code.split('\n').length;
  const run = RUNNABLE[l] && S.env[RUNNABLE[l]];
  const btn = (act, ic, label, cls = '') => `<button class="cb-btn ${cls}" data-cb="${act}" title="${label}">${icon(ic, 13)}<span>${label}</span></button>`;
  return `<div class="code${n > 24 ? ' tall' : ''}" data-lang="${esc(l)}"><div class="code-head"><span class="cb-lang">${esc(lang || 'text')}</span>` +
    (n > 1 ? `<span class="cb-lines">${n} lines</span>` : '') + '<span class="cb-sp"></span>' +
    (isHtmlCode(code, l) ? btn('preview', 'eye', 'Preview', 'hot') : '') +
    (run ? btn('run', 'play', 'Run', 'hot') : '') +
    (n > 24 ? btn('expand', 'expand', 'Expand', 'ic-only') : '') +
    btn('wrap', 'wrap', 'Wrap lines', 'ic-only') + btn('save', 'download', 'Save as file', 'ic-only') + btn('copy', 'copy', 'Copy') +
    `</div><div class="code-body">${n > 1 ? `<div class="gutter">${Array.from({ length: n }, (_, i) => i + 1).join('\n')}</div>` : ''}` +
    `<pre><code>${highlight(code, lang)}</code></pre></div></div>`;
}

const RE_LIST = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/;
const RE_TSEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const RE_PH = /^\u0001(\d+)\u0001$/;

function md(src) {
  const blocks = [];
  src = String(src || '').replace(/\r\n?/g, '\n');
  src = src.replace(/(^|\n)[ \t]*```([^\n`]*)\n([\s\S]*?)(?:\n[ \t]*```[ \t]*(?=\n|$)|$)/g, (_, pre, lang, code) => {
    blocks.push(codeBlock(code, lang.trim().split(/\s+/)[0]));
    return pre + '\u0001' + (blocks.length - 1) + '\u0001';
  });
  src = src.replace(/\n?[ \t]*```[^\n`]*$/, '');   // lone fence at the end: still streaming, or a stray one

  const isStart = l => RE_PH.test(l.trim()) || /^#{1,6}\s/.test(l) || /^\s*>/.test(l) || RE_LIST.test(l) ||
    /^\s*([-*_])\s*(\1\s*){2,}$/.test(l);
  const splitRow = l => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());

  function render(lines) {
    let out = '', i = 0;
    while (i < lines.length) {
      const l = lines[i];
      const t = l.trim();
      if (!t) { i++; continue; }
      let m;
      if ((m = t.match(RE_PH))) { out += blocks[+m[1]]; i++; continue; }
      if ((m = l.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/))) { const n = m[1].length; out += `<h${n}>${inline(m[2])}</h${n}>`; i++; continue; }
      if (/^\s*([-*_])\s*(\1\s*){2,}$/.test(l)) { out += '<hr>'; i++; continue; }
      if (/^\s*>/.test(l)) {
        const buf = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ''));
        out += '<blockquote>' + render(buf) + '</blockquote>'; continue;
      }
      if (t.includes('|') && i + 1 < lines.length && RE_TSEP.test(lines[i + 1])) {
        const head = splitRow(l); i += 2; const rows = [];
        while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(splitRow(lines[i++]));
        out += '<div class="tbl-wrap"><table><thead><tr>' + head.map(c => `<th>${inline(c)}</th>`).join('') + '</tr></thead><tbody>' +
          rows.map(r => '<tr>' + head.map((_, k) => `<td>${inline(r[k] || '')}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>';
        continue;
      }
      if ((m = l.match(RE_LIST))) {
        const base = m[1].length, ordered = /\d/.test(m[2]), start = ordered ? parseInt(m[2]) : 1;
        const items = [];
        while (i < lines.length) {
          const li = lines[i], lm = li.match(RE_LIST);
          if (lm && lm[1].length <= base + 1 && /\d/.test(lm[2]) === ordered) { items.push([lm[3]]); i++; continue; }
          if (lm && lm[1].length <= base + 1) break;          // other list type at same level
          if (!li.trim()) {
            const nx = lines[i + 1];
            if (nx !== undefined && (/^\s{2,}\S/.test(nx) || (RE_LIST.test(nx) && nx.match(RE_LIST)[1].length <= base + 1 && /\d/.test(nx.match(RE_LIST)[2]) === ordered))) { i++; continue; }
            break;
          }
          if (/^\s+\S/.test(li) || RE_PH.test(li.trim())) {
            if (!items.length) break;
            items[items.length - 1].push(li.replace(new RegExp('^\\s{0,' + (base + 4) + '}'), '')); i++; continue;
          }
          if (items.length && !isStart(li)) { items[items.length - 1].push(li); i++; continue; }  // lazy continuation
          break;
        }
        const tag = ordered ? 'ol' : 'ul';
        out += `<${tag}${ordered && start !== 1 ? ` start="${start}"` : ''}>` + items.map(it => {
          let first = it[0], task = '';
          const tm = first.match(/^\[([ xX])\]\s+(.*)$/);
          if (tm) { task = `<span class="task">${tm[1] === ' ' ? '☐' : '☑'}</span>`; first = tm[2]; }
          const rest = it.slice(1);
          return '<li>' + task + inline(first) + (rest.length ? render(rest) : '') + '</li>';
        }).join('') + `</${tag}>`;
        continue;
      }
      const buf = [];
      while (i < lines.length && lines[i].trim() && !(buf.length && isStart(lines[i])) &&
        !(lines[i].includes('|') && RE_TSEP.test(lines[i + 1] || ''))) buf.push(lines[i++]);
      if (!buf.length) buf.push(lines[i++]);
      out += '<p>' + buf.map(x => inline(x.trim())).join('<br>') + '</p>';
    }
    return out;
  }
  return render(src.split('\n'));
}

/* ------------------------------------------------------------------ state */
const S = {
  models: [], ollama: {}, servers: [], folders: [],
  chats: [], chat: null, model: null, settings: {},
  streaming: null, attachments: [], pulls: {}, modalTab: 'installed', pickerIndex: -1, drawerTab: 'chat', env: {}, panel: null,
};
const PRESETS = [
  { name: 'Assistant', text: 'You are a helpful assistant.' },
  { name: 'Concise', text: 'Answer as briefly as possible. No filler, no preamble.' },
  { name: 'Coder', text: 'You are an expert programmer. Give working code first, then a short explanation. Use Markdown code blocks with a language tag.' },
  { name: 'Tutor', text: 'You are a patient tutor. Explain step by step with small examples, then check understanding with one short question.' },
  { name: 'Writer', text: 'You are an imaginative writer. Use vivid, original language and avoid clichés.' },
  { name: 'Deutsch', text: 'Du bist ein hilfreicher Assistent. Antworte immer auf Deutsch.' },
  { name: 'Français', text: 'Tu es un assistant utile. Réponds toujours en français.' },
];
const KEEP = [['5m', '5 min'], ['30m', '30 min'], ['2h', '2 h'], ['-1', 'Always'], ['0', 'Unload']];
const CTX = [2048, 4096, 8192, 16384, 32768, 65536, 131072];
const SUGGESTIONS = [
  { icon: 'bulb', title: 'Explain something', text: 'How do transformers in AI work? Explain it like I am 15.' },
  { icon: 'code', title: 'Write code', text: 'Write a Python script that renames all photos in a folder by the date they were taken.' },
  { icon: 'monitor', title: 'Build a website', text: 'Build a single-file HTML page (CSS and JavaScript inside) with a glowing animated clock on a dark background.' },
  { icon: 'globe', title: 'Translate', text: 'Translate into German and French: "The servers are down, but the coffee is still hot."' },
];
const LIBRARY = [
  { name: 'qwen3:4b', desc: 'Small and smart, can think', size: '2.6 GB' },
  { name: 'qwen3:8b', desc: 'Strong all-rounder with thinking', size: '5.2 GB' },
  { name: 'gemma3:4b', desc: 'Google, understands images', size: '3.3 GB' },
  { name: 'llama3.2:3b', desc: 'Meta, very fast chat', size: '2.0 GB' },
  { name: 'deepseek-r1:8b', desc: 'Step-by-step reasoning', size: '5.2 GB' },
  { name: 'qwen2.5-coder:7b', desc: 'Made for programming', size: '4.7 GB' },
  { name: 'mistral:7b', desc: 'Classic, reliable all-rounder', size: '4.4 GB' },
  { name: 'phi4-mini', desc: 'Microsoft, compact and quick', size: '2.5 GB' },
  { name: 'llava:7b', desc: 'Describes images and photos', size: '4.7 GB' },
  { name: 'gemma3:12b', desc: 'Bigger Gemma with vision (part runs on CPU with 8 GB VRAM)', size: '8.1 GB' },
];

/* ----------------------------------------------------------------- models */
const findModel = id => S.models.find(m => m.id === id);
const hasCap = (m, c) => !!(m && (m.caps || []).includes(c));

async function loadModels(quiet = false) {
  let d;
  try { d = await api('models'); }
  catch (e) { if (!quiet) toast('Could not scan models: ' + e.message, 'err'); return; }
  Object.assign(S, { models: d.models, ollama: d.ollama, servers: d.servers, folders: d.folders });
  if (S.model) S.model = findModel(S.model.id) || S.model;
  if (!S.model || !S.model.chattable) {
    const saved = findModel(S.settings.model);
    const pick = (saved && saved.chattable) ? saved : S.models.find(m => m.chattable && hasCap(m, 'completion')) || S.models.find(m => m.chattable);
    if (pick) S.model = pick;
  }
  updateModelUI(); updateStatus();
  if (!$('#picker').hidden) renderPicker();
  if (!$('#modal').hidden && S.modalTab !== 'download') renderModal(); else updateModalCounts();
  if (S.chat && !S.chat.messages.length) renderThread();
}

function selectModel(m, silent) {
  if (!m) return;
  if (!m.chattable) {
    if (m.backend === 'ollama' && !S.ollama.running) { startOllama(); return; }
    toast(m.reason || 'This model cannot chat right now.', 'err'); return;
  }
  S.model = m; S.settings.model = m.id; saveSettings();
  updateModelUI(); closePicker();
  if (S.chat && !S.chat.messages.length) renderThread();
  if (!silent) $('#input').focus();
}

function badges(m, compact) {
  const b = [];
  if (m.loaded) b.push(`<span class="badge b-live">${icon('memory', 11)}${compact ? '' : 'In memory'}</span>`);
  if (hasCap(m, 'vision')) b.push(`<span class="badge b-vision" title="Understands images">${icon('eye', 11)}${compact ? '' : 'Vision'}</span>`);
  if (hasCap(m, 'thinking')) b.push(`<span class="badge b-think" title="Can think before it answers">${icon('brain', 11)}${compact ? '' : 'Thinking'}</span>`);
  if (hasCap(m, 'tools')) b.push(`<span class="badge b-tools" title="Supports tool calls">${icon('tool', 11)}${compact ? '' : 'Tools'}</span>`);
  if (hasCap(m, 'embedding')) b.push('<span class="badge b-embed">Embedding</span>');
  return b.join('');
}
const metaLine = m => [m.params, m.quant, fmtSize(m.size), m.ctx ? fmtCtx(m.ctx) + ' ctx' : ''].filter(Boolean).join(' · ');

function updateModelUI() {
  const m = S.model;
  $('#modelName').textContent = m ? m.name : 'Choose a model';
  $('#modelPill .dot').className = 'dot ' + (!m ? '' : m.loaded ? 'live' : m.chattable ? 'ready' : '');
  $('#modelCaps').innerHTML = m ? [hasCap(m, 'vision') ? icon('eye', 14) : '', hasCap(m, 'thinking') ? icon('brain', 14) : ''].join('') : '';
  const think = $('#thinkChip');
  think.classList.toggle('hidden', !hasCap(m, 'thinking'));
  think.classList.toggle('on', !!S.settings.think);
  $('#attachBtn').title = hasCap(m, 'vision') ? 'Attach images or code files' : 'Attach code or text files (this model cannot see images)';
  updateCtx();
  $('#input').placeholder = m ? `Message ${m.name}…` : 'Pick a model to start…';
  updateSendBtn();
}

function updateStatus() {
  const o = S.ollama, online = S.servers.filter(s => s.online);
  const n = S.models.filter(m => m.chattable).length;
  let text, cls;
  if (o.running) { text = `Ollama ${o.version ? 'v' + o.version : ''} · ${n} ready`; cls = 'live'; }
  else if (online.length) { text = `${online.map(s => s.name).join(', ')} · ${n} ready`; cls = 'live'; }
  else if (o.installed) { text = 'Ollama is stopped'; cls = 'warn'; }
  else { text = 'No AI server found'; cls = 'err'; }
  if (o.running && online.length) text = `Ollama + ${online.length} server${online.length > 1 ? 's' : ''} · ${n} ready`;
  $('#statusText').textContent = text;
  $('#statusPill .dot').className = 'dot ' + cls;
}

async function startOllama() {
  toast('Starting Ollama…');
  try { await api('ollama/start', {}); toast('Ollama is running', 'ok'); }
  catch (e) { toast(e.message, 'err'); }
  await loadModels();
}

/* ----------------------------------------------------------------- picker */
function groupModels(list) {
  const order = ['Ollama', ...S.servers.map(s => s.name), 'GGUF files'];
  const map = new Map();
  for (const src of order) { const it = list.filter(m => m.source === src); if (it.length) map.set(src, it); }
  for (const m of list) if (!order.includes(m.source)) { if (!map.has(m.source)) map.set(m.source, []); map.get(m.source).push(m); }
  return map;
}
function openPicker() {
  const r = $('#modelPill').getBoundingClientRect(), p = $('#picker');
  p.style.left = Math.max(10, r.left) + 'px'; p.style.top = (r.bottom + 8) + 'px';
  p.hidden = false; $('#modelPill').classList.add('open');
  $('#pkSearch').value = ''; S.pickerIndex = -1; renderPicker();
  setTimeout(() => $('#pkSearch').focus(), 20);
}
function closePicker() { $('#picker').hidden = true; $('#modelPill').classList.remove('open'); }
function renderPicker() {
  const q = $('#pkSearch').value.trim().toLowerCase();
  const list = S.models.filter(m => !q || m.name.toLowerCase().includes(q) || (m.source || '').toLowerCase().includes(q));
  let h = '';
  if (!S.ollama.running && S.ollama.installed && !list.some(m => m.source === 'Ollama') && !q)
    h += `<div class="pk-group"><span>Ollama</span><button class="btn small primary" data-act="start-ollama">${icon('power', 13)}Start</button></div>`;
  for (const [src, items] of groupModels(list)) {
    let extra = '';
    if (src === 'Ollama') extra = S.ollama.running ? '<span class="g-status"><i class="dot live"></i>running</span>'
      : `<button class="btn small primary" data-act="start-ollama">${icon('power', 13)}Start Ollama</button>`;
    else if (src === 'GGUF files') extra = '<span class="g-status">need a server</span>';
    else extra = '<span class="g-status"><i class="dot live"></i>online</span>';
    h += `<div class="pk-group"><span>${esc(src)}</span>${extra}</div>`;
    for (const m of items) {
      const active = S.model && S.model.id === m.id;
      h += `<button class="pk-item ${m.chattable ? '' : 'off'} ${active ? 'active' : ''}" data-id="${esc(m.id)}" title="${esc(m.reason || m.name)}">
        <i class="dot ${m.loaded ? 'live' : m.chattable ? 'ready' : ''}"></i>
        <div class="pk-main"><div class="pk-name">${esc(m.name)}</div><div class="pk-meta">${esc(metaLine(m) || m.reason || '')}</div></div>
        <div class="pk-badges">${badges(m, true)}</div>${active ? `<span class="pk-check">${icon('check', 16)}</span>` : ''}</button>`;
    }
  }
  if (!list.length) h += `<div class="pk-empty">${q ? 'No model matches “' + esc(q) + '”.' : 'No models installed yet.'}
    <button class="btn small primary" data-act="manage-download">${icon('download', 14)}Download a model</button></div>`;
  $('#pkList').innerHTML = h;
  S.pickerIndex = -1;
}
function pickerKey(e) {
  const items = $$('#pkList .pk-item:not(.off)');
  if (!items.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    S.pickerIndex = (S.pickerIndex + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
    items.forEach((el, i) => el.classList.toggle('kb', i === S.pickerIndex));
    items[S.pickerIndex].scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') {
    e.preventDefault();
    const el = items[Math.max(0, S.pickerIndex)];
    selectModel(findModel(el.dataset.id));
  }
}

/* ------------------------------------------------------------------ chats */
async function loadChats() {
  try { S.chats = (await api('chats')).chats; } catch { S.chats = []; }
  renderChatList();
}
function newChat() {
  S.chat = { id: uid(), title: '', created: Date.now(), updated: Date.now(), messages: [] };
  renderThread(); renderChatList(); chatSwitched();
  $('#input').focus();
}
function chatSwitched() {
  if (!S.settings || !$('#webBtn')) return;
  updateToolUI();
  if (S.panel && S.panel.kind === 'ws' && !$('#panel').hidden && S.panel.chatId !== S.chat.id) {
    if (S.chat.code) openWorkspace(S.chat); else closePanel();
  }
}
async function openChat(id) {
  if (S.chat && S.chat.id === id) return;
  let c;
  if (S.streaming && S.streaming.chat.id === id) c = S.streaming.chat;
  else { try { c = await api('chats/' + id); } catch (e) { toast('Could not open chat', 'err'); return; } }
  S.chat = c;
  const m = findModel(c.model_id);
  if (m && m.chattable) selectModel(m, true);
  renderThread(true); renderChatList(); chatSwitched();
}
function chatMeta(c) {
  const last = [...c.messages].reverse().find(m => m.content);
  return { id: c.id, title: c.title || 'New chat', updated: c.updated, model_name: c.model_name, count: c.messages.length, preview: last ? last.content.slice(0, 140) : '', pinned: !!c.pinned };
}
async function saveChat(c) {
  if (!c.messages.length) return;
  c.updated = Date.now();
  const { _q, _auto, ...rest } = c;
  const clean = { ...rest, messages: c.messages.map(({ pending, _thinkOpen, _webOpen, ...m }) => m) };
  try { await api('chats/save', { chat: clean }); } catch (e) { toast('Could not save chat: ' + e.message, 'err'); }
  const i = S.chats.findIndex(x => x.id === c.id);
  if (i >= 0) S.chats[i] = chatMeta(c); else S.chats.unshift(chatMeta(c));
  renderChatList();
}
function renderChatList() {
  const q = $('#chatSearch').value.trim().toLowerCase();
  const items = S.chats.filter(c => !q || (c.title || '').toLowerCase().includes(q) || (c.preview || '').toLowerCase().includes(q))
    .sort((a, b) => b.updated - a.updated);
  const el = $('#chatList');
  if (!items.length) { el.innerHTML = `<div class="cl-empty">${q ? 'No chats found' : 'Your chats will show up here'}</div>`; return; }
  const now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime(), day = 864e5;
  const bucket = t => t >= today ? 'Today' : t >= today - day ? 'Yesterday' : t >= today - 7 * day ? 'Previous 7 days' : t >= today - 30 * day ? 'Previous 30 days' : 'Older';
  let h = '', last = null;
  for (const c of items) {
    const b = bucket(c.updated);
    if (b !== last) { h += `<div class="cl-group">${b}</div>`; last = b; }
    const live = S.streaming && S.streaming.chat.id === c.id;
    h += `<div class="ci ${S.chat && S.chat.id === c.id ? 'active' : ''}" data-id="${esc(c.id)}" title="${esc(c.preview)}">
      <span class="ci-title">${esc(c.title || 'New chat')}</span>${live ? '<i class="dot live pulse"></i>' : ''}
      <span class="ci-acts"><button data-act="rename" title="Rename">${icon('edit', 14)}</button><button data-act="delete" title="Delete">${icon('trash', 14)}</button></span></div>`;
  }
  el.innerHTML = h;
}
function renameChat(el, id) {
  const c = S.chats.find(x => x.id === id); if (!c) return;
  const title = el.querySelector('.ci-title');
  const inp = document.createElement('input'); inp.value = c.title;
  title.replaceWith(inp); inp.focus(); inp.select();
  let done = false;
  const finish = async ok => {
    if (done) return; done = true;
    const v = inp.value.trim();
    if (ok && v && v !== c.title) {
      c.title = v; if (S.chat && S.chat.id === id) S.chat.title = v;
      if (S.streaming && S.streaming.chat.id === id) S.streaming.chat.title = v;
      await api('chats/rename', { id, title: v }).catch(() => {});
    }
    renderChatList();
  };
  inp.onkeydown = e => { if (e.key === 'Enter') finish(true); if (e.key === 'Escape') { e.stopPropagation(); finish(false); } };
  inp.onblur = () => finish(true);
}
async function deleteChat(id) {
  const c = S.chats.find(x => x.id === id);
  if (!await confirmDialog({ title: 'Delete chat?', text: `“${c ? c.title : 'This chat'}” will be deleted for good.` })) return;
  if (S.streaming && S.streaming.chat.id === id) S.streaming.ctrl.abort();
  await api('chats/delete', { id }).catch(() => {});
  S.chats = S.chats.filter(x => x.id !== id);
  if (S.chat && S.chat.id === id) newChat(); else renderChatList();
  toast('Chat deleted');
}
function makeTitle(text) {
  const t = text.replace(/\s+/g, ' ').trim();
  return t.length > 48 ? t.slice(0, 46).replace(/\s\S*$/, '') + '…' : t || 'Image chat';
}

/* ----------------------------------------------------------------- thread */
const scroller = () => $('#scroller');
const nearBottom = () => { const s = scroller(); return s.scrollHeight - s.scrollTop - s.clientHeight < 120; };
const toBottom = (smooth) => { const s = scroller(); s.scrollTo({ top: s.scrollHeight, behavior: smooth ? 'smooth' : 'auto' }); };

function emptyState() {
  const m = S.model, o = S.ollama;
  let sub, cta = '';
  if (m) sub = `<i class="dot ${m.loaded ? 'live' : 'ready'}"></i>Chatting with <b>${esc(m.name)}</b>${m.params ? ' · ' + esc(m.params) : ''}${m.loaded ? ' · in memory' : ''}`;
  else if (o.installed && !o.running) { sub = 'Ollama is installed but not running.'; cta = `<button class="btn primary" data-act="start-ollama">${icon('power', 15)}Start Ollama</button>`; }
  else if (!S.models.length) { sub = 'No local models found yet.'; cta = `<button class="btn primary" data-act="manage-download">${icon('download', 15)}Download a model</button>`; }
  else { sub = 'Pick a model to start.'; cta = `<button class="btn primary" data-act="open-picker">${icon('cube', 15)}Choose a model</button>`; }
  const hour = new Date().getHours();
  const greet = hour < 5 ? 'Up late?' : hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const still = S.introFor === (S.chat && S.chat.id);
  const who = ((S.settings && S.settings.style && S.settings.style.name) || '').trim().slice(0, 30);
  return `<div class="empty${still ? ' still' : ''}"><div class="e-orb"><div class="e-orb-core">${icon('spark', 30)}</div></div>
    <h1>${greet}${who ? ', ' + esc(who) : ''}. What should we make?</h1><div class="sub">${sub}</div>
    ${cta ? `<div class="empty-cta">${cta}</div>` : `<div class="cards">${SUGGESTIONS.map((s, i) =>
      `<button class="card-s" data-sugg="${i}"><span class="ic">${icon(s.icon, 17)}</span><span><b>${s.title}</b><small>${esc(s.text)}</small></span></button>`).join('')}</div>`}</div>`;
}

function renderThread(jump) {
  const t = $('#thread');
  if (!S.chat || !S.chat.messages.length) {
    const html = emptyState();
    if (html !== S.emptyHtml || !t.querySelector('.empty')) t.innerHTML = html;   // no re-render, no replayed intro
    S.emptyHtml = html.replace('class="empty"', 'class="empty still"');
    S.introFor = S.chat && S.chat.id;
    updateCtx();
    return;
  }
  S.emptyHtml = null;
  t.innerHTML = '';
  S.chat.messages.forEach(m => t.append(buildMsg(m)));
  updateCtx();
  if (jump !== false) requestAnimationFrame(() => toBottom(false));
}

function buildMsg(m) {
  const el = document.createElement('div');
  el.dataset.id = m.id;
  if (m.role === 'user' && m.auto) {
    el.className = 'msg note';
    el.innerHTML = `<details class="note-box"><summary>${icon('tool', 14)}<span>Workspace report sent back to the model</span>${icon('chev', 14)}</summary><pre></pre></details>`;
    el.querySelector('pre').textContent = m.content;
  } else if (m.role === 'user') {
    el.className = 'msg user';
    el.innerHTML = webTag(m) + (m.images && m.images.length ? `<div class="u-imgs">${m.images.map(s => `<img src="${s}" data-zoom>`).join('')}</div>` : '') +
      (m.files && m.files.length ? `<div class="u-files">${m.files.map((f, i) => fileChip(f, `data-ufile="${i}"`)).join('')}</div>` : '') +
      `<div class="bubble"></div><div class="u-acts"><button data-act="copy" title="Copy">${icon('copy', 15)}</button><button data-act="edit" title="Edit and resend">${icon('edit', 15)}</button></div>`;
    el.querySelector('.bubble').textContent = m.content;
    el.querySelector('.bubble').hidden = !m.content;
  } else {
    el.className = 'msg assistant';
    el.innerHTML = `<div class="a-head"><span class="avatar">${icon('spark', 14)}</span><span class="a-name"></span></div>
      <div class="web-slot"></div>
      <div class="think" hidden><button class="think-head" data-act="think"><span class="think-ic">${icon('brain', 15)}</span><span class="think-label"></span><span class="chev">${icon('chev', 15)}</span></button>
        <div class="think-body"><div class="think-inner"><div class="think-text"></div></div></div></div>
      <div class="body md"></div><div class="src-slot"></div><div class="err-slot"></div>
      <div class="m-foot"><span class="stats"></span><span class="acts"><button data-act="copy" title="Copy">${icon('copy', 15)}</button><button data-act="regen" title="Regenerate">${icon('refresh', 15)}</button></span></div>`;
    el.querySelector('.a-name').textContent = m.model || 'Assistant';
    updateMsg(el, m);
  }
  return el;
}

function splitThink(m) {
  let t = m.thinking || '', c = m.content || '';
  const s = c.indexOf('<think>');
  if (s >= 0) {
    const e = c.indexOf('</think>', s);
    if (e >= 0) { t += c.slice(s + 7, e); c = c.slice(0, s) + c.slice(e + 8); }
    else { t += c.slice(s + 7); c = c.slice(0, s); }
  } else {
    const e = c.indexOf('</think>');           // some thinking models skip the opening tag
    if (e >= 0) { t += c.slice(0, e); c = c.slice(e + 8); }
  }
  return { t: t.trim() ? t.replace(/^\n+/, '') : '', c: c.replace(/^\s+/, '') };
}

function updateMsg(el, m) {
  const v = splitThink(m);
  const thinkingNow = !!(m.pending && v.t && !v.c);
  el.classList.toggle('pending', !!m.pending);

  const think = el.querySelector('.think');
  think.hidden = !v.t;
  if (v.t) {
    const open = m._thinkOpen !== undefined ? m._thinkOpen : thinkingNow;
    think.classList.toggle('open', open);
    el.querySelector('.think-label').innerHTML = thinkingNow ? '<span class="shimmer">Thinking…</span>'
      : m.thinkTime ? `Thought for ${fmtDur(m.thinkTime)}` : 'Thoughts';
    const tt = el.querySelector('.think-text');
    const stick = tt.scrollHeight - tt.scrollTop - tt.clientHeight < 30;
    tt.textContent = v.t;
    if (thinkingNow && stick) tt.scrollTop = tt.scrollHeight;
  }

  const ws = el.querySelector('.web-slot'), wh = webBoxHtml(m);
  if (ws._html !== wh) { ws._html = wh; ws.innerHTML = wh; }
  const ss = el.querySelector('.src-slot'), sh = sourcesHtml(m);
  if (ss._html !== sh) { ss._html = sh; ss.innerHTML = sh; }

  const body = el.querySelector('.body');
  const key = v.c + (m.pending ? '\u0002' : '') + (m.code ? '\u0003' + opsKey(m) : '') + (m.sources ? '\u0004' + m.sources.length : '');
  if (m.pending && !v.c && !v.t) { body.innerHTML = m.web && m.web.active ? '' : '<div class="typing"><i></i><i></i><i></i></div>'; body._key = null; }
  else if (body._key !== key) {           // unchanged text: keep the DOM (and any Run output in it)
    body._key = key;
    body.innerHTML = m.code ? renderCodeMsg(v.c, m) : md(v.c);
    if (m.sources) linkCites(body, m.sources);
    const lastCode = body.lastElementChild;
    if (m.pending && lastCode && lastCode.classList.contains('code')) { const cb = lastCode.querySelector('.code-body'); cb.scrollTop = cb.scrollHeight; }
    if (m.pending && v.c) {
      let target = body.lastElementChild;
      while (target && target.lastElementChild && /^(UL|OL|LI|BLOCKQUOTE|DIV|TABLE|TBODY|TR)$/.test(target.tagName) && !target.classList.contains('code')) target = target.lastElementChild;
      const caret = document.createElement('span'); caret.className = 'caret';
      if (!(target && target.closest('.op'))) (target && !target.classList.contains('code') && target.tagName !== 'HR' ? target : body).append(caret);
    }
  }

  el.querySelector('.err-slot').innerHTML = m.error
    ? `<div class="err-box">${icon('alert', 16)}<span>${esc(m.error)}</span><button class="btn small" data-act="regen">${icon('refresh', 13)}Retry</button></div>` : '';

  const st = m.stats || {}, parts = [];
  if (m.stopped) parts.push('Stopped');
  if (st.tokens) parts.push(`<b>${st.tokens}</b> tokens${st.estimated ? ' (approx.)' : ''}`);
  if (st.tps) parts.push(`<b>${st.tps.toFixed(1)}</b> tok/s`);
  if (st.ttft != null) parts.push(`${fmtDur(st.ttft)} to first token`);
  if (st.load > 0.5) parts.push(`${fmtDur(st.load)} loading`);
  el.querySelector('.stats').innerHTML = parts.join(' · ');
  const isLast = S.chat && S.chat.messages[S.chat.messages.length - 1] === m;
  el.querySelector('.acts [data-act=regen]').hidden = !isLast || !!S.streaming;
}

function msgEl(m) { return $(`#thread [data-id="${m.id}"]`); }

/* --------------------------------------------------------------- generate */
async function send(text, images, files = [], web = null) {
  if (S.streaming) return;
  if (!S.model || !S.model.chattable) { toast('Pick a model first', 'err'); openPicker(); return; }
  const chat = S.chat;
  chat._auto = 0;
  chat.messages.push({ id: uid(), role: 'user', content: text, images: images.length ? images : undefined, files: files.length ? files : undefined, web: web || undefined });
  if (!chat.title) chat.title = makeTitle(text || (files[0] && files[0].name) || '');
  if (chat.messages.length === 1) $('#thread').innerHTML = '';
  const el = buildMsg(chat.messages[chat.messages.length - 1]);
  el.classList.add('enter');
  $('#thread').append(el);
  await generate();
}

async function generate() {
  const chat = S.chat, model = S.model;
  if (!model || !model.chattable) { toast('Pick a model first', 'err'); return; }
  const msg = { id: uid(), role: 'assistant', content: '', thinking: '', model: model.name, pending: true, code: chat.code || undefined };
  const history = chat.messages.filter(m => !m.kind && !m.local && (!m.error || m.role === 'user')).map(m => ({   // images, plans, dice stay out
    role: m.role, content: m.role === 'assistant' ? (m.code ? compressOps(splitThink(m).c) : splitThink(m).c) : withFiles(m), images: m.images || [],
  }));
  const asker = chat.messages[chat.messages.length - 1];
  chat.messages.push(msg);
  chat.model_id = model.id; chat.model_name = model.name;
  if (S.chat === chat) { $$('#thread .acts [data-act=regen]').forEach(b => b.hidden = true); const el = buildMsg(msg); el.classList.add('enter'); $('#thread').append(el); toBottom(true); }

  const ctrl = new AbortController();
  S.streaming = { ctrl, chat, msg };
  updateSendBtn(); renderChatList();

  let frame = null, thinkStart = null, thinkEnd = null;
  const paint = () => {
    frame = null;
    if (S.chat !== chat) return;
    const el = msgEl(msg); if (!el) return;
    const stick = nearBottom();
    updateMsg(el, msg);
    if (stick) toBottom(false);
    if (msg.code) wsLive(chat, msg);
  };
  const schedule = () => { if (!frame) frame = requestAnimationFrame(paint); };

  const s = S.settings;
  try {
    let system = (s.system || '') + (typeof extraSystem === 'function' ? extraSystem(chat, msg) : '');   // style + plan (extras.js)
    if (asker && asker.role === 'user' && asker.web && !asker.auto) {      // web search before the answer
      if (!asker.ctx) await research(chat, asker, msg, ctrl.signal, model, schedule);
      else { msg.web = { mode: asker.web, steps: asker.webSteps || [], active: false }; msg.sources = asker.sources; }
      if (asker.ctx) system += webRules() + asker.ctx;
    }
    if (chat.code) system += await codeSystem(chat, model);
    const resp = await api('chat', {
      model_id: model.id, messages: history, system,
      options: model.backend === 'ollama' ? { temperature: +s.temperature, top_p: +s.top_p, num_ctx: +s.num_ctx } : { temperature: +s.temperature, top_p: +s.top_p },
      think: hasCap(model, 'thinking') ? !!s.think : null, keep_alive: s.keep_alive,
    }, { stream: true, signal: ctrl.signal });
    for await (const ev of ndjson(resp)) {
      if (ev.type === 'thinking') { thinkStart ??= performance.now(); msg.thinking += ev.text; }
      else if (ev.type === 'content') {
        msg.content += ev.text;
        if (thinkStart && !thinkEnd && splitThink(msg).c) thinkEnd = performance.now();
        if (!thinkStart && msg.content.includes('<think>')) thinkStart = performance.now();
        if (msg.code) syncOps(chat, msg);
      }
      else if (ev.type === 'done') msg.stats = ev.stats;
      else if (ev.type === 'error') msg.error = ev.message || ev.error;
      schedule();
    }
  } catch (e) {
    if (e.name === 'AbortError') msg.stopped = true;
    else msg.error = String(e.message || e);
  }
  if (thinkStart) msg.thinkTime = ((thinkEnd || performance.now()) - thinkStart) / 1000;
  if (!msg.content && !msg.thinking && !msg.error && !msg.stopped) msg.error = 'The model returned an empty answer.';
  if (msg.web) msg.web.active = false;
  delete msg.pending;
  if (msg._thinkOpen === undefined) msg._thinkOpen = false;
  if (msg.code && !msg.stopped && !msg.error) fenceToOps(chat, msg);       // code pasted in the chat goes into the file
  if (msg.code && !msg.stopped) { syncOps(chat, msg, true); await (chat._q || Promise.resolve()); }
  if (msg.code) { const D = wsData(chat.id); D.live = null; wsRender(chat.id); }
  S.streaming = null;
  if (frame) cancelAnimationFrame(frame);
  paint();
  if (S.chat === chat) $$('#thread .msg.assistant').forEach(el => { const m = chat.messages.find(x => x.id === el.dataset.id); if (m) updateMsg(el, m); });
  updateSendBtn(); updateCtx();
  await saveChat(chat);
  if (model.backend === 'ollama') setTimeout(() => loadModels(true), 400);   // refresh "in memory"
  // code mode: failed edits or runs go back to the model, at most twice per message
  const report = msg.code && !msg.stopped && !msg.error ? codeFeedback(msg) : null;
  if (report && (chat._auto || 0) < 2 && S.chat === chat && S.model === model) {
    chat._auto = (chat._auto || 0) + 1;
    const note = { id: uid(), role: 'user', auto: true, content: report };
    chat.messages.push(note);
    const el = buildMsg(note); el.classList.add('enter'); $('#thread').append(el); toBottom(true);
    await generate();
  }
}

function stop() { if (S.streaming) S.streaming.ctrl.abort(); }

async function regenerate() {
  if (S.streaming) return;
  const msgs = S.chat.messages;
  if (msgs.length && msgs[msgs.length - 1].role === 'assistant') {
    const last = msgs.pop(); const el = msgEl(last); if (el) el.remove();
  }
  if (!msgs.length) return;
  await generate();
}

function startEdit(el, m) {
  if (el.classList.contains('editing')) return;
  el.classList.add('editing');
  const b = el.querySelector('.bubble');
  b.innerHTML = `<textarea class="edit-ta"></textarea><div class="edit-bar"><button class="btn ghost small" data-act="edit-cancel">Cancel</button><button class="btn primary small" data-act="edit-save">Save & send</button></div>`;
  const ta = b.querySelector('textarea'); ta.value = m.content; autosize(ta, 400); ta.focus();
  ta.oninput = () => autosize(ta, 400);
  ta.onkeydown = e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); saveEdit(el, m); }
    if (e.key === 'Escape') { e.stopPropagation(); renderThread(false); }
  };
}
async function saveEdit(el, m) {
  const v = el.querySelector('.edit-ta').value.trim();
  if (!v) return;
  if (S.streaming) { stop(); await new Promise(r => setTimeout(r, 80)); }
  const i = S.chat.messages.indexOf(m);
  if (m.content !== v) { delete m.ctx; delete m.sources; delete m.webSteps; }   // new question: search again
  m.content = v;
  S.chat.messages = S.chat.messages.slice(0, i + 1);
  renderThread(false);
  await generate();
}

/* --------------------------------------------------------------- composer */
function autosize(ta, max = 240) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, max) + 'px'; }
function updateSendBtn() {
  const b = $('#sendBtn');
  if (S.streaming) { b.className = 'send-btn stop'; b.title = 'Stop (Esc)'; return; }
  const ready = ($('#input').value.trim() || S.attachments.length) && S.model && S.model.chattable;
  b.className = 'send-btn' + (ready ? '' : ' disabled'); b.title = 'Send (Enter)';
}
async function submit() {
  if (S.streaming) { stop(); return; }
  const ta = $('#input');
  let text = ta.value.trim();
  if (!text && !S.attachments.length) return;
  if (!S.model || !S.model.chattable) { toast('Pick a model first', 'err'); openPicker(); return; }
  let web = S.deepNext ? 'deep' : S.settings.web === 'search' ? 'search' : null;
  const pre = text.match(/^\/(search|deep)\b\s*/i);
  if (pre) { web = pre[1].toLowerCase(); text = text.slice(pre[0].length).trim(); }
  if (web && !text) { toast('Write what to look up after /' + web, 'err'); return; }
  if (web && !await webAllowed()) return;
  const imgs = S.attachments.filter(a => a.url).map(a => a.url);
  const files = S.attachments.filter(a => a.text != null).map(a => ({ name: a.name, text: a.text }));
  ta.value = ''; autosize(ta); S.attachments = []; renderAttachments(); closeSlash();
  if (S.deepNext) { S.deepNext = false; updateToolUI(); }
  send(text, imgs, files, web);
}
function readImage(file) {
  return new Promise((res, rej) => {
    const fr = new FileReader();
    fr.onerror = rej;
    fr.onload = () => {
      const img = new Image();
      img.onload = () => {
        const max = 1536, k = Math.min(1, max / Math.max(img.width, img.height));
        if (k === 1 && file.size < 1.5e6) return res(fr.result);
        const c = document.createElement('canvas'); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        res(c.toDataURL('image/jpeg', .9));
      };
      img.onerror = rej; img.src = fr.result;
    };
    fr.readAsDataURL(file);
  });
}
const TEXT_EXT = /\.(txt|md|markdown|py|pyw|ipynb|js|mjs|cjs|ts|tsx|jsx|json|jsonc|html?|css|scss|sass|less|c|h|cpp|hpp|cc|cs|java|kt|kts|go|rs|rb|php|lua|luau|sh|bash|zsh|ps1|psm1|bat|cmd|sql|xml|svg|yaml|yml|toml|ini|cfg|conf|csv|tsv|log|gd|gdshader|shader|glsl|hlsl|swift|dart|r|vue|svelte|astro|env|gitignore|dockerfile|makefile|gradle|tex|srt|vb|fs|zig|nim|ex|exs|erl|hs|clj|scala|pl|asm|s|cmake|mcmeta|properties)$/i;
const EXT_LANG = { py: 'python', pyw: 'python', js: 'javascript', mjs: 'javascript', cjs: 'javascript', ts: 'typescript', tsx: 'tsx', jsx: 'jsx',
  htm: 'html', md: 'markdown', yml: 'yaml', ps1: 'powershell', psm1: 'powershell', sh: 'bash', rs: 'rust', rb: 'ruby', cs: 'csharp', kt: 'kotlin', gd: 'gdscript', h: 'c', hpp: 'cpp', cc: 'cpp' };
const extOf = name => (name.match(/\.([\w]+)$/) || [, ''])[1].toLowerCase();
const langOfFile = name => EXT_LANG[extOf(name)] || extOf(name) || 'text';
function withFiles(m) {
  if (!m.files || !m.files.length) return m.content;
  const blocks = m.files.map(f => `File: ${f.name}\n\`\`\`${langOfFile(f.name)}\n${f.text}\n\`\`\``).join('\n\n');
  return (m.content ? m.content + '\n\n' : '') + blocks;
}
function fileChip(f, attrs = '') {
  const lines = f.text.split('\n').length;
  return `<button class="file-chip" ${attrs} title="Open ${esc(f.name)}">${icon('file', 15)}<span>${esc(f.name)}</span><small>${lines} line${lines === 1 ? '' : 's'}</small></button>`;
}
async function addFiles(files) {
  files = [...files];
  const imgs = files.filter(f => f.type.startsWith('image/') && !/svg/.test(f.type));
  const texts = files.filter(f => !imgs.includes(f) && (TEXT_EXT.test(f.name) || f.type.startsWith('text/') || /json|xml|javascript/.test(f.type)));
  const skipped = files.length - imgs.length - texts.length;
  if (imgs.length && !hasCap(S.model, 'vision')) toast(`${S.model ? S.model.name : 'This model'} cannot see images. Pick a model with the eye badge.`, 'err', 4500);
  for (const f of imgs) {
    try { S.attachments.push({ id: uid(), url: await readImage(f) }); } catch { toast('Could not read ' + f.name, 'err'); }
  }
  for (const f of texts) {
    if (f.size > 400 * 1024) { toast(`${f.name} is too big (max 400 KB)`, 'err'); continue; }
    try { S.attachments.push({ id: uid(), name: f.name, text: await f.text() }); } catch { toast('Could not read ' + f.name, 'err'); }
  }
  if (skipped) toast(`${skipped} file${skipped > 1 ? 's' : ''} skipped: only images and text/code files work`, 'err');
  renderAttachments(); updateSendBtn(); $('#input').focus();
}
function renderAttachments() {
  $('#attachments').innerHTML = S.attachments.map(a => a.url
    ? `<div class="att"><img src="${a.url}"><button data-rm="${a.id}" title="Remove">${icon('x', 12)}</button></div>`
    : `<div class="att-file">${fileChip(a, `data-afile="${a.id}"`)}<button data-rm="${a.id}" title="Remove">${icon('x', 12)}</button></div>`).join('');
  updateCtx();
}

/* ------------------------------------------------------- context meter */
function estTokens(s) { return Math.ceil((s || '').length / 3.6); }
function updateCtx() {
  const el = $('#ctxMeter'), m = S.model;
  const limit = m ? (m.backend === 'ollama' ? +S.settings.num_ctx || m.ctx : m.ctx) : null;
  if (!limit || !S.chat) { el.hidden = true; return; }
  let n = estTokens(S.settings.system) + estTokens($('#input').value);
  for (const x of S.chat.messages) n += estTokens(x.role === 'assistant' ? splitThink(x).c : withFiles(x)) + (x.images ? x.images.length * 600 : 0);
  for (const a of S.attachments) n += a.url ? 600 : estTokens(a.text);
  const p = Math.min(1, n / limit);
  el.hidden = n < 1;
  el.className = 'ctx' + (p > .9 ? ' full' : p > .7 ? ' high' : '');
  el.style.setProperty('--p', (p * 100).toFixed(1) + '%');
  el.querySelector('span').textContent = `${fmtCtx(n)} / ${fmtCtx(limit)}`;
  el.title = `About ${n.toLocaleString()} of ${limit.toLocaleString()} tokens of context used.` + (p > .9 ? ' The model will start forgetting the start of this chat. Start a new chat or raise the context length.' : '');
}

/* -------------------------------------------------------- slash commands */
const COMMANDS = [
  { cmd: 'search', desc: 'Look this up on the web first', text: '/search ' },
  { cmd: 'deep', desc: 'Deep research: browse several pages, watch the browser', text: '/deep ' },
  { cmd: 'website', desc: 'Single-file web page you can preview', text: 'Build a complete single-file HTML page (CSS and JavaScript inside one ```html block) for: ' },
  { cmd: 'game', desc: 'Small browser game in one HTML file', text: 'Make a small, polished, playable browser game in one HTML file (one ```html block, no external files): ' },
  { cmd: 'explain', desc: 'Explain code step by step', text: 'Explain this code step by step, simply:\n\n' },
  { cmd: 'fix', desc: 'Find and fix bugs', text: 'Find and fix the bugs in this code. Show the full corrected code, then list what you changed:\n\n' },
  { cmd: 'refactor', desc: 'Cleaner code, same behavior', text: 'Refactor this code to be cleaner and easier to read without changing what it does:\n\n' },
  { cmd: 'optimize', desc: 'Make it faster', text: 'Make this code faster. Show the new code and explain why it is faster:\n\n' },
  { cmd: 'tests', desc: 'Write unit tests', text: 'Write unit tests for this code. Cover normal cases and edge cases:\n\n' },
  { cmd: 'comment', desc: 'Add comments and docstrings', text: 'Add clear comments and docstrings to this code. Do not change the logic:\n\n' },
  { cmd: 'convert', desc: 'Port code to another language', text: 'Convert this code to LANGUAGE, using that language\'s usual style:\n\n' },
  { cmd: 'script', desc: 'Python script that does a task', text: 'Write a Python script (standard library only if possible) that: ' },
  { cmd: 'regex', desc: 'Build a regular expression', text: 'Write a regular expression that matches: \n\nShow examples that match and examples that do not.' },
  { cmd: 'sql', desc: 'Write an SQL query', text: 'Write an SQL query that: ' },
  { cmd: 'commit', desc: 'Commit message for a diff', text: 'Write a short Conventional Commits message for this diff:\n\n' },
  { cmd: 'review', desc: 'Code review', text: 'Review this code like a senior developer. List bugs, risks and improvements, most important first:\n\n' },
  { cmd: 'summarize', desc: 'Summarize text', text: 'Summarize this in 5 short bullet points:\n\n' },
  { cmd: 'translate', desc: 'Translate text', text: 'Translate into English (keep the tone):\n\n' },
];
let slashIndex = 0;
function slashMatches() {
  const v = $('#input').value, m = v.match(/^\/(\w*)$/);
  if (!m && !S.slashForced) return null;
  const q = m ? m[1].toLowerCase() : '';
  return COMMANDS.filter(c => c.cmd.startsWith(q) || (q.length > 1 && c.desc.toLowerCase().includes(q)));
}
function renderSlash() {
  const list = slashMatches(), el = $('#slash');
  if (!list || !list.length) { el.hidden = true; return; }
  slashIndex = Math.min(slashIndex, list.length - 1);
  el.innerHTML = `<div class="sl-head">Prompt commands <span>↑↓ choose · Enter use · Esc close</span></div>` +
    list.map((c, i) => `<button class="sl-item ${i === slashIndex ? 'kb' : ''}" data-slash="${c.cmd}"><b>/${c.cmd}</b><span>${esc(c.desc)}</span></button>`).join('');
  el.hidden = false;
  const k = el.querySelector('.kb'); if (k) k.scrollIntoView({ block: 'nearest' });
}
function closeSlash() { S.slashForced = false; $('#slash').hidden = true; }
function applySlash(cmd) {
  const c = COMMANDS.find(x => x.cmd === cmd); if (!c) return;
  const ta = $('#input'); ta.value = c.text; closeSlash(); autosize(ta); updateSendBtn(); ta.focus();
  const sel = c.text.indexOf('LANGUAGE');
  if (sel >= 0) ta.setSelectionRange(sel, sel + 8); else ta.setSelectionRange(ta.value.length, ta.value.length);
}
function slashKey(e) {
  if ($('#slash').hidden) return false;
  const list = slashMatches(); if (!list || !list.length) return false;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); slashIndex = (slashIndex + (e.key === 'ArrowDown' ? 1 : -1) + list.length) % list.length; renderSlash(); return true; }
  if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); applySlash(list[slashIndex].cmd); return true; }
  if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeSlash(); return true; }
  return false;
}

/* ----------------------------------------------------------- code blocks */
const LANG_EXT = { python: 'py', py: 'py', javascript: 'js', js: 'js', typescript: 'ts', ts: 'ts', html: 'html', htm: 'html', css: 'css', json: 'json',
  powershell: 'ps1', ps1: 'ps1', bash: 'sh', sh: 'sh', shell: 'sh', csharp: 'cs', 'c#': 'cs', cpp: 'cpp', 'c++': 'cpp', c: 'c', java: 'java',
  rust: 'rs', go: 'go', ruby: 'rb', php: 'php', lua: 'lua', luau: 'luau', sql: 'sql', yaml: 'yml', yml: 'yml', xml: 'xml', svg: 'svg',
  markdown: 'md', md: 'md', gdscript: 'gd', kotlin: 'kt', swift: 'swift', batch: 'bat', bat: 'bat', toml: 'toml', ini: 'ini', jsx: 'jsx', tsx: 'tsx' };
function suggestName(code, lang) {
  const named = code.match(/^\s*(?:#|\/\/|--|<!--|\/\*)\s*(?:file(?:name)?\s*:\s*)?([\w.-]+\.[a-z0-9]{1,6})\b/i);
  if (named) return named[1];
  const title = code.match(/<title>([^<]{1,60})<\/title>/i);
  const base = title ? title[1].trim().toLowerCase().replace(/[^\w]+/g, '-').replace(/^-|-$/g, '') || 'page' : (lang === 'html' ? 'page' : 'code');
  return `${base}.${LANG_EXT[lang] || (isHtmlCode(code, lang) ? 'html' : 'txt')}`;
}
async function saveText(name, text) {
  const nat = nativeApi();
  if (nat && nat.save_file) {
    try { const p = await nat.save_file(name, text); if (p) toast('Saved to ' + p, 'ok'); } catch (e) { toast('Save failed: ' + e, 'err'); }
    return;
  }
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' })); a.download = name; a.click();
}
const blockCode = b => b.querySelector('pre').innerText.replace(/\n$/, '');
function flash(btn, html, back, ms = 1400) { btn.innerHTML = html; setTimeout(() => btn.innerHTML = back, ms); }

async function codeAction(btn) {
  const block = btn.closest('.code'), lang = block.dataset.lang, code = blockCode(block);
  switch (btn.dataset.cb) {
    case 'copy': await navigator.clipboard.writeText(code); flash(btn, icon('check', 13) + '<span>Copied</span>', icon('copy', 13) + '<span>Copy</span>'); break;
    case 'wrap': block.classList.toggle('wrapped'); btn.classList.toggle('on'); break;
    case 'expand': block.classList.toggle('expanded'); btn.classList.toggle('on'); break;
    case 'save': saveText(suggestName(code, lang), code); break;
    case 'run': runBlock(block, code, RUNNABLE[lang], btn); break;
    case 'preview': {
      const title = (code.match(/<title>([^<]{1,80})<\/title>/i) || [, lang === 'svg' ? 'SVG image' : 'Web page'])[1].trim();
      openPreview(mergeBlocks(block, code, lang), title);
      break;
    }
  }
}
function mergeBlocks(block, html, lang) {
  if (lang === 'svg' || (/^\s*<svg[\s>]/i.test(html) && !/<html[\s>]/i.test(html)))
    return `<!doctype html><html><head><meta charset="utf-8"><style>html,body{height:100%;margin:0}body{display:grid;place-items:center;background:#fff}svg{max-width:100%;max-height:100vh}</style></head><body>${html}</body></html>`;
  // separate ```css / ```js blocks in the same answer are put into the page
  const all = [...(block.closest('.body') || block.parentElement).querySelectorAll('.code')];
  const css = all.filter(b => b.dataset.lang === 'css').map(blockCode).join('\n');
  const js = all.filter(b => ['js', 'javascript'].includes(b.dataset.lang)).map(blockCode).join('\n');
  if (css && !html.includes(css.slice(0, 40))) {
    html = /<\/head>/i.test(html) ? html.replace(/<\/head>/i, () => `<style>\n${css}\n</style>\n</head>`) : `<style>\n${css}\n</style>\n` + html;
  }
  if (js && !html.includes(js.slice(0, 40))) {
    const tag = `<script>\n${js}\n<\/script>\n`;
    const i = html.toLowerCase().lastIndexOf('</body>');
    html = i >= 0 ? html.slice(0, i) + tag + html.slice(i) : html + tag;
  }
  return html;
}

async function runBlock(block, code, runner, btn) {
  if (!runner || !S.env[runner]) { toast('This language cannot run here', 'err'); return; }
  if (!S.settings.run_ok) {
    const ok = await confirmDialog({ title: `Run this ${RUN_NAMES[runner]} code?`,
      text: 'It runs on your PC with your user rights, in a new folder under MTAI\\data\\runs, and is stopped after 60 seconds. Only run code you trust. MTAI will not ask again.',
      ok: 'Run', danger: false });
    if (!ok) return;
    S.settings.run_ok = true; saveSettings();
  }
  let out = block.querySelector('.run-out');
  if (!out) { out = document.createElement('div'); out.className = 'run-out'; block.append(out); }
  out.innerHTML = `<div class="ro-head"><span class="spin"></span>Running ${RUN_NAMES[runner]}…</div>`;
  btn.disabled = true;
  let r;
  try { r = await api('run', { lang: runner, code }); } catch (e) { r = { error: e.message }; }
  btn.disabled = false;
  if (r.error) { out.innerHTML = `<div class="ro-head err">${icon('alert', 14)}${esc(r.error)}</div>`; return; }
  const ok = r.code === 0 && !r.timed_out;
  const status = r.timed_out ? `Stopped after ${r.timeout} s` : `Exit code ${r.code}`;
  const text = (r.stdout ? esc(r.stdout) : '') + (r.stderr ? `<span class="ro-err">${esc(r.stderr)}</span>` : '');
  out.innerHTML = `<div class="ro-head ${ok ? 'ok' : 'err'}">${icon(ok ? 'check' : 'alert', 14)}<b>${status}</b><span>${fmtDur(r.seconds)}</span>
      <span class="cb-sp"></span>${ok ? '' : `<button class="cb-btn hot" data-ro="fix">${icon('wand', 13)}<span>Ask AI to fix</span></button>`}
      <button class="cb-btn ic-only" data-ro="folder" data-path="${esc(r.cwd)}" title="Open run folder">${icon('folder', 13)}</button>
      <button class="cb-btn ic-only" data-ro="close" title="Close">${icon('x', 13)}</button></div>
    <pre class="ro-text">${text || '<span class="ro-none">(no output)</span>'}</pre>`;
  out._result = r;
}
function askFix(block) {
  const r = block.querySelector('.run-out')._result, code = blockCode(block);
  const errText = (r.stderr || r.stdout || '').trim().split('\n').slice(-25).join('\n');
  const ta = $('#input');
  ta.value = `This ${RUN_NAMES[RUNNABLE[block.dataset.lang]]} code failed${r.timed_out ? ' (it ran longer than 60 seconds)' : ''}:\n\n\`\`\`${block.dataset.lang}\n${code}\n\`\`\`\n\nOutput:\n\`\`\`\n${errText}\n\`\`\`\n\nFix it and show the full corrected code.`;
  autosize(ta); updateSendBtn(); ta.focus();
}

/* --------------------------------------------------------- preview panel */
const PV_HOOK = `<script>(()=>{const s=(t,a)=>{try{parent.postMessage({__mtai:1,type:t,args:a.map(x=>{if(x instanceof Error)return x.stack||String(x);try{return typeof x==='object'?JSON.stringify(x,null,1):String(x)}catch(e){return String(x)}})},'*')}catch(e){}};` +
  `['log','info','warn','error','debug'].forEach(k=>{const o=console[k];console[k]=(...a)=>{s(k,a);o.apply(console,a)}});` +
  `addEventListener('error',e=>s('error',[e.message+(e.lineno?' (line '+e.lineno+')':'')]));addEventListener('unhandledrejection',e=>s('error',['Unhandled promise rejection: '+((e.reason&&e.reason.message)||e.reason)]));})();<\/script>`;
function withHook(doc) {
  if (!/<html[\s>]|<!doctype/i.test(doc)) doc = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>\n${doc}\n</body></html>`;
  for (const re of [/<head[^>]*>/i, /<html[^>]*>/i, /<!doctype[^>]*>/i]) {
    const m = doc.match(re);
    if (m) return doc.slice(0, m.index + m[0].length) + PV_HOOK + doc.slice(m.index + m[0].length);
  }
  return PV_HOOK + doc;
}
async function openPreview(doc, title) {
  const prev = S.panel || {};
  S.panel = { kind: 'html', doc, original: doc, title, tab: 'preview', device: prev.device || 'desktop', logs: [], id: prev.id };
  showPanel();
  await pushPreview();
}
function openFile(f) {
  const prev = S.panel || {};
  S.panel = { kind: 'file', doc: f.text, original: f.text, title: f.name, tab: 'code', device: prev.device || 'desktop', logs: [] };
  showPanel();
}
async function pushPreview() {
  const p = S.panel; if (!p || p.kind !== 'html') return;
  p.logs = []; renderConsole();
  try {
    const r = await api('preview', { id: p.id, html: withHook(p.doc) });
    p.id = r.id; p.url = r.url;
    $('#pvUrl').textContent = r.url.replace(/^https?:\/\//, '');
    $('#pvFrame').src = r.url + '?v=' + Date.now();
  } catch (e) { toast('Preview failed: ' + e.message, 'err'); }
}
function showPanel() {
  const p = S.panel, panel = $('#panel'), app = $('#app');
  if (panel.hidden) {
    panel.hidden = false;
    let w = 0; try { w = +localStorage.getItem('mtai-pv-w'); } catch {}
    panel.style.width = (w > 300 ? Math.min(w, innerWidth - 480) : Math.round(innerWidth * .46)) + 'px';
    if (innerWidth < 1450 && !app.classList.contains('no-side')) { app.classList.add('no-side'); S.panelHidSide = true; }
  }
  $('#pvTitle').textContent = p.title;
  panel.dataset.kind = p.kind;
  panel.classList.toggle('file-mode', p.kind === 'file');
  panel.classList.remove('busy');
  $('[data-pvtab=code] span').textContent = p.kind === 'ws' ? 'Files' : 'Code';
  if (p.kind === 'html' || p.kind === 'file') { $('#pvCode').value = p.doc; $('#pvCode').readOnly = p.kind === 'file'; updateEdited(); }
  else $('#pvEdited').hidden = true;
  if (p.kind !== 'web') $('#webFrame').src = 'about:blank';
  if (p.kind !== 'html' && p.kind !== 'ws') $('#pvFrame').src = 'about:blank';
  $('#wsCode')._key = null;
  setPanelTab(p.kind === 'web' ? 'web' : p.tab); setDevice(p.device); renderConsole();
  if (p.kind === 'web') webRender();
}
function closePanel() {
  $('#panel').hidden = true; $('#pvFrame').src = 'about:blank'; $('#webFrame').src = 'about:blank';
  if (S.streaming && S.panel && S.panel.kind === 'ws') S.wsNoAuto = S.streaming.msg.id;   // closed while coding: do not pop up again
  if (S.panelHidSide) { $('#app').classList.remove('no-side'); S.panelHidSide = false; }
}
function setPanelTab(tab) {
  const p = S.panel, kind = p.kind;
  if (kind === 'file') tab = 'code';
  if (kind === 'web') tab = 'web';
  p.tab = tab;
  $$('[data-pvtab]').forEach(b => b.classList.toggle('on', b.dataset.pvtab === tab));
  $('#pvStage').hidden = tab !== 'preview';
  $('#pvCode').hidden = !(tab === 'code' && kind !== 'ws');
  $('#wsView').hidden = !(tab === 'code' && kind === 'ws');
  $('#pvConsole').hidden = tab !== 'console';
  $('#webView').hidden = tab !== 'web';
  $('.pv-tools').classList.toggle('pv-code-tools', tab !== 'preview');
  if (kind === 'ws') {
    if (tab === 'preview') {
      const url = wsPreviewUrl(p.chatId);
      p.url = url;
      $('#pvUrl').textContent = url ? url.replace(/^https?:\/\/[^/]+\/w\/[^/]+\//, '') : 'no .html file yet';
      $('#pvFrame').src = url ? url + '?v=' + Date.now() : 'about:blank';
      p.logs = (wsData(p.chatId).logs = (wsData(p.chatId).logs || []));
    } else wsRender(p.chatId);
  }
}
function setDevice(d) {
  S.panel.device = d;
  $$('[data-device]').forEach(b => b.classList.toggle('on', b.dataset.device === d));
  $('#pvDevice').className = 'pv-device ' + d;
}
function updateEdited() { const p = S.panel; $('#pvEdited').hidden = !p || p.doc === p.original; }
function renderConsole() {
  const p = S.panel; if (!p) return;
  const errs = p.logs.filter(l => l.type === 'error').length;
  const c = $('#pvCount'); c.textContent = p.logs.length || ''; c.className = errs ? 'err' : '';
  $('#pvConsole').innerHTML = (errs ? `<div class="cl-fix">${icon('alert', 15)}<span>${errs} error${errs > 1 ? 's' : ''} on this page</span><button class="cb-btn hot" data-pv="fix">${icon('wand', 13)}<span>Fix with AI</span></button></div>` : '') +
    (p.logs.length ? p.logs.map(l => `<div class="cl-row ${l.type}"><span class="cl-type">${l.type}</span><pre>${esc(l.args.join(' '))}</pre></div>`).join('')
    : '<div class="cl-empty">No console output yet. console.log() and errors from the page show up here.</div>');
  $('#pvFixDot').hidden = !errs;
}
function askFixPage() {
  const p = S.panel, errors = p.logs.filter(l => l.type === 'error').map(l => l.args.join(' ')).slice(-10).join('\n');
  const ta = $('#input');
  ta.value = `This web page has errors in the browser console:\n\n\`\`\`\n${errors}\n\`\`\`\n\nHere is the page:\n\n\`\`\`html\n${p.doc}\n\`\`\`\n\nFix it and give me the complete corrected page in one \`\`\`html block.`;
  autosize(ta); updateSendBtn(); updateCtx(); ta.focus();
}
window.addEventListener('message', e => {
  const d = e.data;
  if (!d || !d.__mtai || !S.panel) return;
  if (e.source === $('#webFrame').contentWindow) {           // the research browser
    if (d.type === 'read-done' && readWaiter) readWaiter();
    else if (d.type === 'link' && /^https?:/.test(d.url || '')) openWebPage(d.url);
    return;
  }
  if (e.source !== $('#pvFrame').contentWindow) return;
  S.panel.logs.push({ type: d.type, args: d.args || [] });
  if (S.panel.logs.length > 500) S.panel.logs.shift();
  renderConsole();
});
const pushEdited = debounce(() => pushPreview(), 600);

/* --------------------------------------------------------------- shortcuts */
function showShortcuts() {
  const rows = [['Enter', 'Send'], ['Shift Enter', 'New line'], ['/', 'Prompt commands (in the message box)'], ['Esc', 'Stop the answer, close menus'],
    ['Ctrl N', 'New chat'], ['Ctrl K', 'Switch model'], ['Ctrl B', 'Show or hide the sidebar'], ['Ctrl ,', 'Chat settings'],
    ['Ctrl P', 'Show or hide the preview panel'], ['Ctrl Shift M', 'Models'], ['Ctrl Shift L', 'Privacy mode on / off'], ['Ctrl I', 'Image mode on / off'], ['Ctrl J', 'Planning on / off'], ['Ctrl G', 'Play menu'], ['Ctrl /', 'This list']];
  const d = $('#dialog');
  d.innerHTML = `<div class="dialog keys"><h3>Keyboard shortcuts</h3>${rows.map(([k, t]) => `<div class="key-row"><span>${t}</span><span>${k.split(' ').map(x => `<kbd>${x}</kbd>`).join(' ')}</span></div>`).join('')}
    <div class="d-acts"><button class="btn ghost" data-tour="1">${icon('spark', 14)}Show the welcome tour</button><button class="btn primary" data-r="1">Got it</button></div></div>`;
  d.hidden = false;
  d.onclick = e => {
    if (e.target.closest('[data-tour]')) { d.hidden = true; d.onclick = null; if (window.mtaiWelcome) window.mtaiWelcome.start(); return; }
    if (e.target === d || e.target.closest('[data-r]')) { d.hidden = true; d.onclick = null; }
  };
}

/* ----------------------------------------------------------------- export */
function chatToMarkdown(c) {
  const out = [`# ${c.title || 'Chat'}`, '', `_MTAI · Model: ${c.model_name || '?'} · ${new Date(c.updated || Date.now()).toLocaleString()}_`, ''];
  for (const m of c.messages) {
    if (m.kind === 'image') { out.push(`## Image (${m.model || 'image model'})`, '', m.image ? `![${(m.prompt || '').replace(/[\[\]]/g, '')}](${location.origin}${m.image.url})` : '_(no image)_', ''); continue; }
    if (m.kind) continue;
    out.push(m.role === 'user' ? '## You' : `## ${m.model || 'Assistant'}`, '');
    out.push(m.role === 'assistant' ? splitThink(m).c : withFiles(m), '');
  }
  return out.join('\n');
}
async function exportChat() {
  if (!S.chat || !S.chat.messages.length) { toast('Nothing to export yet'); return; }
  saveText((S.chat.title || 'chat').replace(/[\\/:*?"<>|]+/g, '').slice(0, 60) + '.md', chatToMarkdown(S.chat));
}

/* --------------------------------------------------------------- settings */
const persistSettings = debounce(() => api('settings', S.settings).catch(() => {}), 350);
function saveSettings() { persistSettings(); }
function setRangeFill(r) { r.style.setProperty('--p', ((r.value - r.min) / (r.max - r.min) * 100) + '%'); }
function renderDrawer() {
  $$('[data-dtab]').forEach(b => b.classList.toggle('on', b.dataset.dtab === S.drawerTab));
  if (S.drawerTab === 'look') return renderAppearance();
  const s = S.settings, m = S.model;
  $('#drawerBody').innerHTML = `
    <div class="field"><label>System prompt</label><textarea id="setSystem" rows="5" spellcheck="false"></textarea>
      <div class="presets">${PRESETS.map((p, i) => `<button class="chip small ${s.system === p.text ? 'on' : ''}" data-preset="${i}">${p.name}</button>`).join('')}</div></div>
    <div class="field"><div class="row"><label>Temperature</label><span class="val" id="vTemp"></span></div>
      <input type="range" id="setTemp" min="0" max="2" step="0.05"><div class="help">Low: focused and exact. High: more creative and random.</div></div>
    <div class="field"><div class="row"><label>Top P</label><span class="val" id="vTopP"></span></div>
      <input type="range" id="setTopP" min="0.05" max="1" step="0.05"><div class="help">Keeps only the most likely words. 0.9 is a good default.</div></div>
    <div class="field"><div class="row"><label>Context length</label><span class="val">${m && m.ctx ? 'max ' + fmtCtx(m.ctx) : 'Ollama'}</span></div>
      <select id="setCtx">${CTX.map(n => `<option value="${n}" ${+s.num_ctx === n ? 'selected' : ''}>${fmtCtx(n)} tokens${n === 8192 ? ' (default)' : ''}</option>`).join('')}</select>
      <div class="help">How much of the chat the model remembers. More context uses more VRAM.</div></div>
    <div class="field"><div class="row"><label>Thinking</label><label class="switch"><input type="checkbox" id="setThink" ${s.think ? 'checked' : ''}><i></i></label></div>
      <div class="help">For models with the thinking badge (qwen3, deepseek-r1…). Off = faster answers.</div></div>
    <div class="field"><span class="lbl">Keep model in memory</span>
      <div class="seg" id="setKeep">${KEEP.map(([v, l]) => `<button data-keep="${v}" class="${String(s.keep_alive) === v ? 'on' : ''}">${l}</button>`).join('')}</div>
      <div class="help">Ollama only. Longer = instant replies, but VRAM stays in use.</div></div>
    <div class="field priv-field"><div class="row"><label>Privacy mode</label><label class="switch"><input type="checkbox" id="setPrivacy" ${s.privacy ? 'checked' : ''}><i></i></label></div>
      <div class="help">MTAI blocks every connection outside this PC: web search, deep research, downloads, cloud models, outside links and internet in previews. Python and PowerShell code runs in Windows' offline sandbox. <button class="fn-link" data-act="privacy-diag">Privacy diagnostics</button></div></div>
    <div class="field"><button class="btn ghost wide" id="resetSettings">${icon('refresh', 14)}Reset to defaults</button></div>`;
  $('#setSystem').value = s.system || '';
  const t = $('#setTemp'), p = $('#setTopP');
  t.value = s.temperature; p.value = s.top_p;
  const sync = () => { $('#vTemp').textContent = (+t.value).toFixed(2); $('#vTopP').textContent = (+p.value).toFixed(2); setRangeFill(t); setRangeFill(p); };
  sync();
  t.oninput = () => { s.temperature = +t.value; sync(); saveSettings(); };
  p.oninput = () => { s.top_p = +p.value; sync(); saveSettings(); };
  $('#setSystem').oninput = e => { s.system = e.target.value; $$('[data-preset]').forEach(b => b.classList.toggle('on', PRESETS[b.dataset.preset].text === s.system)); saveSettings(); };
  $('#setCtx').onchange = e => { s.num_ctx = +e.target.value; saveSettings(); };
  $('#setThink').onchange = e => { s.think = e.target.checked; updateModelUI(); saveSettings(); };
  $('#setPrivacy').onchange = e => { const want = e.target.checked; e.target.checked = !want; setPrivacy(want); };
}
function setTheme(patch, rerender = true) {
  S.settings.theme = themeOf({ ...themeOf(S.settings.theme), ...patch });
  applyTheme(S.settings.theme); saveSettings();
  if (rerender) renderAppearance();
}
const ANIM_HELP = {
  none: 'Everything is instant. Spinners still turn so you can see when MTAI is busy.',
  reduced: 'Short fades only: no sliding, bouncing, ripples or moving light.',
  medium: 'Ripples, sliding lists, the theme reveal and a glow while the AI answers.',
  high: 'All of medium, plus a cursor glow, background parallax, a magnetic send button, tilting cards and sparks when you send.',
};
function renderAppearance() {
  const t = themeOf(S.settings.theme);
  const colorRow = (key, label, help) => `<div class="color-row"><label class="swatch-in" style="--c:${t[key]}"><input type="color" data-color="${key}" value="${t[key]}"></label>
    <div class="cr-main"><b>${label}</b><small>${help}</small></div><input class="hex" data-hex="${key}" value="${t[key]}" maxlength="7" spellcheck="false"></div>`;
  $('#drawerBody').innerHTML = `
    <div class="field"><span class="lbl">Theme</span>
      <div class="themes">${THEMES.map(th => `<button class="theme ${t.preset === th.id ? 'on' : ''}" data-theme="${th.id}" style="--a:${th.accent};--b:${th.accent2};--g:${th.bg}">
        <span class="th-prev"><i></i></span><span>${th.name}</span></button>`).join('')}
        <button class="theme ${t.preset === 'custom' ? 'on' : ''}" data-theme="custom" style="--a:${t.accent};--b:${t.accent2};--g:${t.bg}"><span class="th-prev custom"><i></i></span><span>Custom</span></button></div></div>
    <div class="field"><span class="lbl">Custom colors</span>
      ${colorRow('accent', 'Accent', 'Buttons, links, highlights')}
      ${colorRow('accent2', 'Second accent', 'Gradients and glow')}
      ${colorRow('bg', 'Background', 'Keep it dark for the glass look')}</div>
    <div class="field"><div class="row"><label>Background glow</label><span class="val" id="vGlow"></span></div>
      <input type="range" id="setGlow" min="0" max="1.6" step="0.05"></div>
    <div class="field"><div class="row"><label>Moving background</label><label class="switch"><input type="checkbox" id="setMotion" ${t.motion ? 'checked' : ''}><i></i></label></div>
      <div class="help">Off keeps the glow but stops it from drifting.</div></div>
    <div class="field"><span class="lbl">Animations</span>
      <div class="seg anim-seg" id="setAnim">${ANIM_LEVELS.map(a => `<button data-anim="${a}" class="${t.anim === a ? 'on' : ''}">${a[0].toUpperCase() + a.slice(1)}</button>`).join('')}</div>
      <div class="help" id="animHelp">${ANIM_HELP[t.anim]}</div></div>
    <div class="field"><button class="btn ghost wide" data-theme="amethyst">${icon('refresh', 14)}Back to Amethyst</button></div>`;
  const g = $('#setGlow');
  g.value = t.glow;
  const sync = () => { $('#vGlow').textContent = Math.round(g.value * 100) + '%'; setRangeFill(g); };
  sync();
  g.oninput = () => { sync(); setTheme({ glow: +g.value }, false); };
  $('#setMotion').onchange = e => setTheme({ motion: e.target.checked }, false);
  $$('#setAnim [data-anim]').forEach(b => b.onclick = () => {
    setTheme({ anim: b.dataset.anim }, false);
    $$('#setAnim [data-anim]').forEach(x => x.classList.toggle('on', x === b));
    $('#animHelp').textContent = ANIM_HELP[b.dataset.anim];
  });
  $$('[data-color]').forEach(inp => inp.oninput = () => {
    const k = inp.dataset.color;
    $(`[data-hex="${k}"]`).value = inp.value; inp.parentElement.style.setProperty('--c', inp.value);
    setTheme({ [k]: inp.value, preset: 'custom' }, false);
    const c = $('[data-theme="custom"]'); $$('.theme').forEach(b => b.classList.toggle('on', b === c));
    c.style.setProperty('--' + ({ accent: 'a', accent2: 'b', bg: 'g' })[k], inp.value);
  });
  $$('[data-hex]').forEach(inp => inp.oninput = () => {
    let v = inp.value.trim(); if (!v.startsWith('#')) v = '#' + v;
    if (hexOk(v)) { const ci = $(`[data-color="${inp.dataset.hex}"]`); ci.value = v.toLowerCase(); ci.dispatchEvent(new Event('input')); }
  });
}
function pickTheme(id) {
  if (id === 'custom') { setTheme({ preset: 'custom' }); return; }
  const th = THEMES.find(x => x.id === id); if (!th) return;
  setTheme({ preset: th.id, accent: th.accent, accent2: th.accent2, bg: th.bg });
}
function openDrawer(tab) { if (tab) S.drawerTab = tab; renderDrawer(); $('#drawer').classList.add('open'); }
function closeDrawer() { $('#drawer').classList.remove('open'); }

/* ------------------------------------------------------------------ modal */
function openModels(tab) { if (tab) S.modalTab = tab; $('#modal').hidden = false; closePicker(); renderModal(); }
function closeModal() { $('#modal').hidden = true; }
function updateModalCounts() {
  $('#cntInstalled').textContent = S.models.filter(m => m.backend !== 'file').length || '';
  $('#cntServers').textContent = (S.servers.filter(s => s.online).length + (S.ollama.running ? 1 : 0)) || '';
  $('#cntFiles').textContent = S.models.filter(m => m.backend === 'file').length || '';
  const active = Object.values(S.pulls).filter(j => !j.done).length;
  $('#cntPulls').textContent = active || '';
}
function hashStr(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h); }
function modelCard(m) {
  const hue = (hashStr(m.family || m.name) % 7 - 3) * 14;      // small hue shift around the theme colors
  const initials = m.name.replace(/^.*\//, '').replace(/[^a-z0-9]/gi, ' ').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  const kv = [['Params', m.params], ['Quant', m.quant], ['Size', fmtSize(m.size)], ['Context', fmtCtx(m.ctx)], ['Family', m.family],
    ['In VRAM', m.loaded && m.vram != null ? fmtSize(m.vram) : null]].filter(x => x[1]);
  const acts = [];
  if (m.chattable) acts.push(`<button class="btn small primary" data-act="use" data-id="${esc(m.id)}">${icon('chat', 14)}Chat</button>`);
  if (m.backend === 'ollama' && m.loaded) acts.push(`<button class="btn small" data-act="unload" data-name="${esc(m.name)}">${icon('memory', 14)}Unload</button>`);
  if (m.backend === 'ollama' && S.ollama.running) acts.push(`<button class="btn small ghost" data-act="del-model" data-name="${esc(m.name)}" title="Delete from disk">${icon('trash', 14)}</button>`);
  return `<div class="mcard ${S.model && S.model.id === m.id ? 'active' : ''}">
    <div class="mc-top"><div class="mc-ic" style="filter:hue-rotate(${hue}deg)">${esc(initials || '?')}</div>
      <div><div class="mc-name">${esc(m.name)}</div><div class="mc-src">${esc(m.source)}${m.reason ? ' · ' + esc(m.reason) : ''}</div></div></div>
    ${kv.length ? `<div class="kv">${kv.map(([k, v]) => `<div><small>${k}</small><span>${esc(v)}</span></div>`).join('')}</div>` : ''}
    ${badges(m) ? `<div class="mc-badges">${badges(m)}</div>` : ''}
    <div class="mc-acts">${acts.join('')}</div></div>`;
}
function renderModal() {
  updateModalCounts();
  $$('.m-nav [data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === S.modalTab));
  const body = $('#modalBody'), o = S.ollama;
  const refresh = `<button class="btn small" data-act="refresh">${icon('refresh', 14)}Refresh</button>`;
  const banner = o.installed && !o.running
    ? `<div class="banner">${icon('alert', 18)}<span>Ollama is installed but not running.</span><button class="btn small primary" data-act="start-ollama">${icon('power', 14)}Start Ollama</button></div>`
    : !o.installed ? `<div class="banner">${icon('info', 18)}<span>Ollama is not installed. It is the easiest way to run local models.</span><button class="btn small" data-act="open-url" data-url="https://ollama.com/download">${icon('ext', 14)}ollama.com</button></div>` : '';

  if (S.modalTab === 'installed') {
    const list = S.models.filter(m => m.backend !== 'file');
    body.innerHTML = `<div class="m-head"><div><h2>Installed models</h2><p>${list.length} model${list.length === 1 ? '' : 's'} · Ollama folder: ${esc(o.dir || '?')}</p></div><div class="spacer"></div>${refresh}</div>
      ${banner}${list.length ? `<div class="grid">${list.map(modelCard).join('')}</div>`
        : `<div class="empty-box">No models yet.<br><br><button class="btn primary" data-tab-go="download">${icon('download', 14)}Download one</button></div>`}`;
  } else if (S.modalTab === 'download') {
    const have = new Set(S.models.filter(m => m.backend === 'ollama').map(m => m.name));
    const priv = privacyOn(), can = o.running && !priv;
    body.innerHTML = `<div class="m-head"><div><h2>Download models</h2><p>Pulls models from the Ollama library. Models up to ~8B parameters run fully on an 8 GB GPU.</p></div></div>
      ${priv ? privacyBanner('Downloads are off in privacy mode, because they connect to the Ollama library on the internet.') : banner}
      <div class="pull-row ${priv ? 'priv-locked' : ''}"><input id="pullName" placeholder="Model name, e.g. qwen3:4b" spellcheck="false" ${priv ? 'disabled' : ''}><button class="btn primary" data-act="pull" ${can ? '' : 'disabled'}>${icon('download', 15)}Download</button></div>
      <div id="pullJobs"></div>
      <div class="sec-title">Suggestions</div>
      <div class="grid ${priv ? 'priv-locked' : ''}">${LIBRARY.map(l => `<button class="sugg" data-pull="${l.name}" ${can ? '' : 'disabled'}><b>${l.name}${have.has(l.name) || have.has(l.name + ':latest') ? '<span class="badge b-live">Installed</span>' : ''}</b><small>${l.desc}</small><em>≈ ${l.size}</em></button>`).join('')}</div>
      <p style="margin-top:16px;color:var(--dim);font-size:12.5px">Browse everything at <span class="link" data-act="open-url" data-url="https://ollama.com/library">ollama.com/library</span></p>`;
    renderPullJobs();
  } else if (S.modalTab === 'servers') {
    const row = (dot, name, sub, side, btn = '') => `<div class="list-row"><i class="dot ${dot}"></i><div class="lr-main"><b>${name}</b><small>${sub}</small></div><span class="lr-side">${side}</span>${btn}</div>`;
    body.innerHTML = `<div class="m-head"><div><h2>Servers</h2><p>Local AI servers MTAI looks for. Start one, then press Refresh.</p></div><div class="spacer"></div>${refresh}</div>
      ${row(o.running ? 'live' : o.installed ? 'warn' : 'err', 'Ollama', esc(o.url || ''),
        o.running ? `running · v${esc(o.version || '?')}` : o.installed ? 'stopped' : 'not installed',
        !o.running && o.installed ? `<button class="btn small primary" data-act="start-ollama">${icon('power', 14)}Start</button>` : '')}
      ${S.servers.map(s => row(s.online ? 'live' : '', esc(s.name), esc(s.url), s.online ? `online · ${s.count} model${s.count === 1 ? '' : 's'}` : 'offline')).join('')}
      <div class="sec-title">How to connect</div>
      <div class="list-row"><div class="lr-main"><b>LM Studio</b><small>Developer tab → Start Server (port 1234). Its downloaded models show up here.</small></div></div>
      <div class="list-row"><div class="lr-main"><b>llama.cpp</b><small>llama-server -m model.gguf --port 8080</small></div></div>
      <div class="list-row"><div class="lr-main"><b>Jan / KoboldCpp / text-generation-webui / vLLM</b><small>Turn on the OpenAI-compatible API server (ports 1337 / 5001 / 5000 / 8000).</small></div></div>`;
  } else if (S.modalTab === 'files') {
    const files = S.models.filter(m => m.backend === 'file');
    body.innerHTML = `<div class="m-head"><div><h2>GGUF files</h2><p>Model files found on disk. To chat with one, load it in LM Studio or llama.cpp.</p></div><div class="spacer"></div>
      <button class="btn small primary" data-act="add-folder">${icon('folder', 14)}Add folder</button>${refresh}</div>
      <div class="sec-title">Folders scanned</div>
      ${S.folders.map(f => `<div class="list-row"><i class="dot ${f.exists ? (f.count ? 'live' : 'ready') : ''}"></i><div class="lr-main"><b>${esc(f.path)}</b><small>${f.exists ? f.count + ' file' + (f.count === 1 ? '' : 's') : 'does not exist'}${f.default ? ' · default' : ''}</small></div>
        ${f.default ? '' : `<button class="btn small ghost" data-act="rm-folder" data-path="${esc(f.path)}" title="Stop scanning">${icon('x', 14)}</button>`}</div>`).join('')}
      <div class="sec-title">Files</div>
      ${files.length ? files.map(f => `<div class="list-row">${icon('file', 18)}<div class="lr-main"><b>${esc(f.name)}</b><small>${esc(f.path)}</small></div><span class="lr-side">${[f.quant, fmtSize(f.size)].filter(Boolean).join(' · ')}</span></div>`).join('')
        : '<div class="empty-box">No .gguf files found. Add a folder that holds them.</div>'}`;
  }
}
function renderPullJobs() {
  const el = $('#pullJobs'); if (!el) return;
  el.innerHTML = Object.values(S.pulls).reverse().map(j => {
    const pc = j.total ? Math.min(100, j.completed / j.total * 100) : (j.done && !j.error ? 100 : 0);
    const speed = j.speed ? ` · ${fmtSize(j.speed)}/s` : '';
    const sizes = j.total ? ` · ${fmtSize(j.completed)} / ${fmtSize(j.total)}` : '';
    return `<div class="job ${j.done ? (j.error ? 'fail' : 'done') : ''}"><div class="job-top"><b>${esc(j.name)}</b>
      <span class="st">${esc(j.error || j.status)}${j.done ? '' : sizes + speed}</span><span class="pc">${pc.toFixed(0)}%</span>
      ${j.done ? '' : `<button class="btn small ghost" data-act="cancel-pull" data-name="${esc(j.name)}">${icon('x', 13)}</button>`}</div>
      <div class="bar"><i style="width:${pc}%"></i></div></div>`;
  }).join('');
}
async function pull(name) {
  name = (name || '').trim();
  if (!name) return;
  if (privacyOn()) { privacyBlocked('download'); return; }
  if (S.pulls[name] && !S.pulls[name].done) return;
  const job = S.pulls[name] = { name, status: 'Starting…', total: 0, completed: 0, ctrl: new AbortController(), t: performance.now(), b: 0 };
  renderPullJobs(); updateModalCounts();
  let frame = null;
  try {
    const resp = await api('ollama/pull', { name }, { stream: true, signal: job.ctrl.signal });
    for await (const ev of ndjson(resp)) {
      if (ev.error) { job.error = ev.error; break; }
      if (ev.status) job.status = ev.status;
      if (ev.total) {
        const now = performance.now(), done = ev.completed || 0;
        if (ev.total !== job.total) { job.t = now; job.b = done; }
        else if (now - job.t > 800) { job.speed = (done - job.b) / ((now - job.t) / 1000); job.t = now; job.b = done; }
        job.total = ev.total; job.completed = done;
      }
      if (!frame) frame = requestAnimationFrame(() => { frame = null; renderPullJobs(); });
    }
  } catch (e) { job.error = e.name === 'AbortError' ? 'Cancelled' : e.message; }
  job.done = true;
  if (!job.error) { job.status = 'Ready'; toast(`${name} is ready to chat`, 'ok'); await loadModels(true); }
  else if (job.error !== 'Cancelled') toast(`Download of ${name} failed: ${job.error}`, 'err', 5000);
  renderPullJobs(); updateModalCounts();
  if (!$('#modal').hidden && S.modalTab === 'download') renderModal();
}

/* ------------------------------------------------------------------ events */
function bind() {
  const input = $('#input');
  const ctxSoon = debounce(updateCtx, 250);
  input.addEventListener('input', () => { autosize(input); updateSendBtn(); slashIndex = 0; S.slashForced = false; renderSlash(); ctxSoon(); });
  input.addEventListener('keydown', e => {
    if (slashKey(e)) return;
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
  });
  input.addEventListener('blur', () => setTimeout(() => { if (!$('#slash').matches(':hover')) closeSlash(); }, 150));
  input.addEventListener('paste', e => {
    const files = [...(e.clipboardData?.files || [])];
    if (files.length) { e.preventDefault(); addFiles(files); }
  });
  $('#sendBtn').onclick = submit;
  $('#attachBtn').onclick = () => $('#fileInput').click();
  $('#promptBtn').onclick = () => {
    if (!$('#slash').hidden) { closeSlash(); return; }
    S.slashForced = true; slashIndex = 0; renderSlash(); $('#input').focus();
  };
  $('#slash').onmousedown = e => e.preventDefault();          // keep focus in the message box
  $('#slash').onclick = e => { const b = e.target.closest('[data-slash]'); if (b) applySlash(b.dataset.slash); };
  $('#keysBtn').onclick = showShortcuts;
  $('#fileInput').onchange = e => { addFiles(e.target.files); e.target.value = ''; };
  $('#attachments').onclick = e => {
    const b = e.target.closest('[data-rm]');
    if (b) { S.attachments = S.attachments.filter(a => a.id !== b.dataset.rm); renderAttachments(); updateSendBtn(); return; }
    const f = e.target.closest('[data-afile]'); if (f) openFile(S.attachments.find(a => a.id === f.dataset.afile));
  };

  // preview panel
  $('#panel').addEventListener('click', e => {
    const t = e.target.closest('[data-pvtab]'); if (t) { setPanelTab(t.dataset.pvtab); return; }
    const d = e.target.closest('[data-device]'); if (d) { setDevice(d.dataset.device); return; }
    const b = e.target.closest('[data-pv]'); if (!b) return;
    const p = S.panel;
    if (p.kind === 'ws') {
      const D = wsData(p.chatId);
      switch (b.dataset.pv) {
        case 'close': closePanel(); break;
        case 'fix': {
          const errs = (p.logs || []).filter(l => l.type === 'error').slice(-8).map(l => l.args.join(' ')).join('\n');
          const ta = $('#input'); ta.value = `These errors showed up in the console:\n\n\`\`\`\n${errs}\n\`\`\`\n\nFix them with edits.`; autosize(ta); updateSendBtn(); ta.focus(); break;
        }
        case 'reload': D.loaded = false; wsLoad(p.chatId).then(() => { $('#wsCode')._key = null; setPanelTab(p.tab); }).catch(err => toast(err.message, 'err')); break;
        case 'folder': api('ws/open-folder', { ws: p.chatId }); break;
        case 'open': { const u = wsPreviewUrl(p.chatId); if (u) api('open', { url: u }); else toast('No .html file in the workspace yet'); break; }
        case 'save': if (D.sel && D.files[D.sel] != null) saveText(D.sel.split('/').pop(), D.files[D.sel]); break;
      }
      return;
    }
    if (p.kind === 'web') {
      const t = p.tabs[p.cur];
      if (b.dataset.pv === 'close') closePanel();
      else if (b.dataset.pv === 'open' && t && !t.serp) api('open', { url: t.url });
      else if (b.dataset.pv === 'open' && t) api('open', { url: t.url });
      else if (b.dataset.pv === 'reload' && t) { t.preview = null; webShow(p.cur); }
      return;
    }
    switch (b.dataset.pv) {
      case 'close': closePanel(); break;
      case 'fix': askFixPage(); break;
      case 'reload': if (p.kind === 'html') pushPreview(); break;
      case 'revert': p.doc = p.original; $('#pvCode').value = p.doc; updateEdited(); pushPreview(); break;
      case 'open': if (p.url) api('open', { url: p.url }); break;
      case 'save': saveText(p.kind === 'file' ? p.title : suggestName(p.doc, 'html'), p.doc); break;
    }
  });
  $('#pvCode').addEventListener('input', e => { S.panel.doc = e.target.value; updateEdited(); pushEdited(); });
  $('#pvCode').addEventListener('keydown', e => {
    if (e.key === 'Tab') { e.preventDefault(); const t = e.target, s = t.selectionStart; t.setRangeText('  ', s, t.selectionEnd, 'end'); t.dispatchEvent(new Event('input')); }
  });
  $('#pvResize').addEventListener('pointerdown', e => {
    const panel = $('#panel'), startX = e.clientX, startW = panel.offsetWidth;
    document.body.classList.add('resizing');
    const move = ev => { panel.style.width = Math.max(320, Math.min(innerWidth - 460, startW + startX - ev.clientX)) + 'px'; };
    const up = () => {
      document.body.classList.remove('resizing'); removeEventListener('pointermove', move); removeEventListener('pointerup', up);
      try { localStorage.setItem('mtai-pv-w', panel.offsetWidth); } catch {}
    };
    addEventListener('pointermove', move); addEventListener('pointerup', up);
  });

  let dragDepth = 0;
  window.addEventListener('dragenter', e => { if ([...e.dataTransfer.types].includes('Files')) { dragDepth++; $('#dropZone').classList.add('show'); } });
  window.addEventListener('dragleave', () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $('#dropZone').classList.remove('show'); });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => { e.preventDefault(); dragDepth = 0; $('#dropZone').classList.remove('show'); if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files); });

  $('#newChatBtn').onclick = newChat;
  $('#chatSearch').oninput = renderChatList;
  $('#chatList').onclick = e => {
    const ci = e.target.closest('.ci'); if (!ci) return;
    const act = e.target.closest('[data-act]');
    if (act && act.dataset.act === 'rename') { e.stopPropagation(); renameChat(ci, ci.dataset.id); return; }
    if (act && act.dataset.act === 'delete') { e.stopPropagation(); deleteChat(ci.dataset.id); return; }
    if (e.target.tagName !== 'INPUT') openChat(ci.dataset.id);
  };
  $('#chatList').ondblclick = e => { const ci = e.target.closest('.ci'); if (ci && e.target.tagName !== 'INPUT') renameChat(ci, ci.dataset.id); };

  const toggleSide = show => {
    const app = $('#app'); show = show ?? app.classList.contains('no-side');
    app.classList.toggle('no-side', !show); S.settings.sidebar = show; saveSettings();
  };
  $('#hideSideBtn').onclick = () => toggleSide(false);
  $('#showSideBtn').onclick = () => toggleSide(true);
  $('#modelPill').onclick = () => $('#picker').hidden ? openPicker() : closePicker();
  $('#pkSearch').oninput = renderPicker;
  $('#pkSearch').onkeydown = pickerKey;
  $('#thinkChip').onclick = () => { S.settings.think = !S.settings.think; updateModelUI(); saveSettings(); toast(S.settings.think ? 'Thinking on' : 'Thinking off: faster answers'); };
  const toggleDrawer = tab => ($('#drawer').classList.contains('open') && S.drawerTab === tab) ? closeDrawer() : openDrawer(tab);
  $('#settingsBtn').onclick = () => toggleDrawer('chat');
  $('#themeBtn').onclick = () => toggleDrawer('look');
  $('#exportBtn').onclick = exportChat;
  $('#modelsBtn').onclick = () => openModels('installed');
  $('#statusPill').onclick = () => openModels('servers');
  $('#modal').onclick = e => { if (e.target.id === 'modal') closeModal(); };
  $('.m-nav').onclick = e => { const b = e.target.closest('[data-tab]'); if (b) { S.modalTab = b.dataset.tab; renderModal(); } };

  const s = scroller();
  s.addEventListener('scroll', () => $('#toBottom').classList.toggle('show', !nearBottom()), { passive: true });
  $('#toBottom').onclick = () => toBottom(true);
  new ResizeObserver(() => document.documentElement.style.setProperty('--composer-h', $('#composerWrap').offsetHeight + 'px')).observe($('#composerWrap'));

  // one delegated handler for buttons that live in re-rendered markup
  document.addEventListener('click', async e => {
    const a = e.target.closest('a[href]');
    if (a) { e.preventDefault(); if (/^https?:/.test(a.href)) api('open', { url: a.href }); return; }
    const zoom = e.target.closest('[data-zoom]'); if (zoom) { lightbox(zoom.getAttribute('src'), zoom.alt || ''); return; }
    const cb = e.target.closest('[data-cb]'); if (cb) { codeAction(cb); return; }
    const ro = e.target.closest('[data-ro]');
    if (ro) {
      const block = ro.closest('.code');
      if (ro.dataset.ro === 'close') block.querySelector('.run-out').remove();
      else if (ro.dataset.ro === 'fix') askFix(block);
      else if (ro.dataset.ro === 'folder') api('open-folder', { path: ro.dataset.path });
      return;
    }
    const uf = e.target.closest('[data-ufile]');
    if (uf) { const mm = S.chat.messages.find(x => x.id === uf.closest('.msg').dataset.id); if (mm) openFile(mm.files[+uf.dataset.ufile]); return; }
    const sugg = e.target.closest('[data-sugg]');
    if (sugg) { const ta = $('#input'); ta.value = SUGGESTIONS[sugg.dataset.sugg].text; autosize(ta); updateSendBtn(); ta.focus(); return; }
    const pk = e.target.closest('.pk-item'); if (pk) { selectModel(findModel(pk.dataset.id)); return; }
    const preset = e.target.closest('[data-preset]');
    if (preset) { S.settings.system = PRESETS[preset.dataset.preset].text; saveSettings(); renderDrawer(); return; }
    const th = e.target.closest('[data-theme]'); if (th) { pickTheme(th.dataset.theme); return; }
    const dt = e.target.closest('[data-dtab]'); if (dt) { S.drawerTab = dt.dataset.dtab; renderDrawer(); return; }
    const keep = e.target.closest('[data-keep]');
    if (keep) { S.settings.keep_alive = keep.dataset.keep; saveSettings(); renderDrawer(); return; }
    const go = e.target.closest('[data-tab-go]'); if (go) { S.modalTab = go.dataset.tabGo; renderModal(); return; }
    const pl = e.target.closest('[data-pull]'); if (pl) { pull(pl.dataset.pull); return; }
    if (e.target.closest('#resetSettings')) {
      const { model: keepModel, sidebar: side, theme, privacy, web, web_ok, run_ok, style, plan, image, fun } = S.settings;
      S.settings = { system: PRESETS[0].text, temperature: 0.7, top_p: 0.9, num_ctx: 8192, think: true, keep_alive: '10m', model: keepModel, sidebar: side, theme, privacy, web, web_ok, run_ok, style, plan, image, fun, onboarded: true };
      saveSettings(); renderDrawer(); updateModelUI(); toast('Settings reset'); return;
    }

    const btn = e.target.closest('[data-act]'); if (!btn) return;
    const act = btn.dataset.act, msgNode = btn.closest('.msg');
    const m = msgNode && S.chat ? S.chat.messages.find(x => x.id === msgNode.dataset.id) : null;
    switch (act) {
      case 'copy': if (m) { await navigator.clipboard.writeText(m.role === 'assistant' ? splitThink(m).c : m.content); btn.innerHTML = icon('check', 15); setTimeout(() => btn.innerHTML = icon('copy', 15), 1400); } break;
      case 'edit': if (m) startEdit(msgNode, m); break;
      case 'edit-save': if (m) saveEdit(msgNode, m); break;
      case 'edit-cancel': renderThread(false); break;
      case 'regen': regenerate(); break;
      case 'webwatch': if (m) watchResearch(m); break;
      case 'webbox': if (m) { const el = msgNode.querySelector('.webbox'); m._webOpen = !el.classList.contains('open'); el.classList.toggle('open', m._webOpen); msgNode.querySelector('.web-slot')._html = null; } break;
      case 'think': if (m) { const el = msgNode.querySelector('.think'); m._thinkOpen = !el.classList.contains('open'); el.classList.toggle('open', m._thinkOpen); } break;
      case 'start-ollama': btn.disabled = true; await startOllama(); break;
      case 'manage': openModels('installed'); break;
      case 'manage-download': openModels('download'); break;
      case 'open-picker': openPicker(); break;
      case 'refresh': btn.disabled = true; await loadModels(); btn.disabled = false; toast('Model list refreshed', 'ok', 1800); break;
      case 'close-drawer': closeDrawer(); break;
      case 'close-modal': closeModal(); break;
      case 'use': selectModel(findModel(btn.dataset.id)); closeModal(); break;
      case 'pull': pull($('#pullName').value); $('#pullName').value = ''; break;
      case 'cancel-pull': S.pulls[btn.dataset.name]?.ctrl.abort(); break;
      case 'unload':
        try { await api('ollama/unload', { name: btn.dataset.name }); toast(`${btn.dataset.name} unloaded from memory`, 'ok'); } catch (err) { toast(err.message, 'err'); }
        await loadModels(true); break;
      case 'del-model':
        if (await confirmDialog({ title: `Delete ${btn.dataset.name}?`, text: 'The model files are removed from disk. You can download it again later.' })) {
          try { await api('ollama/delete', { name: btn.dataset.name }); toast(`${btn.dataset.name} deleted`, 'ok'); } catch (err) { toast(err.message, 'err'); }
          await loadModels(true);
        }
        break;
      case 'open-url': api('open', { url: btn.dataset.url }); break;
      case 'add-folder': {
        const nat = nativeApi();
        const p = nat ? await nat.pick_folder() : prompt('Folder that holds .gguf files:');
        if (p) { try { await api('folders/add', { path: p }); await loadModels(true); renderModal(); toast('Folder added', 'ok'); } catch (err) { toast(err.message, 'err'); } }
        break;
      }
      case 'rm-folder': await api('folders/remove', { path: btn.dataset.path }); await loadModels(true); renderModal(); break;
    }
  });
  document.addEventListener('keydown', e => {
    if (e.target.id === 'pullName' && e.key === 'Enter') { pull(e.target.value); e.target.value = ''; return; }
  });

  document.addEventListener('mousedown', e => {
    if (!$('#picker').hidden && !e.target.closest('#picker') && !e.target.closest('#modelPill')) closePicker();
    if ($('#drawer').classList.contains('open') && !e.target.closest('#drawer') && !e.target.closest('#settingsBtn') && !e.target.closest('#themeBtn') && !e.target.closest('#dialog')) closeDrawer();
  });

  document.addEventListener('keydown', e => {
    const ctrl = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
    if (ctrl && k === 'n') { e.preventDefault(); newChat(); }
    else if (ctrl && k === 'k') { e.preventDefault(); $('#picker').hidden ? openPicker() : closePicker(); }
    else if (ctrl && k === 'b') { e.preventDefault(); toggleSide(); }
    else if (ctrl && e.key === ',') { e.preventDefault(); $('#drawer').classList.contains('open') ? closeDrawer() : openDrawer(); }
    else if (ctrl && e.shiftKey && k === 'm') { e.preventDefault(); openModels(); }
    else if (ctrl && k === 'p') {
      e.preventDefault();
      if (!$('#panel').hidden) closePanel();
      else if (S.chat && S.chat.code) openWorkspace(S.chat);
      else if (S.panel) { showPanel(); if (S.panel.kind === 'html') pushPreview(); if (S.panel.kind === 'web' && S.panel.cur >= 0) webShow(S.panel.cur); }
      else toast('No preview yet. Press Preview on an HTML code block.');
    }
    else if (ctrl && e.key === '/') { e.preventDefault(); showShortcuts(); }
    else if (e.key === 'Escape') {
      if (!$('#dialog').hidden) { $('#dialog').hidden = true; return; }
      if (!$('#slash').hidden) { closeSlash(); return; }
      if (!$('#picker').hidden) { closePicker(); return; }
      if (!$('#modal').hidden) { closeModal(); return; }
      if ($('#drawer').classList.contains('open')) { closeDrawer(); return; }
      if (S.streaming) stop();
    } else if (!ctrl && !e.altKey && e.key.length === 1 && !e.target.closest('input,textarea,select') && $('#dialog').hidden && $('#modal').hidden) {
      $('#input').focus();                     // start typing anywhere
    }
  });
  window.addEventListener('focus', () => loadModels(true));
}

/* -------------------------------------------------------------------- init */
async function init() {
  toolsInit();
  privacyInit();
  hydrateIcons();
  bind();
  bindTools();
  bindPrivacy();
  const boot = window.mtaiBoot || { step() {}, done() {} };
  boot.step('Loading settings', .3);
  try { S.settings = await api('settings'); } catch { S.settings = {}; }
  try { S.env = await api('env'); } catch { S.env = {}; }
  applyTheme(S.settings.theme);
  updatePrivacyUI(false);
  if (S.settings.sidebar === false) $('#app').classList.add('no-side');
  newChat();
  boot.step('Finding your models', .55);
  let left = 2;
  const part = () => { left--; boot.step(left ? 'Opening your chats' : 'Ready', left ? .8 : 1); };
  try { await Promise.all([Promise.resolve(loadModels()).finally(part), Promise.resolve(loadChats()).finally(part)]); }
  finally { boot.done(); }
  setInterval(() => { if (!S.streaming) loadModels(true); }, 20000);
}
init();
