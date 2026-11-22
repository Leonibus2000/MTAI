'use strict';
/* MTAI - extras: cloud models with your own API keys, image generation, planning,
   how the AI talks to you (Style), read aloud, pinned chats, quick actions on
   selected text, and fun stuff (Play menu, dice, confetti, a snake game).

   Loaded after app.js and before motion.js. Everything lives inside this IIFE so no
   top-level name can clash with the other scripts. It changes app.js behavior by
   wrapping app.js's global functions (window.buildMsg = ...), the same trick motion.js uses.
   The only names it adds to window: extraSystem (called by generate() in app.js). */
(() => {
  const X = { cloud: null, imgB: null, imgMode: false, planOnce: false, gallery: null, speakId: null };

  /* ------------------------------------------------------------------ icons */
  Object.assign(ICONS, {
    key: '<circle cx="7.5" cy="15.5" r="4"/><path d="M10.4 12.6L20 3M16.5 6.5l2.5 2.5M14 9l2 2"/>',
    plan: '<path d="M10 6.5h10M10 12h10M10 17.5h10"/><path d="M3.8 6.3l1.3 1.3 2.4-2.6M3.8 11.8l1.3 1.3 2.4-2.6"/><circle cx="5.4" cy="17.6" r="1.3"/>',
    game: '<path d="M7 7.5h10a5 5 0 0 1 4.8 6.3l-.6 2.3a2.6 2.6 0 0 1-4.4 1.1L14.5 15h-5l-2.3 2.2a2.6 2.6 0 0 1-4.4-1.1l-.6-2.3A5 5 0 0 1 7 7.5z"/><path d="M8 10v3.6M6.2 11.8h3.6"/><circle cx="15.6" cy="11" r=".7"/><circle cx="17.6" cy="13" r=".7"/>',
    pin: '<path d="M9.5 3.5h5l-.8 5.5 3.3 3.3H7l3.3-3.3z"/><path d="M12 12.3V21"/>',
    speaker: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18.2 6.4a7.6 7.6 0 0 1 0 11.2"/>',
    dice: '<rect x="4" y="4" width="16" height="16" rx="4"/><circle cx="8.8" cy="8.8" r="1"/><circle cx="15.2" cy="15.2" r="1"/><circle cx="15.2" cy="8.8" r="1"/><circle cx="8.8" cy="15.2" r="1"/><circle cx="12" cy="12" r="1"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>',
    quote: '<path d="M5 17h4l2-4V7H5v6h3zM13 17h4l2-4V7h-6v6h3z"/>',
    party: '<path d="M4 20l4.5-12 7.5 7.5z"/><path d="M14 3.5l.6 1.8M19.5 8.5l1.8-.6M16.5 6.2l2-2M12.5 8.5c1.5-1.5 1.5-3 .5-4.5M15.5 11.5c1.5-1.5 3-1.5 4.5-.5"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    stopSq: '<rect x="6.5" y="6.5" width="11" height="11" rx="2.5"/>',
    plus2: '<path d="M12 5v14M5 12h14"/>',
  });
  // app.js turned data-icon into svg before this file loaded: redraw the new ones
  for (const [sel, name, size] of [['#planChip', 'plan', 15], ['#playBtn', 'game', 18], ['#imgBtn', 'image', 15],
    ['.m-nav [data-tab="cloud"]', 'key', 18], ['.m-nav [data-tab="images"]', 'image', 18]]) {
    const el = $(sel), svg = el && el.querySelector('svg.i');
    if (svg) svg.outerHTML = icon(name, size); else if (el) el.insertAdjacentHTML('afterbegin', icon(name, size));
  }

  const wrap = (name, fn) => { const orig = window[name]; if (typeof orig === 'function') window[name] = fn(orig); };
  const settingsReady = () => S.settings && Object.keys(S.settings).length > 0;
  const ago = t => { const s = Date.now() / 1000 - t; return s < 90 ? 'just now' : s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' d ago'; };
  const animOk = () => animLevel() >= 2;      // Appearance > Animations: medium or high

  /* ===================================================================== CLOUD */
  const PROV_LOOK = {
    openai: ['#10a37f', 'GPT'], anthropic: ['#d97757', 'C'], gemini: ['#4f8df5', 'G'], xai: ['#d4d4d8', 'X'],
    deepseek: ['#4d6bfe', 'DS'], mistral: ['#ff7000', 'M'], groq: ['#f55036', 'GQ'], openrouter: ['#7c7ff2', 'OR'], custom: ['#a78bfa', '+'],
  };
  async function loadCloud() {
    try { X.cloud = await api('cloud'); } catch (e) { X.cloud = { providers: [], sdk: true, error: e.message }; }
    updateCounts();
    return X.cloud;
  }
  function updateCounts() {
    const c = $('#cntCloud'); if (c) c.textContent = X.cloud ? (X.cloud.providers.filter(p => p.has_key).length || '') : '';
    const g = $('#cntImages'); if (g) g.textContent = X.gallery ? (X.gallery.length || '') : '';
  }
  function cloudCard(p) {
    const [col, mark] = PROV_LOOK[p.id] || ['#a78bfa', '?'];
    const on = p.has_key, err = on && p.error;
    const state = !on ? '<span class="cc-state">Not connected</span>'
      : p.refreshing ? '<span class="cc-state"><span class="spin"></span>Checking</span>'
      : err ? '<span class="cc-state bad"><i class="dot err"></i>Problem</span>'
      : `<span class="cc-state ok"><i class="dot live"></i>${p.count} model${p.count === 1 ? '' : 's'}</span>`;
    return `<div class="ccard ${on ? 'on' : ''} ${err ? 'bad' : ''}" data-prov="${p.id}" style="--pc:${col}">
      <div class="cc-top"><span class="cc-logo">${mark}</span><div class="cc-name"><b>${esc(p.custom && p.name_custom ? p.name_custom : p.label)}</b><small>${esc(p.desc)}</small></div>${state}</div>
      ${err ? `<div class="cc-err">${icon('alert', 14)}<span>${esc(p.error)}</span></div>` : ''}
      ${p.id === 'anthropic' && !X.cloud.sdk ? `<div class="cc-err soft">${icon('info', 14)}<span>Claude needs the Anthropic SDK. Run <code>py -m pip install anthropic</code>, then restart MTAI.</span></div>` : ''}
      ${p.custom ? `<div class="cc-row"><input class="cc-in" data-f="base" placeholder="Base URL, e.g. https://api.together.xyz/v1" value="${esc(on ? p.base : '')}" spellcheck="false">
        <input class="cc-in narrow" data-f="name" placeholder="Name" value="${esc(p.name_custom || '')}" spellcheck="false"></div>` : ''}
      <div class="cc-row"><input class="cc-in" type="password" data-f="key" autocomplete="off" spellcheck="false"
        placeholder="${on ? 'Saved: ' + esc(p.masked) + ' (paste a new key to replace it)' : 'Paste your API key' + (p.hint ? ' (' + esc(p.hint) + ')' : '')}">
        <button class="btn small primary" data-act="cloud-save">${on ? 'Save' : 'Connect'}</button></div>
      <div class="cc-row"><input class="cc-in" data-f="filter" value="${esc(p.filter || '')}" spellcheck="false" placeholder="Only show models with these words (comma separated, optional)">
        ${on ? `<button class="btn small ghost" data-act="cloud-remove" title="Delete this key from the PC">${icon('trash', 14)}</button>` : ''}</div>
      <div class="cc-foot">${p.keys_url ? `<span class="link" data-act="open-url" data-url="${esc(p.keys_url)}">${icon('ext', 12)}Get a key</span>` : ''}
        ${p.img ? `<span class="cc-tag">${icon('image', 12)}Image generation</span>` : ''}${on && p.at ? `<span class="cc-when">checked ${ago(p.at)}</span>` : ''}</div></div>`;
  }
  function renderCloud(body) {
    if (!X.cloud) { body.innerHTML = '<div class="empty-box"><span class="spin"></span></div>'; loadCloud().then(() => { if (S.modalTab === 'cloud' && !$('#modal').hidden) renderModal(); }); return; }
    const st = X.cloud, priv = privacyOn();
    body.innerHTML = `<div class="m-head"><div><h2>Cloud models</h2><p>Bring your own API keys for GPT, Claude, Gemini, Grok, DeepSeek and more. Their models join the model list next to your local ones.</p></div>
        <div class="spacer"></div><button class="btn small" data-act="cloud-refresh" ${priv ? 'disabled' : ''}>${icon('refresh', 14)}Refresh</button></div>
      ${priv ? privacyBanner('Cloud models are off in privacy mode. Your keys stay saved.') : ''}
      <div class="cloud-note">${icon('shieldOn', 17)}<span>Keys are ${st.encrypted ? 'encrypted with your Windows account (DPAPI)' : 'saved'} in MTAI's data folder and never shown again in full.
        When you chat with a cloud model, that chat goes to the company that runs it. Local models still keep everything on this PC.</span></div>
      <div class="cloud-grid ${priv ? 'priv-locked' : ''}">${st.providers.map(cloudCard).join('')}</div>`;
  }
  async function cloudSave(btn) {
    const card = btn.closest('[data-prov]'), pid = card.dataset.prov;
    const p = X.cloud.providers.find(x => x.id === pid);
    const val = f => { const i = card.querySelector(`[data-f="${f}"]`); return i ? i.value.trim() : undefined; };
    const key = val('key');
    if (!key && !p.has_key) { const i = card.querySelector('[data-f="key"]'); i.classList.remove('nope'); void i.offsetWidth; i.classList.add('nope'); i.focus(); toast('Paste the API key first', 'err'); return; }
    if (privacyOn()) { privacyBlocked('cloud'); return; }
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span>Checking';
    let r;
    try {
      const resp = await fetch('/api/cloud/key', { method: 'POST', headers: { 'X-Token': TOKEN, 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: pid, key: key || null, base: val('base'), filter: val('filter'), name: val('name') }) });
      r = await resp.json();
    } catch (e) { r = { error: e.message }; }
    if (r.providers) X.cloud = { ...X.cloud, ...r };
    if (r.error) { toast(r.error, 'err', 6000); if (!r.providers) await loadCloud(); }
    else {
      toast(`${p.name} connected: ${r.count} model${r.count === 1 ? '' : 's'}`, 'ok');
      const rc = btn.getBoundingClientRect(); confetti({ x: rc.left + rc.width / 2, y: rc.top, n: 70, spread: .9 });
      X.imgB = null;
    }
    await loadModels(true);
    if (S.modalTab === 'cloud') renderModal();
  }
  async function cloudRemove(btn) {
    const pid = btn.closest('[data-prov]').dataset.prov, p = X.cloud.providers.find(x => x.id === pid);
    if (!await confirmDialog({ title: `Remove the ${p.name} key?`, text: 'The key is deleted from this PC and its models leave the list.', ok: 'Remove' })) return;
    try { X.cloud = { ...X.cloud, ...await api('cloud/remove', { provider: pid }) }; } catch (e) { toast(e.message, 'err'); }
    if (S.model && S.model.provider === pid) S.model = null;
    X.imgB = null;
    await loadModels(true); renderModal(); toast(`${p.name} key removed`);
  }

  /* ============================================================ IMAGE MODELS */
  const imgCfg = () => {
    const c = (S.settings.image && typeof S.settings.image === 'object') ? S.settings.image : (S.settings.image = {});
    if (!['square', 'wide', 'tall'].includes(c.aspect)) c.aspect = 'square';
    c.steps = Math.max(4, Math.min(60, +c.steps || 25));
    return c;
  };
  async function loadImgBackends() {
    try { X.imgB = await api('images/backends'); } catch (e) { X.imgB = { backends: [], error: e.message }; }
    return X.imgB;
  }
  function pickBackend() {
    const list = (X.imgB && X.imgB.backends) || [], cfg = imgCfg();
    const ok = list.filter(b => !b.blocked);
    return list.find(b => b.id === cfg.backend && !b.blocked) || ok.find(b => b.local) || ok[0] || null;
  }
  function backendOptions(sel) {
    const list = (X.imgB && X.imgB.backends) || [];
    const groups = new Map();
    for (const b of list) { if (!groups.has(b.label)) groups.set(b.label, []); groups.get(b.label).push(b); }
    return [...groups].map(([g, items]) => `<optgroup label="${esc(g)}${items[0].local ? ' (this PC)' : ''}">${items.map(b =>
      `<option value="${esc(b.id)}" ${b.id === sel ? 'selected' : ''} ${b.blocked ? 'disabled' : ''}>${esc(b.name)}${b.blocked ? ' (privacy mode)' : ''}</option>`).join('')}</optgroup>`).join('');
  }
  const ASPECT_ICON = { square: '<i class="ar sq"></i>', wide: '<i class="ar wd"></i>', tall: '<i class="ar tl"></i>' };
  function renderImgBar() {
    const bar = $('#imgBar');
    $('#imgBtn').classList.toggle('on', X.imgMode);
    $('#composer').classList.toggle('img-mode', X.imgMode);
    bar.hidden = !X.imgMode;
    if (!X.imgMode) return;
    if (!X.imgB) { bar.innerHTML = `<span class="spin"></span><span class="ib-note">Looking for image models…</span>`; loadImgBackends().then(renderImgBar); return; }
    const b = pickBackend(), cfg = imgCfg();
    if (!b) {
      bar.innerHTML = `${icon('image', 15)}<span class="ib-note">No image model yet. Download one in a click (from 2.6 GB), or use a cloud key.</span>
        <button class="btn small primary" data-act="img-setup">${icon('download', 13)}Get a model</button>`;
      return;
    }
    bar.innerHTML = `${icon('image', 15)}<select id="imgModel" title="Image model">${backendOptions(b.id)}</select>
      <div class="seg ib-aspect">${['square', 'wide', 'tall'].map(a => `<button data-aspect="${a}" class="${cfg.aspect === a ? 'on' : ''}" title="${a[0].toUpperCase() + a.slice(1)}">${ASPECT_ICON[a]}</button>`).join('')}</div>
      <span class="ib-where ${b.local ? 'local' : ''}">${b.local ? 'on this PC' : 'cloud: ' + esc(b.label)}</span>
      <button class="icon-btn" data-act="img-setup" title="Image settings">${icon('sliders', 15)}</button>`;
    $('#imgModel').onchange = e => { imgCfg().backend = e.target.value; saveSettings(); renderImgBar(); updateToolUI(); };
  }
  function toggleImgMode(force) {
    X.imgMode = force ?? !X.imgMode;
    renderImgBar(); updateToolUI(); updateSendBtn();
    $('#input').placeholder = X.imgMode ? 'Describe the picture…' : S.model ? `Message ${S.model.name}…` : 'Pick a model to start…';
    $('#input').focus();
  }

  /* ---- plain-language picture requests: "generate me an image of a fox", "draw me a castle",
     "mach mir ein Bild von ...", "dessine-moi un mouton". Returns the picture prompt, or null. */
  const IMG_NOUN = '(?:image|picture|pic|photo|photograph|drawing|painting|illustration|artwork|art|wallpaper|portrait|sketch|logo|poster|selfie|render)s?';
  const IMG_ADJ = '(?:(?:ai|new|quick|cool|nice|cute|pretty|beautiful|realistic|photorealistic|photo-?realistic|high[- ]quality|hd|4k|8k|little|small|simple|funny|detailed|digital|anime|cartoon|pixel[- ]art|3d|another|different|second|epic|dark|scary|aesthetic)[ ,]+){0,4}';
  const IMG_RULES = [
    // EN: (generate|make|...) (me) (a) (cute) image (of|showing|...) X
    new RegExp(`^(?:generate|make|create|draw|paint|render|produce|design|sketch|illustrate|give|show|send|get|do|whip up|cook up) (?:me |us |for me )?(?:(?:an?|some|one|two|three|four|\\d+) )?${IMG_ADJ}${IMG_NOUN}(?: (?:of|showing|depicting|that shows|that show|featuring|with|where|in which)\\b|:| -)\\s*(.+)$`, 'i'),
    // EN, no verb: "an image of X" / "picture of X"
    new RegExp(`^(?:an? )?${IMG_ADJ}${IMG_NOUN} (?:of|showing|depicting)\\s+(.+)$`, 'i'),
    // EN: draw / paint (me) a X
    /^(?:draw|paint|sketch|illustrate|doodle) (?:me |us )?((?:an?|some|two|three|four|\d+|my) .+)$/i,
    // DE
    /^(?:generier\w*|erstell\w*|erzeug\w*|mach\w*|zeichne\w*|mal|male|malt) (?:mir |uns )?(?:bitte )?(?:mal )?(?:ein(?:e|en)?|zwei|drei|\d+) (?:\p{L}+ ){0,2}(?:bild|bilder|foto|fotos|zeichnung|gemälde|illustration|logo|poster|hintergrundbild)(?: (?:von|vom|mit|zu|über|wo|auf dem|das|die|der)\b|:)\s*(.+)$/iu,
    /^(?:zeichne|male|mal) (?:mir |uns )?((?:ein(?:e|en)?|zwei|drei|\d+) .+)$/iu,
    // DE, verb at the end: "(kannst du) (mir) ein Bild von einer Katze generieren"
    /^(?:mir |uns )?(?:bitte )?(?:mal )?(?:ein(?:e|en)?|zwei|drei|\d+) (?:\p{L}+ ){0,2}(?:bild|bilder|foto|fotos|zeichnung|gemälde|illustration|logo|poster|hintergrundbild) (?:von|vom|mit) (.+?) (?:generieren|erstellen|erzeugen|machen|zeichnen|malen)$/iu,
    // FR
    /^(?:génère|genere|générer|crée|cree|créer|fais|fait|faire|dessine|dessiner|peins|peindre)(?:[- ]?moi| moi)? (?:une?|des|deux|trois|\d+) (?:\p{L}+ ){0,2}(?:image|images|photo|photos|dessin|dessins|illustration|peinture|logo|affiche|fond d'écran)(?: (?:de|du|des|avec|montrant|qui montre|où)\b| d'|:)\s*(.+)$/iu,
    /^(?:dessine|peins)(?:[- ]?moi)? ((?:une?|des|deux|trois|\d+) .+)$/iu,
  ];
  // openers that can stand in front: "hey, can you please ...", "i want you to ...", "kannst du bitte ...", "peux-tu ..."
  const IMG_OPEN = /^(?:hey|hi|hello|yo|ok|okay|alright|so|now|and|also|then|please|pls|plz|mtai|just|quickly|(?:can|could|would|will) (?:you|u)|(?:i want|i'd like|i would like|i need|i wanna)(?: you to)?|go ahead and|try to|bitte|kannst du|könntest du|kannst|hallo|hey du|peux-tu|tu peux|pourrais-tu|est-ce que tu peux|s'il te plaît|s'il te plait|stp|salut)\b[ ,!.:]*/iu;
  const IMG_TAIL = /[\s,.!?]*(?:please|pls|plz|for me|thanks|thank you|thx|bitte|danke|stp|s'il te plaît|s'il te plait|merci)?[\s.!?]*$/iu;
  // "make an image of my hard drive" is not a picture; neither is "draw a conclusion"
  const IMG_NOT = /\b(?:disk|disc|drive|hdd|ssd|iso|docker|container|kubernetes|partition|backup|virtual machine|vm|os|system image|usb|sd card|firmware|bootable|conclusions?|comparison|parallels?|distinction|plan|outline|roadmap|attention|diagram in (?:mermaid|ascii)|ascii)\b/i;
  function imageIntent(text) {
    let s = String(text || '').trim();
    if (!s || s.length > 900 || s.startsWith('/') || s.includes('```')) return null;
    s = s.replace(/\s+/g, ' ');
    for (let i = 0, prev; i < 8 && prev !== s; i++) { prev = s; s = s.replace(IMG_OPEN, ''); }
    s = s.replace(/[\s.!?]+$/, '');
    for (const re of IMG_RULES) {
      const m = s.match(re);
      if (!m) continue;
      let p = m[1].replace(IMG_TAIL, '').trim();
      for (let i = 0, prev; i < 3 && prev !== p; i++) { prev = p; p = p.replace(IMG_TAIL, '').trim(); }
      if (p.length < 2 || !/\p{L}/u.test(p) || IMG_NOT.test(p)) return null;
      return p;
    }
    return null;
  }
  window.imageIntent = imageIntent;          // for tests

  /* make a picture: the prompt goes into the chat as a user message, the picture as an image card */
  async function makeImage(prompt, opts = {}) {
    const chat = S.chat;
    if (!X.imgB || !pickBackend()) await loadImgBackends();
    const b = opts.backend ? (X.imgB.backends || []).find(x => x.id === opts.backend) || pickBackend() : pickBackend();
    if (!b) { toast('No image model yet: download one here, it takes one click.', 'err', 5500); openModels('images'); return false; }
    if (!b.local && privacyOn()) { privacyBlocked('cloud'); return false; }
    const cfg = imgCfg();
    let reqId = opts.reqId;
    if (!opts.again) {
      reqId = uid();
      chat.messages.push({ id: reqId, role: 'user', content: opts.said || prompt, local: true, imgReq: true });
      if (!chat.title) chat.title = makeTitle(opts.title || prompt);
      if (chat.messages.length === 1) $('#thread').innerHTML = '';
      const ue = buildMsg(chat.messages[chat.messages.length - 1]); ue.classList.add('enter'); $('#thread').append(ue);
    }
    const msg = { id: uid(), role: 'assistant', kind: 'image', prompt, model: b.name, backend: b.id, provider: b.label, local: !!b.local,
      aspect: opts.aspect || cfg.aspect, pending: true, started: Date.now() };
    if (opts.auto) Object.assign(msg, { auto: true, said: opts.said, reqId });
    chat.messages.push(msg);
    const el = buildMsg(msg); el.classList.add('enter'); $('#thread').append(el); toBottom(true);
    renderChatList();
    const tick = setInterval(() => paintImg(msg), 500);
    let poll = null;
    try {
      // follow-ups and other languages: the chat model first writes the English prompt the image model needs
      if (opts.prep) {
        msg._prep = opts.prepBy || 'the chat model'; paintImg(msg);
        const p = await opts.prep();
        delete msg._prep;
        if (p && p !== msg.prompt) { msg.prompt = p; msg.written = true; }
      }
      poll = b.provider === 'mtai' ? setInterval(() => api('imagegen').then(s => { msg._gen = s.gen; }).catch(() => {}), 800) : null;
      const r = await api('images/generate', { backend: b.id, prompt: msg.prompt, aspect: msg.aspect, steps: cfg.steps, negative: cfg.negative || '' });
      msg.image = { url: r.url, name: r.name }; msg.revised = r.revised || (msg.written ? msg.prompt : undefined); msg.secs = r.time;
      X.gallery = null;
    } catch (e) { msg.error = e.message; delete msg._prep; }
    clearInterval(tick); clearInterval(poll); delete msg._gen;
    delete msg.pending;
    paintImg(msg, undefined, true);
    if (S.chat === chat && nearBottom()) setTimeout(() => toBottom(true), 60);
    await saveChat(chat);
    return true;
  }
  // look for image models once the app is up, so the first picture request answers at once
  addEventListener('mtai:ready', () => setTimeout(() => { if (!X.imgB && imgCfg().auto !== false) loadImgBackends(); }, 400), { once: true });
  /* follow-ups right after a picture: "now make it at night", "add a hat", "mach es blau", "avec un chapeau".
     Returns the change in the user's words, or null. Only asked when the chat's last message is a finished picture. */
  const FOLLOW_RULES = [
    /^(?:show (?:me |us )?(?:the|a|an|her|him|it|them|this|that|its|his|more|all)\b|let (?:me|us) see|to see (?:the|her|him|it|them|its|his|all|more)\b|see (?:her|him|it|them|its|his|all of)\b|(?:can|could) (?:i|we) see|i (?:want|wanna|would like|'d like) (?:to see|it|her|him|them|the)\b|zoom (?:out|in)|full[- ]body|whole|from far|far away|close[- ]?up|crop|make (?:it|him|her|them|this|that|the \p{L}+)|turn(?:it|him|her|them|this|the \p{L}+)|change (?:it|him|her|them|this|that|the)|add|remove|put|give (?:it|him|her|them)|replace|swap|same (?:but|with|thing|one)|again|another(?: one)?|one more|redo|try again|(?:but )?(?:with|without)\b|in (?:the )?(?:style of|winter|summer|autumn|fall|spring|space|the rain|the snow|rain|snow|anime|cartoon|pixel art|watercolou?r|3d|black and white|color)|as an? |at (?:night|sunset|sunrise|dawn|dusk|noon|daytime)|more |less |darker|brighter|zoom|closer|wider|from (?:above|below|behind|the side|the front)|colou?r)/iu,
    /^(?:zeig (?:mir |uns )?(?:die|den|das|sie|ihn|es|mehr|alles)\b|ich will (?:sie|ihn|es|die|den|das) (?:\p{L}+ )?sehen|(?:die|den|das) ganze|von weitem|näher|mach(?:e)? (?:es|ihn|sie|das|den|die|ihm|ihr)|änder\w*|füg\w*|entfern\w*|gib (?:ihm|ihr|ihnen|es)|ersetz\w*|nochmal|noch (?:eins|einmal|ein)|(?:aber )?(?:mit|ohne)\b|bei nacht|in der nacht|nachts|im (?:winter|sommer|herbst|frühling|schnee|regen|stil|weltall)|als )/iu,
    /^(?:montre[- ]?(?:moi )?(?:le|la|les|lui|tout|plus)\b|je veux (?:le|la|les) voir|en entier|de loin|de plus près|fais[- ](?:le|la|les)|rends[- ](?:le|la|les)|change\w*|ajoute\w*|enlève\w*|retire\w*|mets|remplace\w*|encore|une autre|(?:mais )?(?:avec|sans)\b|la nuit|de nuit|en (?:hiver|été|automne|noir et blanc)|dans le style|comme )/iu,
  ];
  const FOLLOW_OPEN = /^(?:but|great|nice|cool|perfect|awesome|lovely|lol|wow|good|jetzt|nun|aber|super|toll|schön|maintenant|mais|génial|parfait)\b[ ,!.:]*/iu;
  const IMPERATIVE = /^(?:show|let me see|let us see|can i see|could i see|can we see|zoom|crop|zeig|montre|make|turn|change|add|remove|put|give|replace|swap|redo|mach|änder|füg|entfern|gib|ersetz|fais|rends|ajoute|enlève|retire|mets|remplace)/iu;
  function imageFollowUp(text) {
    let s = String(text || '').trim().replace(/\s+/g, ' ');
    if (!s || s.length > 240 || s.startsWith('/') || s.includes('```')) return null;
    for (let i = 0, prev; i < 8 && prev !== s; i++) { prev = s; s = s.replace(IMG_OPEN, '').replace(FOLLOW_OPEN, ''); }
    const question = /\?\s*$/.test(s);
    s = s.replace(/[\s.!?]+$/, '');
    if (!s || !FOLLOW_RULES.some(re => re.test(s))) return null;
    if (question && !IMPERATIVE.test(s)) return null;          // "with what model was this made?" is a question, "can you make it blue?" is not
    return s;
  }
  window.imageFollowUp = imageFollowUp;      // for tests
  // German or French words: the image models only understand English
  const looksForeign = t => /[äöüßàâçéèêëîïôûùœæ]/i.test(t) ||
    /\b(?:der|das|dem|den|ein|eine|einen|einem|einer|mit|und|von|vom|auf|im|bitte|kannst|mir|le|la|les|une|du|avec|et|sur|dans|moi|peux|chapeau)\b/i.test(t);
  // "einer Katze mit Hut" -> "Katze mit Hut", "a red fox" -> "Red fox"
  const titleOf = p => { const t = String(p).replace(/^(?:(?:an|a|the|some|eines|einem|einen|einer|eine|ein|der|die|das|den|dem|une|un|des|les|le|la)\s+|l')/i, '').trim(); return t ? t[0].toUpperCase() + t.slice(1) : p; };
  const PROMPT_SCHEMA = { type: 'object', additionalProperties: false, required: ['prompt'], properties: { prompt: { type: 'string' } } };
  // the chat model writes the English prompt: a translation, or the last prompt with the change applied
  async function writePrompt({ prev, said, fallback }) {
    const model = S.model && S.model.chattable ? S.model : null;
    if (!model) return fallback;
    const ask = prev
      ? `You write prompts for an image generator that only understands English.\nThe last picture was made from this prompt: "${prev}"\nThe user now says: "${said}"\nWrite the prompt for the new picture in English. Put the subject with the change first (image models weigh the first words most). Keep the rest of the last prompt, but drop any words that clash with the change (for example "portrait" or "close-up" when the user wants the full body, "sunset" when they want night). Translate anything that is not English.`
      : `You write prompts for an image generator that only understands English.\nThe user asked for a picture with these words: "${said}"\nWrite the image prompt in English. Keep every detail the user gave and add nothing new. Leave out the request itself (like "make me a picture of").`;
    const ctrl = new AbortController(), t = setTimeout(() => ctrl.abort(), 30000);
    try {
      const txt = await askModel(model, ask + '\nOne line, comma separated, at most 60 words. Answer as JSON: {"prompt": "..."}',
        { maxTokens: 150, signal: ctrl.signal, schema: PROMPT_SCHEMA, extra: { keep_image: true } });
      let p; try { p = JSON.parse(txt.slice(txt.indexOf('{'), txt.lastIndexOf('}') + 1)).prompt; } catch { p = txt; }
      p = String(p || '').replace(/^["'\s]+|["'\s]+$/g, '').replace(/\s+/g, ' ').slice(0, 400);
      return p.length >= 3 ? p : fallback;
    } catch { return fallback; } finally { clearTimeout(t); }
  }
  // the chat's last message, when it is a finished picture
  const lastPicture = () => { const ms = S.chat && S.chat.messages, m = ms && ms[ms.length - 1]; return m && m.kind === 'image' && m.image && !m.pending ? m : null; };

  /* a picture request typed as a normal message: send it to the image model instead of the chat model.
     follow = the picture this message changes (or null for a new request) */
  async function autoImage(text, prompt, done, follow) {
    if (!X.imgB || !pickBackend()) await loadImgBackends();
    if (!pickBackend()) {
      toast('That sounds like a picture request. Get an image model first (one click), then send it again.', 'info', 6500);
      openModels('images');
      return;
    }
    done();
    if (!X.autoTold) {
      X.autoTold = true;
      toast(follow ? 'Sounded like a change to the last picture, so MTAI is painting a new one. Press the chat button under it for a text answer instead.'
        : 'Sounded like a picture request, so MTAI is painting it. Press the chat button under the picture for a text answer instead.', 'info', 7000);
    }
    const rewrite = follow || looksForeign(text);
    const fallback = follow ? `${follow.prompt}, ${prompt}` : prompt;
    await makeImage(rewrite ? fallback : prompt, {
      auto: true, said: text, title: titleOf(prompt), aspect: follow ? follow.aspect : undefined,
      prep: rewrite ? () => writePrompt({ prev: follow && follow.prompt, said: text, fallback }) : null,
      prepBy: S.model && S.model.chattable ? S.model.name : null,
    });
  }
  // undo an automatic picture: remove the request and the card, and send the words to the chat model
  async function imageToChat(m, node) {
    if (S.streaming || !S.chat) return;
    const chat = S.chat, msgs = chat.messages;
    for (let i = msgs.length - 1; i >= 0; i--) if (msgs[i] === m || msgs[i].id === m.reqId) msgs.splice(i, 1);
    node && node.remove();
    const req = m.reqId && $(`#thread .msg[data-id="${m.reqId}"]`); if (req) req.remove();
    await saveChat(chat);
    const ta = $('#input'); ta.value = m.said || m.prompt; autosize(ta);
    X.skipAuto = true;
    submit();
  }
  function imgEl(m) {
    const el = document.createElement('div');
    el.className = 'msg assistant img-msg'; el.dataset.id = m.id;
    el.innerHTML = `<div class="a-head"><span class="avatar img-av">${icon('image', 14)}</span><span class="a-name"></span></div>
      <div class="img-card"></div><div class="m-foot"><span class="stats"></span><span class="acts"></span></div>`;
    el.querySelector('.a-name').textContent = m.model || 'Image';
    paintImg(m, el);
    return el;
  }
  function paintImg(m, el = msgEl(m), fresh) {
    if (!el) return;
    const card = el.querySelector('.img-card');
    card.style.setProperty('--ar', { square: '1 / 1', wide: '3 / 2', tall: '2 / 3' }[m.aspect] || '1 / 1');
    if (!m.pending && !m.image && !m.error) m.error = 'The picture was not finished (MTAI was closed).';
    const state = m.pending ? 'pending' : m.error ? 'error' : 'done';
    if (card.dataset.state !== state) {
      card.dataset.state = state;
      card.innerHTML = state === 'pending'
        ? `<div class="img-wait"><div class="iw-blobs"><i></i><i></i><i></i></div><div class="iw-grain"></div><div class="iw-text"><span class="shimmer">Painting…</span><small class="iw-time"></small></div><div class="iw-bar"><i></i></div></div>`
        : state === 'error' ? `<div class="err-box">${icon('alert', 16)}<span>${esc(m.error)}</span><button class="btn small" data-act="img-again">${icon('refresh', 13)}Retry</button></div>`
        : `<div class="img-frame ${fresh ? 'reveal' : ''}"><img src="${esc(m.image.url)}" data-zoom alt="${esc(m.prompt)}"></div>${m.revised ? `<div class="img-rev">${icon('wand', 12)}<span>${esc(m.revised)}</span></div>` : ''}`;
    }
    if (state === 'pending') {
      const g = m._gen && m._gen.active ? m._gen : null;
      card.querySelector('.iw-time').textContent = `${fmtDur((Date.now() - m.started) / 1000)} · ${m._prep ? `${m._prep} writes the prompt` : g ? (g.step && g.of > 1 ? `step ${g.step} of ${g.of}` : g.status || 'Starting the engine') : m.provider}`;
      const bar = card.querySelector('.iw-bar'); bar.classList.toggle('on', !!(g && g.of > 1 && g.step));
      if (g && g.of) bar.firstElementChild.style.width = (g.step / g.of * 100) + '%';
    }
    el.querySelector('.stats').innerHTML = state === 'done' ? [m.local ? 'On this PC' : esc(m.provider), m.secs ? fmtDur(m.secs) : '', m.aspect].filter(Boolean).join(' · ') : '';
    const toChat = m.auto && state !== 'pending' ? `<button data-act="img-chat" title="Not a picture request? Answer in chat instead">${icon('chat', 15)}</button>` : '';
    el.querySelector('.acts').innerHTML = (state === 'done'
      ? `<button data-act="img-again" title="Make another one">${icon('refresh', 15)}</button><button data-act="img-prompt" title="Copy the prompt">${icon('copy', 15)}</button>
         <button data-act="img-attach" title="Attach to the next message">${icon('clip', 15)}</button><button data-act="img-reveal" title="Show in folder">${icon('folder', 15)}</button>` : '') + toChat;
  }

  /* ---- built-in image models: one-click downloads, light and fast -> heavy and detailed */
  async function loadIG() { try { X.ig = await api('imagegen'); } catch { X.ig = null; } return X.ig; }
  const igJobs = () => Object.values((X.ig && X.ig.jobs) || {});
  const igActive = () => igJobs().some(j => !j.finished);
  const gb = n => (n / 1e9).toFixed(n >= 1e10 ? 0 : 1) + ' GB';
  function igPoll() {
    if (X.igTimer) return;
    X.igTimer = setInterval(async () => {
      const before = new Map(igJobs().map(j => [j.id, j.finished]));
      await loadIG();
      for (const j of igJobs()) {
        if (j.finished && before.get(j.id) === false) {
          if (!j.error) {
            const m = X.ig.models.find(x => x.id === j.id);
            const cfg = imgCfg();
            if (!cfg.backend || !String(cfg.backend).startsWith('mtai|')) { cfg.backend = 'mtai|' + j.id; saveSettings(); }
            toast(`${m.tier} is ready. Press the Image chip and describe a picture.`, 'ok', 5000);
            const c = document.querySelector(`.ig-card[data-id="${j.id}"]`);
            if (c) { const r = c.getBoundingClientRect(); confetti({ x: r.left + r.width / 2, y: r.top + 30, n: 90 }); }
            X.imgB = null; renderImgBar();
          } else if (j.error !== 'Cancelled') toast(j.error, 'err', 7000);
        }
      }
      paintLadder();
      if (!igActive()) { clearInterval(X.igTimer); X.igTimer = null; }
    }, 700);
  }
  const dots = (n, cls) => `<span class="ig-dots ${cls}">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= n ? 'on' : ''}"></i>`).join('')}</span>`;
  function igCard(m, i) {
    const j = (X.ig.jobs || {})[m.id], running = j && !j.finished, priv = privacyOn();
    const def = imgCfg().backend === 'mtai|' + m.id;
    let act;
    if (running) {
      const pc = j.total ? Math.min(100, j.done / j.total * 100) : 0;
      act = `<div class="ig-prog"><div class="bar"><i style="width:${pc.toFixed(1)}%"></i></div>
        <div class="ig-pl"><small>${esc(j.phase || 'Starting…')}${j.total ? ` · ${gb(j.done)} / ${gb(j.total)}` : ''}${j.speed > 1e5 ? ` · ${(j.speed / 1e6).toFixed(1)} MB/s` : ''}</small>
        <button class="icon-btn" data-act="ig-cancel" data-id="${m.id}" title="Cancel">${icon('x', 14)}</button></div></div>`;
    } else if (m.installed) {
      act = `<div class="ig-row"><button class="btn small primary" data-act="ig-try" data-id="${m.id}">${icon('image', 13)}Try it</button>
        ${def ? '<span class="ig-def" title="New pictures use this model">Default</span>' : `<button class="btn small" data-act="ig-use" data-id="${m.id}" title="Make it the default image model">Use</button>`}
        <button class="icon-btn" data-act="ig-del" data-id="${m.id}" title="Delete from disk">${icon('trash', 14)}</button></div>`;
    } else {
      const extra = X.ig.engine ? 0 : X.ig.engine_size;
      act = `${j && j.error && j.error !== 'Cancelled' ? `<div class="cc-err">${icon('alert', 14)}<span>${esc(j.error)}</span></div>` : ''}
        <button class="btn ${m.best ? 'primary' : ''} wide ig-dl" data-act="ig-dl" data-id="${m.id}" ${priv || igActive() ? 'disabled' : ''}>${icon('download', 15)}Download · ${gb(m.size + extra)}</button>`;
    }
    return `<div class="ig-card ${m.installed ? 'ok' : ''} ${running ? 'busy' : ''} ${def ? 'def' : ''}" data-id="${m.id}" style="--k:${i}">
      ${m.installed ? `<span class="ig-best ok">${icon('check', 11)}Downloaded</span>` : m.best ? '<span class="ig-best">Best start</span>' : ''}
      <div class="ig-tier">${esc(m.tier)}</div><div class="ig-model">${esc(m.model)}</div>
      <div class="ig-meters"><div><small>Speed</small>${dots(m.speed, 'sp')}</div><div><small>Detail</small>${dots(m.detail, 'dt')}</div></div>
      <p>${esc(m.desc)}</p>
      <div class="ig-facts"><span>${icon('download', 12)}${gb(m.size)}</span><span>${icon('bolt', 12)}${esc(m.time)}</span><span>${m.base} px</span></div>
      ${m.fits === false ? `<div class="ig-warn">${icon('alert', 12)}Wants ${m.vram} GB of GPU memory: slow here</div>` : ''}
      <div class="ig-act">${act}</div></div>`;
  }
  function ladderHtml() {
    const s = X.ig;
    if (!s) return '<div class="ig-sec"><div class="empty-box"><span class="spin"></span></div></div>';
    const note = s.engine ? `${icon('check', 12)}Image engine installed` : `${icon('info', 12)}The first download also installs the image engine (about ${gb(s.engine_size)}, only once)`;
    return `<div class="ig-sec">
      <div class="ig-head"><h3>Download an image model</h3><p>Runs on this PC: free, private and offline after the download. Start small, add more later.</p></div>
      ${privacyOn() ? `<div class="ig-priv">${icon('shieldOn', 14)}Downloads are off in privacy mode. Models you already have keep working.</div>` : ''}
      <div class="ig-scale"><span>${icon('bolt', 13)}Light and fast</span><i></i><span>Heavy and detailed${icon('spark', 13)}</span></div>
      <div class="ig-ladder">${s.models.map(igCard).join('')}</div>
      <div class="ig-foot"><span>${icon('folder', 12)}Saved in <b>${esc(s.root)}</b>${s.free ? ` · ${gb(s.free)} free` : ''}</span>
        <span class="link" data-act="ig-open">Open</span><span class="link" data-act="ig-move">Change folder</span>
        <span>${note}</span><span>${s.gpu ? `${icon('cube', 12)}${esc(s.gpu)} · ${s.vram} GB` : `${icon('alert', 12)}No NVIDIA GPU found: pictures will be slow`}</span></div></div>`;
  }
  function paintLadder() {
    const sec = document.querySelector('#modalBody .ig-sec');
    if (!sec || $('#modal').hidden || S.modalTab !== 'images') return;
    const html = ladderHtml();
    if (sec._html === html) return;
    const tmp = document.createElement('div'); tmp.innerHTML = html;
    const fresh = tmp.firstElementChild; fresh._html = html; fresh.classList.add('still');
    sec.replaceWith(fresh);
  }
  async function igAction(act, btn) {
    const id = btn.dataset.id, m = X.ig && X.ig.models.find(x => x.id === id);
    if (act === 'ig-dl') {
      if (privacyOn()) { toast('Downloads are off in privacy mode', 'err'); return; }
      if (m.fits === false && !await confirmDialog({ title: `${m.tier} is heavy for this PC`, text: `It wants about ${m.vram} GB of GPU memory. It will still work, but slowly. Download anyway?`, ok: 'Download', danger: false })) return;
      try { X.ig = await api('imagegen/download', { id }); } catch (e) { toast(e.message, 'err', 6000); return; }
      paintLadder(); igPoll();
    } else if (act === 'ig-cancel') { await api('imagegen/cancel', { id }).catch(() => {}); }
    else if (act === 'ig-use') { imgCfg().backend = 'mtai|' + id; saveSettings(); X.imgB = null; renderModal(); renderImgBar(); toast(`${m.tier} is now the default image model`, 'ok'); }
    else if (act === 'ig-try') { imgCfg().backend = 'mtai|' + id; saveSettings(); X.imgB = null; closeModal(); toggleImgMode(true); const ta = $('#input'); ta.value = 'A cozy cabin in a snowy forest at night, warm light in the windows'; ta.dispatchEvent(new Event('input')); ta.focus(); ta.select(); }
    else if (act === 'ig-del') {
      if (!await confirmDialog({ title: `Delete ${m.tier} (${m.model})?`, text: `Frees about ${gb(m.size)}. You can download it again later. Pictures you made stay.` })) return;
      try { X.ig = await api('imagegen/delete', { id }); } catch (e) { toast(e.message, 'err'); }
      if (imgCfg().backend === 'mtai|' + id) { imgCfg().backend = null; saveSettings(); }
      X.imgB = null; renderModal(); renderImgBar();
    } else if (act === 'ig-open') api('imagegen/open-folder', {});
    else if (act === 'ig-move') {
      const nat = nativeApi(), p = nat ? await nat.pick_folder() : prompt('Folder for image models:');
      if (!p) return;
      try { X.ig = await api('imagegen/folder', { path: p }); toast('Image models now go to ' + X.ig.root, 'ok'); } catch (e) { toast(e.message, 'err'); }
      X.imgB = null; renderModal();
    }
  }

  /* Images tab in the Models window: built-in downloads, other sources, defaults, gallery */
  function renderImages(body) {
    if (!X.imgB) { body.innerHTML = '<div class="empty-box"><span class="spin"></span></div>'; loadImgBackends().then(() => { if (S.modalTab === 'images') renderModal(); }); return; }
    if (!X.ig) loadIG().then(() => { paintLadder(); if (igActive()) igPoll(); });
    if (!X.gallery) { X.gallery = []; api('images/list').then(r => { X.gallery = r.images || []; updateCounts(); if (S.modalTab === 'images' && !$('#modal').hidden) renderModal(); }).catch(() => {}); }
    const st = X.imgB, cfg = imgCfg(), b = pickBackend(), cloud = (X.cloud && X.cloud.providers) || [];
    const row = (dot, name, sub, side, btn = '') => `<div class="list-row"><i class="dot ${dot}"></i><div class="lr-main"><b>${name}</b><small>${sub}</small></div><span class="lr-side">${side}</span>${btn}</div>`;
    const cloudRow = id => { const p = cloud.find(x => x.id === id); const n = st.backends.filter(x => x.provider === id).length;
      return row(n ? 'live' : '', esc(p ? p.name : id), id === 'openai' ? 'gpt-image, DALL-E' : id === 'gemini' ? 'Imagen' : 'Grok image models', n ? `${n} model${n > 1 ? 's' : ''}` : 'no key',
        n ? '' : `<button class="btn small" data-tab-go="cloud">${icon('key', 13)}Add key</button>`); };
    body.innerHTML = `<div class="m-head"><div><h2>Image generation</h2><p>Make pictures on this PC or with cloud APIs. Press the Image chip under the message box, or type <b>/image</b>.</p></div>
        <div class="spacer"></div><button class="btn small" data-act="img-rescan">${icon('refresh', 14)}Scan again</button></div>
      ${ladderHtml()}
      <div class="sec-title">Other image apps on this PC</div>
      ${row(st.a1111 ? 'live' : '', 'Stable Diffusion WebUI (AUTOMATIC1111 / Forge)', esc(st.a1111_url) + ' · start it with the --api flag', st.a1111 ? 'online' : 'offline')}
      ${row(st.comfy ? 'live' : '', 'ComfyUI', esc(st.comfy_url) + ' · uses a simple txt2img workflow with your checkpoints', st.comfy ? 'online' : 'offline')}
      <div class="sec-title">Cloud</div>${cloudRow('openai')}${cloudRow('gemini')}${cloudRow('xai')}
      <div class="sec-title">Defaults</div>
      <div class="img-defaults">
        <div class="field"><label>Model</label><select id="imgDefModel">${b ? backendOptions(b.id) : '<option>No image model found</option>'}</select></div>
        <div class="field"><span class="lbl">Shape</span><div class="seg" id="imgDefAspect">${['square', 'wide', 'tall'].map(a => `<button data-aspect="${a}" class="${cfg.aspect === a ? 'on' : ''}">${ASPECT_ICON[a]}${a[0].toUpperCase() + a.slice(1)}</button>`).join('')}</div></div>
        <div class="field"><div class="row"><label>Steps (WebUI and ComfyUI)</label><span class="val" id="vSteps">${cfg.steps}</span></div><input type="range" id="imgSteps" min="4" max="60" step="1" value="${cfg.steps}"></div>
        <div class="field"><label>Avoid (negative prompt)</label><input type="text" id="imgNeg" value="${esc(cfg.negative || '')}" placeholder="blurry, extra fingers, watermark" spellcheck="false"></div>
        <div class="field"><div class="row"><label>Understand picture requests</label><label class="switch"><input type="checkbox" id="imgAuto" ${cfg.auto !== false ? 'checked' : ''}><i></i></label></div>
          <div class="help">“Generate me an image of a fox”, “draw me a castle”, “mach mir ein Bild von …” go to the image model by themselves, without the Image chip.</div></div>
      </div>
      <div class="sec-title gal-title">Gallery <span>${X.gallery.length} picture${X.gallery.length === 1 ? '' : 's'}</span><button class="btn small ghost" data-act="img-folder">${icon('folder', 13)}Open folder</button></div>
      ${X.gallery.length ? `<div class="gallery">${X.gallery.map((g, i) => `<div class="gal-it" style="--i:${Math.min(i, 20)}"><img src="${esc(g.url)}" data-zoom loading="lazy"><button data-act="img-del" data-name="${esc(g.name)}" title="Delete">${icon('trash', 13)}</button></div>`).join('')}</div>`
        : '<div class="empty-box">Pictures you make show up here.</div>'}`;
    const steps = $('#imgSteps'); setRangeFill(steps);
    steps.oninput = () => { cfg.steps = +steps.value; $('#vSteps').textContent = steps.value; setRangeFill(steps); saveSettings(); };
    $('#imgNeg').oninput = e => { cfg.negative = e.target.value; saveSettings(); };
    $('#imgAuto').onchange = e => { cfg.auto = e.target.checked; saveSettings(); };
    const dm = $('#imgDefModel'); if (b) dm.onchange = e => { cfg.backend = e.target.value; saveSettings(); renderImgBar(); };
  }

  /* ================================================================== PLANNING */
  const PLAN_SYS = `You are planning how to answer the user's last message. Do not answer it yet.
Write a short, concrete plan of 2 to 7 steps that you will follow when you answer. Each step has a short title (max 8 words) and one sentence of detail.
Reply with JSON only, in this shape: {"goal": "what the user wants, in one sentence", "steps": [{"title": "...", "detail": "..."}]}`;
  const PLAN_SCHEMA = { type: 'object', additionalProperties: false, required: ['goal', 'steps'], properties: {
    goal: { type: 'string' },
    steps: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['title', 'detail'], properties: { title: { type: 'string' }, detail: { type: 'string' } } } } } };

  function parsePlan(text) {
    const t = (text || '').replace(/<think>[\s\S]*?<\/think>/g, '');
    const a = t.indexOf('{'), b = t.lastIndexOf('}');
    if (a >= 0 && b > a) {
      try {
        const j = JSON.parse(t.slice(a, b + 1));
        const steps = (j.steps || []).map(s => typeof s === 'string' ? { title: s, detail: '' } : { title: String(s.title || s.step || '').trim(), detail: String(s.detail || s.description || '').trim() }).filter(s => s.title);
        if (steps.length) return { goal: String(j.goal || '').trim(), steps };
      } catch {}
    }
    const steps = [...t.matchAll(/^\s*(?:\d+[.)]|[-*])\s+(.+)$/gm)].map(m => {
      const [title, ...rest] = m[1].replace(/\*\*/g, '').split(/\s[-:–]\s|:\s/);
      return { title: title.trim().slice(0, 80), detail: rest.join(' ').trim() };
    }).filter(s => s.title);
    return { goal: '', steps: steps.slice(0, 9) };
  }
  function liveTitles(text) {
    return [...(text || '').matchAll(/"title"\s*:\s*"((?:[^"\\]|\\.)*)"/g)].map(m => { try { return JSON.parse('"' + m[1] + '"'); } catch { return m[1]; } });
  }

  async function makePlan(chat, asker) {
    const model = S.model;
    const pm = { id: uid(), role: 'assistant', kind: 'plan', model: model.name, pending: true, goal: '', steps: [], status: 'drafting' };
    chat.messages.push(pm);
    if (S.chat === chat) { const el = buildMsg(pm); el.classList.add('enter'); $('#thread').append(el); toBottom(true); }
    const ctrl = new AbortController();
    S.streaming = { ctrl, chat, msg: pm };
    updateSendBtn(); renderChatList();
    const hist = chat.messages.filter(m => !m.kind && !m.local && !m.error).slice(-8).map(m => ({
      role: m.role, content: m.role === 'assistant' ? splitThink(m).c.slice(0, 4000) : withFiles(m).slice(0, 12000), images: m === asker ? (m.images || []) : [] }));
    let text = '';
    try {
      const s = S.settings;
      const resp = await api('chat', { model_id: model.id, messages: hist, system: PLAN_SYS + (chat.code ? '\nThe answer will edit files in a code workspace, so plan the file changes.' : ''), format: PLAN_SCHEMA,
        options: model.backend === 'ollama' ? { temperature: 0.3, num_ctx: +s.num_ctx } : { temperature: 0.3 },
        think: hasCap(model, 'thinking') ? false : null, keep_alive: s.keep_alive }, { stream: true, signal: ctrl.signal });
      for await (const ev of ndjson(resp)) {
        if (ev.type === 'content') { text += ev.text; const t = liveTitles(text); if (t.length !== pm.steps.length) { pm.steps = t.map(x => ({ title: x, detail: '' })); paintPlan(pm); } }
        else if (ev.type === 'error') pm.error = ev.message || ev.error;
      }
    } catch (e) { pm.error = e.name === 'AbortError' ? 'Planning stopped.' : String(e.message || e); }
    S.streaming = null;
    delete pm.pending;
    if (!pm.error) {
      const p = parsePlan(text);
      if (p.steps.length) { pm.goal = p.goal; pm.steps = p.steps; pm.status = 'review'; }
      else pm.error = 'The model did not write a usable plan. Answer without one, or try again.';
    }
    if (pm.error) pm.status = 'failed';
    paintPlan(pm); updateSendBtn(); renderChatList();
    await saveChat(chat);
  }
  function planEl(m) {
    const el = document.createElement('div');
    el.className = 'msg assistant plan-msg'; el.dataset.id = m.id;
    el.innerHTML = `<div class="plan-card"></div>`;
    paintPlan(m, el);
    return el;
  }
  function paintPlan(m, el = msgEl(m)) {
    if (!el) return;
    const card = el.querySelector('.plan-card');
    const n = m.steps.length, prog = m.progress || 0, review = m.status === 'review';
    const sub = m.status === 'drafting' ? '<span class="shimmer">Planning…</span>' : m.status === 'review' ? 'Edit the steps, then run the plan'
      : m.status === 'approved' ? (prog >= n ? 'Done' : prog ? `Step ${Math.min(prog + 1, n)} of ${n}` : 'Approved') : m.status === 'skipped' ? 'Skipped' : 'No plan';
    const key = JSON.stringify([m.status, m.steps, m.goal, prog, m.error]);
    if (card._key === key) return;
    const editing = card.contains(document.activeElement) && review;
    if (editing) return;                          // do not re-render under the cursor
    card._key = key;
    card.dataset.state = m.status;
    card.innerHTML = `<div class="pc-head"><span class="pc-ic">${icon('plan', 16)}</span><b>Plan</b><span class="pc-sub">${sub}</span><span class="pc-model">${esc(m.model || '')}</span></div>
      ${m.goal ? `<div class="pc-goal" ${review ? 'contenteditable="plaintext-only" spellcheck="false"' : ''}>${esc(m.goal)}</div>` : ''}
      <ol class="pc-steps">${m.steps.map((s, i) => `<li class="pc-step ${m.status === 'approved' && i < prog ? 'done' : ''} ${m.status === 'approved' && i === prog && prog < n ? 'active' : ''}" style="--i:${i}">
        <span class="pc-num"><b>${i + 1}</b>${icon('check', 13)}</span>
        <div class="pc-body"><div class="pc-title" ${review ? 'contenteditable="plaintext-only" spellcheck="false"' : ''}>${esc(s.title)}</div>
        ${s.detail || review ? `<div class="pc-detail" ${review ? 'contenteditable="plaintext-only" spellcheck="false" data-ph="Detail (optional)"' : ''}>${esc(s.detail)}</div>` : ''}</div>
        ${review ? `<button class="pc-del" data-act="plan-del" data-i="${i}" title="Remove step">${icon('x', 13)}</button>` : ''}</li>`).join('')}</ol>
      ${m.error ? `<div class="err-box">${icon('alert', 16)}<span>${esc(m.error)}</span></div>` : ''}
      ${review ? `<button class="pc-add" data-act="plan-add">${icon('plus2', 14)}Add step</button>` : ''}
      ${review || m.status === 'failed' ? `<div class="pc-acts"><button class="btn small ghost" data-act="plan-skip">Answer without a plan</button>
        <button class="btn small ghost" data-act="plan-redo">${icon('refresh', 13)}New plan</button>
        ${review ? `<button class="btn small primary" data-act="plan-run">${icon('play', 13)}Run plan</button>` : ''}</div>` : ''}`;
  }
  function readPlanDom(m) {
    const el = msgEl(m); if (!el) return;
    const g = el.querySelector('.pc-goal'); if (g) m.goal = g.textContent.trim();
    m.steps = [...el.querySelectorAll('.pc-step')].map(li => ({ title: li.querySelector('.pc-title').textContent.trim(), detail: (li.querySelector('.pc-detail') || {}).textContent?.trim() || '' })).filter(s => s.title);
  }
  function currentPlan(chat, skip) {
    for (let i = chat.messages.length - 1; i >= 0; i--) {
      const m = chat.messages[i];
      if (m === skip || (m.role === 'assistant' && !m.kind) || m.auto) continue;
      if (m.kind === 'plan') return m.status === 'approved' ? m : null;
      if (m.role === 'user') return null;
    }
    return null;
  }
  async function planAction(act, btn, m) {
    const chat = S.chat;
    if (act === 'plan-add') { readPlanDom(m); m.steps.push({ title: 'New step', detail: '' }); paintPlan(m); const t = [...msgEl(m).querySelectorAll('.pc-title')].pop(); t.focus(); getSelection().selectAllChildren(t); return; }
    if (act === 'plan-del') { readPlanDom(m); m.steps.splice(+btn.dataset.i, 1); document.activeElement.blur(); paintPlan(m); return; }
    if (S.streaming) return;
    if (act === 'plan-run') {
      readPlanDom(m);
      if (!m.steps.length) { toast('The plan has no steps', 'err'); return; }
      m.status = 'approved'; m.progress = 0; paintPlan(m);
      await generate();
    } else if (act === 'plan-skip') {
      m.status = 'skipped'; paintPlan(m); await generate();
    } else if (act === 'plan-redo') {
      chat.messages = chat.messages.filter(x => x !== m); msgEl(m)?.remove();
      const asker = [...chat.messages].reverse().find(x => x.role === 'user' && !x.auto);
      if (asker) await makePlan(chat, asker);
    }
  }
  function planText(p) {
    return `\n\nPLAN: you wrote this plan for your answer and the user approved it. Follow it in order. Start each step with a Markdown heading exactly like "### Step 1: ${p.steps[0].title}". Keep each step focused, then end with a short wrap-up.
Goal: ${p.goal || '(see the last message)'}
${p.steps.map((s, i) => `${i + 1}. ${s.title}${s.detail ? ' - ' + s.detail : ''}`).join('\n')}`;
  }
  function paintPlanStrip(el, m) {
    const chat = (S.streaming && S.streaming.msg === m) ? S.streaming.chat : S.chat;
    const pm = chat && chat.messages.find(x => x.id === m.planId);
    let strip = el.querySelector('.plan-strip');
    if (!pm || !pm.steps.length) { if (strip) strip.remove(); return; }
    const n = pm.steps.length, text = splitThink(m).c;
    let cur = 0;
    for (const x of text.matchAll(/^\s*#{1,4}\s*\**\s*Step\s+(\d+)/gim)) cur = Math.max(cur, Math.min(n, +x[1]));
    const done = !m.pending && !m.error && !m.stopped;
    const html = `${icon('plan', 13)}<div class="ps-dots">${pm.steps.map((s, i) => `<i class="${done || i + 1 < cur ? 'd' : i + 1 === cur ? 'a' : ''}" title="${esc(s.title)}"></i>`).join('')}</div>
      <span>${done ? `Plan done · ${n} step${n > 1 ? 's' : ''}` : m.pending ? (cur ? `Step ${cur} of ${n}: ${esc(pm.steps[cur - 1].title)}` : 'Starting the plan…') : 'Plan stopped'}</span>`;
    if (!strip) { strip = document.createElement('div'); strip.className = 'plan-strip'; el.querySelector('.body').before(strip); }
    if (strip._html !== html) { strip._html = html; strip.innerHTML = html; }
    const prog = done ? n : Math.max(0, cur - 1);
    if (pm.progress !== prog) { pm.progress = prog; paintPlan(pm); }
    if (m.pending) X.livePlan = m.id;
    else if (X.livePlan === m.id) { X.livePlan = null; if (done) { const r = strip.getBoundingClientRect(); confetti({ x: r.left + 60, y: r.top, n: 60, spread: .7 }); } }
  }
  function togglePlan(force) {
    S.settings.plan = force ?? !S.settings.plan; saveSettings(); updatePlanChip();
    toast(S.settings.plan ? 'Planning on: the AI shows you a plan before it answers' : 'Planning off');
  }
  const updatePlanChip = () => $('#planChip').classList.toggle('on', !!(S.settings && S.settings.plan));

  /* ===================================================================== STYLE */
  const PERSONAS = [
    { id: 'default', e: '✨', name: 'Default', text: '' },
    { id: 'friend', e: '🙂', name: 'Friendly buddy', text: 'Talk like a warm, upbeat friend: casual words, encouragement and a bit of humor.' },
    { id: 'pro', e: '💼', name: 'Professional', text: 'Be precise, neutral and businesslike, like a senior consultant.' },
    { id: 'teacher', e: '📚', name: 'Patient teacher', text: 'Teach step by step, use simple examples and analogies, and check understanding with a short question at the end.' },
    { id: 'coach', e: '🔥', name: 'Hype coach', text: 'Be an energetic motivational coach: bold, positive, and push the user to take action.' },
    { id: 'wit', e: '😏', name: 'Dry wit', text: 'Be helpful with dry, sarcastic humor. Never mean, and never at the cost of correctness.' },
    { id: 'pirate', e: '🏴‍☠️', name: 'Pirate', text: 'Talk like a cheerful pirate captain (arr, matey, ship metaphors) but keep all facts and code correct.' },
    { id: 'bard', e: '🎭', name: 'Bard', text: 'Speak in a Shakespeare-like Early Modern English style with flourish, but keep the content correct and clear.' },
    { id: 'noir', e: '🕵️', name: 'Noir detective', text: 'Narrate like a 1940s noir detective: moody metaphors and short, punchy sentences.' },
    { id: 'zen', e: '🧘', name: 'Zen monk', text: 'Be calm and wise like a Zen monk: gentle, minimal and thoughtful.' },
    { id: 'caveman', e: '🦴', name: 'Caveman', text: 'Talk like a smart caveman: short words, no articles, but correct facts.' },
    { id: 'robot', e: '🤖', name: 'Retro robot', text: 'Speak like a friendly retro robot: literal, precise, the occasional BEEP BOOP.' },
  ];
  const STYLE_OPTS = [
    ['length', 'Answer length', [['short', 'Short'], ['', 'Balanced'], ['long', 'Detailed']]],
    ['tone', 'Tone', [['casual', 'Casual'], ['', 'Neutral'], ['formal', 'Formal']]],
    ['level', 'Explain for', [['beginner', 'Beginner'], ['', 'Everyone'], ['expert', 'Expert']]],
    ['format', 'Layout', [['prose', 'Paragraphs'], ['', 'Mixed'], ['bullets', 'Bullets']]],
    ['emoji', 'Emoji', [['none', 'None'], ['', 'Rarely'], ['lots', 'Lots']]],
  ];
  const STYLE_TEXT = {
    length: { short: 'Keep answers short: a few sentences, no filler.', long: 'Give detailed, thorough answers with examples.' },
    tone: { casual: 'Use a casual, relaxed tone.', formal: 'Use a formal, polite tone.' },
    level: { beginner: 'Explain for a beginner: no jargon, or explain every technical term.', expert: 'The user is an expert: skip the basics and be technical.' },
    format: { prose: 'Write in flowing paragraphs, avoid bullet lists.', bullets: 'Prefer bullet points and short sections.' },
    emoji: { none: 'Never use emoji.', lots: 'Use plenty of fitting emoji.' },
  };
  const LANGS = ['', 'English', 'Deutsch', 'Français', 'Español', 'Italiano', 'Português', 'Nederlands', 'Polski', 'Türkçe', '日本語', '中文', 'other'];
  const styleCfg = () => (S.settings.style && typeof S.settings.style === 'object') ? S.settings.style : (S.settings.style = {});
  window.mtaiStyle = { PERSONAS, STYLE_OPTS, LANGS, styleCfg, confetti: o => confetti(o) };     // welcome.js asks the same questions on first start
  function styleText() {
    if (!settingsReady()) return '';
    const st = styleCfg(), lines = [];
    const p = PERSONAS.find(x => x.id === st.persona);
    if (p && p.text) lines.push(p.text);
    for (const [k] of STYLE_OPTS) if (STYLE_TEXT[k][st[k]]) lines.push(STYLE_TEXT[k][st[k]]);
    const lang = st.lang === 'other' ? (st.langOther || '').trim() : st.lang;
    if (lang) lines.push(`Always answer in ${lang}, unless the user asks for another language.`);
    if ((st.name || '').trim()) lines.push(`The user's name is ${st.name.trim()}. Use it now and then, naturally.`);
    if ((st.about || '').trim()) lines.push(`About the user: ${st.about.trim()}`);
    if ((st.rules || '').trim()) lines.push(st.rules.trim());
    if (!lines.length) return '';
    return '\n\nHOW TO TALK TO THE USER (follow this unless the user asks otherwise; keep facts and code correct):\n- ' + lines.join('\n- ');
  }
  function renderStyle() {
    const st = styleCfg();
    $('#drawerBody').innerHTML = `
      <div class="field"><span class="lbl">Personality</span><div class="personas">${PERSONAS.map(p => `<button class="persona ${(st.persona || 'default') === p.id ? 'on' : ''}" data-persona="${p.id}"><span class="pe">${p.e}</span><span>${p.name}</span></button>`).join('')}</div></div>
      ${STYLE_OPTS.map(([k, label, opts]) => `<div class="field"><span class="lbl">${label}</span><div class="seg" data-sopt="${k}">${opts.map(([v, l]) => `<button data-v="${v}" class="${(st[k] || '') === v ? 'on' : ''}">${l}</button>`).join('')}</div></div>`).join('')}
      <div class="field"><label>Language</label><select id="stLang">${LANGS.map(l => `<option value="${l}" ${(st.lang || '') === l ? 'selected' : ''}>${l === '' ? 'Same as my message' : l === 'other' ? 'Other…' : l}</option>`).join('')}</select>
        <input type="text" id="stLangOther" placeholder="Language" value="${esc(st.langOther || '')}" ${st.lang === 'other' ? '' : 'hidden'} style="margin-top:8px"></div>
      <div class="field"><label>Your name</label><input type="text" id="stName" value="${esc(st.name || '')}" placeholder="What should the AI call you?" spellcheck="false"></div>
      <div class="field"><label>About you</label><textarea id="stAbout" rows="3" placeholder="Job, interests, what you are learning, your PC…">${esc(st.about || '')}</textarea></div>
      <div class="field"><label>Extra rules</label><textarea id="stRules" rows="3" placeholder="Always… / Never…  e.g. Always give metric units.">${esc(st.rules || '')}</textarea>
        <div class="help">Works with every model, local and cloud. It is added after the system prompt from the Chat tab.</div></div>
      <details class="field st-preview"><summary>${icon('eye', 13)}What the AI is told</summary><pre id="stPreview"></pre></details>
      <div class="field st-acts"><button class="btn ghost" data-act="style-test">${icon('chat', 14)}Try it</button><button class="btn ghost" data-act="style-reset">${icon('refresh', 14)}Reset style</button></div>`;
    const prev = () => { $('#stPreview').textContent = styleText().trim() || '(nothing extra: the model uses its normal style)'; };
    prev();
    const save = () => { saveSettings(); prev(); };
    $$('.persona').forEach(b => b.onclick = () => { st.persona = b.dataset.persona; $$('.persona').forEach(x => x.classList.toggle('on', x === b)); save(); b.classList.remove('pop'); void b.offsetWidth; b.classList.add('pop'); });
    $$('[data-sopt]').forEach(seg => seg.onclick = e => { const b = e.target.closest('[data-v]'); if (!b) return; st[seg.dataset.sopt] = b.dataset.v; seg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); save(); });
    $('#stLang').onchange = e => { st.lang = e.target.value; $('#stLangOther').hidden = st.lang !== 'other'; save(); };
    for (const [id, k] of [['#stLangOther', 'langOther'], ['#stName', 'name'], ['#stAbout', 'about'], ['#stRules', 'rules']]) $(id).oninput = e => { st[k] = e.target.value; save(); };
  }

  window.extraSystem = (chat, msg) => {
    let s = styleText();
    const plan = chat && currentPlan(chat, msg);
    if (plan && msg) { msg.planId = plan.id; s += planText(plan); }
    return s + pictureText(chat);
  };
  // pictures stay out of the model's history, so without this note "show me the full cat" reaches it with no context
  function pictureText(chat) {
    const pics = ((chat && chat.messages) || []).filter(m => m.kind === 'image' && m.image).slice(-6);
    if (!pics.length) return '';
    return `\n\nThis chat also contains pictures that MTAI's built-in image tool painted for the user. You did not make them, you cannot see them, and you cannot make pictures yourself.
Their descriptions, oldest first:\n${pics.map((m, i) => `${i + 1}. ${m.prompt}`).join('\n')}
When the user talks about "it", "her", "the cat" and so on, they most likely mean the last picture. If they want a changed or new picture, tell them in one short sentence to ask for it directly (for example "make it at night" or "make me an image of ..."), and MTAI will paint it. Do not refuse harmless picture requests and do not link to image websites.`;
  }

  /* ================================================================ READ ALOUD */
  function plainSpeech(m) {
    return splitThink(m).c.replace(/```[\s\S]*?(```|$)/g, ' (code) ').replace(/<(file|edit)[\s\S]*?<\/\1>/g, ' (file change) ')
      .replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[#*_`>|~]+/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function pickVoice() {
    const vs = speechSynthesis.getVoices().filter(v => !privacyOn() || v.localService);
    const st = settingsReady() ? styleCfg() : {};
    const code = { English: 'en', Deutsch: 'de', Français: 'fr', Español: 'es', Italiano: 'it', Português: 'pt', Nederlands: 'nl', Polski: 'pl', Türkçe: 'tr', 日本語: 'ja', 中文: 'zh' }[st.lang] || (navigator.language || 'en').slice(0, 2);
    const same = vs.filter(v => v.lang.toLowerCase().startsWith(code));
    return same.find(v => /natural|neural/i.test(v.name)) || same[0] || vs[0] || null;
  }
  function speak(m, btn) {
    if (!('speechSynthesis' in window)) { toast('Read aloud is not available here', 'err'); return; }
    const was = X.speakId;
    speechSynthesis.cancel(); X.speakId = null;
    $$('.acts [data-act="speak"].on').forEach(b => { b.classList.remove('on'); b.innerHTML = icon('speaker', 15); });
    if (was === m.id) return;
    const text = plainSpeech(m); if (!text) return;
    const parts = text.match(/[^.!?]+[.!?]*\s*/g) || [text], chunks = [];
    for (const p of parts) { if (chunks.length && (chunks[chunks.length - 1] + p).length < 220) chunks[chunks.length - 1] += p; else chunks.push(p); }
    const v = pickVoice();
    X.speakId = m.id; btn.classList.add('on'); btn.innerHTML = icon('stopSq', 15);
    chunks.forEach((c, i) => {
      const u = new SpeechSynthesisUtterance(c);
      if (v) { u.voice = v; u.lang = v.lang; }
      u.rate = 1.03;
      if (i === chunks.length - 1) u.onend = () => { if (X.speakId === m.id) { X.speakId = null; btn.classList.remove('on'); btn.innerHTML = icon('speaker', 15); } };
      speechSynthesis.speak(u);
    });
  }

  /* ============================================================== PINNED CHATS */
  async function togglePin(id) {
    const c = S.chats.find(x => x.id === id); if (!c) return;
    c.pinned = !c.pinned;
    for (const ch of [S.chat, S.streaming && S.streaming.chat]) if (ch && ch.id === id) ch.pinned = c.pinned;
    renderChatList();
    try { await api('chats/pin', { id, pinned: c.pinned }); } catch {}
    toast(c.pinned ? 'Pinned to the top' : 'Unpinned');
  }

  /* ===================================================== SELECTION QUICK ACTIONS */
  const selBar = document.createElement('div');
  selBar.className = 'sel-bar'; selBar.hidden = true;
  selBar.innerHTML = [['ask', 'quote', 'Ask about this'], ['explain', 'bulb', 'Explain'], ['simplify', 'wand', 'Simpler'], ['translate', 'globe', 'Translate'],
    ['speak', 'speaker', 'Read'], ['copy', 'copy', 'Copy']].map(([a, ic, t]) => `<button data-sel="${a}" title="${t}">${icon(ic, 14)}<span>${t}</span></button>`).join('');
  document.body.append(selBar);
  let selText = '';
  function showSelBar() {
    const sel = getSelection(), text = sel.toString().trim();
    if (!text || text.length < 2 || sel.rangeCount === 0) { selBar.hidden = true; return; }
    const node = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement);
    if (!node || !node.closest('#thread .msg') || node.closest('textarea,input,[contenteditable]')) { selBar.hidden = true; return; }
    selText = text.slice(0, 4000);
    const r = sel.getRangeAt(0).getBoundingClientRect();
    selBar.hidden = false;
    const w = selBar.offsetWidth;
    selBar.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + 'px';
    selBar.style.top = Math.max(8, r.top - 46) + 'px';
    selBar.classList.remove('in'); void selBar.offsetWidth; selBar.classList.add('in');
  }
  document.addEventListener('mouseup', e => { if (!(e.target.closest && e.target.closest('.sel-bar'))) setTimeout(showSelBar, 10); });
  document.addEventListener('mousedown', e => { if (!(e.target.closest && e.target.closest('.sel-bar'))) selBar.hidden = true; });
  $('#scroller').addEventListener('scroll', () => { selBar.hidden = true; }, { passive: true });
  selBar.onmousedown = e => e.preventDefault();
  selBar.onclick = async e => {
    const b = e.target.closest('[data-sel]'); if (!b) return;
    const a = b.dataset.sel, q = selText.length > 1500 ? selText.slice(0, 1500) + '…' : selText;
    selBar.hidden = true;
    if (a === 'copy') { await navigator.clipboard.writeText(selText); toast('Copied', 'ok', 1400); return; }
    if (a === 'speak') { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(selText); const v = pickVoice(); if (v) u.voice = v; speechSynthesis.speak(u); return; }
    const ta = $('#input');
    const quoted = q.split('\n').map(l => '> ' + l).join('\n');
    if (a === 'ask') { ta.value = quoted + '\n\n'; autosize(ta); updateSendBtn(); ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); return; }
    const lang = (settingsReady() && styleCfg().lang && styleCfg().lang !== 'other') ? styleCfg().lang : (navigator.language || '').startsWith('de') ? 'German' : 'English';
    ta.value = quoted + '\n\n' + { explain: 'Explain this part in simple words.', simplify: 'Say this again, simpler and shorter.', translate: `Translate this into ${lang}.` }[a];
    autosize(ta); updateSendBtn();
    if (!S.streaming && S.model && S.model.chattable) submit(); else ta.focus();
  };

  /* ===================================================================== FUN */
  /* confetti: canvas burst, no library */
  function confetti({ x = innerWidth / 2, y = innerHeight / 3, n = 140, spread = 1 } = {}) {
    if (!animOk()) return;
    const c = document.createElement('canvas'); c.className = 'confetti';
    c.width = innerWidth * devicePixelRatio; c.height = innerHeight * devicePixelRatio;
    document.body.append(c);
    const g = c.getContext('2d'); g.scale(devicePixelRatio, devicePixelRatio);
    const cs = getComputedStyle(document.documentElement);
    const cols = [cs.getPropertyValue('--accent'), cs.getPropertyValue('--accent2'), cs.getPropertyValue('--accent-l'), '#ffffff', '#fbbf24', '#5eead4', '#fb7185'].map(s => s.trim()).filter(Boolean);
    const P = Array.from({ length: n }, () => {
      const a = -Math.PI / 2 + (Math.random() - .5) * Math.PI * spread, v = 6 + Math.random() * 9;
      return { x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, r: Math.random() * Math.PI, vr: (Math.random() - .5) * .35, w: 5 + Math.random() * 6, h: 3 + Math.random() * 5, c: cols[(Math.random() * cols.length) | 0], life: 1 };
    });
    let last = performance.now();
    const step = t => {
      const dt = Math.min(2, (t - last) / 16.7); last = t;
      g.clearRect(0, 0, innerWidth, innerHeight);
      let alive = 0;
      for (const p of P) {
        p.vy += .32 * dt; p.vx *= .985; p.vy *= .985; p.x += p.vx * dt; p.y += p.vy * dt; p.r += p.vr * dt; p.life -= .006 * dt;
        if (p.life <= 0 || p.y > innerHeight + 20) continue;
        alive++;
        g.save(); g.globalAlpha = Math.min(1, p.life * 2); g.translate(p.x, p.y); g.rotate(p.r); g.fillStyle = p.c;
        g.fillRect(-p.w / 2, -p.h / 2 * Math.abs(Math.cos(p.r * 2)), p.w, p.h * Math.abs(Math.cos(p.r * 2)) + .5); g.restore();
      }
      if (alive) requestAnimationFrame(step); else c.remove();
    };
    requestAnimationFrame(step);
  }

  const EIGHT = ['Yes, without a doubt.', 'Signs point to yes.', 'Count on it.', 'Very likely.', 'The stars say yes.', 'Probably, yes.',
    'Ask again after a coffee.', 'Too foggy to tell right now.', 'Better not tell you now.', 'Focus and ask again.',
    'Unlikely.', 'My sources say no.', 'No. Absolutely not.', 'The orb frowns at this.', 'Doubtful.', 'Only if you really want it.'];
  function funCommand(cmd, arg) {
    const chat = S.chat;
    let card;
    if (cmd === 'roll' || cmd === 'dice') {
      const m = (arg || '').match(/^(\d{0,2})d(\d{1,4})\s*([+-]\s*\d+)?/i);
      const cnt = Math.max(1, Math.min(20, +(m && m[1]) || 1)), sides = Math.max(2, Math.min(1000, +(m && m[2]) || 6)), mod = m && m[3] ? +m[3].replace(/\s/g, '') : 0;
      const rolls = Array.from({ length: cnt }, () => 1 + Math.floor(Math.random() * sides));
      const total = rolls.reduce((a, b) => a + b, 0) + mod;
      card = { icon: 'dice', anim: 'roll', title: `Rolled ${cnt}d${sides}${mod ? (mod > 0 ? '+' : '') + mod : ''}`, big: String(total),
        detail: cnt > 1 || mod ? rolls.join(' + ') + (mod ? ` ${mod > 0 ? '+' : '−'} ${Math.abs(mod)}` : '') : (rolls[0] === sides ? 'Natural max!' : rolls[0] === 1 ? 'Ouch, a 1.' : '') };
    } else if (cmd === 'coin' || cmd === 'flip') {
      const heads = Math.random() < .5;
      card = { icon: 'spark', anim: 'flip', title: 'Coin flip', big: heads ? 'Heads' : 'Tails', detail: '' };
    } else if (cmd === '8ball') {
      card = { icon: 'spark', anim: 'shake', title: arg ? `“${arg.slice(0, 120)}”` : 'The orb has spoken', big: EIGHT[(Math.random() * EIGHT.length) | 0], detail: '' };
    } else if (cmd === 'pick') {
      const opts = (arg || '').split(/\s*(?:,|\bor\b|\/|\n)\s*/i).map(s => s.trim()).filter(Boolean);
      if (opts.length < 2) { toast('Give at least two options: /pick pizza, sushi, tacos', 'err'); return; }
      card = { icon: 'shuffle', anim: 'roll', title: `Picked from ${opts.length}`, big: opts[(Math.random() * opts.length) | 0], detail: opts.join(' · ') };
    } else { confetti(); confetti({ x: innerWidth * .2, y: innerHeight * .6, n: 60 }); confetti({ x: innerWidth * .8, y: innerHeight * .6, n: 60 }); return; }
    const msg = { id: uid(), role: 'assistant', kind: 'fun', local: true, ...card, t: Date.now() };
    if (!chat.messages.length) $('#thread').innerHTML = '';
    chat.messages.push(msg);
    if (!chat.title) chat.title = card.title;
    const el = buildMsg(msg); el.classList.add('enter', 'fresh-fun'); $('#thread').append(el); toBottom(true);
    if (card.detail === 'Natural max!') { const r = el.getBoundingClientRect(); confetti({ x: r.left + 80, y: r.top + 20, n: 80 }); }
    saveChat(chat);
  }
  function funEl(m) {
    const el = document.createElement('div');
    el.className = 'msg assistant fun-msg'; el.dataset.id = m.id;
    el.innerHTML = `<div class="fun-card a-${m.anim || 'roll'}"><span class="fun-ic">${icon(m.icon === 'shuffle' ? 'refresh' : m.icon, 22)}</span>
      <div class="fun-main"><small></small><b></b><em></em></div></div>`;
    el.querySelector('small').textContent = m.title; el.querySelector('b').textContent = m.big; el.querySelector('em').textContent = m.detail || '';
    return el;
  }

  /* Play menu: AI games (any chat model) and small offline toys */
  const GAMES = [
    { e: '❓', name: 'Twenty questions', sub: 'Think of something, the AI guesses', text: 'Let\'s play 20 Questions! I am thinking of something. Ask me one yes/no question at a time, number your questions, and try to guess it in 20 or fewer. Start with your first question.' },
    { e: '🧠', name: 'Trivia quiz', sub: '5 questions, keeps score', text: 'Quiz me with 5 fun trivia questions on mixed topics, one at a time, multiple choice A-D. After each answer tell me if I was right, add a short fun fact, and keep score. Give my final score at the end. Ask the first question now.' },
    { e: '🗡️', name: 'Text adventure', sub: 'Dark fantasy, your choices', text: 'Run a short dark fantasy text adventure for me. Describe each scene in 3-4 vivid sentences, then give me 3 numbered choices (I can also type my own). Track my health and inventory and show them after each scene. Start now.' },
    { e: '🤔', name: 'Would you rather', sub: 'Odd choices, honest takes', text: 'Let\'s play Would You Rather. Give me a creative, funny dilemma, wait for my choice, react to it, then give the next one.' },
    { e: '📖', name: 'Story ping-pong', sub: 'Write a story together', text: 'Let\'s write a story together. You write 2-3 sentences with a surprising twist, then stop and let me continue. Keep it going turn by turn. Start with an intriguing opening.' },
    { e: '🎬', name: 'Emoji riddles', sub: 'Guess the movie from emoji', text: 'Give me an emoji riddle: a famous movie, game or song told only with emoji. Let me guess, give a hint if I am wrong, keep score, and give the next riddle after each one.' },
    { e: '🔥', name: 'Gentle roast', sub: 'Friendly, never mean', text: 'Ask me 3 quick questions about myself, one at a time. Then write a short, friendly, funny roast of me based on my answers. Keep it kind.' },
    { e: '🕵️', name: 'Murder mystery', sub: 'Interrogate suspects', text: 'Run a short murder mystery game. Describe the crime scene and 4 suspects. I can question suspects and inspect clues; answer in character. I win if I name the killer and the motive. Begin.' },
  ];
  function openPlay() {
    const d = $('#dialog');
    const best = (S.settings.fun && S.settings.fun.snake) || 0;
    d.innerHTML = `<div class="dialog play-dialog"><div class="pl-head"><span class="pl-ic">${icon('game', 22)}</span><div><h3>Play</h3><p>Games with the AI, plus a few toys that work offline.</p></div></div>
      <div class="sec-title">With the AI ${S.model ? `<span>· ${esc(S.model.name)}</span>` : ''}</div>
      <div class="pl-grid">${GAMES.map((g, i) => `<button class="pl-card" data-game="${i}" style="--i:${i}"><span class="pe">${g.e}</span><b>${g.name}</b><small>${g.sub}</small></button>`).join('')}</div>
      <div class="sec-title">Offline toys</div>
      <div class="pl-grid toys">
        <button class="pl-card" data-toy="snake" style="--i:8"><span class="pe">🐍</span><b>Orb snake</b><small>Best: ${best}</small></button>
        <button class="pl-card" data-toy="roll" style="--i:9"><span class="pe">🎲</span><b>Roll dice</b><small>/roll 2d6</small></button>
        <button class="pl-card" data-toy="coin" style="--i:10"><span class="pe">🪙</span><b>Flip a coin</b><small>/coin</small></button>
        <button class="pl-card" data-toy="8ball" style="--i:11"><span class="pe">🔮</span><b>Magic orb</b><small>/8ball will it work?</small></button>
        <button class="pl-card" data-toy="party" style="--i:12"><span class="pe">🎉</span><b>Confetti</b><small>/confetti</small></button>
      </div>
      <div class="d-acts"><button class="btn ghost" data-r="0">Close</button></div></div>`;
    d.hidden = false;
    d.onclick = e => {
      if (e.target === d || e.target.closest('[data-r]')) { d.hidden = true; d.onclick = null; return; }
      const g = e.target.closest('[data-game]');
      if (g) {
        if (!S.model || !S.model.chattable) { toast('Pick a chat model first', 'err'); return; }
        d.hidden = true; d.onclick = null;
        if (S.streaming) { toast('Wait for the current answer first'); return; }
        newChat(); send(GAMES[+g.dataset.game].text, []);
        return;
      }
      const t = e.target.closest('[data-toy]'); if (!t) return;
      const toy = t.dataset.toy;
      if (toy === 'snake') { snake(); return; }
      d.hidden = true; d.onclick = null;
      if (toy === '8ball') { const ta = $('#input'); ta.value = '/8ball '; autosize(ta); ta.focus(); return; }
      funCommand(toy === 'party' ? 'confetti' : toy, toy === 'roll' ? '2d6' : '');
    };
  }

  /* Orb snake: tiny canvas game, best score saved in settings */
  function snake() {
    const d = $('#dialog');
    d.innerHTML = `<div class="dialog snake-dialog"><div class="sn-top"><b>Orb snake</b><span class="sn-score">0</span><span class="sn-best"></span></div>
      <canvas width="408" height="408"></canvas><div class="sn-help">Arrow keys or WASD · Space pauses · Esc closes</div>
      <div class="d-acts"><button class="btn ghost" data-r="0">Close</button><button class="btn primary" data-r="again">Restart</button></div></div>`;
    d.hidden = false;
    const cv = d.querySelector('canvas'), g = cv.getContext('2d'), N = 17, C = cv.width / N;
    const cs = getComputedStyle(document.documentElement), A = cs.getPropertyValue('--accent').trim(), B = cs.getPropertyValue('--accent2').trim();
    const fun = (S.settings.fun && typeof S.settings.fun === 'object') ? S.settings.fun : (S.settings.fun = {});
    let body, dir, next, food, score, dead, paused, timer, speed;
    const place = () => { do food = { x: (Math.random() * N) | 0, y: (Math.random() * N) | 0 }; while (body.some(p => p.x === food.x && p.y === food.y)); };
    const reset = () => { body = [{ x: 8, y: 8 }, { x: 7, y: 8 }, { x: 6, y: 8 }]; dir = next = { x: 1, y: 0 }; score = 0; dead = false; paused = false; speed = 130; place(); upd(); clearInterval(timer); timer = setInterval(tick, speed); };
    const upd = () => { d.querySelector('.sn-score').textContent = score; d.querySelector('.sn-best').textContent = 'Best ' + (fun.snake || 0); };
    const tick = () => {
      if (d.hidden || !cv.isConnected) { clearInterval(timer); removeEventListener('keydown', key, true); return; }
      if (paused || dead) return draw();
      dir = next;
      const h = { x: (body[0].x + dir.x + N) % N, y: (body[0].y + dir.y + N) % N };
      if (body.some(p => p.x === h.x && p.y === h.y)) {
        dead = true;
        if (score > (fun.snake || 0)) { fun.snake = score; saveSettings(); const r = cv.getBoundingClientRect(); confetti({ x: r.left + r.width / 2, y: r.top + 60, n: 90 }); }
        upd(); return draw();
      }
      body.unshift(h);
      if (h.x === food.x && h.y === food.y) { score++; upd(); place(); if (speed > 70) { speed -= 4; clearInterval(timer); timer = setInterval(tick, speed); } } else body.pop();
      draw();
    };
    const draw = () => {
      g.clearRect(0, 0, cv.width, cv.height);
      g.fillStyle = 'rgba(255,255,255,.035)';
      for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) if ((i + j) % 2) g.fillRect(i * C, j * C, C, C);
      const t = performance.now() / 300;
      g.shadowBlur = 18; g.shadowColor = B; g.fillStyle = B;
      g.beginPath(); g.arc(food.x * C + C / 2, food.y * C + C / 2, C * (.3 + Math.sin(t) * .04), 0, 7); g.fill();
      g.shadowColor = A;
      body.forEach((p, i) => { g.globalAlpha = 1 - i / (body.length + 6); g.fillStyle = i ? A : '#fff'; g.beginPath(); g.roundRect(p.x * C + 2, p.y * C + 2, C - 4, C - 4, 7); g.fill(); });
      g.globalAlpha = 1; g.shadowBlur = 0;
      if (dead || paused) {
        g.fillStyle = 'rgba(0,0,0,.55)'; g.fillRect(0, 0, cv.width, cv.height);
        g.fillStyle = '#fff'; g.font = '600 22px Segoe UI'; g.textAlign = 'center';
        g.fillText(dead ? `Game over · ${score}` : 'Paused', cv.width / 2, cv.height / 2);
        g.font = '13px Segoe UI'; g.fillStyle = 'rgba(255,255,255,.7)'; g.fillText(dead ? 'Press Space or Restart' : 'Space to go on', cv.width / 2, cv.height / 2 + 26);
      }
    };
    const key = e => {
      if (d.hidden) { removeEventListener('keydown', key, true); return; }
      const k = e.key.toLowerCase();
      const m = { arrowup: [0, -1], w: [0, -1], arrowdown: [0, 1], s: [0, 1], arrowleft: [-1, 0], a: [-1, 0], arrowright: [1, 0], d: [1, 0] }[k];
      if (m) { e.preventDefault(); e.stopPropagation(); if (m[0] !== -dir.x || m[1] !== -dir.y) next = { x: m[0], y: m[1] }; }
      else if (k === ' ') { e.preventDefault(); e.stopPropagation(); if (dead) reset(); else paused = !paused; }
      else if (k === 'escape') { clearInterval(timer); removeEventListener('keydown', key, true); }
    };
    addEventListener('keydown', key, true);
    d.onclick = e => {
      const b = e.target.closest('[data-r]');
      if (b && b.dataset.r === 'again') { reset(); return; }
      if (e.target === d || b) { d.hidden = true; d.onclick = null; clearInterval(timer); removeEventListener('keydown', key, true); }
    };
    reset();
  }

  /* easter eggs: the Konami code throws a party, the logo does not like being poked */
  const KONAMI = ['arrowup', 'arrowup', 'arrowdown', 'arrowdown', 'arrowleft', 'arrowright', 'arrowleft', 'arrowright', 'b', 'a'];
  let kpos = 0;
  document.addEventListener('keydown', e => {
    const k = e.key.toLowerCase();
    kpos = k === KONAMI[kpos] ? kpos + 1 : (k === KONAMI[0] ? 1 : 0);
    if (kpos === KONAMI.length) {
      kpos = 0;
      document.body.classList.add('party'); toast('Party mode! 🎉', 'ok');
      confetti(); setTimeout(() => confetti({ x: innerWidth * .25, n: 90 }), 300); setTimeout(() => confetti({ x: innerWidth * .75, n: 90 }), 600);
      setTimeout(() => document.body.classList.remove('party'), 9000);
    }
  });
  let pokes = 0, pokeT = 0;
  $('.brand .logo').addEventListener('click', e => {
    pokes = Date.now() - pokeT < 700 ? pokes + 1 : 1; pokeT = Date.now();
    const l = e.currentTarget; l.classList.remove('poke'); void l.offsetWidth; l.classList.add('poke');
    if (pokes === 5) { pokes = 0; l.classList.remove('poke'); l.classList.add('spin-out'); setTimeout(() => l.classList.remove('spin-out'), 1600);
      toast(['Okay, okay, I am awake.', 'That tickles.', 'The orb sees you.', 'Achievement: Logo poker'][(Math.random() * 4) | 0]); const r = l.getBoundingClientRect(); confetti({ x: r.left + 10, y: r.top + 10, n: 50, spread: 1.4 }); }
  });

  /* ============================================================= SLASH COMMANDS */
  COMMANDS.push(
    { cmd: 'image', desc: 'Make a picture (image model)', text: '/image ' },
    { cmd: 'plan', desc: 'Plan first: you edit the plan, then the AI answers', text: '/plan ' },
    { cmd: 'eli5', desc: 'Explain like I am five', text: 'Explain like I am five: ' },
    { cmd: 'tldr', desc: 'Very short summary', text: 'TL;DR in 2 sentences:\n\n' },
    { cmd: 'quiz', desc: 'Quiz me on a topic', text: 'Quiz me on TOPIC: 5 questions, one at a time, tell me if I was right and keep score.' },
    { cmd: 'proscons', desc: 'Pros and cons table', text: 'Make a pros and cons table for: ' },
    { cmd: 'email', desc: 'Write an email', text: 'Write a short, friendly email that: ' },
    { cmd: 'joke', desc: 'Tell a joke', text: 'Tell me a short, clever joke about ' },
    { cmd: 'poem', desc: 'Write a short poem', text: 'Write a short poem about ' },
    { cmd: 'roll', desc: 'Roll dice, e.g. /roll 2d6+1 (offline)', text: '/roll 1d20' },
    { cmd: 'coin', desc: 'Flip a coin (offline)', text: '/coin' },
    { cmd: '8ball', desc: 'Ask the magic orb (offline)', text: '/8ball ' },
    { cmd: 'pick', desc: 'Pick one: /pick pizza, sushi (offline)', text: '/pick ' },
    { cmd: 'confetti', desc: 'Celebrate', text: '/confetti' },
    { cmd: 'play', desc: 'Open the Play menu', text: '/play' },
  );
  wrap('applySlash', orig => function (cmd) {
    orig.apply(this, arguments);
    const ta = $('#input'), i = ta.value.indexOf('TOPIC');
    if (i >= 0) ta.setSelectionRange(i, i + 5);
  });

  /* ================================================================= WRAPPERS */
  wrap('generate', orig => async function () {
    const chat = S.chat, last = chat && chat.messages[chat.messages.length - 1];
    const want = (S.settings.plan || X.planOnce) && last && last.role === 'user' && !last.auto && !last.local && !last.planned && S.model && S.model.chattable;
    X.planOnce = false;
    if (!want) return orig.apply(this, arguments);
    last.planned = true;
    return makePlan(chat, last);
  });
  wrap('submit', orig => async function () {
    if (S.streaming) return orig.apply(this, arguments);
    const ta = $('#input'), v = ta.value.trim();
    const done = () => { ta.value = ''; autosize(ta); closeSlash(); updateSendBtn(); };
    const im = v.match(/^\/(image|imagine|img|draw)\b\s*/i);
    if ((X.imgMode && v && !v.startsWith('/')) || im) {
      const prompt = im ? v.slice(im[0].length).trim() : v;
      if (!prompt) { toast('Write what the picture should show after /image', 'err'); return; }
      done();
      // image mode: "now at night" right after a picture changes that picture; other languages get an English prompt
      const last = lastPicture(), follow = !im && last && imageFollowUp(prompt) ? last : null;
      const rewrite = !!follow || looksForeign(prompt), fallback = follow ? `${follow.prompt}, ${prompt}` : prompt;
      makeImage(rewrite ? fallback : prompt, { said: prompt, title: titleOf(prompt), aspect: follow ? follow.aspect : undefined,
        prep: rewrite ? () => writePrompt({ prev: follow && follow.prompt, said: prompt, fallback }) : null,
        prepBy: S.model && S.model.chattable ? S.model.name : null });
      return;
    }
    // "generate me an image of ...": the image tool picks it up by itself (Models > Images > Defaults can turn this off)
    const skip = X.skipAuto; X.skipAuto = false;
    if (!skip && imgCfg().auto !== false && !(S.chat && S.chat.code) && !(S.attachments && S.attachments.length)) {
      const ask = imageIntent(v);
      if (ask) { autoImage(v, ask, done, null); return; }
      const last = lastPicture(), change = last && imageFollowUp(v);       // "now make it at night" right after a picture
      if (change) { autoImage(v, change, done, last); return; }
    }
    const f = v.match(/^\/(roll|dice|coin|flip|8ball|pick|confetti|party|play)\b\s*([\s\S]*)$/i);
    if (f) { done(); if (f[1].toLowerCase() === 'play') openPlay(); else funCommand(f[1].toLowerCase(), f[2].trim()); return; }
    const p = v.match(/^\/plan\b\s*/i);
    if (p) {
      if (!v.slice(p[0].length).trim()) { toast('Write your question after /plan', 'err'); return; }
      ta.value = v.slice(p[0].length); X.planOnce = true;
    }
    if (/^\s*(party|celebrate)\s*!*\s*$/i.test(v)) setTimeout(() => confetti({ n: 80 }), 200);
    return orig.apply(this, arguments);
  });
  wrap('updateSendBtn', orig => function () {
    orig.apply(this, arguments);
    if (X.imgMode && !S.streaming) { const b = $('#sendBtn'); b.className = 'send-btn' + ($('#input').value.trim() ? '' : ' disabled'); b.title = 'Make the picture (Enter)'; }
  });
  wrap('buildMsg', orig => function (m) {
    if (m.kind === 'image') return imgEl(m);
    if (m.kind === 'plan') return planEl(m);
    if (m.kind === 'fun') return funEl(m);
    const el = orig.apply(this, arguments);
    if (m.role === 'user' && m.imgReq) { el.classList.add('img-req'); el.querySelector('[data-act="edit"]')?.remove(); el.querySelector('.bubble').insertAdjacentHTML('afterbegin', `<span class="ir-tag">${icon('image', 12)}</span>`); }
    if (m.role === 'assistant' && !m.kind) el.querySelector('.acts')?.insertAdjacentHTML('afterbegin', `<button data-act="speak" title="Read aloud">${icon('speaker', 15)}</button>`);
    return el;
  });
  wrap('updateMsg', orig => function (el, m) {
    if (m.kind === 'image') return paintImg(m, el);
    if (m.kind === 'plan') return paintPlan(m, el);
    if (m.kind) return;
    orig.apply(this, arguments);
    if (m.planId) paintPlanStrip(el, m);
  });
  wrap('regenerate', orig => async function () {
    const msgs = S.chat && S.chat.messages, last = msgs && msgs[msgs.length - 1];
    if (last && last.kind === 'image') { if (!S.streaming) makeImage(last.prompt, { again: true, backend: last.backend, aspect: last.aspect }); return; }
    if (last && last.kind) return;
    return orig.apply(this, arguments);
  });
  wrap('renderModal', orig => function () {
    if (S.modalTab === 'cloud' || S.modalTab === 'images') {
      updateModalCounts();
      $$('.m-nav [data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === S.modalTab));
      return S.modalTab === 'cloud' ? renderCloud($('#modalBody')) : renderImages($('#modalBody'));
    }
    return orig.apply(this, arguments);
  });
  wrap('updateModalCounts', orig => function () { orig.apply(this, arguments); updateCounts(); });
  wrap('openModels', orig => function (tab) { if (tab === 'cloud' || !tab) loadCloud(); return orig.apply(this, arguments); });
  wrap('renderDrawer', orig => function () {
    if (S.drawerTab === 'style') { $$('[data-dtab]').forEach(b => b.classList.toggle('on', b.dataset.dtab === 'style')); return renderStyle(); }
    return orig.apply(this, arguments);
  });
  wrap('badges', orig => function (m, compact) {
    const b = orig.apply(this, arguments);
    return m.cloud ? `<span class="badge b-cloud" title="Runs in the cloud: chats go to ${esc(m.family)}">${icon('cloud', 11)}${compact ? '' : 'Cloud'}</span>` + b : b;
  });
  wrap('renderPicker', orig => function () {
    orig.apply(this, arguments);
    const cloudSrc = new Set(S.models.filter(m => m.cloud).map(m => m.source));
    $$('#pkList .pk-group').forEach(g => {
      const name = g.querySelector('span'), st = g.querySelector('.g-status');
      if (name && st && cloudSrc.has(name.textContent)) st.outerHTML = privacyOn() ? `<span class="g-status">${icon('shieldOn', 12)}off in privacy mode</span>` : `<span class="g-status cloud">${icon('cloud', 12)}cloud</span>`;
    });
    const foot = $('#picker .pk-foot');
    if (foot && !foot.querySelector('[data-act="cloud-open"]')) foot.insertAdjacentHTML('afterbegin', `<button class="btn ghost small" data-act="cloud-open">${icon('key', 14)}<span>API keys</span></button>`);
  });
  wrap('updateModelUI', orig => function () {
    orig.apply(this, arguments);
    const m = S.model;
    $('#modelPill').classList.toggle('cloud', !!(m && m.cloud));
    if (m && m.cloud) $('#modelCaps').insertAdjacentHTML('afterbegin', icon('cloud', 14));
    if (X.imgMode) $('#input').placeholder = 'Describe the picture…';
    if (settingsReady()) { updatePlanChip(); updateToolUI(); }
  });
  wrap('updateToolUI', orig => function () {
    orig.apply(this, arguments);
    const fn = $('#footnote');
    if (privacyOn()) return;
    if (X.imgMode) {
      const b = X.imgB && pickBackend();
      fn.classList.toggle('net', !!(b && !b.local)); fn.classList.remove('priv');
      fn.innerHTML = icon('image', 13) + `<span>${b ? `Image mode: your message becomes a picture made by ${esc(b.name)} ${b.local ? 'on this PC' : '(prompt goes to ' + esc(b.label) + ')'}` : 'Image mode: no image model found yet'}. Press the Image chip again for chat.</span>`;
      return;
    }
    const m = S.model;
    if (m && m.cloud) {
      const rest = fn.textContent.replace(/^Local models run on this PC\. Chats stay on this PC\.$/, '').replace(/\.? ?Chats stay on this PC\.$/, '');
      fn.innerHTML = icon('cloud', 13) + `<span>Cloud model: this chat is sent to ${esc(m.family)}.${rest ? ' ' + esc(rest) + '.' : ''} History stays on this PC.</span>`;
      fn.classList.add('net');
    }
  });
  wrap('updatePrivacyUI', orig => function (animate) {
    orig.apply(this, arguments);
    if (animate) { X.imgB = null; loadModels(true); if (X.imgMode) renderImgBar(); }
    if (!$('#modal').hidden && (S.modalTab === 'cloud' || S.modalTab === 'images')) renderModal();
  });
  wrap('renderChatList', orig => function () {
    orig.apply(this, arguments);
    const el = $('#chatList'), pinned = new Set(S.chats.filter(c => c.pinned).map(c => c.id));
    el.querySelectorAll('.ci').forEach(ci => {
      const on = pinned.has(ci.dataset.id);
      ci.classList.toggle('pinned', on);
      ci.querySelector('.ci-acts')?.insertAdjacentHTML('afterbegin', `<button data-act="pin" title="${on ? 'Unpin' : 'Pin to the top'}">${icon('pin', 14)}</button>`);
    });
    const items = [...el.querySelectorAll('.ci.pinned')];
    if (!items.length) return;
    const head = document.createElement('div'); head.className = 'cl-group pin-group'; head.innerHTML = icon('pin', 11) + '<span>Pinned</span>';
    el.prepend(head); head.after(...items);
    el.querySelectorAll('.cl-group').forEach(g => { const n = g.nextElementSibling; if (!n || n.classList.contains('cl-group')) g.remove(); });
  });
  wrap('chatMeta', orig => function (c) { return { ...orig.apply(this, arguments), pinned: !!c.pinned }; });

  /* ================================================================== EVENTS */
  $('#chatList').addEventListener('click', e => {
    const b = e.target.closest('[data-act="pin"]'); if (!b) return;
    e.stopPropagation(); togglePin(b.closest('.ci').dataset.id);
  }, true);
  $('#planChip').onclick = () => togglePlan();
  $('#imgBtn').onclick = () => toggleImgMode();
  $('#playBtn').onclick = openPlay;
  $('#imgBar').addEventListener('click', e => {
    const a = e.target.closest('[data-aspect]');
    if (a) { imgCfg().aspect = a.dataset.aspect; saveSettings(); renderImgBar(); $('#input').focus(); }
  });
  document.addEventListener('click', async e => {
    const asp = e.target.closest('#imgDefAspect [data-aspect]');
    if (asp) { imgCfg().aspect = asp.dataset.aspect; saveSettings(); renderModal(); renderImgBar(); return; }
    const btn = e.target.closest('[data-act]'); if (!btn) return;
    const act = btn.dataset.act, node = btn.closest('.msg');
    const m = node && S.chat ? S.chat.messages.find(x => x.id === node.dataset.id) : null;
    switch (act) {
      case 'cloud-save': cloudSave(btn); break;
      case 'cloud-remove': cloudRemove(btn); break;
      case 'cloud-refresh': btn.disabled = true; try { X.cloud = { ...X.cloud, ...await api('cloud/refresh', {}) }; } catch (err) { toast(err.message, 'err'); } await loadModels(true); renderModal(); break;
      case 'cloud-open': openModels('cloud'); break;
      case 'img-setup': openModels('images'); break;
      case 'ig-dl': case 'ig-cancel': case 'ig-use': case 'ig-try': case 'ig-del': case 'ig-open': case 'ig-move': igAction(act, btn); break;
      case 'img-rescan': X.imgB = null; X.gallery = null; X.ig = null; renderModal(); if (X.imgMode) renderImgBar(); break;
      case 'img-folder': api('images/reveal', { name: '' }); break;
      case 'img-del':
        if (await confirmDialog({ title: 'Delete this picture?', text: 'The file is removed from the gallery folder. Chats that show it lose the picture.' })) {
          await api('images/delete', { name: btn.dataset.name }).catch(() => {}); X.gallery = null; renderModal();
        }
        break;
      case 'img-again': if (m && !S.streaming) { if (m.error && S.chat.messages[S.chat.messages.length - 1] === m) { S.chat.messages.pop(); node.remove(); } makeImage(m.prompt, { again: true, backend: m.backend, aspect: m.aspect }); } break;
      case 'img-chat': if (m) imageToChat(m, node); break;
      case 'img-prompt': if (m) { await navigator.clipboard.writeText(m.prompt); toast('Prompt copied', 'ok', 1400); } break;
      case 'img-reveal': if (m && m.image) api('images/reveal', { name: m.image.name }); break;
      case 'img-attach':
        if (m && m.image) {
          const blob = await (await fetch(m.image.url)).blob();
          const url = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); });
          S.attachments.push({ id: uid(), url }); renderAttachments(); updateSendBtn();
          if (X.imgMode) toggleImgMode(false);
          toast(hasCap(S.model, 'vision') ? 'Picture attached to your next message' : 'Attached, but this model cannot see images. Pick one with the eye badge.', hasCap(S.model, 'vision') ? 'ok' : 'err');
          $('#input').focus();
        }
        break;
      case 'plan-add': case 'plan-del': case 'plan-run': case 'plan-skip': case 'plan-redo': if (m) planAction(act, btn, m); break;
      case 'speak': if (m) speak(m, btn); break;
      case 'style-reset': S.settings.style = {}; saveSettings(); renderStyle(); toast('Style reset'); break;
      case 'style-test':
        if (!S.model || !S.model.chattable) { toast('Pick a model first', 'err'); break; }
        if (S.streaming) break;
        closeDrawer(); newChat(); send('Say hi and tell me in two short sentences how you are going to talk to me.', []); break;
    }
  });
  document.addEventListener('keydown', e => {
    if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === 'i') { e.preventDefault(); toggleImgMode(); }
    else if (k === 'j') { e.preventDefault(); togglePlan(); }
    else if (k === 'g') { e.preventDefault(); if ($('#dialog').hidden) openPlay(); }
  });
  // plan cards: Enter in a title moves to the next field instead of adding a line
  document.addEventListener('keydown', e => {
    const t = e.target;
    if (!t.matches || !t.matches('.plan-card [contenteditable]')) return;
    if (e.key === 'Enter') { e.preventDefault(); const all = [...t.closest('.plan-card').querySelectorAll('[contenteditable]')]; const n = all[all.indexOf(t) + 1]; if (n) n.focus(); else t.blur(); }
    e.stopPropagation();
  }, true);
  if (window.speechSynthesis) speechSynthesis.getVoices();

  // settings arrive after this file runs: refresh the chips once they are there
  const ready = setInterval(() => {
    if (!settingsReady()) return;
    clearInterval(ready); updatePlanChip(); loadCloud();
  }, 150);
})();
