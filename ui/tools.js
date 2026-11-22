'use strict';
/* MTAI - web search, deep research with a live browser, and code mode (own workspace, edits, live view).
   Loaded before app.js; everything here runs only after app.js has set up S, api(), icon() and friends. */

function toolsInit() {
  Object.assign(ICONS, {
    telescope: '<path d="M3.5 14.5l11-5.5 2 4-11 5.5z"/><path d="M14.5 9l4-2 2 4-4 2"/><path d="M9 17l-2.5 4.5M10.5 16.3L13 21"/>',
    lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  });
}

const todayText = () => new Date().toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return String(u || ''); } };
const sleep = (ms, signal) => new Promise((res, rej) => {
  const t = setTimeout(res, ms);
  if (signal) signal.addEventListener('abort', () => { clearTimeout(t); rej(new DOMException('Aborted', 'AbortError')); }, { once: true });
});
function ctxLimit(model) {
  if (!model) return 8192;
  return (model.backend === 'ollama' ? +S.settings.num_ctx || model.ctx : model.ctx) || 8192;
}

/* One short answer from the model, without thinking and without streaming it into the chat.
   With a JSON schema the model can only answer in that shape (thinking models otherwise leak their reasoning). */
async function askModel(model, prompt, { maxTokens = 160, signal, schema, extra } = {}) {
  const s = S.settings;
  const resp = await api('chat', {
    model_id: model.id, messages: [{ role: 'user', content: prompt }], system: '', format: schema,
    options: model.backend === 'ollama' ? { temperature: 0.2, num_ctx: Math.min(+s.num_ctx || 8192, 8192), num_predict: maxTokens } : { temperature: 0.2, num_predict: maxTokens },
    think: hasCap(model, 'thinking') ? false : null, keep_alive: s.keep_alive, ...(extra || {}),
  }, { stream: true, signal });
  let out = '';
  for await (const ev of ndjson(resp)) {
    if (ev.type === 'content') out += ev.text;
    else if (ev.type === 'error') throw new Error(ev.message || ev.error);
  }
  out = out.replace(/<think>[\s\S]*?(<\/think>|$)/g, '');
  if (out.includes('</think>')) out = out.slice(out.lastIndexOf('</think>') + 8);
  return out.trim();
}
const QUERY_SCHEMA = { type: 'object', properties: { queries: { type: 'array', items: { type: 'string' } } }, required: ['queries'] };
async function askQueries(model, prompt, max, signal) {
  const txt = await askModel(model, prompt + '\n\nAnswer as JSON: {"queries": ["...", "..."]}', { maxTokens: 160, signal, schema: QUERY_SCHEMA });
  try {
    const j = JSON.parse(txt.slice(txt.indexOf('{'), txt.lastIndexOf('}') + 1));
    if (Array.isArray(j.queries)) return parseQueries(j.queries.map(String).join('\n'), max);
  } catch {}
  return parseQueries(txt, max);
}
function parseQueries(text, max) {
  if (/^\s*DONE\s*\.?\s*$/i.test(text)) return [];
  const out = [];
  for (let l of text.split('\n')) {
    l = l.replace(/^\s*(?:[-*•]|\d{1,2}[.):])\s*/, '').replace(/^(?:query|search)\s*\d*\s*:\s*/i, '').replace(/^["'`]+|["'`,]+$/g, '').trim();
    if (l.length < 3 || l.length > 120 || /^DONE\b/i.test(l) || /:$/.test(l) || /\b(the user|we are|let me|i need|i will)\b/i.test(l) || out.includes(l)) continue;
    out.push(l);
    if (out.length >= max) break;
  }
  return out;
}

/* ================================================================== web */

const WEB_NOTE = 'Web search sends your search words to DuckDuckGo and downloads pages from the sites it finds (they see a normal visit from your PC). Your chats, files and models stay on this PC.';
async function webAllowed() {
  if (privacyOn()) { privacyBlocked('web'); return false; }
  if (S.settings.web_ok) return true;
  const ok = await confirmDialog({ title: 'Use the web?', text: WEB_NOTE, ok: 'Allow web search', danger: false });
  if (ok) { S.settings.web_ok = true; saveSettings(); }
  return ok;
}
function webRules() {
  return `\n\nYou have web results for the user's last message (below). Today is ${todayText()}. Base your answer on them and cite the sources with [n] right after the facts they support, for example [2]. If the results do not answer the question, say so and then answer from your own knowledge. Never invent sources or links.`;
}

/* Searches, reads pages and stores the findings on the user message (u.ctx, u.sources). */
async function research(chat, u, msg, signal, model, repaint) {
  const deep = u.web === 'deep';
  const W = msg.web = { mode: u.web, steps: [], active: true };
  updateToolUI();
  const step = (kind, text, extra = {}) => { const st = { kind, text, ...extra }; W.steps.push(st); repaint(); return st; };
  const question = (u.content || '').trim();
  const budget = Math.max(5000, Math.min(40000, ctxLimit(model) * 3.6 * 0.45));
  const maxPages = deep ? 8 : 3;
  const perPage = Math.round(Math.max(900, Math.min(deep ? 3600 : 2600, budget / maxPages)));
  const sources = [], extras = [], seen = new Set(), perHost = {};
  const browser = deep ? openBrowser(msg.id) : null;
  const live = () => browser && S.panel && S.panel.kind === 'web' && S.panel.run === msg.id && !$('#panel').hidden;
  const status = t => { if (browser && S.panel && S.panel.run === msg.id) { S.panel.status = t; webRender(); } };

  // 1. what to search for
  const prior = chat.messages.slice(0, chat.messages.indexOf(u)).filter(m => !m.auto && m.content).slice(-4)
    .map(m => `${m.role === 'user' ? 'User' : 'Assistant'}: ${(m.role === 'assistant' ? splitThink(m).c : m.content).slice(0, 500)}`).join('\n');
  let queries = [];
  if (deep || prior) {
    const st = step('plan', deep ? 'Planning the research' : 'Choosing what to search');
    status('Planning the research…');
    try {
      queries = await askQueries(model, (prior ? `Conversation so far:\n${prior}\n\n` : '') + `Today is ${todayText()}.\nNew message from the user: ${question}\n\n` +
        (deep ? 'Write 3 or 4 different, short web search queries (like you would type into a search engine) that together find what is needed to answer the new message well.'
              : 'Write one short web search query (like you would type into a search engine) that finds the answer to the new message.'), deep ? 4 : 1, signal);
    } catch (e) { if (signal.aborted) throw e; }
    st.done = true;
    st.text = deep ? `Planned ${Math.max(1, queries.length)} search${queries.length === 1 ? '' : 'es'}` : 'Search words ready';
  }
  if (!queries.length) queries = [question.replace(/\s+/g, ' ').slice(0, 200) || 'news'];

  async function search(q, take) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    const st = step('search', q);
    status(`Searching “${q}”…`);
    let r;
    try { r = await api('web/search', { q, n: 8 }, { signal }); }
    catch (e) { if (signal.aborted) throw e; st.done = true; st.error = e.message; repaint(); return []; }
    st.done = true; st.count = r.results.length; st.engine = r.engine; if (r.error) st.error = r.error;
    repaint();
    if (live()) {
      try {
        const pv = await api('preview', { html: serpHtml(q, r.results, r.engine) });
        addTab({ title: q, host: r.engine || 'Search', url: 'https://duckduckgo.com/?q=' + encodeURIComponent(q), preview: pv.url, serp: true });
        await sleep(1100, signal);
      } catch (e) { if (signal.aborted) throw e; }
    }
    const picks = [];
    for (const x of r.results) {
      if (seen.has(x.url)) continue;
      seen.add(x.url);
      if (picks.length < take && (perHost[x.host] || 0) < (deep ? 2 : 1)) { picks.push(x); perHost[x.host] = (perHost[x.host] || 0) + 1; }
      else extras.push(x);
    }
    return picks;
  }
  async function read(x, q) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    if (sources.length >= maxPages) return false;
    const st = step('read', x.title || x.host, { url: x.url, host: x.host });
    status(`Opening ${x.host}…`);
    let f;
    try { f = await api('web/fetch', { url: x.url, q: question + ' ' + q, chars: perPage }, { signal }); }
    catch (e) { if (signal.aborted) throw e; f = { error: e.message }; }
    st.done = true;
    if (f.error || !f.text) { st.error = f.error || 'No readable text'; repaint(); extras.push(x); return false; }
    const src = { n: sources.length + 1, title: f.title || x.title, url: f.url || x.url, host: f.host || x.host, text: f.text };
    sources.push(src);
    Object.assign(st, { n: src.n, url: src.url, title: src.title });
    repaint();
    if (live()) {
      addTab({ title: src.title, host: src.host, url: src.url, preview: f.preview, reader: f.reader });
      status(`Reading ${src.host}…`);
      S.panel.reading = true; webRender();
      await waitRead(signal);
      S.panel.reading = false; webRender();
    }
    return true;
  }

  // 2. search and read
  if (deep) {
    for (const q of queries) { for (const x of await search(q, 2)) await read(x, q); }
    // 3. look for gaps once
    if (sources.length && sources.length < maxPages) {
      const st = step('plan', 'Checking what is still missing');
      status('Checking what is still missing…');
      let more = [];
      try {
        const notes = sources.map(s => `[${s.n}] ${s.title}: ${s.text.slice(0, 320).replace(/\s+/g, ' ')}`).join('\n');
        more = (await askQueries(model, `Question: ${question}\n\nNotes from the pages read so far:\n${notes}\n\nIs important information still missing to answer the question well? If yes, give up to 2 new short web search queries. If nothing important is missing, give an empty list.`, 2, signal))
          .filter(q => !queries.includes(q));
      } catch (e) { if (signal.aborted) throw e; }
      st.done = true; st.text = more.length ? `Follow-up: ${more.length} more search${more.length > 1 ? 'es' : ''}` : 'Enough found';
      repaint();
      for (const q of more) { queries.push(q); for (const x of await search(q, 2)) await read(x, q); }
    }
  } else {
    const picks = await search(queries[0], 5);
    await Promise.all(picks.slice(0, 3).map(x => read(x, queries[0])));
    for (const x of picks.slice(3)) { if (sources.length >= 2) break; await read(x, queries[0]); }
  }

  // 4. the findings, numbered: pages first, then search snippets
  const snippets = extras.filter(x => x.snippet && !sources.some(s => s.url === x.url)).slice(0, deep ? 6 : 4);
  const all = [...sources, ...snippets.map((x, i) => ({ n: sources.length + i + 1, title: x.title, url: x.url, host: x.host, text: x.snippet, snippet: true }))];
  u.sources = all.map(({ n, title, url, host, snippet }) => ({ n, title, url, host, snippet: snippet || undefined }));
  u.ctx = all.length
    ? `\n\nWEB RESULTS (searched ${todayText()}; searches: ${queries.join(' | ')}):\n\n` + all.map(s => `[${s.n}] ${s.title} (${s.host})${s.snippet ? ' - search snippet' : ''}\n${s.text}`).join('\n\n')
    : `\n\nWEB RESULTS: the search found nothing usable (searches: ${queries.join(' | ')}).`;
  u.webSteps = W.steps;
  W.active = false;
  updateToolUI();
  msg.sources = u.sources;
  status('');
  if (browser && S.panel && S.panel.run === msg.id) { S.panel.title = 'Deep research'; S.panel.done = true; webRender(); }
  repaint();
}

function serpHtml(q, results, engine) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>body{font:15px/1.5 system-ui,sans-serif;margin:0;background:#fff;color:#1f1f23}
header{position:sticky;top:0;background:#fff;padding:16px 24px;border-bottom:1px solid #ececec;display:flex;gap:14px;align-items:center}
.q{flex:1;padding:9px 16px;border:1px solid #dcdcdc;border-radius:22px;box-shadow:0 1px 4px rgba(0,0,0,.06)}.e{font:700 13px system-ui;color:#de5833}
main{padding:6px 24px 40px;max-width:700px}.r{padding:12px 0;animation:in .4s both}.h{font-size:12.5px;color:#3c7a3a}.t{font-size:17px;color:#1a0dab;margin:2px 0}
.s{color:#4d5156;font-size:14px}${results.map((_, i) => `.r:nth-child(${i + 1}){animation-delay:${i * 70}ms}`).join('')}@keyframes in{from{opacity:0;transform:translateY(6px)}}</style></head>
<body><header><span class="e">${esc(engine || 'Search')}</span><div class="q">${esc(q)}</div></header><main>${results.map(r =>
    `<div class="r"><div class="h">${esc(r.host)}</div><div class="t">${esc(r.title)}</div><div class="s">${esc(r.snippet)}</div></div>`).join('') || '<p>No results.</p>'}</main></body></html>`;
}

/* ---- the browser panel */
function openBrowser(runId) {
  if ($('#panel').hidden || !S.panel || S.panel.kind !== 'web' || S.panel.run !== runId) {
    const prev = S.panel || {};
    S.panel = { kind: 'web', title: 'Researching…', tabs: [], cur: -1, status: '', run: runId, device: prev.device || 'desktop', logs: [] };
    showPanel();
  }
  return true;
}
function addTab(t) {
  const p = S.panel; if (!p || p.kind !== 'web') return;
  p.tabs.push(t);
  webShow(p.tabs.length - 1);
}
async function webShow(i) {
  const p = S.panel; if (!p || p.kind !== 'web' || !p.tabs[i]) return;
  const t = p.tabs[i];
  p.cur = i;
  if (!t.preview) {                            // tabs rebuilt from an old answer: fetch a fresh copy
    p.status = 'Opening ' + t.host + '…'; webRender();
    try { const f = await api('web/fetch', { url: t.url, q: t.title || '', chars: 1500 }); if (f.error) throw new Error(f.error); Object.assign(t, { preview: f.preview, reader: f.reader }); }
    catch (e) { toast('Could not open the page: ' + e.message, 'err'); }
    p.status = '';
    if (S.panel !== p || p.cur !== i) return;
  }
  if (t.preview) $('#webFrame').src = t.preview;
  webRender();
  const el = $('#webTabs .on'); if (el) el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
}
function watchResearch(m) {
  const steps = ((m.web && m.web.steps) || []).filter(s => s.kind === 'read' && s.n);
  if (!steps.length) { toast('No pages to show'); return; }
  const prev = S.panel || {};
  S.panel = { kind: 'web', title: 'Deep research', tabs: steps.map(s => ({ title: s.title, host: s.host, url: s.url, preview: null })), cur: -1, status: '', run: null, done: true, device: prev.device || 'desktop', logs: [] };
  showPanel();
  webShow(0);
}
function webRender() {
  const p = S.panel; if (!p || p.kind !== 'web') return;
  $('#pvTitle').textContent = p.title;
  $('#panel').classList.toggle('busy', !p.done && !!p.status);
  $('#webTabs').innerHTML = p.tabs.map((t, i) => `<button class="wt ${i === p.cur ? 'on' : ''}" data-wtab="${i}" title="${esc(t.url)}">` +
    (t.serp ? `<i class="wt-ic">${icon('search', 11)}</i>` : `<i class="wt-ic">${esc((t.host || '?')[0].toUpperCase())}</i>`) + `<span>${esc(t.title)}</span></button>`).join('');
  const t = p.tabs[p.cur];
  $('#pvUrl').innerHTML = t ? `<span class="lock">${icon('lock', 11)}</span>${esc(t.url.replace(/^https?:\/\//, ''))}${t.reader ? ' <em class="rd">reader view</em>' : ''}` : 'about:blank';
  const st = $('#webStatus');
  st.hidden = !p.status;
  st.innerHTML = p.status ? `<span class="spin"></span><span>${esc(p.status)}</span>` : '';
  $('#webScan').classList.toggle('on', !!p.reading);
  $('#webEmpty').hidden = p.tabs.length > 0;
}
let readWaiter = null;
function waitRead(signal) {
  return new Promise(res => {
    const t0 = performance.now();
    const done = () => { if (!readWaiter) return; readWaiter = null; clearTimeout(cap); const left = 1800 - (performance.now() - t0); setTimeout(res, Math.max(0, left)); };
    const cap = setTimeout(done, 9000);
    readWaiter = done;
    if (signal) signal.addEventListener('abort', done, { once: true });
  });
}
async function openWebPage(url, title) {
  const prev = S.panel || {};
  if (!(S.panel && S.panel.kind === 'web' && !$('#panel').hidden)) {
    S.panel = { kind: 'web', title: 'Browser', tabs: [], cur: -1, status: '', run: null, done: true, device: prev.device || 'desktop', logs: [] };
    showPanel();
  }
  const i = S.panel.tabs.findIndex(t => t.url === url);
  if (i >= 0) { webShow(i); return; }
  S.panel.status = 'Opening ' + hostOf(url) + '…'; webRender();
  try {
    const f = await api('web/fetch', { url, q: title || '', chars: 1500 });
    if (f.error) throw new Error(f.error);
    S.panel.status = '';
    addTab({ title: f.title || title || hostOf(url), host: f.host, url: f.url, preview: f.preview, reader: f.reader });
  } catch (e) { S.panel.status = ''; webRender(); toast('Could not open the page: ' + e.message, 'err'); }
}

/* ---- in the chat */
function webBoxHtml(m) {
  const W = m.web; if (!W) return '';
  const pages = W.steps.filter(s => s.kind === 'read' && s.n).length;
  const label = W.active ? `<span class="shimmer">${W.mode === 'deep' ? 'Researching the web…' : 'Searching the web…'}</span>`
    : `${W.mode === 'deep' ? 'Deep research' : 'Searched the web'} · ${pages} page${pages === 1 ? '' : 's'} read`;
  const steps = W.steps.map(s => {
    const ic = s.error ? 'alert' : s.kind === 'search' ? 'search' : s.kind === 'read' ? 'globe' : 'spark';
    const run = !s.done ? '<span class="spin"></span>' : '';
    let text;
    if (s.kind === 'search') text = `Searched <b>“${esc(s.text)}”</b>${s.done ? ` <small>${s.count || 0} results${s.engine ? ' · ' + esc(s.engine) : ''}</small>` : ''}`;
    else if (s.kind === 'read') text = s.n ? `<button class="wb-page" data-wpage="${esc(s.url)}" data-wtitle="${esc(s.title || '')}"><i>${s.n}</i><b>${esc(s.host)}</b><span>${esc(s.title || '')}</span></button>`
      : `Reading <b>${esc(s.host || '')}</b>`;
    else text = esc(s.text);
    return `<div class="wb-step ${s.error ? 'err' : ''}">${run || icon(ic, 13)}<span class="wb-t">${text}${s.error ? ` <small class="wb-err">${esc(s.error)}</small>` : ''}</span></div>`;
  }).join('');
  const open = m._webOpen !== undefined ? m._webOpen : !!W.active;
  return `<div class="webbox ${open ? 'open' : ''} ${W.active ? 'active' : ''}"><button class="wb-head" data-act="webbox"><span class="wb-ic">${icon(W.mode === 'deep' ? 'telescope' : 'globe', 15)}</span><span class="wb-label">${label}</span>` +
    `${W.mode === 'deep' && !W.active ? `<span class="wb-watch" data-act="webwatch" title="Show the pages in the browser panel">${icon('eye', 13)}Browser</span>` : ''}<span class="chev">${icon('chev', 15)}</span></button>` +
    `<div class="wb-body"><div class="wb-inner"><div class="wb-steps">${steps}</div></div></div></div>`;
}
function sourcesHtml(m) {
  const list = (m.sources || []).filter(s => !s.snippet);
  if (!list.length || m.pending) return '';
  return `<div class="sources">${list.map(s => `<a class="src" href="${esc(s.url)}" title="${esc(s.title)}"><i>${s.n}</i><span>${esc(s.host)}</span></a>`).join('')}</div>`;
}
function linkCites(root, sources) {
  if (!sources || !sources.length) return;
  const map = new Map(sources.map(s => [s.n, s]));
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: n => n.parentElement.closest('pre,code,a,.code') ? NodeFilter.FILTER_REJECT : /\[\d/.test(n.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP,
  });
  const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const t of nodes) {
    const plain = esc(t.data);
    const out = plain.replace(/\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]/g, (all, list) => list.split(/\s*,\s*/).map(x => {
      const s = map.get(+x);
      return s ? `<a class="cite" href="${esc(s.url)}" title="${esc(s.title)} · ${esc(s.host)}">${x}</a>` : `[${x}]`;
    }).join(''));
    if (out !== plain) { const span = document.createElement('span'); span.innerHTML = out; t.replaceWith(...span.childNodes); }
  }
}
function webTag(m) {
  if (!m.web || m.role !== 'user') return '';
  return `<div class="u-tag">${icon(m.web === 'deep' ? 'telescope' : 'globe', 12)}${m.web === 'deep' ? 'Deep research' : 'Web search'}</div>`;
}

/* ============================================================ code mode */

const CODE_RULES = `

CODE MODE. You work in a project folder (the workspace). You change files with the tags below. MTAI applies them to the files at once, so write them exactly like this.
The user does not want new code in the chat. They want their files changed. So when they ask for a change, EDIT THE FILE with an <edit> tag. Never answer with a code block (\`\`\`) for them to copy. Never send back a whole file that already exists.

Create a new file:
<file path="folder/name.ext">
the whole file content
</file>

Change an existing file. Always do this for files that exist; never rewrite a whole existing file:
<edit path="name.ext">
<<<<<<< SEARCH
lines copied exactly from the current file
=======
the new lines
>>>>>>> REPLACE
</edit>

One edit tag can hold several SEARCH/REPLACE pairs. SEARCH must match the current file exactly (same spaces) and be just long enough to be unique. To add code, SEARCH for the line just before the place, and in REPLACE repeat that line followed by the new lines.
Delete a file: <delete path="name.ext"/>
Run a .py, .js or .ps1 file and see its output (an .html file opens in the preview): <run path="main.py"/>

Rules: never put \`\`\` code fences around the tags or inside them. Paths are relative to the workspace. Start with one or two sentences about what you will do. After the tags, say in one sentence what the user can try. Do not repeat the code outside the tags.
Use <file> only for a file that does not exist yet. For every change to an existing file use <edit> with small SEARCH/REPLACE pairs, even for big changes (use several pairs).`;

const wsd = {};
function wsData(id) { return wsd[id] || (wsd[id] = { files: {}, order: [], changed: {}, live: null, runs: {}, sel: null, loaded: false }); }
async function wsLoad(id) {
  const r = await api('ws/list', { ws: id, content: true });
  const D = wsData(id);
  D.files = {}; D.order = r.files.map(f => f.path); D.meta = r.files; D.runs = r.runs || {}; D.dir = r.dir; D.loaded = true;
  r.files.forEach(f => { if (f.text != null) D.files[f.path] = f.text; });
  if (!D.sel || !D.order.includes(D.sel)) D.sel = D.order.find(p => /(^|\/)index\.html?$/i.test(p)) || D.order[0] || null;
  return r;
}
async function codeSystem(chat, model) {
  const r = await wsLoad(chat.id);
  const budget = Math.max(6000, ctxLimit(model) * 3.6 * 0.5);
  let used = 0, out = '';
  const open = r.files.find(f => f.path === wsData(chat.id).sel && f.text != null);
  if (!r.files.length) out = '\n\nThe workspace is empty so far. Create the files the user needs.';
  else {
    out = '\n\nWORKSPACE FILES (current content):';
    if (open) {          // the file in the Code tab goes first and is always shown whole
      out += `\n\n--- ${open.path} (OPEN in the user's Code tab) ---\n${open.text.replace(/\n$/, '')}`;
      used += open.text.length;
    }
    for (const f of r.files) {
      if (f === open) continue;
      if (f.text == null) { out += `\n\n--- ${f.path} (binary file, ${fmtSize(f.size)}) ---`; continue; }
      if (used + f.text.length > budget) { out += `\n\n--- ${f.path} (${f.lines} lines, too long to show) ---`; continue; }
      out += `\n\n--- ${f.path} ---\n${f.text.replace(/\n$/, '')}`;
      used += f.text.length;
    }
  }
  const runs = Object.entries(r.runs || {});
  if (runs.length) out += '\n\nLAST RUNS:\n' + runs.map(([p, x]) => `${p}: ${x.timed_out ? 'stopped after 60 s' : 'exit code ' + x.code}\n${((x.stdout || '') + (x.stderr ? '\n' + x.stderr : '')).trim().slice(-700) || '(no output)'}`).join('\n\n');
  if (open) out += `\n\nTHE OPEN FILE is ${open.path}. When the user asks for a change and does not name a file, change ${open.path} with <edit path="${open.path}">.`;
  return CODE_RULES + out;
}
/* Old answers go back to the model without their tags: the files themselves are in the system message.
   (A short note in place of the tags gets copied by small models instead of writing real tags.) */
function compressOps(text) {
  return codeSegs(text).filter(s => s.t === 'text').map(s => s.s).join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

/* ---- parsing the model's tags (also while they are still streaming) */
const OP_RE = /<(file|edit)\s+path\s*=\s*["']([^"'\n]+)["']\s*>|<(delete|run)\s+path\s*=\s*["']([^"'\n]+)["']\s*\/?>(?:\s*<\/(?:delete|run)>)?/g;
function codeSegs(text, pending) {
  const segs = []; let i = 0, m;
  OP_RE.lastIndex = 0;
  while ((m = OP_RE.exec(text))) {
    if (m.index > i) segs.push({ t: 'text', s: text.slice(i, m.index) });
    if (m[3]) { segs.push({ t: 'op', type: m[3], path: m[4], closed: true }); i = OP_RE.lastIndex; continue; }
    const type = m[1], close = new RegExp(`</${type}\\s*>`, 'g');
    close.lastIndex = OP_RE.lastIndex;
    const end = close.exec(text);
    const body = end ? text.slice(OP_RE.lastIndex, end.index) : text.slice(OP_RE.lastIndex);
    segs.push({ t: 'op', type, path: m[2], body, closed: !!end });
    if (!end) { i = text.length; break; }
    i = close.lastIndex; OP_RE.lastIndex = i;
  }
  if (i < text.length) segs.push({ t: 'text', s: text.slice(i) });
  segs.forEach((s, k) => {                     // fences a model put around the tags
    if (s.t !== 'text') return;
    if (segs[k + 1] && segs[k + 1].t === 'op') s.s = s.s.replace(/\n?[ \t]*```[\w-]*[ \t]*\n?\s*$/, '\n');
    if (segs[k - 1] && segs[k - 1].t === 'op') s.s = s.s.replace(/^\s*```[ \t]*(\n|$)/, '\n');
  });
  const last = segs[segs.length - 1];
  if (pending && last && last.t === 'text') last.s = last.s.replace(/<\/?(?:f|fi|fil|file|e|ed|edi|edit|d|de|del|dele|delet|delete|r|ru|run)?(?:\s[^<>]*)?$/, '');
  return segs;
}
function fileBody(body) {
  let b = String(body || '').replace(/^[ \t]*\n/, '');
  const f = b.match(/^\s*```[\w.+-]*[ \t]*\n([\s\S]*?)(?:\n[ \t]*```\s*)?$/);
  if (f) b = f[1];
  return b.replace(/\n[ \t]*$/, '\n');
}
function parseEdits(body) {
  const pairs = []; let cur = null, mode = null;
  for (const l of String(body || '').split('\n')) {
    if (/^\s*<{5,}\s*SEARCH\b/i.test(l)) { cur = { s: [], r: [], sep: false, done: false }; pairs.push(cur); mode = 's'; continue; }
    if (cur && mode === 's' && /^\s*={5,}\s*$/.test(l)) { cur.sep = true; mode = 'r'; continue; }
    if (cur && mode && /^\s*>{5,}\s*REPLACE\b/i.test(l)) { cur.done = true; mode = null; continue; }
    if (cur && mode === 's') cur.s.push(l); else if (cur && mode === 'r') cur.r.push(l);
  }
  return pairs.map(p => ({ search: p.s.join('\n'), replace: p.r.join('\n'), sep: p.sep, done: p.done }));
}
function jsApplyEdit(text, search, replace) {
  if (!search.trim()) return text.trim() ? null : replace + '\n';
  if (text.includes(search)) return text.replace(search, () => replace);
  const tl = text.split('\n'), sl = search.split('\n');
  for (let i = 0; i + sl.length <= tl.length; i++) {
    if (sl.every((s, k) => tl[i + k].trim() === s.trim())) return [...tl.slice(0, i), ...replace.split('\n'), ...tl.slice(i + sl.length)].join('\n');
  }
  return null;
}

/* ---- applying them */
function syncOps(chat, msg, final) {
  const ops = codeSegs(splitThink(msg).c, !final).filter(s => s.t === 'op');
  msg.ops = msg.ops || [];
  ops.forEach((op, i) => {
    if (msg.ops[i] || !(op.closed || final)) return;
    msg.ops[i] = { type: op.type, path: op.path, status: 'queued' };
    chat._q = (chat._q || Promise.resolve()).then(() => runOp(chat, msg, i, op)).catch(e => {
      Object.assign(msg.ops[i], { status: 'error', errors: [String(e.message || e)] }); refreshMsg(chat, msg);
    });
  });
}
function refreshMsg(chat, msg) { if (S.chat === chat) { const el = msgEl(msg); if (el) updateMsg(el, msg); } }
async function runOp(chat, msg, i, op) {
  const o = msg.ops[i], D = wsData(chat.id);
  o.status = 'working'; refreshMsg(chat, msg);
  if (op.type === 'run') return runWsFile(chat, msg, o);
  let payload;
  if (op.type === 'file') payload = { type: 'write', path: op.path, content: fileBody(op.body) };
  else if (op.type === 'delete') payload = { type: 'delete', path: op.path };
  else {
    const edits = parseEdits(op.body).filter(p => p.sep);
    if (!edits.length) { Object.assign(o, { status: 'error', errors: [`The edit for ${op.path} had no SEARCH/REPLACE pair.`] }); refreshMsg(chat, msg); return; }
    payload = { type: 'edit', path: op.path, edits: edits.map(({ search, replace }) => ({ search, replace })) };
  }
  let r;
  try { r = await api('ws/apply', { ws: chat.id, op: payload }); } catch (e) { r = { ok: false, errors: [e.message] }; }
  Object.assign(o, { status: r.ok ? 'done' : 'error', added: r.added || 0, removed: r.removed || 0, created: !!r.created, errors: r.errors || [], path: r.path || o.path });
  if (op.type === 'delete') { delete D.files[o.path]; D.order = D.order.filter(p => p !== o.path); if (D.sel === o.path) D.sel = D.order[0] || null; }
  else if (r.content != null) {
    D.files[o.path] = r.content;
    if (!D.order.includes(o.path)) { D.order.push(o.path); D.order.sort(); }
    D.changed[o.path] = { lines: r.changed || [], t: Date.now() };
    D.sel = o.path; D.flash = o.path;
  }
  D.live = null;
  refreshMsg(chat, msg); wsRender(chat.id);
  if (S.chat === chat) updateToolUI();
  if (S.panel && S.panel.kind === 'ws' && S.panel.chatId === chat.id && S.panel.tab === 'preview') setPanelTab('preview');
}
async function runWsFile(chat, msg, o) {
  if (!S.settings.run_ok) {
    const ok = await confirmDialog({ title: `Let the AI run ${o.path}?`,
      text: 'Code mode can run the .py, .js and .ps1 files it writes. They run on your PC with your user rights, in this chat\'s workspace folder, and are stopped after 60 seconds. MTAI will not ask again.',
      ok: 'Allow', danger: false });
    if (!ok) { Object.assign(o, { status: 'skipped', errors: ['You did not allow running code.'] }); refreshMsg(chat, msg); return; }
    S.settings.run_ok = true; saveSettings();
  }
  let r;
  try { r = await api('ws/run', { ws: chat.id, path: o.path }); } catch (e) { r = { error: e.message }; }
  if (r.error) Object.assign(o, { status: 'error', errors: [r.error] });
  else if (r.preview) {
    Object.assign(o, { status: 'done', preview: true });
    const D = wsData(chat.id); D.sel = r.path;
    if (S.chat === chat) { await openWorkspace(chat, r.path); setPanelTab('preview'); }
  } else {
    const out = ((r.stdout || '') + (r.stderr || '')).slice(-6000);
    Object.assign(o, { status: r.code === 0 && !r.timed_out ? 'done' : 'error', code: r.code, timed_out: r.timed_out, seconds: r.seconds, out });
    const D = wsData(chat.id); D.runs[o.path] = { code: r.code, timed_out: r.timed_out };
    wsLog(chat.id, o.status === 'done' ? 'run' : 'error', `$ ${o.path}  ·  ${r.timed_out ? 'stopped after 60 s' : 'exit code ' + r.code}  ·  ${fmtDur(r.seconds)}\n${out.trim() || '(no output)'}`);
  }
  refreshMsg(chat, msg);
}
function wsLog(id, type, text) {
  const D = wsData(id); D.logs = D.logs || [];
  D.logs.push({ type, args: [text] }); if (D.logs.length > 300) D.logs.shift();
  if (S.panel && S.panel.kind === 'ws' && S.panel.chatId === id) { S.panel.logs = D.logs; renderConsole(); }
}
/* Safety net for models that still answer with ``` blocks instead of tags.
   A block that is a whole file (for the file open in the Code tab, another workspace file it names,
   or a new file) is turned into a <file> tag, so it lands in the file and the chat shows an op card.
   Snippets cannot be applied safely, so the model is asked once more to apply them with <edit>. */
const CM_FENCE = /```([\w.+#-]*)[^\n]*\n([\s\S]*?)\n[ \t]*```/g;
const CM_LANG = { html: 'html', htm: 'html', svg: 'svg', js: 'js', javascript: 'js', jsx: 'js', mjs: 'js', ts: 'ts', typescript: 'ts', py: 'py', python: 'py',
  css: 'css', json: 'json', ps1: 'ps1', powershell: 'ps1', md: 'md', markdown: 'md', java: 'java', c: 'c', cpp: 'cpp', 'c++': 'cpp', cs: 'cs', csharp: 'cs',
  go: 'go', rs: 'rs', rust: 'rs', lua: 'lua', gd: 'gd', gdscript: 'gd' };
const CM_NEW = { html: 'index.html', js: 'script.js', py: 'main.py', css: 'style.css', ts: 'main.ts', json: 'data.json', ps1: 'script.ps1', md: 'README.md' };
const cmExt = p => ({ htm: 'html', mjs: 'js', jsx: 'js' })[((String(p).match(/\.(\w+)$/) || [])[1] || '').toLowerCase()] || ((String(p).match(/\.(\w+)$/) || [])[1] || '').toLowerCase();
function fenceToOps(chat, msg) {
  const text = splitThink(msg).c;
  if (codeSegs(text).some(s => s.t === 'op')) return;
  const D = wsData(chat.id);
  const open = D.sel && D.files[D.sel] != null ? D.sel : null;
  const fences = [...text.matchAll(CM_FENCE)].map(f => {
    const body = f[2], lang = f[1].toLowerCase();
    const ext = CM_LANG[lang] || (!lang && open ? cmExt(open) : '');
    const before = text.slice(Math.max(0, f.index - 160), f.index);
    return { raw: f[0], body, ext, lines: body.split('\n').length, before };
  }).filter(f => f.ext && f.lines >= 3);
  if (!fences.length) return;
  const files = D.order.filter(p => D.files[p] != null);
  const plan = fences.map(f => {
    // a workspace path named just above the block wins, then the open file, then the only file of that type
    const named = files.filter(p => f.before.includes(p) || f.before.includes(p.split('/').pop())).pop();
    const same = files.filter(p => cmExt(p) === f.ext);
    const target = named || (open && cmExt(open) === f.ext ? open : same.length === 1 ? same[0] : null);
    if (!target) {
      // a new file only when the workspace is empty or the answer names the new file just above the block
      const m = f.before.match(new RegExp(`([\\w./-]+\\.${f.ext === 'html' ? 'html?' : f.ext})\\b(?![\\s\\S]*\\.${f.ext}\\b)`, 'i'));
      const name = m ? m[1].replace(/^\.?\//, '') : !files.length ? CM_NEW[f.ext] : null;
      return name && !name.includes('..') ? { path: name, f } : { snippet: true, f };
    }
    const have = D.files[target].split('\n').length;
    const whole = f.lines >= have * 0.7 || (f.ext === 'html' && /<!doctype|<html[\s>]/i.test(f.body) && /<!doctype|<html[\s>]/i.test(D.files[target]));
    return whole ? { path: target, f } : { snippet: true, f, path: target };
  }).filter(Boolean);
  if (!plan.length) return;
  if (plan.some(p => p.snippet)) { msg.fenceNudge = (plan.find(p => p.snippet && p.path) || {}).path || open || ''; return; }
  const seen = new Set();
  for (const p of plan) {
    if (seen.has(p.path)) continue;                // two blocks for one file: keep the first
    seen.add(p.path);
    msg.content = msg.content.replace(p.f.raw, () => `<file path="${p.path}">\n${p.f.body}\n</file>`);
  }
  msg.autoApplied = true;
}
function codeFeedback(msg) {
  if (msg.fenceNudge != null && !(msg.ops || []).length)
    return `Workspace report (sent by MTAI automatically):\n- You wrote code in the chat, but no file changed. The user wants the files edited, not code to copy.\n\n` +
      `Apply those changes now with <edit path="${msg.fenceNudge || 'the file'}"> and SEARCH/REPLACE pairs. Copy the SEARCH lines exactly from the current file in the system message. Do not write any \`\`\` code blocks and do not explain the code again.`;
  const bad = (msg.ops || []).filter(o => o && o.status === 'error');
  if (!bad.length) return null;
  const lines = bad.map(o => o.type === 'run'
    ? `- Running ${o.path} failed: ${o.timed_out ? 'it ran longer than 60 seconds' : o.errors && o.errors.length ? o.errors.join(' ') : 'exit code ' + o.code}${o.out ? `\n\`\`\`\n${o.out.trim().split('\n').slice(-30).join('\n')}\n\`\`\`` : ''}`
    : `- ${o.errors.join(' ')}`);
  return `Workspace report (sent by MTAI automatically):\n${lines.join('\n')}\n\nFix these problems. For a failed edit, copy the SEARCH lines exactly from the current file in the system message. Do not repeat changes that already worked.`;
}

/* ---- rendering in the chat */
function opsKey(m) { return (m.ops || []).map(o => o ? o.status[0] + (o.added || 0) : '_').join(''); }
function renderCodeMsg(text, m) {
  const segs = codeSegs(text, m.pending);
  let k = -1, h = '';
  for (const s of segs) {
    if (s.t === 'text') { if (s.s.trim()) h += md(s.s); continue; }
    k++;
    h += opCard(s, (m.ops || [])[k], k, m);
  }
  return h;
}
function opCard(seg, o, k, m) {
  const writing = !seg.closed && m.pending;
  const st = o ? o.status : writing ? 'writing' : seg.closed ? 'queued' : 'error';
  const lines = seg.body != null ? (seg.type === 'file' ? fileBody(seg.body) : seg.body).split('\n').length : 0;
  const ic = { file: 'file', edit: 'edit', delete: 'trash', run: 'play' }[seg.type];
  let verb, detail = '';
  if (seg.type === 'file') verb = st === 'writing' ? 'Writing' : st === 'done' ? (o.created ? 'Created' : 'Updated') : st === 'error' ? 'Could not write' : 'Writing';
  else if (seg.type === 'edit') verb = st === 'writing' ? 'Editing' : st === 'done' ? 'Edited' : st === 'error' ? (o && o.added ? 'Partly edited' : 'Edit failed') : 'Editing';
  else if (seg.type === 'delete') verb = st === 'done' ? 'Deleted' : st === 'error' ? 'Could not delete' : 'Deleting';
  else verb = st === 'done' ? (o.preview ? 'Opened' : 'Ran') : st === 'error' ? 'Run failed' : st === 'skipped' ? 'Not run' : 'Running';
  if (st === 'writing') detail = `${lines} line${lines === 1 ? '' : 's'} so far`;
  else if (o && o.status === 'done' && seg.type !== 'run' && seg.type !== 'delete') detail = `<span class="add">+${o.added}</span> <span class="del">−${o.removed}</span>`;
  else if (o && seg.type === 'run' && o.status !== 'working' && o.status !== 'queued' && !o.preview) detail = o.timed_out ? 'stopped after 60 s' : o.code != null ? `exit code ${o.code} · ${fmtDur(o.seconds)}` : '';
  const spin = st === 'writing' || st === 'working' || st === 'queued';
  const mark = spin ? '<span class="spin"></span>' : st === 'done' ? icon('check', 14) : icon('alert', 14);
  const errs = o && o.errors && o.errors.length ? `<div class="op-err">${o.errors.map(esc).join('<br>')}</div>` : '';
  const out = o && o.out != null ? `<pre class="op-out">${esc(o.out.trim().split('\n').slice(-14).join('\n')) || '<span class="ro-none">(no output)</span>'}</pre>` : '';
  return `<div class="op ${st}"><button class="op-card" data-op="${k}" data-path="${esc(seg.path)}" data-optype="${seg.type}" title="Show in the workspace">` +
    `<span class="op-ic">${icon(ic, 15)}</span><span class="op-main"><b>${verb} <code>${esc(seg.path)}</code></b>${detail ? `<small>${detail}</small>` : ''}</span><span class="op-mark">${mark}</span></button>${errs}${out}</div>`;
}

/* ---- the workspace panel with the live view */
function panelIsWs(id) { return S.panel && S.panel.kind === 'ws' && S.panel.chatId === id && !$('#panel').hidden; }
async function openWorkspace(chat, path) {
  const D = wsData(chat.id);
  if (path) D.sel = path;
  if (!panelIsWs(chat.id)) {
    const prev = S.panel || {};
    S.panel = { kind: 'ws', chatId: chat.id, title: 'Workspace', tab: 'code', device: prev.device || 'desktop', logs: D.logs || (D.logs = []) };
    showPanel();
  }
  if (!D.loaded) { try { await wsLoad(chat.id); if (path) D.sel = path; } catch (e) { toast('Could not read the workspace: ' + e.message, 'err'); } }
  wsRender(chat.id);
}
function wsLive(chat, msg) {
  const segs = codeSegs(splitThink(msg).c, true).filter(s => s.t === 'op');
  const open = segs.find(s => !s.closed && (s.type === 'file' || s.type === 'edit'));
  const D = wsData(chat.id);
  if (!open) { if (D.live) { D.live = null; wsRender(chat.id); } return; }
  D.live = open; D.sel = open.path;
  if (!panelIsWs(chat.id) && S.wsNoAuto !== msg.id && S.chat === chat) openWorkspace(chat, open.path);
  else wsRender(chat.id);
}
function hlLines(text, lang) {
  const out = []; let open = '';
  for (const raw of highlight(text, lang).split('\n')) {
    const line = open + raw;
    for (const t of raw.match(/<span class="[^"]+">|<\/span>/g) || []) open = t === '</span>' ? '' : t;
    out.push(open ? line + '</span>' : line);
  }
  return out;
}
const lineRow = (no, html, cls = '') => `<div class="ln ${cls}"><span class="no">${no}</span><span class="tx">${html || ' '}</span></div>`;
function wsCodeHtml(D) {
  const p = D.sel, live = D.live && D.live.path === p ? D.live : null;
  if (!p) return { html: '<div class="ws-empty">No files yet. Ask for something in code mode and watch it being written here.</div>' };
  const lang = langOfFile(p);
  if (live && live.type === 'file') {
    const text = fileBody(live.body).replace(/\n$/, '');
    const rows = hlLines(text, lang);
    return { html: rows.map((h, i) => lineRow(i + 1, h + (i === rows.length - 1 ? '<span class="type-caret"></span>' : ''), 'new')).join(''), bottom: true };
  }
  let text = D.files[p];
  if (text == null) return { html: `<div class="ws-empty">${D.order.includes(p) ? 'This file cannot be shown (binary or too big).' : 'Waiting for the file…'}</div>` };
  text = text.replace(/\n$/, '');
  if (live && live.type === 'edit') {
    const pairs = parseEdits(live.body);
    for (const q of pairs.slice(0, -1)) text = jsApplyEdit(text, q.search, q.replace) ?? text;
    const cur = pairs[pairs.length - 1];
    const tl = text.split('\n'), rows = hlLines(text, lang);
    if (!cur) return { html: rows.map((h, i) => lineRow(i + 1, h)).join(''), banner: 'Getting ready to edit…' };
    const sl = cur.search.split('\n'); if (!cur.sep && sl.length > 1 && sl[sl.length - 1].trim() === '') sl.pop();
    let at = -1;
    if (sl.some(s => s.trim())) {
      for (let i = 0; i + sl.length <= tl.length; i++) {
        let ok = true;
        for (let k = 0; k < sl.length && ok; k++) {
          const a = tl[i + k].trim(), b = sl[k].trim();
          ok = (k === sl.length - 1 && !cur.sep) ? a.startsWith(b) : a === b;
        }
        if (ok) { at = i; break; }
      }
    }
    if (at < 0) return { html: rows.map((h, i) => lineRow(i + 1, h)).join(''), banner: cur.sep ? 'Could not find the lines this edit changes yet' : 'Finding the lines to change…' };
    const add = cur.sep ? hlLines(cur.replace, lang) : [];
    let h = '';
    for (let i = 0; i < at; i++) h += lineRow(i + 1, rows[i]);
    for (let k = 0; k < sl.length; k++) h += lineRow(at + k + 1, rows[at + k], cur.sep ? 'del' : 'find');
    add.forEach((x, k) => { h += lineRow('+', x + (k === add.length - 1 && !cur.done ? '<span class="type-caret"></span>' : ''), 'add'); });
    for (let i = at + sl.length; i < rows.length; i++) h += lineRow(i + 1, rows[i]);
    return { html: h, focus: at + (cur.sep ? sl.length + add.length : sl.length) - 1 };
  }
  const ch = D.changed[p], fresh = ch && Date.now() - ch.t < 4000, set = new Set(fresh ? ch.lines : []);
  const rows = hlLines(text, lang);
  return { html: rows.slice(0, 5000).map((h, i) => lineRow(i + 1, h, set.has(i + 1) ? 'chg' : '')).join(''), focus: fresh && ch.lines.length ? ch.lines[0] - 1 : null };
}
function wsRender(id) {
  if (!panelIsWs(id)) return;
  const D = wsData(id), p = S.panel;
  const paths = [...D.order]; if (D.live && !paths.includes(D.live.path)) { paths.push(D.live.path); paths.sort(); }
  $('#wsTree').innerHTML = `<div class="ws-th"><span>Files</span><em>${paths.length}</em></div>` + (paths.length ? paths.map(x => {
    const dir = x.includes('/') ? x.slice(0, x.lastIndexOf('/') + 1) : '', name = x.slice(dir.length);
    const live = D.live && D.live.path === x, ch = D.changed[x] && Date.now() - D.changed[x].t < 120000;
    return `<button class="ws-f ${x === D.sel ? 'on' : ''} ${live ? 'live' : ''}" data-wsf="${esc(x)}" title="${esc(x)}">${icon('file', 13)}<span>${dir ? `<i>${esc(dir)}</i>` : ''}${esc(name)}</span>${live ? '<em class="w"></em>' : ch ? '<em class="c"></em>' : ''}</button>`;
  }).join('') : '<div class="ws-none">Empty</div>');
  $('#pvTitle').textContent = D.live ? (D.live.type === 'edit' ? 'Editing ' : 'Writing ') + D.live.path.split('/').pop() : 'Workspace';
  $('#panel').classList.toggle('busy', !!D.live);
  if (p.tab !== 'preview') $('#pvUrl').textContent = D.sel || 'workspace';
  const v = wsCodeHtml(D), box = $('#wsCode');
  const key = (D.sel || '') + '\u0001' + v.html.length + v.html.slice(-200) + (v.banner || '');
  if (box._key !== key) {
    const keepBottom = v.bottom && box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    const switched = box._sel !== D.sel;
    box._key = key; box._sel = D.sel;
    box.innerHTML = (v.banner ? `<div class="ws-banner"><span class="spin"></span>${esc(v.banner)}</div>` : '') + `<div class="ws-lines">${v.html}</div>`;
    if (v.bottom && (keepBottom || switched || D.live)) box.scrollTop = box.scrollHeight;
    else if (v.focus != null) { const row = box.querySelectorAll('.ln')[v.focus]; if (row) { const top = row.offsetTop - box.clientHeight / 2; if (Math.abs(box.scrollTop - top) > box.clientHeight / 3 || switched) box.scrollTo({ top, behavior: 'smooth' }); } }
    else if (switched) box.scrollTop = 0;
  }
  if (D.flash) { const f = D.flash; D.flash = null; setTimeout(() => { if (panelIsWs(id) && !D.live) { $('#wsCode')._key = null; wsRender(id); } }, 4100); }
}
function wsPreviewUrl(id) {
  const D = wsData(id);
  const html = D.sel && /\.html?$/i.test(D.sel) ? D.sel : D.order.find(x => /(^|\/)index\.html?$/i.test(x)) || D.order.find(x => /\.html?$/i.test(x));
  return html ? `${S.env.preview_base}/w/${id}/${html.split('/').map(encodeURIComponent).join('/')}` : null;
}

/* ---- composer: web chips, code chip, footnote */
function updateToolUI() {
  const busy = !!(S.streaming && S.streaming.msg.web && S.streaming.msg.web.active);
  const priv = privacyOn();
  const web = !priv && (S.settings.web === 'search' || busy), deep = !priv && !!S.deepNext, code = !!(S.chat && S.chat.code);
  $('#webBtn').classList.toggle('on', web && !deep);
  $('#deepBtn').classList.toggle('on', deep);
  $('#codeChip').classList.toggle('on', code);
  $('#wsBtn').hidden = !code;
  for (const b of [$('#webBtn'), $('#deepBtn')]) {
    b.classList.toggle('blocked', priv);
    b.setAttribute('aria-disabled', String(priv));
  }
  if (priv) {
    $('#footnote').innerHTML = icon('shield', 13) + `<span>${privacyLine()}</span>`;
    $('#footnote').classList.remove('net'); $('#footnote').classList.add('priv');
    return;
  }
  $('#footnote').classList.remove('priv');
  const notes = [];
  if (deep) notes.push('Deep research: the AI searches DuckDuckGo and reads several pages');
  else if (web) notes.push('Web search on: search words go to DuckDuckGo');
  if (code) {
    const t = wsData(S.chat.id).sel;
    notes.push(t ? `Code mode: changes go into ${t} (the file open in the Code tab)` : 'Code mode: files live in this chat\'s workspace folder');
  }
  $('#footnote').textContent = notes.length ? notes.join(' · ') + '. Chats stay on this PC.' : 'Local models run on this PC. Chats stay on this PC.';
  $('#footnote').classList.toggle('net', web || deep);
}
async function toggleWeb(mode) {
  if (mode === 'deep') {
    if (!S.deepNext && !await webAllowed()) return;
    S.deepNext = !S.deepNext;
    if (S.deepNext) toast('Deep research for the next message: the browser panel shows what it reads');
  } else {
    const on = S.settings.web !== 'search';
    if (on && !await webAllowed()) return;
    S.settings.web = on ? 'search' : 'off'; S.deepNext = false; saveSettings();
    toast(on ? 'Web search on: answers use fresh results from the web' : 'Web search off');
  }
  updateToolUI(); $('#input').focus();
}
function toggleCode() {
  const c = S.chat; if (!c) return;
  c.code = !c.code;
  if (c.code) toast('Code mode on: the AI gets its own project folder and edits files there. You can watch it in the panel.', 'info', 4500);
  else toast('Code mode off');
  if (c.messages.length) saveChat(c);
  updateToolUI();
  if (c.code && innerWidth > 1100) openWorkspace(c);
  else if (!c.code && S.panel && S.panel.kind === 'ws') closePanel();
}

function bindTools() {
  $('#webBtn').onclick = () => toggleWeb('search');
  $('#deepBtn').onclick = () => toggleWeb('deep');
  $('#codeChip').onclick = toggleCode;
  $('#wsBtn').onclick = () => { if (panelIsWs(S.chat.id)) closePanel(); else openWorkspace(S.chat); };
  $('#wsTree').addEventListener('click', e => {
    const f = e.target.closest('[data-wsf]'); if (!f || !S.panel) return;
    const D = wsData(S.panel.chatId); D.sel = f.dataset.wsf; $('#wsCode')._key = null;
    if (S.panel.tab !== 'code') setPanelTab(S.panel.tab); wsRender(S.panel.chatId);
    updateToolUI();
  });
  $('#webTabs').addEventListener('click', e => { const t = e.target.closest('[data-wtab]'); if (t) webShow(+t.dataset.wtab); });
  document.addEventListener('click', e => {
    const op = e.target.closest('[data-op]');
    if (op && S.chat) {
      const D = wsData(S.chat.id); D.sel = op.dataset.path; D.changed[op.dataset.path] && (D.changed[op.dataset.path].t = Date.now());
      openWorkspace(S.chat, op.dataset.optype === 'run' ? null : op.dataset.path).then(() => {
        if (op.dataset.optype === 'run') setPanelTab(/\.html?$/i.test(op.dataset.path) ? 'preview' : 'console');
        else { setPanelTab('code'); $('#wsCode')._key = null; wsRender(S.chat.id); }
      });
      return;
    }
    const wp = e.target.closest('[data-wpage]'); if (wp) { openWebPage(wp.dataset.wpage, wp.dataset.wtitle); return; }
  });
}
