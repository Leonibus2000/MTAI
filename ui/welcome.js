'use strict';
/* MTAI - first start: a welcome card that asks a few preferences (name, language, personality,
   answers, look) and then offers a spotlight tour of the buttons. Every question can be skipped,
   and "Skip all" ends it at any point. settings.onboarded marks it done (finished or skipped);
   Shortcuts (Ctrl+/) > "Show the welcome tour" starts it again.
   Loaded after extras.js and before motion.js. Only window.mtaiWelcome is exported. */
(() => {
  const W = { step: 0, el: null, tour: -1, prevFocus: null };
  const st = () => window.mtaiStyle.styleCfg();
  const save = () => saveSettings();
  const name = () => (st().name || '').trim();

  /* ---------------------------------------------------------------- questions */
  const seg = (key, opts) => `<div class="seg wl-seg" data-wseg="${key}">${opts.map(([v, l]) =>
    `<button data-v="${v}" class="${(st()[key] || '') === v ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  const STEPS = [
    {
      id: 'hello', bare: true,
      html: () => `<div class="wl-orb"><span class="logo"></span></div>
        <h2>Welcome to MTAI</h2>
        <p>Your AI on your own PC. Chats, files and models stay on this machine unless you turn on a web or cloud feature.</p>
        <p class="wl-small">A few quick questions so MTAI fits you, then a short tour. About a minute, and every question can be skipped.</p>
        <div class="wl-acts center"><button class="btn ghost" data-w="skipall">Skip, I know my way</button><button class="btn primary" data-w="next">${icon('spark', 15)}Let's set it up</button></div>`,
    },
    {
      id: 'name', title: 'What should MTAI call you?', sub: 'The AI uses your name now and then, and the start screen greets you with it.',
      html: () => `<input type="text" id="wlName" class="wl-in" maxlength="40" placeholder="Your name or nickname" value="${esc(name())}" spellcheck="false" autocomplete="off">`,
      bind: c => { const i = c.querySelector('#wlName'); i.oninput = () => { st().name = i.value.trim(); save(); }; setTimeout(() => i.focus(), 60); },
    },
    {
      id: 'lang', title: 'Which language should it answer in?', sub: '"Same as my message" answers in whatever language you write.',
      html: () => `<div class="wl-chips">${window.mtaiStyle.LANGS.filter(l => l !== 'other').map(l =>
        `<button class="wl-chip ${(st().lang || '') === l ? 'on' : ''}" data-lang="${l}">${l || 'Same as my message'}</button>`).join('')}</div>`,
      bind: c => c.querySelectorAll('[data-lang]').forEach(b => b.onclick = () => {
        st().lang = b.dataset.lang; save(); c.querySelectorAll('[data-lang]').forEach(x => x.classList.toggle('on', x === b));
      }),
    },
    {
      id: 'persona', title: 'Pick a personality', sub: 'How the AI talks to you. Default is plain and helpful.',
      html: () => `<div class="wl-personas">${window.mtaiStyle.PERSONAS.map(p =>
        `<button class="wl-persona ${(st().persona || 'default') === p.id ? 'on' : ''}" data-persona="${p.id}"><span class="pe">${p.e}</span><span>${p.name}</span></button>`).join('')}</div>`,
      bind: c => c.querySelectorAll('[data-persona]').forEach(b => b.onclick = () => {
        st().persona = b.dataset.persona; save(); c.querySelectorAll('[data-persona]').forEach(x => x.classList.toggle('on', x === b));
      }),
    },
    {
      id: 'answers', title: 'How should answers be?', sub: 'You can fine-tune more later under Chat settings > Style.',
      html: () => window.mtaiStyle.STYLE_OPTS.filter(([k]) => ['length', 'level', 'emoji'].includes(k)).map(([k, label, opts]) =>
        `<div class="wl-row"><span>${label}</span>${seg(k, opts)}</div>`).join(''),
      bind: c => c.querySelectorAll('[data-wseg]').forEach(s => s.onclick = e => {
        const b = e.target.closest('[data-v]'); if (!b) return;
        st()[s.dataset.wseg] = b.dataset.v; save(); s.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
      }),
    },
    {
      id: 'look', title: 'Choose your look', sub: 'Colors change right away. More options in Appearance (the palette button).',
      html: () => {
        const t = themeOf(S.settings.theme);
        return `<div class="wl-themes">${THEMES.map(th => `<button class="wl-theme ${t.preset === th.id ? 'on' : ''}" data-wtheme="${th.id}" style="--a:${th.accent};--b:${th.accent2};--g:${th.bg}"><i></i><span>${th.name}</span></button>`).join('')}</div>
          <div class="wl-row"><span>Animations</span><div class="seg wl-seg" id="wlAnim">${ANIM_LEVELS.map(a => `<button data-anim="${a}" class="${t.anim === a ? 'on' : ''}">${a[0].toUpperCase() + a.slice(1)}</button>`).join('')}</div></div>`;
      },
      bind: c => {
        c.querySelectorAll('[data-wtheme]').forEach(b => b.onclick = () => { pickTheme(b.dataset.wtheme); c.querySelectorAll('[data-wtheme]').forEach(x => x.classList.toggle('on', x === b)); });
        c.querySelectorAll('#wlAnim [data-anim]').forEach(b => b.onclick = () => { setTheme({ anim: b.dataset.anim }, false); c.querySelectorAll('#wlAnim button').forEach(x => x.classList.toggle('on', x === b)); });
      },
    },
    {
      id: 'tourask', bare: true,
      html: () => `<div class="wl-orb small">${icon('eye', 26)}</div>
        <h2>${name() ? `Nice to meet you, ${esc(name())}!` : 'All set!'}</h2>
        <p>Want a quick tour of the buttons? It points at each one and says what it does.</p>
        <div class="wl-acts center"><button class="btn ghost" data-w="finish">No thanks, start chatting</button><button class="btn primary" data-w="tour">${icon('spark', 15)}Show me around</button></div>`,
    },
  ];
  const QUESTIONS = STEPS.filter(s => !s.bare).length;

  /* ------------------------------------------------------------------- tour */
  const TOUR = [
    ['#modelPill', 'Your AI model', 'Pick which AI you talk to (Ctrl+K). Local models run on this PC. Cloud models work with your own API key.'],
    ['#newChatBtn', 'New chat', 'Starts a fresh chat (Ctrl+N). Your old chats stay in the list below, newest first.'],
    ['#composer', 'Message box', 'Type here and press Enter. Press / for ready-made prompts like /website, /game or /image.'],
    ['#attachBtn', 'Attach', 'Add pictures (for vision models) or code and text files. You can also drop them on the window.'],
    ['#webBtn', 'Search', 'The AI looks things up on the web before it answers, and shows its sources.'],
    ['#deepBtn', 'Deep research', 'The AI reads several web pages for one question, and you can watch its little browser.'],
    ['#imgBtn', 'Pictures', 'Turns your message into a picture. You can also just write "make me an image of a fox", then "now at night".'],
    ['#codeChip', 'Code mode', 'Gives the AI its own project folder. It edits real files there, runs them, and you see a live preview.'],
    ['#thinkChip', 'Think', 'Lets models that can reason think first. Slower, but better at hard questions.'],
    ['#planChip', 'Plan', 'The AI writes a short plan you can edit before it answers.'],
    ['#privChip', 'Privacy mode', 'One click blocks everything that could leave this PC: web, cloud models and downloads.'],
    ['#playBtn', 'Play', 'Games and toys for a break (Ctrl+G).'],
    ['#themeBtn', 'Appearance', 'Themes, your own colors, and how much animation you want.'],
    ['#settingsBtn', 'Chat settings', 'System prompt, creativity, memory, and the Style tab: how the AI talks to you.'],
    ['#modelsBtn', 'Models', 'Download local models, add API keys, and get image models in one click.'],
    ['#keysBtn', 'Shortcuts', 'All keyboard shortcuts. You can start this tour again from here.'],
  ];
  const visible = el => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !el.closest('[hidden]'); };
  let tourList = [];

  /* ------------------------------------------------------------------ render */
  function shell() {
    const el = document.createElement('div');
    el.id = 'welcome'; el.className = 'wl-back';
    el.innerHTML = `<div class="wl-card" role="dialog" aria-modal="true"></div><div class="wl-spot" hidden></div><div class="wl-tip" hidden></div>`;
    document.body.append(el);
    el.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey, true);
    addEventListener('resize', placeTour);
    return el;
  }
  function render(dir = 1) {
    const s = STEPS[W.step], card = W.el.querySelector('.wl-card');
    const qi = STEPS.slice(0, W.step + 1).filter(x => !x.bare).length;
    card.className = 'wl-card' + (s.bare ? ' bare' : '') + (dir < 0 ? ' back' : '');
    card.innerHTML = s.bare ? s.html() : `
      <div class="wl-head"><span class="wl-count">${qi} of ${QUESTIONS}</span><button class="wl-x" data-w="skipall" title="Skip all">Skip all ${icon('x', 13)}</button></div>
      <div class="wl-dots">${Array.from({ length: QUESTIONS }, (_, i) => `<i class="${i < qi ? 'on' : ''}"></i>`).join('')}</div>
      <h2>${s.title}</h2><p class="wl-sub">${s.sub}</p>
      <div class="wl-body">${s.html()}</div>
      <div class="wl-acts"><button class="btn ghost" data-w="back">${icon('undo', 14)}Back</button><span class="spacer"></span>
        <button class="btn ghost" data-w="next">Skip</button><button class="btn primary" data-w="next">Next</button></div>`;
    void card.offsetWidth; card.classList.add('in');
    if (s.bind) s.bind(card);
    else setTimeout(() => card.querySelector('.btn.primary')?.focus(), 60);
  }
  function go(d) {
    W.step = Math.max(0, Math.min(STEPS.length - 1, W.step + d));
    render(d);
  }

  function startTour() {
    tourList = TOUR.filter(([sel]) => visible($(sel)));
    W.tour = 0;
    W.el.classList.add('touring');
    W.el.querySelector('.wl-card').hidden = true;
    W.el.querySelector('.wl-spot').hidden = false;
    W.el.querySelector('.wl-tip').hidden = false;
    paintTour();
  }
  function paintTour() {
    const [sel, title, text] = tourList[W.tour], tip = W.el.querySelector('.wl-tip');
    tip.innerHTML = `<div class="wl-head"><span class="wl-count">${W.tour + 1} of ${tourList.length}</span><button class="wl-x" data-w="finish" title="End the tour">End tour ${icon('x', 13)}</button></div>
      <h3>${title}</h3><p>${text}</p>
      <div class="wl-acts"><button class="btn ghost small" data-w="tback" ${W.tour ? '' : 'disabled'}>${icon('undo', 13)}Back</button><span class="spacer"></span>
        <button class="btn primary small" data-w="tnext">${W.tour === tourList.length - 1 ? 'Finish' : 'Next'}</button></div>`;
    tip.classList.remove('pop'); void tip.offsetWidth; tip.classList.add('pop');
    placeTour();
    setTimeout(() => tip.querySelector('[data-w="tnext"]')?.focus(), 60);
  }
  function placeTour() {
    if (!W.el || W.tour < 0) return;
    const el = $(tourList[W.tour][0]); if (!el) return;
    const r = el.getBoundingClientRect(), pad = 6, spot = W.el.querySelector('.wl-spot'), tip = W.el.querySelector('.wl-tip');
    Object.assign(spot.style, { left: r.left - pad + 'px', top: r.top - pad + 'px', width: r.width + pad * 2 + 'px', height: r.height + pad * 2 + 'px' });
    const tw = Math.min(330, innerWidth - 24), th = tip.offsetHeight || 170;
    const below = r.bottom + 14 + th < innerHeight;
    let left = Math.max(12, Math.min(innerWidth - tw - 12, r.left + r.width / 2 - tw / 2));
    let top = below ? r.bottom + 14 : r.top - th - 14;
    top = Math.max(12, Math.min(innerHeight - th - 12, top));
    Object.assign(tip.style, { left: left + 'px', top: top + 'px', width: tw + 'px' });
    tip.dataset.side = below ? 'below' : 'above';
  }

  function finish() {
    S.settings.onboarded = true; save();
    const n = name();
    close();
    if (typeof renderThread === 'function' && S.chat && !S.chat.messages.length) { S.emptyHtml = null; renderThread(); }
    toast(n ? `You're all set, ${n}. Have fun!` : "You're all set. Have fun!", 'ok', 3500);
    try { window.mtaiStyle.confetti({ n: 90 }); } catch {}
    $('#input')?.focus();
  }
  function close() {
    if (!W.el) return;
    document.removeEventListener('keydown', onKey, true);
    removeEventListener('resize', placeTour);
    const el = W.el; W.el = null; W.tour = -1;
    el.classList.add('out');
    setTimeout(() => el.remove(), animLevel() ? 350 : 0);
  }

  function onClick(e) {
    if (!W.el) return;                                       // fading out: clicks no longer count
    const b = e.target && e.target.closest('[data-w]'); if (!b) return;
    const a = b.dataset.w;
    if (a === 'next') { if (W.step === STEPS.length - 1) finish(); else go(1); }
    else if (a === 'back') go(-1);
    else if (a === 'skipall' || a === 'finish') finish();
    else if (a === 'tour') startTour();
    else if (a === 'tnext') { if (W.tour >= tourList.length - 1) finish(); else { W.tour++; paintTour(); } }
    else if (a === 'tback') { if (W.tour > 0) { W.tour--; paintTour(); } }
  }
  function onKey(e) {
    if (!W.el) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); finish(); return; }
    if (W.tour >= 0) {
      if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); onClick({ target: W.el.querySelector('[data-w="tnext"]') }); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); e.stopPropagation(); onClick({ target: W.el.querySelector('[data-w="tback"]') }); }
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault(); e.stopPropagation();
      const p = W.el.querySelector('.wl-card .btn.primary'); if (p) p.click();
    }
  }

  function start() {
    if (W.el) return;
    W.step = 0; W.tour = -1;
    $('#dialog').hidden = true; if (typeof closeDrawer === 'function') closeDrawer();
    W.el = shell();
    render(1);
  }
  window.mtaiWelcome = { start };

  // first start: settings.onboarded is false until the welcome was finished or skipped once
  addEventListener('mtai:ready', () => {
    if (S.settings && S.settings.onboarded !== true) setTimeout(start, animLevel() >= 2 ? 650 : 50);
  }, { once: true });
})();
