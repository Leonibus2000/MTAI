'use strict';
/* MTAI - privacy mode. One switch that turns off everything that could reach the internet.
   The backend enforces it (netguard.py: audit hook in MTAI's Python, a gate proxy that this
   browser is started behind, an offline sandbox for code runs); this file is the switch,
   the warning, the animation, the self-test probes for this browser and the diagnostics page.
   Loaded after tools.js and before app.js; runs only after app.js has set up S, api(), icon(). */

const PRIV_ITEMS = [
  { icon: 'globe', name: 'Web search', off: 'No search words go to DuckDuckGo', back: 'Can be switched on again' },
  { icon: 'telescope', name: 'Deep research', off: 'No web pages are downloaded', back: 'Can be used again' },
  { icon: 'download', name: 'Model downloads', off: 'Ollama and image model downloads are blocked', back: 'Downloads work again' },
  { icon: 'ext', name: 'Outside links', off: 'Links do not open in your browser (MTAI cannot keep it offline)', back: 'Links open in your browser' },
  { icon: 'cloud', name: 'Cloud AI and remote servers', off: 'GPT, Claude, Gemini, Grok, Ollama cloud models and cloud images are off', back: 'Cloud models with your API keys work again' },
  { icon: 'wifi', name: 'Internet in previews and code', off: 'MTAI\'s browser is cut off; Python and PowerShell run in Windows\' offline sandbox', back: 'Previews and code can go online' },
];

function privacyInit() {
  Object.assign(ICONS, {
    shield: '<path d="M12 3l7.5 3v5.6c0 4.6-3.1 8.1-7.5 9.4-4.4-1.3-7.5-4.8-7.5-9.4V6z"/>',
    shieldOn: '<path d="M12 3l7.5 3v5.6c0 4.6-3.1 8.1-7.5 9.4-4.4-1.3-7.5-4.8-7.5-9.4V6z"/><path d="M8.8 12.2l2.3 2.3 4.2-4.4"/>',
    cloud: '<path d="M7 18.5h10.2a4.3 4.3 0 0 0 .5-8.6A6 6 0 0 0 6.3 9.3 4.6 4.6 0 0 0 7 18.5z"/>',
    wifi: '<path d="M2.5 9.2a14 14 0 0 1 19 0M5.6 12.6a9.4 9.4 0 0 1 12.8 0M8.7 16a5 5 0 0 1 6.6 0"/><path d="M12 19.4h.01"/>',
  });
}

const privacyOn = () => !!(typeof S !== 'undefined' && S.settings && S.settings.privacy);
function isLocalUrl(u) {
  try {
    const h = new URL(u, location.href).hostname.replace(/^\[|\]$/g, '');
    return h === 'localhost' || h === '::1' || /^127\./.test(h);
  } catch { return false; }
}
function privacyBanner(text) {
  return `<div class="banner priv-banner">${icon('shieldOn', 18)}<span>${esc(text)}</span><button class="btn small ghost" data-act="privacy-off">Turn off</button></div>`;
}

/* A blocked click: small shake on the control plus one shield toast (not a pile of them). */
let _privToastAt = 0;
function privacyBlocked(kind) {
  const el = kind === 'web' ? $('#webBtn') : kind === 'deep' ? $('#deepBtn') : null;
  if (el) { el.classList.remove('nope'); void el.offsetWidth; el.classList.add('nope'); }
  const chip = $('#privChip'); chip.classList.remove('ping'); void chip.offsetWidth; chip.classList.add('ping');
  if (Date.now() - _privToastAt < 1500) return;
  _privToastAt = Date.now();
  const what = { web: 'Web search is off', deep: 'Deep research is off', download: 'Downloads are off', link: 'Links do not open in your browser' }[kind] || 'That needs the internet';
  const t = document.createElement('div');
  t.className = 'toast priv';
  t.innerHTML = icon('shieldOn', 17) + `<span>${esc(what)} in privacy mode. Turn it off with the shield at the top.</span>`;
  $('#toasts').append(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, 3400);
}

/* ---- warning dialog */
function privacyDialog(on) {
  return new Promise(res => {
    const d = $('#dialog');
    const busyWeb = on && S.streaming && S.streaming.msg.web && S.streaming.msg.web.active;
    const pulls = on && Object.values(S.pulls).some(j => !j.done);
    const rows = PRIV_ITEMS.map((it, i) => `<div class="pd-row" style="--i:${i}"><span class="pd-ic ${on ? 'x' : ''}">${icon(it.icon, 17)}</span>
      <div><b>${it.name}</b><small>${on ? it.off : it.back}</small></div><em>${on ? 'Off' : 'On'}</em></div>`).join('');
    const extra = [busyWeb && 'The web research that is running now stops.', pulls && 'Running model downloads are cancelled.',
      'Open internet connections are cut.'].filter(Boolean).join(' ');
    d.innerHTML = `<div class="dialog priv-dialog ${on ? 'turn-on' : 'turn-off'}">
      <div class="pd-head"><span class="pd-shield">${icon(on ? 'shieldOn' : 'shield', 28)}</span>
        <div><h3>${on ? 'Turn on privacy mode?' : 'Turn off privacy mode?'}</h3>
        <p>${on ? 'MTAI blocks every connection outside this PC and checks the block right away. Your chats, files and local models keep working.' : 'MTAI can connect to the internet again when you use these features.'}</p></div></div>
      <div class="pd-list">${rows}</div>
      ${on ? `<div class="pd-warn">${icon('alert', 16)}<span>Pages and code that need the internet (CDN libraries, online APIs) will fail. JavaScript files do not run. Ollama and other model servers are separate programs: MTAI only talks to them on this PC, and they stay online unless you block them in Privacy diagnostics (Windows Firewall). <b>${esc(extra)}</b></span></div>`
        : `<div class="pd-warn soft">${icon('info', 16)}<span>Web search stays off until you switch it on. Each web feature still shows a note before it sends anything.</span></div>`}
      <div class="d-acts"><button class="btn ghost" data-r="0">Cancel</button>
        <button class="btn ${on ? 'primary' : 'danger'}" data-r="1">${icon(on ? 'shieldOn' : 'shield', 15)}${on ? 'Turn on privacy mode' : 'Turn off'}</button></div></div>`;
    d.hidden = false;
    const done = v => { d.hidden = true; d.onclick = null; document.removeEventListener('keydown', key, true); res(v); };
    const key = e => { if (e.key === 'Escape') { e.stopPropagation(); done(false); } if (e.key === 'Enter') { e.stopPropagation(); e.preventDefault(); done(true); } };
    document.addEventListener('keydown', key, true);
    d.onclick = e => { const b = e.target.closest('[data-r]'); if (b) done(b.dataset.r === '1'); else if (e.target === d) done(false); };
    setTimeout(() => d.querySelector('[data-r="1"]').focus(), 20);
  });
}

/* ---- switching */
async function setPrivacy(on) {
  if (S.privBusy || on === privacyOn()) return;
  if (!await privacyDialog(on)) return;
  S.privBusy = true;
  if (on) {
    if (S.streaming && S.streaming.msg.web && S.streaming.msg.web.active) stop();
    for (const j of Object.values(S.pulls)) if (!j.done) j.ctrl.abort();
    S.deepNext = false;
    S.settings.web = 'off';
  }
  S.settings.privacy = on;
  PRIV.stat = { level: on ? 'checking' : 'off' };
  try { await api('settings', S.settings); }       // straight away, not debounced: the backend must know now
  catch (e) { S.settings.privacy = !on; S.privBusy = false; PRIV.stat = null; toast('Could not change privacy mode: ' + e.message, 'err'); return; }
  await playPrivacyFx(on, () => updatePrivacyUI(true));
  S.privBusy = false;
  if (on) {
    // the user agreed earlier to have the firewall rules added with privacy mode (Windows still asks each time)
    const fw = S.settings.firewall || {};
    if (fw.auto && (fw.programs || []).length) await fwApply(fw.programs, true, { quiet: true });
    privacyVerify({ quiet: false });
  } else fwRemove({ quiet: true });        // privacy off: MTAI's firewall rules go (nothing happens when there are none)
}

/* ---- Windows Firewall rules for local AI programs (Ollama, LM Studio...). Nothing here changes Windows
   without the consent screen first; Windows itself asks for administrator permission each time. */
async function fwApply(programs, auto, { quiet = false } = {}) {
  PRIV.fwBusy = 'apply'; renderDiagIf();
  toast('Windows asks for administrator permission to add MTAI\'s firewall rules.', 'info', 4200);
  let r;
  try { r = await api('firewall/apply', { confirm: true, programs, auto }); }
  catch (e) { r = { error: e.message }; }
  PRIV.fwBusy = null;
  if (r.error) toast((r.declined ? '' : 'Firewall rules not added: ') + r.error, 'err', 6000);
  else {
    const res = r.result || {};
    const errs = (res.errors || []).length;
    toast(`Firewall rules in place for ${programs.length} program${programs.length === 1 ? '' : 's'}` +
      `${(res.closed || []).length ? `, ${res.closed.length} open connection(s) closed` : ''}${errs ? `, ${errs} problem(s): see Privacy diagnostics` : ''}.`, errs ? 'err' : 'ok', 5000);
  }
  if (!$('#dialog').hidden && $('#dialog .priv-diag')) await loadFw();
  return r;
}

async function fwRemove({ quiet = false, adopt = false } = {}) {
  PRIV.fwBusy = 'remove'; renderDiagIf();
  let r;
  try { r = await api('firewall/remove', { adopt }); }
  catch (e) { r = { error: e.message }; }
  PRIV.fwBusy = null;
  const n = ((r.result || {}).removed || []).length;
  if (r.error) toast('MTAI\'s firewall rules are still in place: ' + r.error + ' Remove them in Privacy diagnostics.', 'err', 7000);
  else if (n || !quiet) toast(r.gone ? `MTAI's firewall rules were removed (${n}). Checked: none are left.` : 'Some MTAI firewall rules are still there: see Privacy diagnostics.', r.gone ? 'ok' : 'err', 5000);
  if (!$('#dialog').hidden && $('#dialog .priv-diag')) await loadFw();
  return r;
}

async function loadFw() {
  try { PRIV.fw = await api('firewall'); } catch (e) { PRIV.fw = { error: e.message }; }
  if (PRIV.fw && PRIV.fw.backends && !PRIV.fwSel) {
    const want = new Set(((PRIV.fw.settings || {}).programs || []).map(p => p.toLowerCase()));
    PRIV.fwSel = new Set();
    for (const b of PRIV.fw.backends) for (const e of b.exes)
      if (e.selectable && (want.size ? want.has(e.path.toLowerCase()) : e.default) || e.restricted) PRIV.fwSel.add(e.path);
  }
  renderDiagIf();
}
const renderDiagIf = () => { if (!$('#dialog').hidden && $('#dialog .priv-diag')) renderDiag(); };

const PRIV = { stat: null, running: null, fw: null, fwSel: null, fwBusy: null, fwConsent: false, fwTest: null };
const _partly = c => {
  const n = c.UNPROTECTED || 0, u = c.UNVERIFIED || 0;
  return (n ? `, ${n} part${n === 1 ? ' is' : 's are'} not protected (local AI programs without firewall rules)` : '') +
    (u ? `, ${u} check${u === 1 ? '' : 's'} could not be confirmed` : '');
};
const _hm = t => t ? new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

function privacyLine() {
  const st = PRIV.stat || {}, c = (st.last && st.last.counts) || {};
  const more = `<button class="fn-link" data-act="privacy-diag">Details</button>`;
  switch (st.level) {
    case 'verified': return `Privacy mode, checked ${_hm(st.last.t)}: MTAI, its browser, code runs${(st.components || []).some(x => x.backend) ? ' and the local AI programs' : ''} cannot reach the internet. ${more}`;
    case 'partly': return `Privacy mode, checked ${_hm(st.last.t)}: nothing got through${_partly(c)}. ${more}`;
    case 'failed': return `Privacy mode: ${c.FAIL} check${c.FAIL === 1 ? '' : 's'} failed, something may reach the internet. ${more}`;
    case 'checking': return 'Privacy mode: checking that MTAI is offline…';
    default: return `Privacy mode: MTAI blocks the internet. Not checked yet. ${more}`;
  }
}

function updatePrivacyUI(animate) {
  const on = privacyOn(), chip = $('#privChip'), lv = on ? (PRIV.stat && PRIV.stat.level) || 'unchecked' : 'off';
  chip.classList.toggle('on', on);
  for (const k of ['verified', 'partly', 'failed', 'checking']) chip.classList.toggle('v-' + k, on && lv === k);
  chip.title = !on ? 'Privacy mode: block everything that uses the internet'
    : lv === 'verified' ? `Privacy mode is on, checked ${_hm(PRIV.stat.last.t)}: nothing got through (click to turn off)`
    : lv === 'failed' ? 'Privacy mode is on, but a check failed (see Details below the message box)'
    : 'Privacy mode is on (click to turn off)';
  chip.querySelector('.pc-shield').innerHTML = icon(on ? 'shieldOn' : 'shield', 15);
  document.body.classList.toggle('private', on);
  if (animate) { chip.classList.remove('land'); void chip.offsetWidth; chip.classList.add('land'); }
  const sw = $('#setPrivacy'); if (sw) sw.checked = on;
  updateToolUI();
  if (!$('#modal').hidden && S.modalTab === 'download') renderModal();
}

/* ---- the animation: icons pop up one by one, then a slash draws through each and they go dark
   (turning off: the slashes wipe away and the icons light up again) */
function playPrivacyFx(on, atExit) {
  return new Promise(res => {
    const fx = document.createElement('div');
    fx.className = 'pfx ' + (on ? 'pfx-on' : 'pfx-off');
    fx.innerHTML = `<div class="pfx-card">
      <div class="pfx-shield"><svg viewBox="0 0 24 24" width="76" height="76" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path class="sh-body" pathLength="1" d="M12 3l7.5 3v5.6c0 4.6-3.1 8.1-7.5 9.4-4.4-1.3-7.5-4.8-7.5-9.4V6z"/>
        <path class="sh-check" pathLength="1" d="M8.8 12.2l2.3 2.3 4.2-4.4"/></svg><i class="pfx-ring"></i><i class="pfx-ring r2"></i></div>
      <div class="pfx-title">${on ? 'Privacy mode on' : 'Privacy mode off'}</div>
      <div class="pfx-sub">${on ? 'MTAI goes offline. The block is checked next' : 'Web features are available again'}</div>
      <div class="pfx-row">${PRIV_ITEMS.map((it, i) => `<div class="pfx-it" style="--i:${i}"><div class="pfx-ic">${icon(it.icon, 26)}
        <svg class="pfx-x" viewBox="0 0 48 48"><line pathLength="1" x1="9" y1="39" x2="39" y2="9"/></svg></div><span>${it.name}</span></div>`).join('')}</div>
      <div class="pfx-skip">Click to skip</div></div>`;
    document.body.append(fx);
    const reduced = (typeof animLevel === 'function' ? animLevel() : 2) <= 1;     // Appearance > Animations: none or reduced
    let ended = false, scene = null;
    const end = () => {
      if (ended) return; ended = true;
      clearTimeout(timer); document.removeEventListener('keydown', key, true);
      scene && scene.stop();
      fx.classList.add('out'); atExit && atExit();
      setTimeout(() => { fx.remove(); res(); }, reduced ? 10 : 420);
    };
    const key = e => { if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); end(); } };
    document.addEventListener('keydown', key, true);
    fx.onclick = end;
    requestAnimationFrame(() => requestAnimationFrame(() => fx.classList.add('show')));
    // turning on: after the icons, a second scene where data tries to leave and the logo drags it back
    const timer = setTimeout(() => {
      if (!on || reduced || ended) return end();
      fx.classList.add('scene2');
      scene = blockScene(fx, end);
    }, reduced ? 900 : on ? 2700 : 2500);
  });
}

/* Scene 2 of turning privacy on (canvas): chips of data fly out of the MTAI logo, hit a shield ring,
   and the logo throws a tether at each one and reels it back in. Purely visual. */
function blockScene(fx, done) {
  const cv = document.createElement('canvas'), ui = document.createElement('div');
  cv.className = 'pbk-cv'; ui.className = 'pbk-ui';
  ui.innerHTML = `<div class="pbk-title">Held at the edge</div><div class="pbk-sub">MTAI blocks its own way out and pulls the data back · <b class="pbk-n">0</b> caught</div><div class="pfx-skip">Click to skip</div>`;
  fx.append(cv, ui);
  const ctx = cv.getContext('2d'), css = getComputedStyle(document.documentElement);
  const C = k => (css.getPropertyValue(k) || '').trim();
  const col = { a: C('--accent') || '#8b5cf6', al: C('--accent-l') || '#a78bfa', a2: C('--accent2') || '#c084fc', a2l: C('--accent2-l') || '#f0abfc',
    deep: C('--deep') || '#7c3aed', bg: C('--bg') || '#07060b', err: C('--err') || '#fb7185', text: C('--text') || '#f4f0ff' };
  const mono = C('--mono') || 'Consolas, monospace';
  let W, H, cx, cy, R, dpr;
  const size = () => {
    dpr = Math.min(2, devicePixelRatio || 1); W = innerWidth; H = innerHeight;
    cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx = W / 2; cy = H / 2 - 20; R = Math.max(120, Math.min(230, Math.min(W, H) * 0.27));
  };
  size(); addEventListener('resize', size);
  const LABELS = ['chat', '01101', '{ }', 'img', 'key', 'msg', 'file', '0x7F', '@', 'txt', 'pdf', 'json', 'name', '1010', 'cookie', 'code'];
  const N = 20, packets = [], ripples = [], sparks = [];
  for (let i = 0; i < N; i++) {
    const ang = (i / N) * Math.PI * 2 + (Math.random() - .5) * .5;
    packets.push({ ang, label: LABELS[i % LABELS.length], t0: 0.35 + (i * 0.083) + Math.random() * 0.12, speed: 340 + Math.random() * 220,
      wob: (Math.random() - .5) * 0.9, state: 'wait', r: 0, trail: [], hue: i % 2 });
  }
  let caught = 0, pulse = 0, finale = -1, raf = 0, stopped = false;
  const nEl = ui.querySelector('.pbk-n');
  const ease = t => 1 - Math.pow(1 - t, 3), backIn = t => t * t * (2.7 * t - 1.7);
  const T0 = performance.now();
  const rr = (x, y, w, h, r) => { ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, h, r) : ctx.rect(x, y, w, h); };

  function logo(s) {
    const w = 78 * s;
    ctx.save(); ctx.translate(cx, cy);
    ctx.shadowColor = col.a; ctx.shadowBlur = 40 + pulse * 50;
    let g;
    if (ctx.createConicGradient) { g = ctx.createConicGradient(3.5 + performance.now() / 1400, 0, 0); [col.deep, col.a2, col.a2l, col.a, col.deep].forEach((c, i) => g.addColorStop(i / 4, c)); }
    else g = col.a;
    ctx.fillStyle = g; rr(-w / 2, -w / 2, w, w, w * 0.34); ctx.fill();
    ctx.shadowBlur = 0; ctx.globalAlpha = .85; ctx.fillStyle = col.bg;
    const iw = w * 0.46; rr(-iw / 2, -iw / 2, iw, iw, iw * 0.3); ctx.fill();
    ctx.globalAlpha = 1; ctx.restore();
  }

  function ring(t) {
    const grow = ease(Math.min(1, t / 0.5));
    ctx.save(); ctx.translate(cx, cy);
    // soft field inside the ring
    const fg = ctx.createRadialGradient(0, 0, R * .2, 0, 0, R);
    fg.addColorStop(0, 'rgba(0,0,0,0)'); fg.addColorStop(1, hexA(col.a, .10 * grow + (finale >= 0 ? .12 * Math.max(0, 1 - (t - finale) / .6) : 0)));
    ctx.fillStyle = fg; ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();
    // dashed shield ring, slowly turning
    ctx.rotate(t * 0.35);
    ctx.lineWidth = 2.2; ctx.strokeStyle = hexA(col.al, .55 * grow); ctx.setLineDash([14, 9]);
    ctx.shadowColor = col.a; ctx.shadowBlur = 14;
    ctx.beginPath(); ctx.arc(0, 0, R, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * grow); ctx.stroke();
    ctx.setLineDash([]); ctx.rotate(-t * 0.35);
    // impact glow on the ring
    for (const p of ripples) {
      const k = (t - p.t) / 0.55; if (k > 1) continue;
      ctx.strokeStyle = hexA(col.err, (1 - k) * .95); ctx.lineWidth = 4 * (1 - k) + 1; ctx.shadowColor = col.err; ctx.shadowBlur = 20;
      ctx.beginPath(); ctx.arc(0, 0, R, p.ang - .28 - k * .2, p.ang + .28 + k * .2); ctx.stroke();
      ctx.strokeStyle = hexA(col.al, (1 - k) * .5); ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(Math.cos(p.ang) * R, Math.sin(p.ang) * R, 6 + k * 34, 0, Math.PI * 2); ctx.stroke();
    }
    if (finale >= 0) {
      const k = (t - finale) / 0.8;
      if (k < 1) { ctx.strokeStyle = hexA(col.al, 1 - k); ctx.lineWidth = 3; ctx.shadowBlur = 24; ctx.beginPath(); ctx.arc(0, 0, R + k * 60, 0, Math.PI * 2); ctx.stroke(); }
    }
    ctx.restore();
  }

  function chip(x, y, p, alpha, hit) {
    ctx.save(); ctx.translate(x, y); ctx.globalAlpha = alpha;
    ctx.font = `600 10.5px ${mono}`;
    const w = Math.max(30, ctx.measureText(p.label).width + 14), h = 19;
    const c = hit ? col.err : (p.hue ? col.a2l : col.al);
    ctx.shadowColor = c; ctx.shadowBlur = 12;
    ctx.fillStyle = hexA(col.bg, .82); rr(-w / 2, -h / 2, w, h, 6); ctx.fill();
    ctx.strokeStyle = c; ctx.lineWidth = 1.3; ctx.stroke();
    ctx.shadowBlur = 0; ctx.fillStyle = c; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(p.label, 0, 0.5);
    ctx.restore();
  }

  function tether(x, y, k, ang) {
    // a wavy glowing line from the logo to the caught chip
    const mx = (cx + x) / 2, my = (cy + y) / 2, nx = -(y - cy), ny = x - cx, L = Math.hypot(nx, ny) || 1;
    const bend = Math.sin(performance.now() / 70 + ang * 3) * 14 * (1 - k) + 18 * (1 - k);
    ctx.save(); ctx.strokeStyle = hexA(col.a2l, .9); ctx.lineWidth = 2; ctx.shadowColor = col.a2; ctx.shadowBlur = 16; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.quadraticCurveTo(mx + nx / L * bend, my + ny / L * bend, x, y); ctx.stroke();
    ctx.restore();
  }

  function frame(now) {
    if (stopped) return;
    const t = (now - T0) / 1000;
    ctx.clearRect(0, 0, W, H);
    pulse *= 0.9;
    ring(t);
    let active = 0;
    for (const p of packets) {
      if (t < p.t0) { active++; continue; }
      const dt = t - p.t0;
      let x, y, alpha = 1, hit = false;
      if (p.state === 'wait') p.state = 'out';
      if (p.state === 'out') {
        p.r = 48 + p.speed * dt + 260 * dt * dt;
        const a = p.ang + p.wob * Math.min(1, dt * 2) * 0.25;
        if (p.r >= R - 4) { p.r = R - 4; p.state = 'hit'; p.th = t; p.ha = a; ripples.push({ ang: a, t });
          for (let s = 0; s < 9; s++) sparks.push({ x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R, vx: (Math.random() - .5) * 160 - Math.cos(a) * 90, vy: (Math.random() - .5) * 160 - Math.sin(a) * 90, t }); }
        p.a = a;
      }
      if (p.state === 'hit') {
        const k = (t - p.th) / 0.17;
        p.r = R - 4 - Math.sin(Math.min(1, k) * Math.PI) * 10; hit = true;
        if (k >= 1) { p.state = 'drag'; p.td = t; }
      }
      if (p.state === 'drag') {
        const k = Math.min(1, (t - p.td) / 0.72);
        p.r = (R - 4) * (1 - backIn(k)) + 20 * backIn(k);
        p.a = p.ha + Math.sin(k * Math.PI) * 0.35 * (p.hue ? 1 : -1);
        hit = k < 0.25;
        if (k >= 1) { p.state = 'in'; caught++; pulse = 1; nEl.textContent = caught; nEl.classList.remove('bump'); void nEl.offsetWidth; nEl.classList.add('bump'); }
      }
      if (p.state === 'in') continue;
      active++;
      x = cx + Math.cos(p.a) * p.r; y = cy + Math.sin(p.a) * p.r;
      p.trail.push([x, y]); if (p.trail.length > 9) p.trail.shift();
      if (p.state === 'drag') tether(x, y, (t - p.td) / 0.72, p.ang);
      for (let i = 0; i < p.trail.length - 1; i++) {        // motion trail
        const [tx, ty] = p.trail[i];
        ctx.fillStyle = hexA(p.state === 'out' ? col.al : col.a2l, (i / p.trail.length) * .35);
        ctx.beginPath(); ctx.arc(tx, ty, 2.2, 0, Math.PI * 2); ctx.fill();
      }
      if (p.state === 'drag') alpha = 1 - Math.max(0, ((t - p.td) / 0.72 - .8) / .2);
      chip(x, y, p, alpha, hit);
    }
    for (let i = sparks.length - 1; i >= 0; i--) {
      const s = sparks[i], k = (t - s.t) / 0.5;
      if (k > 1) { sparks.splice(i, 1); continue; }
      const px = s.x + s.vx * (t - s.t), py = s.y + s.vy * (t - s.t);
      ctx.fillStyle = hexA(k < .4 ? col.err : col.al, 1 - k); ctx.beginPath(); ctx.arc(px, py, 2 * (1 - k) + .6, 0, Math.PI * 2); ctx.fill();
    }
    logo(1 + pulse * 0.13 + Math.sin(t * 3) * 0.015);
    if (!active && finale < 0) finale = t;
    if (finale >= 0 && t - finale > 0.95) return finish();
    raf = requestAnimationFrame(frame);
  }
  function finish() { stop(); done(); }
  function stop() { stopped = true; cancelAnimationFrame(raf); removeEventListener('resize', size); }
  raf = requestAnimationFrame(frame);
  return { stop };
}

function hexA(c, a) {
  const m = /^#([0-9a-f]{6})$/i.exec(c);
  if (!m) return c;
  const n = parseInt(m[1], 16);
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
}

/* ---- self-test probes for this browser. Each one tries a harmless public test host; the backend
   grades them against the gate's own log, so a probe only counts as blocked when the gate (or the
   preview's CSP) is seen refusing it. Nothing from the user is sent. */
const PROBE_JS = String.raw`
async function mtaiProbes(where) {
  const tag = 'mtai-selftest-' + Math.random().toString(36).slice(2, 8), csp = [];
  addEventListener('securitypolicyviolation', e => csp.push(e.blockedURI + ' (' + e.effectiveDirective + ')'));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const el = (tag_, url) => new Promise((res, rej) => { const n = document.createElement(tag_); const t = setTimeout(() => { n.remove(); rej(new Error('timeout')); }, 9000);
    n.onload = () => { clearTimeout(t); n.remove(); res('loaded'); }; n.onerror = () => { clearTimeout(t); n.remove(); rej(new Error('error event')); };
    n.src = url; if (tag_ === 'iframe') n.style.display = 'none'; document.body.append(n); });
  const run = (id, name, host, fn, flags) => { const t0 = Date.now();
    return fn().then(d => ({ id, name, host, where, t0, t1: Date.now(), ok: !(flags && flags.gateOnly), detail: String(d), ...flags }),
      e => ({ id, name, host, where, t0, t1: Date.now(), ok: false, detail: String(e && e.message || e), ...flags })); };
  const P = await Promise.all([
    run('fetch', 'fetch()', 'example.com', () => fetch('https://example.com/?' + tag, { mode: 'no-cors', cache: 'no-store' }).then(r => 'response ' + r.type)),
    run('xhr', 'XMLHttpRequest', 'example.net', () => new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', 'https://example.net/?' + tag);
      x.timeout = 9000; x.onload = () => res('status ' + x.status); x.onerror = () => rej(new Error('network error')); x.ontimeout = () => rej(new Error('timeout')); x.send(); }), { gateOnly: true }),
    run('ws', 'WebSocket', 'echo.websocket.org', () => new Promise((res, rej) => { const w = new WebSocket('wss://echo.websocket.org/');
      const t = setTimeout(() => { try { w.close(); } catch (e) {} rej(new Error('timeout')); }, 9000);
      w.onopen = () => { clearTimeout(t); w.close(); res('open'); }; w.onerror = () => { clearTimeout(t); rej(new Error('error event')); }; })),
    run('img', 'Image', 'example.org', () => el('img', 'https://example.org/favicon.ico?' + tag), { gateOnly: true }),
    run('script', 'Script tag', 'www.example.com', () => el('script', 'https://www.example.com/selftest.js?' + tag), { gateOnly: true }),
    run('iframe', 'Iframe', 'www.iana.org', () => el('iframe', 'https://www.iana.org/?' + tag), { gateOnly: true }),
    run('beacon', 'sendBeacon', 'www.example.net', async () => { const q = navigator.sendBeacon('https://www.example.net/?' + tag, 'selftest'); await sleep(1500); return q ? 'queued' : 'refused'; }, { gateOnly: true }),
    run('webrtc', 'WebRTC UDP (STUN)', 'stun.l.google.com', async () => {
      const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] }), c = [];
      pc.onicecandidate = e => e.candidate && c.push(e.candidate.candidate); pc.createDataChannel('x');
      await pc.setLocalDescription(await pc.createOffer()); await sleep(3500); pc.close();
      const pub = c.filter(x => / typ srflx /.test(x));
      if (pub.length) return 'learned a public address over UDP';
      throw new Error('no public address learned (' + c.length + ' local candidates)'); }, { never_proxied: true }),
  ]);
  await sleep(300);
  for (const p of P) { const hit = csp.find(u => u.includes(p.host)); if (hit) p.csp = hit; }
  return P;
}`;
(0, eval)(PROBE_JS);                                       // defines window.mtaiProbes for this page

function previewProbes() {
  return new Promise(async res => {
    let r; try { r = await api('preview', { html: `<!doctype html><meta charset="utf-8"><body><script>${PROBE_JS}
      mtaiProbes('preview').then(p => parent.postMessage({ __mtaiProbe: p }, '*'));<\/script></body>` }); }
    catch (e) { res([]); return; }
    const f = document.createElement('iframe');
    f.setAttribute('sandbox', $('#pvFrame').getAttribute('sandbox'));
    f.style.cssText = 'position:fixed;width:1px;height:1px;left:-9px;top:-9px;opacity:0;pointer-events:none';
    const done = v => { removeEventListener('message', on); f.remove(); clearTimeout(t); res(v); };
    const on = e => { if (e.source === f.contentWindow && e.data && e.data.__mtaiProbe) done(e.data.__mtaiProbe); };
    const t = setTimeout(() => done([]), 20000);
    addEventListener('message', on);
    f.src = r.url; document.body.append(f);
  });
}

async function privacyVerify({ quiet = true } = {}) {
  if (PRIV.running) return PRIV.running;
  PRIV.running = (async () => {
    if (privacyOn()) { PRIV.stat = { ...(PRIV.stat || {}), level: 'checking' }; updatePrivacyUI(false); }
    const since = Date.now();
    let probes = [];
    // one after the other, so the gate's log for a host can only belong to one of them
    try { probes = [...await window.mtaiProbes('page'), ...await previewProbes()]; } catch (e) {}
    try {
      await api('privacy/verify', { browser: { since, probes } });
      PRIV.stat = await api('privacy');
    } catch (e) { toast('The privacy check did not run: ' + e.message, 'err'); }
    updatePrivacyUI(false);
    if (!$('#dialog').hidden && $('#dialog .priv-diag')) renderDiag();
    const st = PRIV.stat || {}, c = (st.last && st.last.counts) || {};
    if (!quiet && st.on) {
      if (st.level === 'verified') toast(`Privacy mode checked: all ${c.PASS} attempts to reach the internet were blocked.`, 'ok', 4200);
      else if (st.level === 'failed') toast(`Privacy check: ${c.FAIL} attempt${c.FAIL === 1 ? '' : 's'} got through. Open Details below the message box.`, 'err', 6000);
      else toast(`Privacy mode checked: nothing got through${_partly(c)}.`, 'info', 5200);
    }
    return st;
  })();
  try { return await PRIV.running; } finally { PRIV.running = null; }
}

/* ---- diagnostics page */
const KIND_NAMES = { connect: 'Connection', dns: 'DNS lookup', udp: 'UDP data', bind: 'Listening', process: 'Program start', open: 'Open link/file', browser: 'Browser request' };

async function openDiag() {
  const d = $('#dialog');
  d.innerHTML = `<div class="dialog priv-diag"><div class="pdg-load"><span class="spin"></span>Loading privacy diagnostics…</div></div>`;
  d.hidden = false;
  const key = e => { if (e.key === 'Escape' && !d.hidden && d.querySelector('.priv-diag')) { e.stopPropagation(); close(); } };
  const close = () => { d.hidden = true; d.onclick = null; d.onchange = null; document.removeEventListener('keydown', key, true); };
  document.addEventListener('keydown', key, true);
  d.onclick = async e => {
    const b = e.target.closest('[data-pd]');
    if (e.target === d || (b && b.dataset.pd === 'close')) return close();
    if (!b) { const g = e.target.closest('.pdg-gh'); if (g) g.parentElement.classList.toggle('open'); return; }
    if (b.dataset.pd === 'run') {
      if (!privacyOn() && !confirm('With privacy mode off, the check really connects to public test sites (example.com, 1.1.1.1, echo.websocket.org) to show that normal internet works again. Nothing of yours is sent. Run it?')) return;
      b.disabled = true; b.innerHTML = '<span class="spin"></span>Checking…'; await privacyVerify({ quiet: true }); return;
    }
    if (b.dataset.pd === 'clear') { await api('privacy/clear', {}); PRIV.stat = await api('privacy'); renderDiag(); return; }
    if (b.dataset.pd === 'toggle') { close(); setPrivacy(!privacyOn()); }
    if (PRIV.fwBusy) return;
    if (b.dataset.pd === 'fw-refresh') { PRIV.fw = null; renderDiag(); return loadFw(); }
    if (b.dataset.pd === 'fw-apply') { if (PRIV.fwSel && PRIV.fwSel.size) { PRIV.fwConsent = true; renderDiag(); d.querySelector('.dialog').scrollTop = 0; } return; }
    if (b.dataset.pd === 'fw-rt-on' || b.dataset.pd === 'fw-rt-off') {
      const en = b.dataset.pd === 'fw-rt-on';
      if (en && !confirm('MTAI copies the WebView2 runtime (about 900 MB) into its data folder and runs its window from that copy from the next start. Nothing in Windows is changed. Continue?')) return;
      try { const r = await api('browser-runtime', { enable: en }); S.settings.firewall = { ...(S.settings.firewall || {}), private_browser: en }; if ((r.errors || []).length) toast(r.errors.join(' '), 'err'); }
      catch (err) { toast(err.message, 'err'); }
      return loadFw();
    }
    if (b.dataset.pd === 'fw-cancel') { PRIV.fwConsent = false; return renderDiag(); }
    if (b.dataset.pd === 'fw-ok') {
      const auto = !!(d.querySelector('#fwAuto') || {}).checked;
      PRIV.fwConsent = false;
      S.settings.firewall = { ...(S.settings.firewall || {}), programs: [...PRIV.fwSel], auto };
      await fwApply([...PRIV.fwSel], auto);
      if (privacyOn()) privacyVerify({ quiet: true });
      return;
    }
    if (b.dataset.pd === 'fw-remove') {
      if (!confirm('Remove all of MTAI\'s Windows Firewall rules? Windows asks for administrator permission. Rules of other programs are not touched.')) return;
      await fwRemove({ adopt: true });
      if (privacyOn()) privacyVerify({ quiet: true });
      return;
    }
    if (b.dataset.pd === 'fw-test') {
      PRIV.fwBusy = 'test'; renderDiag();
      try { PRIV.fwTest = (await api('firewall/test', {})).rows; } catch (e) { toast(e.message, 'err'); }
      PRIV.fwBusy = null; renderDiag();
    }
  };
  d.onchange = e => {
    const c = e.target.closest('[data-fwp]');
    if (c && PRIV.fwSel) { c.checked ? PRIV.fwSel.add(c.dataset.fwp) : PRIV.fwSel.delete(c.dataset.fwp); renderDiag(); }
    if (e.target.id === 'fwAutoSet') {
      S.settings.firewall = { ...(S.settings.firewall || {}), auto: e.target.checked };
      api('settings', S.settings).catch(err => toast(err.message, 'err'));
    }
  };
  PRIV.fwConsent = false; PRIV.fwTest = null;
  try { PRIV.stat = await api('privacy'); } catch (e) { toast(e.message, 'err'); return close(); }
  renderDiag();
  loadFw();
}

/* the Local AI programs section: what was found, exactly which files, and what Windows has */
function fwSection() {
  const fw = PRIV.fw, on = privacyOn();
  const head = `<h4>Local AI programs (Windows Firewall) <span>${fw && fw.watch && fw.watch.on ? `connection watcher on, ${fw.watch.samples} looks` : 'connection watcher runs while privacy mode is on'} · <button class="fn-link" data-pd="fw-refresh">look again</button></span></h4>`;
  if (!fw) return `<section>${head}<div class="pdg-load"><span class="spin"></span>Looking for Ollama, LM Studio, llama.cpp, ComfyUI and others…</div></section>`;
  if (fw.error) return `<section>${head}<p class="pdg-none">Could not look: ${esc(fw.error)}</p></section>`;
  const st = fw.status || {}, busy = PRIV.fwBusy;
  const mine = (st.ledger || []).filter(e => !e.probe);
  const fwState = st.error ? `<div class="fw-note bad">${icon('alert', 15)}<span>Could not read Windows Firewall: ${esc(st.error)}</span></div>`
    : st.firewall_on ? `<div class="fw-note ok">${icon('check', 15)}<span>Windows Firewall is on for the active network (${esc((st.categories || []).join(', ') || '?')}) and applies local rules.</span></div>`
    : `<div class="fw-note bad">${icon('alert', 15)}<span>Windows Firewall is off for the active network, or a policy ignores local rules: firewall rules would do nothing. MTAI does not change that setting.</span></div>`;
  const leftover = fw.leftover ? `<div class="fw-note warn">${icon('alert', 15)}<span>MTAI firewall rules are still in place although privacy mode is off (MTAI was closed or the administrator prompt was declined). <button class="fn-link" data-pd="fw-remove">Remove them</button></span></div>` : '';
  const strangers = (st.unknown_group_rules || []).length ? `<div class="fw-note warn">${icon('info', 15)}<span>${st.unknown_group_rules.length} rule(s) in the "MTAI Privacy" group are not in MTAI's list (its data folder was reset?): ${esc(st.unknown_group_rules.join(', '))}. "Remove MTAI firewall rules" removes them too.</span></div>` : '';
  const progs = (fw.backends || []).map(b => `<div class="fw-b"><div class="fw-bh"><b>${esc(b.name)}</b><i class="${b.running ? 'run' : ''}">${b.running ? 'running' : 'not running'}</i></div>
    ${b.exes.map(e => `<label class="fw-e ${e.selectable ? '' : 'dis'}"><input type="checkbox" data-fwp="${esc(e.path)}" ${PRIV.fwSel && PRIV.fwSel.has(e.path) ? 'checked' : ''} ${e.selectable && !busy ? '' : 'disabled'}>
      <div><code>${esc(e.path)}</code><small>${esc(e.sources.join(' · '))}${e.pids.length ? ` · process ${e.pids.join(', ')}` : ''}${e.note ? ' · ' + esc(e.note) : ''}</small></div>
      <em class="${e.restricted ? 'ok' : e.selectable ? 'no' : 'na'}">${e.restricted ? 'blocked' : e.selectable ? 'not blocked' : 'not restricted'}</em></label>`).join('')}</div>`).join('')
    || '<p class="pdg-none">No local AI program found on this PC (MTAI looked at running programs, listening ports, PATH and installed programs).</p>';
  const ev = (fw.events || []).slice().reverse();
  const evs = ev.length ? `<div class="pdg-log">${ev.slice(0, 60).map(x => `<div><time>${new Date(x.t * 1000).toLocaleTimeString()}</time><em>${esc(x.kind)}</em><span>${esc(x.remote || x.exe || '')}</span><small>${esc(x.name || '')}${x.who ? ' · ' + esc(x.who) : ''}${x.restricted ? ' · restricted' : ''}</small></div>`).join('')}</div>`
    : `<p class="pdg-none">${on ? 'The connection watcher has seen no outside connection from MTAI or the restricted programs, and no unrestricted program they started.' : 'Turn privacy mode on to watch connections.'}</p>`;
  const sel = PRIV.fwSel ? PRIV.fwSel.size : 0;
  const tests = PRIV.fwTest ? `<div class="pdg-g open"><button class="pdg-gh"><span>Firewall test (just now)</span>${icon('chev', 13)}</button><div class="pdg-gb">${PRIV.fwTest.map(_resRow).join('')}</div></div>` : '';
  const autoSet = (S.settings.firewall || {}).programs ? `<label class="fw-auto"><input type="checkbox" id="fwAutoSet" ${(S.settings.firewall || {}).auto ? 'checked' : ''}> Add these rules every time privacy mode turns on (Windows asks each time). They are always removed when it turns off.</label>` : '';
  const rt = fw.runtime || {}, job = rt.job || {};
  let rtBody;
  if (rt.browser !== 'webview2') rtBody = `<span>MTAI's window is not WebView2 here (${esc(rt.browser || '?')}), so it cannot get its own copy.</span>`;
  else if (job.running) rtBody = `<span><span class="spin"></span> Copying WebView2 ${esc(job.version || '')}: ${job.done} of ${job.total || '…'} files.</span>`;
  else if (job.error) rtBody = `<span>The copy failed: ${esc(job.error)} <button class="fn-link" data-pd="fw-rt-on">Try again</button></span>`;
  else if (!rt.enabled) rtBody = `<span>WebView2 has Microsoft sign-in code that goes around MTAI's gate (it uses Windows' own networking). The shared WebView2 cannot be firewalled without cutting off other programs. MTAI can run its window from its own copy (${rt.size_mb ? rt.size_mb + ' MB' : 'about 900 MB'} in its data folder, nothing in Windows changes) and then block that copy here. <button class="fn-link" data-pd="fw-rt-on">Make the copy</button></span>`;
  else if (rt.in_use) rtBody = `<span>MTAI's window runs from its own WebView2 copy (${esc((rt.current || {}).version || '')}). Tick it below to block it outside this PC.${rt.outdated ? ' A newer WebView2 is installed: MTAI copies it and switches at the next start.' : ''} <button class="fn-link" data-pd="fw-rt-off">Stop using the copy</button></span>`;
  else if (rt.current) rtBody = `<span>The copy is ready (${esc(rt.current.version)}). Restart MTAI to run its window from it. <button class="fn-link" data-pd="fw-rt-off">Do not use it</button></span>`;
  else rtBody = `<span>Waiting for the copy… <button class="fn-link" data-pd="fw-rt-on">Start it</button></span>`;
  if (job.running && !PRIV.fwPoll) PRIV.fwPoll = setTimeout(() => { PRIV.fwPoll = null; if (!$('#dialog').hidden && $('#dialog .priv-diag')) loadFw(); }, 2000);
  return `<section>${head}
    <div class="fw-note ${rt.in_use ? 'ok' : 'warn'}">${icon(rt.in_use ? 'check' : 'info', 15)}<span><b>MTAI's own browser.</b> ${rtBody}</span></div>
    <p class="pdg-note fw-intro">These are separate programs; MTAI's own block does not reach them. MTAI can ask Windows Firewall to block their internet access (everything except 127.0.0.1 and ::1, so MTAI can still use them). Only the files ticked here, only while privacy mode is on.</p>
    ${fwState}${leftover}${strangers}<div class="fw-list">${progs}</div>
    <div class="pdg-acts fw-acts">
      <button class="btn primary small" data-pd="fw-apply" ${on && sel && !busy && st.firewall_on !== false ? '' : 'disabled'}>${busy === 'apply' ? '<span class="spin"></span>Waiting for Windows…' : icon('shieldOn', 14) + `Block ${sel} selected program${sel === 1 ? '' : 's'}…`}</button>
      <button class="btn ghost small" data-pd="fw-test" ${mine.length && !busy ? '' : 'disabled'}>${busy === 'test' ? '<span class="spin"></span>Testing…' : icon('refresh', 14) + 'Test the rules'}</button>
      <button class="btn ghost small" data-pd="fw-remove" ${(st.ledger || []).length || (st.unknown_group_rules || []).length ? '' : 'disabled'}>${busy === 'remove' ? '<span class="spin"></span>Waiting for Windows…' : icon('x', 14) + 'Remove MTAI firewall rules'}</button></div>
    ${on ? '' : '<p class="pdg-note">Turn privacy mode on to add rules. They are only in place while it is on.</p>'}
    ${autoSet}${tests}
    <h4 class="fw-sub">Seen by the connection watcher</h4>${evs}
    ${mine.length ? `<p class="pdg-note">MTAI's rules now (${esc(fw.group)} group): ${mine.map(e => `${esc(e.name)} = ${esc(e.program)} ${e.ok ? '(in force)' : e.present ? '(present, but not as MTAI made it)' : '(missing)'}`).join('; ')}.</p>` : ''}
  </section>`;
}

/* consent: exactly what MTAI will ask Windows to do, and how to undo it */
function fwConsentView() {
  const fw = PRIV.fw || {}, progs = [...(PRIV.fwSel || [])];
  const name = p => { for (const b of fw.backends || []) for (const e of b.exes) if (e.path === p) return e.rule; return ''; };
  return `<div class="pdg-head warn"><span class="pd-shield">${icon('shieldOn', 26)}</span>
      <div><h3>Block these programs in Windows Firewall?</h3><p>MTAI asks Windows to add one rule per program. Windows then shows an administrator prompt; nothing changes if you say No there.</p></div></div>
    <section><h4>Programs that lose internet access</h4><div class="fw-cons">${progs.map(p => `<div><code>${esc(p)}</code><small>rule ${esc(name(p))}</small></div>`).join('')}
      <div><code>${esc(fw.probe && fw.probe.path)}</code><small>rule ${esc(fw.probe && fw.probe.rule)} · a copy of Windows' curl.exe that MTAI uses to test the rule on this PC</small></div></div></section>
    <section><h4>What the rules do</h4><ul class="pdg-lim">
      <li>Outbound, Block, all network types, group "${esc(fw.group)}". Remote addresses: ${esc((fw.remote || []).join(', '))}. That is everything except 127.0.0.0/8 and ::1, so MTAI keeps talking to them on this PC.</li>
      <li>Open connections of these programs to outside addresses are closed now (IPv4; open IPv6 connections are listed, Windows cannot close them).</li>
      <li>No other firewall rule and no firewall setting is changed. Other programs keep their internet access.</li>
      <li>A program these start under a different file name (a plugin running git.exe, for example) is not covered; the connection watcher reports it.</li></ul></section>
    <section><h4>Undo</h4><ul class="pdg-lim">
      <li>The rules are removed when privacy mode turns off (Windows asks again), or any time with "Remove MTAI firewall rules".</li>
      <li>MTAI writes each rule name down before Windows is asked (data\\firewall-rules.json), so they can be removed after a crash too. It only ever removes rules with its own name and group.</li>
      <li>By hand: Windows Defender Firewall with Advanced Security, Outbound Rules, group "MTAI Privacy".</li></ul></section>
    <label class="fw-auto"><input type="checkbox" id="fwAuto" ${(S.settings.firewall || {}).auto ? 'checked' : ''}> Also add these rules every time privacy mode turns on (Windows asks each time)</label>
    <div class="d-acts"><button class="btn ghost" data-pd="fw-cancel">Cancel</button>
      <button class="btn primary" data-pd="fw-ok">${icon('shieldOn', 15)}Ask Windows to add ${progs.length + 1} rules</button></div>`;
}

const _resRow = r => `<div class="pdg-r ${r.result.toLowerCase()}"><em>${r.result}</em><div><b>${esc(r.name)}</b><small>${esc(r.detail)}</small></div></div>`;

function renderDiag() {
  const d = $('#dialog'), st = PRIV.stat || {}, last = st.last, on = !!st.on;
  if (!d.querySelector('.priv-diag')) return;
  if (PRIV.fwConsent) { d.querySelector('.priv-diag').innerHTML = fwConsentView(); return; }
  const cc = (last && last.counts) || {};
  const lvText = {
    verified: ['ok', 'Checked: nothing here can reach the internet', `Every required check passed (${_hm(last && last.t)}): MTAI, its browser, code runs${(st.components || []).some(x => x.backend) ? ' and the local AI programs below' : ''}.`],
    partly: ['warn', cc.UNPROTECTED ? 'MTAI is blocked, but not everything is protected' : 'Nothing got through, some checks unconfirmed',
      (cc.UNPROTECTED ? 'A local AI program on this PC can still reach the internet by itself (see Local AI programs). ' : '') +
      (cc.UNVERIFIED ? 'Some checks could not prove the block either way (yellow rows).' : '')],
    failed: ['bad', 'A check failed', 'At least one attempt reached the internet. See the red rows below.'],
    unchecked: ['warn', 'Privacy mode is on, not checked since it was switched on', 'Run the check to prove the block.'],
    checking: ['warn', 'Checking…', ''],
    off: ['off', 'Privacy mode is off', 'MTAI uses the internet when you use web search, cloud models, downloads or links.'],
  }[st.level] || ['off', 'Unknown', ''];
  const groups = {};
  for (const r of (last && last.results) || []) (groups[r.group] = groups[r.group] || []).push(r);
  const grp = Object.entries(groups).map(([g, rs]) => {
    const n = k => rs.filter(r => r.result === k).length;
    const f = n('FAIL'), u = n('UNVERIFIED'), x = n('UNPROTECTED'), checks = rs.length - n('INFO');
    return `<div class="pdg-g ${f || x ? 'open' : ''}"><button class="pdg-gh"><span>${esc(g)}</span><i class="${f ? 'bad' : x ? 'unp' : u ? 'warn' : 'ok'}">${n('PASS')}/${checks} pass${f ? `, ${f} fail` : ''}${x ? `, ${x} not protected` : ''}${u ? `, ${u} unverified` : ''}</i>${icon('chev', 13)}</button>
      <div class="pdg-gb">${rs.map(_resRow).join('')}</div></div>`;
  }).join('');
  const COMP = { protected: ['on', on ? 'protected' : 'ready'], unprotected: ['unp', 'not protected'], unverified: ['warn', 'unverified'],
    failed: ['no', 'failed'], unchecked: ['warn', 'not checked'], off: ['off', 'off'] };
  const blocked = (st.blocked || []).slice().reverse();
  const c = (last && last.counts) || {};
  const suite = st.suite;
  d.querySelector('.priv-diag').innerHTML = `
    <div class="pdg-head ${lvText[0]}"><span class="pd-shield">${icon(on ? 'shieldOn' : 'shield', 26)}</span>
      <div><h3>${esc(lvText[1])}</h3><p>${esc(lvText[2])}</p></div>
      <button class="icon-btn" data-pd="close" title="Close (Esc)">${icon('x', 16)}</button></div>
    <div class="pdg-acts"><button class="btn primary small" data-pd="run">${icon('refresh', 14)}Run check now</button>
      <button class="btn ghost small" data-pd="toggle">${icon(on ? 'shield' : 'shieldOn', 14)}${on ? 'Turn privacy mode off' : 'Turn privacy mode on'}</button></div>
    <section><h4>Isolation status <span>green only when every required check passed</span></h4><div class="pdg-comp">${(st.components || []).map(x => { const k = COMP[x.state] || COMP.unchecked; return `<div class="${k[0]}">
      <i>${k[1]}</i><b>${esc(x.name)}</b><small>${esc(x.how)}</small></div>`; }).join('')}</div>
      ${(st.live_leaks || []).length ? `<div class="fw-note bad">${icon('alert', 15)}<span>The connection watcher saw outside connections after the last check: ${esc(st.live_leaks.map(e => `${e.name} ${e.remote}`).join(', '))}</span></div>` : ''}</section>
    ${fwSection()}
    <section><h4>Last check ${last ? `<span>${new Date(last.t * 1000).toLocaleString()} · privacy ${last.privacy ? 'on' : 'off'} · ${last.seconds}s${last.browser_probes ? '' : ' · without browser probes'}</span>` : ''}</h4>
      ${last ? `<div class="pdg-counts"><b class="ok">${c.PASS || 0} PASS</b><b class="bad">${c.FAIL || 0} FAIL</b>${c.UNPROTECTED ? `<b class="unp">${c.UNPROTECTED} NOT PROTECTED</b>` : ''}<b class="warn">${c.UNVERIFIED || 0} UNVERIFIED</b>${c.INFO ? `<b class="info">${c.INFO} INFO</b>` : ''}</div>${grp}` : '<p class="pdg-none">No check yet.</p>'}
      <p class="pdg-note">Last fully successful check with privacy on: ${st.last_ok ? new Date(st.last_ok.t * 1000).toLocaleString() : 'none yet'}.
      Full test suite (both modes, real attempts, process network monitor): ${suite ? `${new Date(suite.t * 1000).toLocaleString()}, ${suite.counts.PASS} pass, ${suite.counts.FAIL} fail, ${suite.counts.UNVERIFIED} unverified` : 'not run yet'}. Run it with <code>py tests\\privacy_suite.py</code>.</p></section>
    <section><h4>Blocked attempts <span>${blocked.length} kept${blocked.length ? ` · <button class="fn-link" data-pd="clear">clear</button>` : ''}</span></h4>
      ${blocked.length ? `<div class="pdg-log">${blocked.slice(0, 120).map(e => `<div><time>${new Date(e.t * 1000).toLocaleTimeString()}</time><em>${esc(KIND_NAMES[e.kind] || e.kind)}</em><span>${esc(e.target)}</span><small>${esc(e.component)}</small></div>`).join('')}</div>` : '<p class="pdg-none">Nothing was blocked yet.</p>'}</section>
    <section><h4>Known limitations</h4><ul class="pdg-lim">${(st.limits || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></section>`;
}

function bindPrivacy() {
  $('#privChip').onclick = () => setPrivacy(!privacyOn());
  $('#privChip').oncontextmenu = e => { e.preventDefault(); openDiag(); };
  document.addEventListener('click', e => {
    if (e.target.closest('[data-act="privacy-off"]')) { e.stopPropagation(); setPrivacy(false); }
    if (e.target.closest('[data-act="privacy-diag"]')) { e.stopPropagation(); e.preventDefault(); openDiag(); }
  }, true);
  // the web chips stay clickable while locked, so the click can explain itself
  for (const [id, kind] of [['#webBtn', 'web'], ['#deepBtn', 'deep']]) {
    $(id).addEventListener('click', e => { if (privacyOn()) { e.stopImmediatePropagation(); privacyBlocked(kind); } }, true);
  }
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'l') { e.preventDefault(); setPrivacy(!privacyOn()); }
  });
  // privacy mode was already on when MTAI started: prove the block once the app is up (nothing is sent)
  addEventListener('mtai:ready', () => { if (privacyOn()) setTimeout(() => privacyVerify({ quiet: true }), 1200); });
  api('privacy').then(st => {
    PRIV.stat = st; updatePrivacyUI(false);
    // MTAI was closed (or the prompt declined) while its firewall rules were in place and privacy mode is off now
    if (!st.on && st.fw_rules) setTimeout(() => {
      const t = document.createElement('div');
      t.className = 'toast err';
      t.innerHTML = icon('alert', 17) + `<span>MTAI's Windows Firewall rules from an earlier session are still in place, so some local AI programs stay offline. <button class="fn-link" data-act="privacy-diag">Review and remove</button></span>`;
      $('#toasts').append(t);
      setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, 12000);
    }, 1500);
  }).catch(() => {});
  window.mtaiPrivacy = { verify: privacyVerify, openDiag, probes: () => window.mtaiProbes('page'), previewProbes };
}
