"""
MTAI privacy mode test suite: real attempts, both modes, rerunnable.

    py -3.13 tests\\privacy_suite.py            (about 2-4 minutes, opens a small "MTAI privacy test" window)
    py -3.13 tests\\privacy_suite.py --no-image (skip the local picture test, which needs the GPU)
    py -3.13 tests\\privacy_suite.py --firewall (also the Windows Firewall rules for local AI programs:
                                              two administrator prompts, rules removed again at the end)

It starts MTAI's servers and browser window in this process exactly like the app
does (audit hook, gate proxy, WebView2 behind the gate), then:

  1. Privacy ON: the self-test (privacy_check.py) with this window's browser probes
     and a preview page's probes, the backend routes that need the internet,
     the coding workspace (write, list, run, preview), a local Ollama chat and a
     local picture, while a monitor reads the TCP table of MTAI's whole process
     tree (Python, WebView2 processes, sandboxed runs, image engine) every second.
  2. Switching ON while connections are open: a Python socket, a browser
     WebSocket and a running program must all be cut.
  3. Privacy OFF: the same self-test must show normal networking is back.

With --firewall, after step 1: MTAI's firewall rules for the local AI programs it finds
  (Ollama...) are added with a UAC prompt, then real attempts are made from the restricted
  programs (IPv4, IPv6, host name, LAN, loopback, Ollama's own registry pull by name and by
  IP), the self-test must turn green, and the rules are removed again (second prompt). The
  total number of Windows Firewall rules must be the same before and after.

Every row is PASS, FAIL, UNVERIFIED (could not be proven either way), UNPROTECTED (known
not to be blocked) or INFO. Results go
to data/privacy-tests/latest.json and a readable report-<time>.md next to it.
Only harmless public test hosts are contacted (example.com/.net/.org, 1.1.1.1,
echo.websocket.org, www.iana.org, stun.l.google.com, DuckDuckGo with the word
"example", huggingface.co metadata, the Ollama registry for a name that does not
exist). No chats, files, keys or personal data are sent. Settings are restored.
"""
import json
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import local_ai_chat as L          # noqa: E402  (installs the audit hook)
import webview                     # noqa: E402

NG, PC = L.NG, L.PC
ROWS = []
OUT = L.DATA_DIR / "privacy-tests"
NO_IMAGE = "--no-image" in sys.argv
FIREWALL = "--firewall" in sys.argv
FW, BK = L.FW, L.BK
RESULTS = ("PASS", "FAIL", "UNVERIFIED", "UNPROTECTED", "INFO")


def row(phase, group, name, result, detail=""):
    ROWS.append({"phase": phase, "group": group, "name": name, "result": result, "detail": str(detail)[:400]})
    print(f"[{phase}] {result:<10} {group} / {name}: {str(detail)[:150]}", flush=True)


# ------------------------------------------------------------- monitor --

MON_PS = r"""
$root = %d
while ($true) {
  $all = Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId,Name,CreationDate,CommandLine
  $born = @{}; foreach ($p in $all) { $born[[int]$p.ProcessId] = $p.CreationDate }
  # a child is never older than its parent: skips processes whose parent PID was reused by MTAI
  $kids = @{}; foreach ($p in $all) { $pp = [int]$p.ParentProcessId; if (-not $born.ContainsKey($pp) -or $p.CreationDate -lt $born[$pp].AddSeconds(-1)) { continue }
    if (-not $kids.ContainsKey($pp)) { $kids[$pp] = @() }; $kids[$pp] += $p }
  $names = @{}; foreach ($p in $all) { $tag = ''; if ($p.CommandLine -match '--user-data-dir=("[^"]+"|\S+)') { $tag = ' [' + $Matches[1] + ']' }; if ($p.CommandLine -match '--type=(\S+)') { $tag += ' type=' + $Matches[1] } elseif ($p.Name -eq 'msedgewebview2.exe') { $tag += ' type=browser' }; $names[[int]$p.ProcessId] = $p.Name + $tag }
  $set = @{}; $q = New-Object System.Collections.Queue; $q.Enqueue($root)
  while ($q.Count) { $id = $q.Dequeue(); if ($set.ContainsKey($id)) { continue }; $set[$id] = 1; if ($kids.ContainsKey($id)) { foreach ($c in $kids[$id]) { $q.Enqueue([int]$c.ProcessId) } } }
  $set.Remove($PID) | Out-Null
  $ol = @(); foreach ($p in $all) { if ($p.Name -eq 'ollama.exe' -or $p.Name -eq 'ollama app.exe' -or $p.Name -eq 'llama-server.exe') { $ol += [int]$p.ProcessId } }
  $tcp = Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $_.State -ne 'Listen' -and $_.State -ne 'Bound' }
  foreach ($c in $tcp) {
    $o = [int]$c.OwningProcess
    $who = if ($set.ContainsKey($o)) { 'MTAI' } elseif ($ol -contains $o) { 'OLLAMA' } else { $null }
    if ($who) { Write-Output ("C|" + $who + "|" + $o + "|" + $names[$o] + "|" + $c.RemoteAddress + "|" + $c.RemotePort + "|" + $c.State) }
  }
  Write-Output ("T|" + $set.Count)
  [Console]::Out.Flush()
  Start-Sleep -Milliseconds 700
}
"""


def _outside(addr):
    a = addr.strip().lower()
    return not (a.startswith("127.") or a in ("::1", "0.0.0.0", "::", "") or a.startswith("::ffff:127."))


class Monitor:
    def __init__(self):
        self.lines = []
        self.ticks = 0
        self.max_procs = 0
        self.mark = None
        with NG.allow("privacy test: read the TCP table"):
            self.p = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", MON_PS % L.os.getpid()],
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            line = line.strip()
            if line.startswith("T|"):
                self.ticks += 1
                self.max_procs = max(self.max_procs, int(line[2:] or 0))
            elif line.startswith("C|"):
                _, who, pid, name, ra, rp, st = (line.split("|") + [""] * 7)[:7]
                if _outside(ra):
                    if who == "MTAI" and not any(c["remote"] == f"{ra}:{rp}" and c["pid"] == pid for c in self.lines):
                        print(f"  monitor: new outside connection {name}({pid}) -> {ra}:{rp} {st}", flush=True)
                    self.lines.append({"t": time.time(), "who": who, "pid": pid, "name": name, "remote": f"{ra}:{rp}", "state": st})

    def window(self, t0, t1, who="MTAI"):
        return [c for c in self.lines if t0 <= c["t"] <= t1 and c["who"] == who]

    def wait_ticks(self, n):
        target = self.ticks + n
        for _ in range(200):
            if self.ticks >= target:
                return
            time.sleep(0.1)

    def stop(self):
        try:
            self.p.kill()
        except Exception:
            pass


# ----------------------------------------------------------------- app --

before = json.loads(L.SETTINGS_FILE.read_text("utf-8")) if L.SETTINGS_FILE.is_file() else {}
srv = ThreadingHTTPServer(("127.0.0.1", 0), L.Handler)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
psrv = ThreadingHTTPServer(("127.0.0.1", 0), L.PreviewHandler)
psrv.daemon_threads = True
L.PREVIEW_BASE = f"http://127.0.0.1:{psrv.server_address[1]}"
threading.Thread(target=psrv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}"
L.SERVER_PORT = srv.server_address[1]
gate = NG.start_gate()
L.os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = NG.webview2_args(gate.port)
L.BROWSER.update(mode="webview2", gate=gate.port, runtime=L.use_private_runtime(webview))
win = webview.create_window("MTAI privacy test", BASE + "/", width=1180, height=800, js_api=L.JsApi())
J = lambda js: win.evaluate_js(js)


def api(path, body=None, timeout=120):
    req = urllib.request.Request(BASE + "/api/" + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-Token": L.TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    if r.headers.get("Content-Type", "").startswith("application/x-ndjson"):
        return [json.loads(x) for x in raw.splitlines() if x.strip()]
    return json.loads(raw) if raw.strip() else {}


def js_async(expr, limit=90):
    key = "__t" + secrets.token_hex(4)
    J(f"window.{key}=undefined;Promise.resolve().then(()=>({expr})).then(v=>window.{key}=JSON.stringify({{ok:1,v}}),"
      f"e=>window.{key}=JSON.stringify({{ok:0,v:String(e&&e.message||e)}}))")
    t0 = time.time()
    while time.time() - t0 < limit:
        v = J(f"window.{key}")
        if v:
            d = json.loads(v)
            return d["v"] if d["ok"] else RuntimeError(d["v"])
        time.sleep(0.25)
    return TimeoutError(f"no answer after {limit}s")


def page_privacy(on):
    J(f"S.settings.privacy={'true' if on else 'false'};PRIV.stat=null;updatePrivacyUI(false)")


def graded(phase, run_):
    for r in run_["results"]:
        row(phase, r["group"], r["name"], r["result"], r["detail"])


def refusal(phase, name, path, body):
    try:
        r = api(path, body)
        if isinstance(r, list):
            r = next((x for x in r if x.get("type") == "error"), r[-1] if r else {})
        ok = bool(r.get("privacy")) or "Privacy mode" in str(r.get("error") or r.get("message") or "")
        row(phase, "Backend routes", name, "PASS" if ok else "FAIL", r.get("error") or r.get("message") or json.dumps(r)[:200])
    except Exception as e:
        row(phase, "Backend routes", name, "UNVERIFIED", f"{type(e).__name__}: {e}")


def phase_on(mon):
    ph = "ON"
    L.set_privacy(True)
    page_privacy(True)
    t0 = time.time()
    mon.wait_ticks(2)
    # 1. the self-test with this window's probes (main page + a preview page)
    st = js_async("mtaiPrivacy.verify({quiet:true})", 120)
    if isinstance(st, Exception):
        row(ph, "Self-test", "Run from the page", "FAIL", st)
    else:
        graded(ph, st["last"])
        row(ph, "Self-test", "Status shown in the app", "PASS" if st["level"] in ("verified", "partly") else "FAIL",
            f"level={st['level']}")
        status_rules(ph, st)
    res = js_async("openDiag().then(() => new Promise(r => setTimeout(r, 7000))).then(() => { const t = document.querySelector('.priv-diag').innerText;"
                   " document.getElementById('dialog').hidden = true; return t.includes('Local AI programs') && !t.includes('Looking for') ? 'ok' : t.slice(0, 300); })", 40)
    row(ph, "Diagnostics page", "Shows the Local AI programs section with what was found", "PASS" if res == "ok" else "FAIL", res)
    foot = J("document.getElementById('footnote').textContent")
    row(ph, "Wording", "Footnote does not claim 'Nothing leaves this PC'", "PASS" if "Nothing leaves" not in foot else "FAIL", foot)
    # 2. backend routes that need the internet
    refusal(ph, "Ollama model download", "ollama/pull", {"name": "tinyllama"})
    refusal(ph, "Web search", "web/search", {"q": "example"})
    refusal(ph, "Deep research page fetch", "web/fetch", {"url": "https://example.com"})
    refusal(ph, "Image model download", "imagegen/download", {"id": "sd-turbo"})
    refusal(ph, "Cloud model list refresh", "cloud/refresh", {})
    refusal(ph, "Open a web link", "open", {"url": "https://example.com"})
    refusal(ph, "Open a preview in the system browser", "open", {"url": L.PREVIEW_BASE + "/p/x"})
    keys = [k for k in L.P.PROV if L.P.get_key(k)]
    if keys:
        n0 = len(NG.BLOCKED)
        L.P.refresh_stale(background=False)
        row(ph, "Background", "Cloud model refresh in the background", "PASS",
            f"{len(keys)} key(s); {len(NG.BLOCKED) - n0} attempts blocked")
    else:
        row(ph, "Background", "Cloud model refresh in the background", "UNVERIFIED", "No API keys saved, so nothing would refresh")
    # 3. coding workspace without internet
    ws = "privacyselftest" + secrets.token_hex(3)
    try:
        L.ws_apply(ws, {"type": "write", "path": "main.py", "content":
                        "import socket\nopen('out.txt','w').write('local ok')\nprint('local', open('out.txt').read())\n"
                        "try:\n    socket.create_connection(('example.com', 80), timeout=5); print('NET CONNECTED')\n"
                        "except Exception as e:\n    print('NET FAILED', type(e).__name__)\n"})
        L.ws_apply(ws, {"type": "write", "path": "index.html", "content":
                        "<!doctype html><body><script src='app.js'></script>"
                        "<script>fetch('https://example.com/?mtai-selftest-ws',{mode:'no-cors'}).then(()=>parent.postMessage({__ws:'net-ok'},'*'),"
                        "()=>parent.postMessage({__ws:'net-failed:'+(window.__local||'')},'*'))</script></body>"})
        L.ws_apply(ws, {"type": "write", "path": "app.js", "content": "window.__local='local-script-ran';"})
        files = [f["path"] for f in L.ws_list(ws, False).get("files", [])]
        row(ph, "Coding workspace", "Write and list project files", "PASS" if {"main.py", "index.html", "app.js"} <= set(files) else "FAIL", files)
        r = L.ws_run(ws, "main.py")
        out = (r.get("stdout") or "") + (r.get("stderr") or "")
        good = r.get("sandboxed") and "local local ok" in out and "NET FAILED" in out
        row(ph, "Coding workspace", "Run main.py: local file works, network fails", "PASS" if good else "FAIL", out.strip()[:200])
        r = L.ws_run(ws, "index.html")
        res = js_async(f"""new Promise(res => {{ const f = document.createElement('iframe'); f.style.display='none';
            const on = e => {{ if (e.data && e.data.__ws) {{ removeEventListener('message', on); f.remove(); res(e.data.__ws); }} }};
            addEventListener('message', on); setTimeout(() => res('timeout'), 15000); f.src = {json.dumps(r.get('preview', ''))}; document.body.append(f); }})""", 30)
        row(ph, "Coding workspace", "Preview index.html: local script runs, web fetch fails",
            "PASS" if res == "net-failed:local-script-ran" else "FAIL", res)
    finally:
        shutil.rmtree(L.WS_DIR / ws, ignore_errors=True)
    # 4. local models still work
    L.discover()
    models = [m for m in L.MODELS.values() if m["backend"] == "ollama" and m.get("chattable") and not m.get("remote")]
    pick = next((m for m in models if m["name"].startswith("gemma3:4b")), models[0] if models else None)
    if pick:
        ev = api("chat", {"model_id": pick["id"], "messages": [{"role": "user", "content": "Reply with just the word OK."}],
                          "options": {"num_predict": 12}, "think": False, "keep_alive": "1m"}, timeout=180)
        text = "".join(e.get("text", "") for e in ev if e.get("type") == "content")
        err = next((e.get("message") for e in ev if e.get("type") == "error"), None)
        row(ph, "Local functions", f"Chat with {pick['name']} on Ollama (127.0.0.1)", "PASS" if text and not err else "FAIL",
            err or repr(text[:80]))
    else:
        row(ph, "Local functions", "Chat with a local Ollama model", "UNVERIFIED", "No local Ollama model found")
    if NO_IMAGE:
        row(ph, "Local functions", "Local picture (MTAI image engine)", "UNVERIFIED", "Skipped (--no-image)")
    else:
        st = L.IG.status()
        have = [m for m in (st.get("models") or []) if m.get("installed")]
        mid = next((m["id"] for m in have if m["id"] == "sd-turbo"), have[0]["id"] if have else None)
        if mid:
            r = api("images/generate", {"backend": f"mtai|{mid}", "prompt": "a small red cube on a table", "aspect": "square", "seed": 7}, timeout=400)
            row(ph, "Local functions", f"Local picture with {mid} (image engine has its own guard)",
                "PASS" if r.get("name") else "FAIL", r.get("error") or f"{r.get('name')} in {r.get('time')} s")
            if r.get("name"):
                L.P.delete_image(r["name"])
        else:
            row(ph, "Local functions", "Local picture", "UNVERIFIED", "No image model installed")
    # 5. what the whole process tree did meanwhile
    mon.wait_ticks(2)
    t1 = time.time()
    seen = mon.window(t0, t1)
    row(ph, "Process network monitor", "No outside TCP connection from MTAI's process tree while privacy was on",
        "PASS" if not seen and mon.ticks > 3 else ("UNVERIFIED" if not seen else "FAIL"),
        f"{mon.ticks} samples, up to {mon.max_procs} processes watched; " +
        (", ".join(sorted({f"{c['name']}({c['pid']})->{c['remote']}" for c in seen}))[:300] if seen else "0 outside connections"))
    ol = mon.window(t0, t1, "OLLAMA")
    row(ph, "Outside MTAI (information)", "Ollama's own outside connections in the same time",
        "INFO", (", ".join(sorted({c["remote"] for c in ol}))[:200] or "none seen") + " (Ollama is a separate program)")
    return t0, t1


def status_rules(ph, st):
    """The status may only be green when every required check passed and nothing is unprotected."""
    c = st["last"]["counts"]
    clean = not c.get("FAIL") and not c.get("UNVERIFIED") and not c.get("UNPROTECTED") and st["last"].get("browser_probes")
    ok = (st["level"] == "verified") == bool(clean and all(x["state"] == "protected" for x in st["components"]) and not st.get("live_leaks"))
    row(ph, "Self-test", "Green status only when every required check passed", "PASS" if ok else "FAIL",
        f"level={st['level']}, counts={c}, components=" + ", ".join(f"{x['name']}:{x['state']}" for x in st["components"]))


def _rule_count():
    with NG.allow("privacy test: count firewall rules"):
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "(Get-NetFirewallRule -PolicyStore ActiveStore | Measure-Object).Count; "
                            "(Get-NetFirewallRule -PolicyStore PersistentStore | Measure-Object).Count"],
                           capture_output=True, text=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def _ollama_pull(model):
    req = urllib.request.Request(L.OLLAMA_URL + "/api/pull", data=json.dumps({"model": model, "stream": False}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "read", lambda: b"")().decode("utf-8", "replace") or str(e)


def phase_firewall(mon):
    """Real Windows Firewall rules for the local AI programs (two UAC prompts), then rollback."""
    ph = "FIREWALL"
    before = _rule_count()
    row(ph, "Setup", "Windows Firewall rules before (active, persistent)", "INFO", before)
    found = PC.discover_cached(0)             # local AI programs + MTAI's own WebView2 copy when it runs from one
    progs = [e["path"] for b in found for e in b["exes"] if e["default"]]
    row(ph, "Setup", "Local AI programs found", "INFO" if progs else "UNVERIFIED",
        "; ".join(f"{b['name']}: " + ", ".join(e["path"] for e in b["exes"] if e["default"]) for b in found) or "none")
    if not progs:
        return
    if not FW.status()["firewall_on"]:
        row(ph, "Setup", "Windows Firewall on for the active network", "FAIL", "off or ignoring local rules: the rules would do nothing")
        return
    t0 = time.time()
    r = L.firewall_apply({"confirm": True, "programs": progs, "auto": False})
    if r.get("declined") or r.get("error"):
        row(ph, "Rules", "Rules added (administrator prompt)", "UNVERIFIED" if r.get("declined") else "FAIL", r.get("error"))
        return
    res = r.get("result") or {}
    row(ph, "Rules", "Rules added (administrator prompt)", "PASS" if res.get("ok") else "FAIL",
        f"created {len(res.get('created') or [])}, existed {len(res.get('existed') or [])}, errors {res.get('errors')}, "
        f"connections closed {res.get('closed')}, left {res.get('left')}")
    st = FW.status()
    bad = [e["name"] for e in st["ledger"] if not e["ok"]]
    row(ph, "Rules", "Every rule in Windows is exactly as MTAI made it (read back)", "FAIL" if bad or not st["ledger"] else "PASS",
        f"{len(st['ledger'])} rules; not right: {bad or 'none'}")
    mid = _rule_count()
    row(ph, "Rules", "Only MTAI's rules were added", "PASS" if before and mid and mid[0] - before[0] == len(st["ledger"]) else "UNVERIFIED",
        f"before {before}, now {mid}, MTAI's {len(st['ledger'])}")
    try:
        tags = json.loads(urllib.request.urlopen(L.OLLAMA_URL + "/api/tags", timeout=10).read())
        row(ph, "Localhost", "MTAI still talks to Ollama on 127.0.0.1 (model list)", "PASS", f"{len(tags.get('models') or [])} models")
    except Exception as e:
        row(ph, "Localhost", "MTAI still talks to Ollama on 127.0.0.1", "FAIL", e)
    for x in L.firewall_test()["rows"]:
        row(ph, x["group"], x["name"], x["result"], x["detail"])
    st2 = js_async("mtaiPrivacy.verify({quiet:true})", 180)
    if isinstance(st2, Exception):
        row(ph, "Self-test", "Self-test with the rules in place", "FAIL", st2)
    else:
        bk = [r_ for r_ in st2["last"]["results"] if r_["group"].endswith("(Windows Firewall)")]
        row(ph, "Self-test", "Local AI programs shown as protected", "PASS" if bk and all(r_["result"] in ("PASS", "INFO") for r_ in bk) else "FAIL",
            "; ".join(f"{r_['name']}: {r_['result']}" for r_ in bk)[:300])
        row(ph, "Self-test", "Status with the rules in place", "PASS" if st2["level"] == "verified" else "UNVERIFIED",
            f"level={st2['level']}, counts={st2['last']['counts']}")
        status_rules(ph, st2)
    mon.wait_ticks(2)
    ol = [c for c in mon.window(t0 + 3, time.time(), "OLLAMA") if c["state"] in ("Established", "SynSent")]
    row(ph, "Process network monitor", "No outside connection from Ollama while restricted", "PASS" if not ol else "FAIL",
        ", ".join(sorted({f"{c['name']}->{c['remote']} {c['state']}" for c in ol})) or f"0 seen in {mon.ticks} samples")
    kids = [e for e in BK.events_since(t0) if e["kind"] == "unrestricted child process"]
    row(ph, "Connection watcher", "Programs started by the local AI programs that are not restricted",
        "UNPROTECTED" if kids else "PASS", ", ".join(f"{e['name']} {e['exe']}" for e in kids) or "none seen")
    remove_rules(ph, before)


def remove_rules(ph, before):
    r = L.firewall_remove({})
    if r.get("error"):
        row(ph, "Rollback", "Rules removed (administrator prompt)", "FAIL", r.get("error"))
        return
    have = FW.state()["rules"]
    row(ph, "Rollback", "Rules removed, none of MTAI's left in Windows", "PASS" if r.get("gone") and not have else "FAIL",
        f"removed {len((r.get('result') or {}).get('removed') or [])}; still there: {[x['name'] for x in have] or 'none'}")
    if before is not None:
        after = _rule_count()
        row(ph, "Rollback", "Other firewall rules unchanged (count before = after)", "PASS" if before and after == before else "FAIL",
            f"before {before}, after {after}")
    body = _ollama_pull("mtai-selftest/does-not-exist:1").lower()
    back = any(w in body for w in ("file does not exist", "manifest unknown", "not found", "unauthorized", "pull access denied"))
    row(ph, "Rollback", "Ollama reaches the internet again (pull of a name that does not exist)", "PASS" if back else "UNVERIFIED", body[:160])


def phase_cut(mon):
    ph = "SWITCH"
    L.set_privacy(False)
    page_privacy(False)
    s = socket.create_connection(("example.com", 80), timeout=8)
    s.sendall(b"HEAD / HTTP/1.1\r\nHost: example.com\r\nConnection: keep-alive\r\n\r\n")
    s.recv(4096)
    js_async("""new Promise((res, rej) => { const w = new WebSocket('wss://echo.websocket.org/'); window.__cutWs = {open: 0, closed: 0};
        w.onopen = () => { __cutWs.open = 1; res(1); }; w.onclose = () => { __cutWs.closed = 1; }; w.onerror = () => rej(new Error('ws error'));
        setTimeout(() => rej(new Error('timeout')), 9000); })""", 15)
    ws_open = J("window.__cutWs && window.__cutWs.open")
    box = {}
    th = threading.Thread(target=lambda: box.update(r=L.run_code("python",
        "import socket,time\ns=socket.create_connection(('example.com',80),timeout=8)\nprint('connected',flush=True)\ntime.sleep(40)\nprint('still running')")), daemon=True)
    th.start()
    for _ in range(80):
        if L.RUNNING:
            break
        time.sleep(0.1)
    time.sleep(2)
    mon.wait_ticks(2)
    before_cut = [c for c in mon.lines if c["t"] > time.time() - 3 and c["who"] == "MTAI"]
    row(ph, "Setup", "Outside connections open before the switch (privacy off)",
        "PASS" if before_cut and ws_open else "UNVERIFIED",
        f"{len(before_cut)} seen by the monitor, browser WebSocket open={bool(ws_open)}, program running={bool(L.RUNNING)}")
    t_switch = time.time()
    cut = L.set_privacy(True)
    page_privacy(True)
    time.sleep(2.5)
    try:
        s.settimeout(3)
        s.sendall(b"HEAD / HTTP/1.1\r\nHost: example.com\r\n\r\n")
        d = s.recv(4096)
        row(ph, "Cut on switch", "Open Python socket", "PASS" if not d else "FAIL", "closed (EOF)" if not d else f"still answered {len(d)} bytes")
    except OSError as e:
        row(ph, "Cut on switch", "Open Python socket", "PASS", f"cut: {type(e).__name__}")
    finally:
        s.close()
    row(ph, "Cut on switch", "Open browser WebSocket", "PASS" if J("window.__cutWs.closed") else "FAIL",
        "closed by the gate" if J("window.__cutWs.closed") else "still open")
    th.join(10)
    r = box.get("r") or {}
    row(ph, "Cut on switch", "Program that was running with internet access", "PASS" if not th.is_alive() and "still running" not in (r.get("stdout") or "") else "FAIL",
        f"stopped, exit {r.get('code')}" if not th.is_alive() else "still running")
    mon.wait_ticks(3)
    after = [c for c in mon.lines if c["t"] > t_switch + 1.5 and c["who"] == "MTAI" and c["state"] == "Established"]
    row(ph, "Cut on switch", "Monitor: no established outside connection after the switch", "PASS" if not after else "FAIL",
        f"{cut} cut by MTAI; " + (", ".join(sorted({c['remote'] for c in after})) or "0 left"))


def phase_off():
    ph = "OFF"
    L.set_privacy(False)
    page_privacy(False)
    st = js_async("mtaiPrivacy.verify({quiet:true})", 120)
    if isinstance(st, Exception):
        row(ph, "Self-test", "Run from the page", "FAIL", st)
    else:
        graded(ph, st["last"])
    try:
        r = api("web/search", {"q": "example"}, timeout=40)
        row(ph, "Backend routes", "Web search (DuckDuckGo, query 'example')", "PASS" if r.get("results") else "UNVERIFIED",
            f"{len(r.get('results') or [])} results" + (f", error {r.get('error')}" if r.get("error") else ""))
    except Exception as e:
        row(ph, "Backend routes", "Web search", "FAIL", e)
    try:
        ev = api("ollama/pull", {"name": "mtai-selftest-does-not-exist"}, timeout=60)
        msg = json.dumps(ev)[:200]
        row(ph, "Backend routes", "Ollama pull reaches the registry (name that does not exist)",
            "FAIL" if "Privacy" in msg else "PASS", msg)
    except Exception as e:
        row(ph, "Backend routes", "Ollama pull", "UNVERIFIED", e)
    o, v = PC.attempt(lambda: len(L.IG._hf_files("stabilityai/sd-turbo")))
    row(ph, "Backend routes", "Hugging Face model file list", *PC.grade(False, o, v))


def main_thread():
    mon = None
    try:
        time.sleep(1)
        ready = False
        for _ in range(60):
            if J("typeof S !== 'undefined' && !!S.settings && !!window.mtaiPrivacy && document.getElementById('boot') == null"):
                ready = True
                break
            time.sleep(0.5)
        row("SETUP", "Browser", "MTAI's page loads in the window behind the gate", "PASS" if ready else "FAIL",
            J("location.href + ' ' + document.title"))
        if not ready:
            raise RuntimeError("the app page did not load")
        J("document.getElementById('welcome')&&document.getElementById('welcome').remove()")
        mon = Monitor()
        phase_on(mon)
        if FIREWALL:
            phase_firewall(mon)
        phase_cut(mon)
        phase_off()
    except Exception as e:
        import traceback
        traceback.print_exc()
        row("SUITE", "Suite", "Suite crashed", "FAIL", f"{type(e).__name__}: {e}")
    finally:
        if mon:
            mon.stop()
        if FIREWALL and FW.ledger()["rules"]:             # the suite stopped half way: never leave rules behind
            try:
                remove_rules("CLEANUP", None)
            except Exception as e:
                row("CLEANUP", "Rollback", "Rules removed after a crash", "FAIL", e)
        orig = bool(before.get("privacy"))
        L.set_privacy(orig)
        try:
            page_privacy(orig)
        except Exception:
            pass
        now = json.loads(L.SETTINGS_FILE.read_text("utf-8")) if L.SETTINGS_FILE.is_file() else {}
        if now.get("privacy") != before.get("privacy"):
            now["privacy"] = before.get("privacy", False)
            L.write_json(L.SETTINGS_FILE, now)
        report()
        win.destroy()


def report():
    OUT.mkdir(parents=True, exist_ok=True)
    counts = {k: sum(1 for r in ROWS if r["result"] == k) for k in RESULTS}
    phases = {}
    for r in ROWS:
        phases.setdefault(r["phase"], {k: 0 for k in RESULTS})[r["result"]] += 1
    t = time.time()
    data = {"t": t, "counts": counts, "phase_counts": phases, "rows": ROWS}
    L.write_json(OUT / "latest.json", data)
    md = [f"# MTAI privacy test suite, {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))}", "",
          " · ".join(f"{k} {counts[k]}" for k in RESULTS), ""]
    for ph in phases:
        md += [f"## {ph}  (" + ", ".join(f"{phases[ph][k]} {k.lower()}" for k in RESULTS) + ")", "",
               "| Result | Group | Test | Detail |", "|---|---|---|---|"]
        md += [f"| {r['result']} | {r['group']} | {r['name']} | {r['detail'].replace('|', '/').replace(chr(10), ' ')[:220]} |"
               for r in ROWS if r["phase"] == ph]
        md.append("")
    f = OUT / time.strftime("report-%Y%m%d-%H%M%S.md", time.localtime(t))
    f.write_text("\n".join(md), "utf-8")
    print("\nTOTAL", counts, "\nreport:", f, flush=True)


webview.start(main_thread)
