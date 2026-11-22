'use strict';
/* MTAI - motion layer. Loaded last. Adds ripples, staggered lists, a theme reveal, message and
   composer effects, scroll reveal and (on High) cursor effects. It only adds classes and wraps a
   few render functions, so the app works the same at every level.
   Levels (Appearance > Animations, animLevel() in app.js): 0 none, 1 reduced, 2 medium, 3 high. */
(() => {
  const lv = () => animLevel();
  const animOn = () => lv() >= 2;          // the moving extras: medium and high
  const restart = (el, cls, ms) => {
    if (!el) return;
    el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
    if (ms) { clearTimeout(el['_t' + cls]); el['_t' + cls] = setTimeout(() => el.classList.remove(cls), ms); }
  };
  const wrap = (name, after, before) => {
    const orig = window[name]; if (typeof orig !== 'function') return;
    window[name] = function (...a) {
      const ctx = before ? before(...a) : undefined;
      const r = orig.apply(this, a);
      if (r && typeof r.then === 'function') return r.then(v => { after && after(ctx, ...a); return v; });
      after && after(ctx, ...a);
      return r;
    };
  };

  /* app intro after the boot splash: sidebar slides in, topbar drops, composer rises */
  addEventListener('mtai:ready', () => {
    if (!animOn()) return;
    document.body.classList.add('intro');
    setTimeout(() => document.body.classList.remove('intro'), 1600);
  }, { once: true });

  /* ripple on press. Own tag names, so no app code that looks for span or i ever finds them. */
  const RIPPLE = '.btn, .chip, .tool-chip, .icon-btn, .send-btn, .ci, .pk-item, .sugg, .mcard, .card-s, .seg button, .op-card, .ws-f, .new-chat, .model-pill, .theme, .status-pill, .m-nav button, .acts button, .u-acts button, .sl-item';
  document.addEventListener('pointerdown', e => {
    if (e.button !== 0 || !animOn()) return;
    const el = e.target.closest(RIPPLE);
    if (!el || el.disabled || el.classList.contains('disabled')) return;
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
    let box = el.querySelector(':scope > mt-rpl');
    if (!box) { box = document.createElement('mt-rpl'); el.append(box); }
    const r = el.getBoundingClientRect(), d = Math.max(r.width, r.height) * 2.4;
    const dot = document.createElement('mt-dot');
    dot.style.cssText = `width:${d}px;height:${d}px;left:${e.clientX - r.left - d / 2}px;top:${e.clientY - r.top - d / 2}px`;
    box.append(dot);
    setTimeout(() => { dot.remove(); if (!box.children.length) box.remove(); }, 750);
  }, true);

  /* sidebar: chats that were not there before slide in, one after another */
  const seenChats = new Set();
  wrap('renderChatList', () => {
    let k = 0;
    $$('#chatList .ci').forEach(el => {
      const id = el.dataset.id;
      if (seenChats.has(id)) return;
      seenChats.add(id);
      if (!animOn()) return;
      el.style.setProperty('--d', Math.min(k++, 14) * 32 + 'ms');
      el.classList.add('ci-in');
    });
  });

  /* switching chats: the thread glides in; older messages fade up as they scroll into view */
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(en => {
    if (en.isIntersecting) { en.target.classList.add('rv-in'); io.unobserve(en.target); }
  }), { rootMargin: '0px 0px -30px 0px' }) : null;
  wrap('renderThread', () => {
    const th = $('#thread');
    if (lv() < 1) return;
    restart(th, 'swap', 600);                            // reduced: the CSS makes this a short fade
    if (!io || !animOn()) return;
    const msgs = $$('.msg', th).filter(m => !m.classList.contains('enter'));
    if (msgs.length < 3) return;                         // short chats: the glide is enough
    msgs.forEach(m => { m.classList.add('rv'); io.observe(m); });
    setTimeout(() => msgs.forEach(m => m.classList.add('rv-in')), 4000);   // never leave one hidden
  });

  /* model picker and drawer: items cascade in when they open (not on every filter keystroke) */
  wrap('openPicker', () => animOn() && restart($('#picker'), 'opening', 700));
  wrap('openDrawer', () => animOn() && restart($('#drawer'), 'opening', 800));
  let lastModalTab = null, lastDrawerTab = null;
  wrap('renderModal', () => {
    if (S.modalTab !== lastModalTab && animOn()) restart($('#modalBody'), 'tab-swap', 700);
    lastModalTab = S.modalTab;
  });
  wrap('closeModal', () => { lastModalTab = null; });
  wrap('renderDrawer', () => {
    if (S.drawerTab !== lastDrawerTab && animOn()) restart($('#drawerBody'), 'tab-swap', 700);
    lastDrawerTab = S.drawerTab;
  });

  /* theme presets: the new colors spread out in a circle from the click (View Transitions) */
  let px = innerWidth - 200, py = 120;
  document.addEventListener('pointerdown', e => { px = e.clientX; py = e.clientY; }, true);
  const origPick = window.pickTheme;
  if (typeof origPick === 'function') window.pickTheme = function (id) {
    if (!document.startViewTransition || !animOn()) return origPick(id);
    const root = document.documentElement;
    root.style.setProperty('--vx', px + 'px'); root.style.setProperty('--vy', py + 'px');
    root.style.setProperty('--vr', Math.hypot(Math.max(px, innerWidth - px), Math.max(py, innerHeight - py)) + 'px');
    document.startViewTransition(() => origPick(id));
  };

  /* messages: a sent message launches the send button; a finished answer gets a glow sweep */
  new MutationObserver(list => {
    for (const m of list) {
      if (m.type === 'childList') {
        m.addedNodes.forEach(n => {
          if (n.nodeType === 1 && n.matches('.msg.user.enter') && lv() >= 1) { restart($('#sendBtn'), 'launch', 700); if (lv() >= 3) sparks($('#sendBtn')); }
        });
      } else if (m.target.matches('.msg') && /\bpending\b/.test(m.oldValue || '') && !m.target.classList.contains('pending') && lv() >= 1) {
        restart(m.target, 'fresh', 1600);
      }
    }
  }).observe($('#thread'), { childList: true, attributes: true, attributeFilter: ['class'], attributeOldValue: true, subtree: true });

  /* composer: a moving glow ring while the model is answering */
  const send = $('#sendBtn');
  new MutationObserver(() => $('#composer').classList.toggle('busy', send.classList.contains('stop'))).observe(send, { attributes: true, attributeFilter: ['class'] });

  /* model pill: the name flips when the model changes */
  let lastModel = $('#modelName').textContent;
  new MutationObserver(() => {
    const t = $('#modelName').textContent;
    if (t !== lastModel && lv() >= 1) restart($('#modelPill'), 'flip', 600);
    lastModel = t;
  }).observe($('#modelName'), { childList: true, characterData: true, subtree: true });

  /* copy buttons: the check mark pops */
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-act="copy"], [data-cb="copy"]');
    if (b && lv() >= 1) setTimeout(() => restart(b, 'copied-pop', 600), 40);
  });

  /* toggles: chips and switches bounce when they change */
  document.addEventListener('click', e => {
    if (!animOn()) return;
    const c = e.target.closest('.chip, .tool-chip, .seg button');
    if (c) setTimeout(() => restart(c, 'tap', 450), 0);
  });

  /* the to-bottom button bounces in when it shows */
  const tb = $('#toBottom');
  // only when 'show' is newly added: restart() changes the class list too, so reacting to every change loops forever
  let tbShown = tb && tb.classList.contains('show');
  if (tb) new MutationObserver(() => {
    const now = tb.classList.contains('show');
    if (now && !tbShown && animOn()) restart(tb, 'hop', 600);
    tbShown = now;
  }).observe(tb, { attributes: true, attributeFilter: ['class'] });

  /* =========================================================== HIGH ONLY */
  /* sparks: small lights fly out of an element (send) */
  function sparks(el, n = 14) {
    if (!el) return;
    const r = el.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    for (let i = 0; i < n; i++) {
      const s = document.createElement('mt-spark');
      const a = -Math.PI / 2 + (Math.random() - .5) * Math.PI * 1.5, d = 30 + Math.random() * 46;
      s.style.cssText = `left:${cx}px;top:${cy}px;--dx:${Math.cos(a) * d}px;--dy:${Math.sin(a) * d}px;--s:${.5 + Math.random() * .8};animation-delay:${Math.random() * 60}ms`;
      document.body.append(s);
      setTimeout(() => s.remove(), 900);
    }
  }

  /* cursor glow, background parallax, magnetic send button and tilting cards share one pointer loop */
  const glow = document.createElement('mt-glow');
  document.body.append(glow);
  const bg = $('.bg');
  let mx = innerWidth / 2, my = innerHeight / 2, gx = mx, gy = my, raf = 0, idle = 0, on = false;
  const TILT = '.card-s, .mcard, .ig-card, .ccard, .theme, .gal-it';
  let tilted = null;
  function untilt() { if (tilted) { tilted.style.rotate = ''; tilted.style.scale = ''; tilted = null; } }
  function loop() {
    raf = 0;
    if (lv() < 3) { stopHigh(); return; }
    gx += (mx - gx) * .16; gy += (my - gy) * .16;
    glow.style.transform = `translate3d(${gx - 160}px, ${gy - 160}px, 0)`;
    if (bg) bg.style.transform = `translate3d(${(gx / innerWidth - .5) * -26}px, ${(gy / innerHeight - .5) * -18}px, 0) scale(1.04)`;
    if (Math.abs(mx - gx) + Math.abs(my - gy) > .5 || ++idle < 20) raf = requestAnimationFrame(loop);
  }
  function stopHigh() {
    on = false; glow.classList.remove('on'); untilt();
    if (bg) bg.style.transform = '';
    if (send) send.style.translate = '';
  }
  document.addEventListener('pointermove', e => {
    if (lv() < 3) { if (on) stopHigh(); return; }
    on = true; glow.classList.add('on');
    mx = e.clientX; my = e.clientY; idle = 0;
    if (!raf) raf = requestAnimationFrame(loop);
    // magnetic send button: pulled up to 6 px toward the pointer when it is near
    if (send) {
      const r = send.getBoundingClientRect(), dx = mx - (r.left + r.width / 2), dy = my - (r.top + r.height / 2), dist = Math.hypot(dx, dy);
      send.style.translate = dist < 70 && !send.classList.contains('disabled') ? `${dx / 70 * 6}px ${dy / 70 * 6}px` : '';
    }
    // tilt: the card under the pointer leans toward it
    const c = e.target.closest && e.target.closest(TILT);
    if (c !== tilted) untilt();
    if (c) {
      const r = c.getBoundingClientRect(), nx = (mx - r.left) / r.width - .5, ny = (my - r.top) / r.height - .5;
      if (c.parentElement && !c.parentElement.style.perspective) c.parentElement.style.perspective = '900px';
      c.style.rotate = `${-ny} ${nx} 0 ${Math.min(7, 900 / Math.max(r.width, 80))}deg`;
      c.style.scale = '1.015';
      tilted = c;
    }
  }, { passive: true });
  document.addEventListener('pointerleave', () => { glow.classList.remove('on'); untilt(); if (send) send.style.translate = ''; });

  /* typing: the composer edge brightens a little with each key (high) */
  const input = $('#input');
  if (input) input.addEventListener('input', () => { if (lv() >= 3) restart($('#composer'), 'typed', 380); });

  /* when the level changes, clean up what High left behind */
  new MutationObserver(() => { if (lv() < 3) stopHigh(); })
    .observe(document.body, { attributes: true, attributeFilter: ['data-anim'] });
})();
