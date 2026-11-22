"""
MTAI - a desktop chat app for the AI models installed on this PC.

Finds models from:
  * Ollama (running server, or the model folder on disk when the server is off)
  * OpenAI-compatible local servers: LM Studio, llama.cpp, Jan, KoboldCpp,
    text-generation-webui, vLLM
  * .gguf files on disk (listed; they need a server before you can chat)
  * cloud APIs with your own keys: OpenAI, Anthropic, Gemini, xAI, DeepSeek,
    Mistral, Groq, OpenRouter, custom (providers.py; Claude needs: pip install anthropic)

Image generation (providers.py): Stable Diffusion WebUI / Forge and ComfyUI on this
PC, or OpenAI / Gemini / xAI with a key.

The window is an HTML UI (ui/ folder) shown with pywebview. The Python side is a
small local HTTP server that does discovery, streaming chat, model downloads and
chat history (data/ folder).

Run:   python local_ai_chat.py            (native window, needs: pip install pywebview)
       python local_ai_chat.py --browser  (opens in Edge app mode / default browser)
"""

import argparse
import ctypes
import difflib
import html as htmlmod
import html.parser
import ipaddress
import json
import mimetypes
import os
import socket
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import paths                         # where program files and user data live (source or MTAI.exe)
import netguard as NG                # privacy mode enforcement: audit hook, browser gate
import sandbox as SB                 # offline AppContainer for code runs in privacy mode
NG.install(component_name="MTAI")    # first, before anything can open a connection
import providers as P                # cloud APIs with your own keys + image generation
import imagegen as IG                # built-in image models (one-click downloads)
import privacy_check as PC           # privacy self-test and diagnostics
import backends as BK                # finds local AI programs (Ollama...) and watches network connections
import firewall as FW                # optional Windows Firewall rules for those programs (asks first, UAC)
import webview_runtime as WR         # optional private WebView2 copy, so MTAI's own browser can be firewalled

P.load_cache()

APP_DIR = paths.APP_DIR
UI_DIR = APP_DIR / "ui"
DATA_DIR = paths.DATA_DIR
CHATS_DIR = DATA_DIR / "chats"
SETTINGS_FILE = DATA_DIR / "settings.json"
FOLDERS_FILE = DATA_DIR / "folders.json"
OLD_FOLDERS_FILE = APP_DIR / "extra_model_folders.json"

TOKEN = secrets.token_urlsafe(24)   # every /api call must send this (blocks other web pages)

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
OLLAMA_URL = OLLAMA_URL.replace("0.0.0.0", "127.0.0.1").replace("//localhost", "//127.0.0.1").rstrip("/")

OPENAI_SERVERS = [
    ("LM Studio", "http://127.0.0.1:1234"),
    ("llama.cpp", "http://127.0.0.1:8080"),
    ("Jan", "http://127.0.0.1:1337"),
    ("KoboldCpp", "http://127.0.0.1:5001"),
    ("text-gen-webui", "http://127.0.0.1:5000"),
    ("vLLM", "http://127.0.0.1:8000"),
]

HOME = Path.home()
DEFAULT_GGUF_FOLDERS = [
    HOME / ".lmstudio" / "models",
    HOME / ".cache" / "lm-studio" / "models",
    HOME / "AppData" / "Roaming" / "Jan" / "data" / "models",
    HOME / "jan" / "models",
]

DEFAULT_SETTINGS = {
    "system": "You are a helpful assistant.",
    "temperature": 0.7,
    "top_p": 0.9,
    "num_ctx": 8192,
    "think": True,
    "keep_alive": "10m",
    "model": None,
    "sidebar": True,
    "theme": None,
    "run_ok": False,
    "web": "off",             # off | search: look things up on the web before answering
    "web_ok": False,          # the user saw the note that web search sends queries to DuckDuckGo
    "privacy": False,         # privacy mode: MTAI itself makes no connection outside this PC
    "style": {},              # how the AI talks to you (persona, tone, length, language, name...)
    "plan": False,            # planning mode: the AI writes a plan you can edit before it answers
    "image": {},              # image generation: model, aspect, steps, negative prompt
    "fun": {},                # games and toys: confetti, sounds, high scores
    "onboarded": False,       # False until the welcome (tour + preferences) was finished or skipped once
    "firewall": {},           # {"programs": [paths the user picked], "auto": add/remove with privacy mode,
                              #  "private_browser": run MTAI's window from its own WebView2 copy}
}

# ------------------------------------------------------------ privacy mode --
# When on, every feature that could reach the internet is refused here in the
# backend (friendly messages), and netguard enforces it underneath: the audit hook
# blocks any non-loopback socket, DNS lookup or new process in this Python process,
# the gate proxy blocks the WebView2 browser, and code runs go to an offline
# AppContainer sandbox (sandbox.py). See privacy_check.py for the self-test.

PRIVACY = {"on": False}
PRIVACY_MSG = "Privacy mode is on. MTAI does not connect to the internet."
# 'self' is the preview server's own origin on 127.0.0.1, so pages keep their local files and scripts
PRIVACY_CSP = ("default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
               "connect-src 'self'; form-action 'self'; frame-src 'self' data: blob:; "
               "base-uri 'self'; worker-src 'self' blob:")
BROWSER = {"mode": None, "gate": None}   # how the window was opened: webview2 / edge (behind the gate) or system
RUNNING = set()                          # code runs outside the sandbox, killed when privacy mode turns on
PULLS = set()                            # open Ollama pull streams, closed when privacy mode turns on
SANDBOX_STATE = None                     # set after DATA_DIR: folders the sandbox may use
SERVER_PORT = None                       # MTAI's own port on 127.0.0.1 (the firewall tests check it stays reachable)


def set_privacy(on):
    """Switch privacy mode everywhere at once and stop what is already online."""
    on = bool(on)
    was = PRIVACY["on"]
    PRIVACY["on"] = on
    cut = NG.set_on(on)
    if on and not was:
        for p in list(RUNNING):                  # code that started with internet access
            try:
                p.kill()
                cut += 1
            except Exception:
                pass
        for r in list(PULLS):                    # Ollama stops a pull when its client goes away
            try:
                r.close()
                cut += 1
            except Exception:
                pass
        for mid, j in list(IG.JOBS.items()):     # image model downloads from Hugging Face
            if not j.get("finished"):
                j["cancel"] = True
                cut += 1
    NG.STATE["cut"] = cut
    if on != was or on != BK.WATCH["on"]:
        BK.watch(on, FW.restricted_programs)    # connection watcher: catches what the audit hook cannot see
    if on and not was:
        NG.STATE["recheck"] = None
        threading.Thread(target=_recheck_connections, daemon=True, name="privacy-recheck").start()
    return cut


def _recheck_connections():
    """Right after privacy mode went on (and the cut): which outside connections are still open?"""
    time.sleep(0.6)
    try:
        NG.STATE["recheck"] = BK.scan(FW.restricted_programs())
    except Exception as e:
        NG.STATE["recheck"] = {"error": f"{type(e).__name__}: {e}", "conns": []}


# ------------------------------------------- local AI programs + Windows Firewall --

def firewall_info():
    """What the Local AI programs section of Privacy diagnostics shows. Reads only; changes nothing."""
    if FW.ledger().get("pending"):
        FW._reconcile()                      # MTAI stopped while Windows was being asked: see what is really there
    found = PC.discover_cached(0)
    st = FW.status()
    good = {str(e["program"]).lower() for e in st["ledger"] if e["ok"]}
    for b in found:
        for e in b["exes"]:
            e["rule"] = FW.rule_name(e["path"])
            e["restricted"] = e["path"].lower() in good
    since = NG.STATE.get("changed") or 0
    return {"backends": found, "status": st, "privacy": PRIVACY["on"],
            "leftover": (not PRIVACY["on"]) and bool(st["ledger"] or st["unknown_group_rules"]),
            "events": BK.events_since(since)[-100:] if PRIVACY["on"] else [],
            "watch": {k: BK.WATCH[k] for k in ("on", "since", "samples", "error")},
            "settings": read_json(SETTINGS_FILE, {}).get("firewall") or {},
            "group": FW.GROUP, "remote": FW.REMOTE, "probe": {"path": str(FW.probe_path()), "rule": FW.rule_name(FW.probe_path())},
            "runtime": {**WR.status(), "in_use": WR.in_use_by(os.getpid()), "browser": BROWSER.get("mode"),
                        "enabled": bool((read_json(SETTINGS_FILE, {}).get("firewall") or {}).get("private_browser"))}}


def browser_runtime(body):
    """Turn MTAI's private WebView2 copy on or off (it is used from the next start)."""
    s = {**DEFAULT_SETTINGS, **read_json(SETTINGS_FILE, {})}
    fw = dict(s.get("firewall") or {})
    fw["private_browser"] = bool(body.get("enable"))
    s["firewall"] = fw
    write_json(SETTINGS_FILE, s)
    out = {"ok": True}
    if fw["private_browser"]:
        st = WR.status()
        if not st["current"] or st["outdated"]:
            try:
                WR.make_copy()
            except Exception as e:
                out = {"error": str(e)}
    elif not WR.in_use_by(os.getpid()):
        out["errors"] = WR.remove_copy()
    PC._DISC["v"] = None
    return {**out, "runtime": {**WR.status(), "in_use": WR.in_use_by(os.getpid()), "enabled": fw["private_browser"]}}


def firewall_apply(body):
    """Make the rules for programs the user ticked. Only paths that discovery really found are accepted."""
    if body.get("confirm") is not True:
        return {"error": "Not confirmed."}
    allowed = {e["path"].lower(): e["path"] for b in PC.discover_cached(120) for e in b["exes"] if e["selectable"]}
    progs, refused = [], []
    for x in body.get("programs") or []:
        (progs if str(x).lower() in allowed else refused).append(allowed.get(str(x).lower(), str(x)))
    if refused:
        return {"error": "MTAI did not find these programs itself, so it does not restrict them: " + ", ".join(refused)}
    if not progs:
        return {"error": "No program selected."}
    s = {**DEFAULT_SETTINGS, **read_json(SETTINGS_FILE, {})}
    s["firewall"] = {**(s.get("firewall") or {}), "programs": progs, "auto": bool(body.get("auto"))}
    write_json(SETTINGS_FILE, s)
    try:
        out = FW.apply(progs, with_probe=True, close=True)
    except FW.Declined as e:
        return {"declined": True, "error": str(e), "status": FW.status()}
    except Exception as e:
        return {"error": str(e), "status": FW.status()}
    return {"ok": bool(out.get("ok")), "result": out, "status": FW.status()}


def firewall_remove(body):
    """Delete MTAI's rules (all of them, or the names given). Rules of other programs are never touched."""
    if not FW.ledger()["rules"] and not body.get("adopt"):
        return {"ok": True, "result": {"removed": []}, "gone": True}     # nothing of MTAI's there: no prompt
    st = FW.status()
    if body.get("adopt") and st["unknown_group_rules"]:
        # rules in MTAI's own group with MTAI's name pattern whose ledger entry was lost (deleted data folder)
        led = FW.ledger()
        have = {r["name"]: r for r in FW.state()["rules"]}
        for n in st["unknown_group_rules"]:
            if re.fullmatch(r"MTAI-Privacy-[0-9a-f]{12,32}", n) and n in have:
                led["rules"].append({"name": n, "program": have[n].get("program"), "made": None, "state": "found"})
        FW._save(led)
    try:
        out = FW.remove(body.get("names") or None)
    except FW.Declined as e:
        return {"declined": True, "error": str(e), "status": FW.status()}
    except Exception as e:
        return {"error": str(e), "status": FW.status()}
    st = FW.status()
    return {"ok": bool(out.get("ok", True)), "result": out, "status": st,
            "gone": not st["ledger"] and not st["unknown_group_rules"]}


def firewall_test():
    """Real attempts from the restricted programs (the probe copy of curl, and Ollama itself)."""
    port = SERVER_PORT or int(urlparse(OLLAMA_URL).port or 11434)
    rows = FW.test_rule_template(port)
    for b in PC.discover_cached(60):
        if b["id"] == "ollama" and b["running"]:
            exe = next((e["path"] for e in b["exes"] if e["name"].lower() == "ollama.exe"), None)
            rows += FW.test_ollama(OLLAMA_URL, exe)
    return {"rows": [dict(zip(("group", "id", "name", "result", "detail"), r)) for r in rows]}


def _safe_browser_open(url, *a, **k):
    """webbrowser.open for pywebview's new-window links and MTAI's own links: refused in privacy mode,
    because the system browser is outside MTAI's network block."""
    if PRIVACY["on"]:
        NG.note("open", url, component="Link", detail="system browser")
        return False
    with NG.allow("open a link in the system browser"):
        return _real_browser_open(url, *a, **k)


_real_browser_open = webbrowser.open
webbrowser.open = _safe_browser_open


def is_loopback_url(url):
    return NG.is_loopback_url(url)

POOL = ThreadPoolExecutor(max_workers=12)
MODELS = {}                 # id -> model dict, from the last discovery
MODELS_LOCK = threading.Lock()


# ------------------------------------------------------------------ helpers --

def read_json(path, default):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except Exception:
        return default


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)


def http_json(url, data=None, method=None, timeout=2.0):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8", "replace")) if raw.strip() else {}


def http_error_text(e):
    try:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body).get("error", body)
            if isinstance(body, dict):
                body = body.get("message", str(body))
        except Exception:
            pass
    except Exception:
        body = ""
    return f"HTTP {e.code}: {str(body)[:400] or e.reason}"


def ollama_exe():
    found = shutil.which("ollama")
    if found:
        return found
    local = HOME / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"
    return str(local) if local.exists() else None


def ollama_models_dir():
    env = os.environ.get("OLLAMA_MODELS")
    if not env and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                env = winreg.QueryValueEx(k, "OLLAMA_MODELS")[0]
        except OSError:
            env = None
    return Path(env) if env else HOME / ".ollama" / "models"


def custom_folders():
    folders = read_json(FOLDERS_FILE, None)
    if folders is None:                       # carry over the folders of version 1
        folders = read_json(OLD_FOLDERS_FILE, [])
        if folders:
            write_json(FOLDERS_FILE, folders)
    return [f for f in folders if isinstance(f, str)]


# ---------------------------------------------------------------- discovery --

_show_cache = {}


def ollama_show(name, digest):
    key = (name, digest)
    if key in _show_cache:
        return _show_cache[key]
    try:
        d = http_json(OLLAMA_URL + "/api/show", {"model": name}, timeout=5)
    except Exception:
        return {"caps": [], "ctx": None}
    info = d.get("model_info") or {}
    ctx = next((v for k, v in info.items() if k.endswith(".context_length")), None)
    caps = d.get("capabilities") or []
    if not caps:                               # older Ollama: guess
        caps = ["completion"] + (["vision"] if d.get("projector_info") else [])
    res = {"caps": caps, "ctx": ctx}
    _show_cache[key] = res
    return res


def discover_ollama():
    status = {"installed": bool(ollama_exe()), "running": False, "version": None,
              "dir": str(ollama_models_dir()), "url": OLLAMA_URL}
    models = []
    try:
        status["version"] = http_json(OLLAMA_URL + "/api/version", timeout=1).get("version")
        status["running"] = True
        status["installed"] = True
    except Exception:
        pass

    if status["running"]:
        try:
            tags = http_json(OLLAMA_URL + "/api/tags", timeout=4).get("models", [])
        except Exception:
            tags = []
        try:
            ps = {m["name"]: m for m in http_json(OLLAMA_URL + "/api/ps", timeout=2).get("models", [])}
        except Exception:
            ps = {}
        shows = list(POOL.map(lambda m: ollama_show(m["name"], m.get("digest")), tags))
        for m, sh in zip(tags, shows):
            d = m.get("details") or {}
            caps = sh.get("caps", [])
            chat_ok = "completion" in caps or "vision" in caps or not caps
            loaded = ps.get(m["name"])
            # Ollama "cloud" models run on ollama.com: the local server forwards the chat there
            remote = bool(m.get("remote_host") or m.get("remote_model")) or bool(re.search(r"[-:]cloud\b", m["name"]))
            models.append({
                "id": "ollama|" + m["name"], "name": m["name"], "backend": "ollama",
                "source": "Ollama", "url": OLLAMA_URL, "size": m.get("size", 0),
                "params": d.get("parameter_size"), "quant": d.get("quantization_level"),
                "family": d.get("family"), "modified": m.get("modified_at"),
                "caps": caps, "ctx": sh.get("ctx"),
                "chattable": chat_ok and not (remote and PRIVACY["on"]),
                "reason": ("Privacy mode is on: this Ollama model runs on ollama.com" if chat_ok and remote and PRIVACY["on"]
                           else None if chat_ok else "Embedding model, it cannot chat"),
                "remote": remote, "loaded": bool(loaded), "vram": (loaded or {}).get("size_vram"),
            })
        return status, models

    root = ollama_models_dir() / "manifests"
    if root.is_dir():
        status["installed"] = True
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            parts = f.relative_to(root).parts
            if len(parts) < 3:
                continue
            ns, model, tag = parts[-3], parts[-2], parts[-1]
            name = f"{model}:{tag}" if ns == "library" else f"{ns}/{model}:{tag}"
            man = read_json(f, {})
            size = sum(l.get("size", 0) for l in man.get("layers", []) if isinstance(l, dict))
            models.append({
                "id": "ollama|" + name, "name": name, "backend": "ollama", "source": "Ollama",
                "url": OLLAMA_URL, "size": size, "params": None, "quant": None, "family": None,
                "caps": [], "ctx": None, "chattable": False,
                "reason": "Ollama is not running", "loaded": False,
            })
    return status, models


def probe_server(label, url):
    status = {"name": label, "url": url, "online": False, "count": 0}
    models = []
    try:
        data = http_json(url + "/v1/models", timeout=0.8)
    except Exception:
        return status, models
    status["online"] = True
    extra = {}
    if label == "LM Studio":                     # richer info from LM Studio's own API
        try:
            for m in http_json(url + "/api/v0/models", timeout=1).get("data", []):
                extra[m.get("id")] = m
        except Exception:
            pass
    for m in data.get("data", []):
        mid = m.get("id") or m.get("name")
        if not mid:
            continue
        x = extra.get(mid, {})
        mtype = x.get("type", "llm")
        caps = ["completion"]
        if mtype == "vlm":
            caps.append("vision")
        if mtype == "embeddings" or "embed" in mid.lower():
            caps = ["embedding"]
        chat_ok = "embedding" not in caps
        models.append({
            "id": f"openai|{url}|{mid}", "name": mid, "backend": "openai",
            "source": label, "url": url, "size": 0, "params": None,
            "quant": x.get("quantization"), "family": x.get("arch"), "caps": caps,
            "ctx": x.get("max_context_length"), "chattable": chat_ok,
            "reason": None if chat_ok else "Embedding model, it cannot chat",
            "loaded": x.get("state") == "loaded",
        })
    status["count"] = len(models)
    return status, models


QUANT_RE = re.compile(r"(IQ\d_[A-Z0-9_]+|Q\d_K(?:_[SML])?|Q\d_\d|Q\d|F16|BF16|F32)", re.I)


def discover_files():
    folders = [(str(p), True) for p in DEFAULT_GGUF_FOLDERS] + [(p, False) for p in custom_folders()]
    out, seen, info = [], set(), []
    for folder, default in folders:
        p = Path(folder)
        exists = p.is_dir()
        count = 0
        if exists:
            try:
                for f in p.rglob("*.gguf"):
                    if f in seen or "mmproj" in f.name.lower():
                        continue
                    seen.add(f)
                    count += 1
                    try:
                        size = f.stat().st_size
                    except OSError:
                        size = 0
                    q = QUANT_RE.search(f.stem)
                    out.append({
                        "id": "file|" + str(f), "name": f.stem, "backend": "file",
                        "source": "GGUF files", "size": size, "path": str(f),
                        "quant": q.group(1).upper() if q else None, "params": None,
                        "caps": [], "chattable": False, "loaded": False,
                        "reason": "File only. Load it in LM Studio or llama.cpp to chat.",
                    })
            except OSError:
                pass
        info.append({"path": folder, "default": default, "exists": exists, "count": count})
    return info, out


def discover():
    fut_ollama = POOL.submit(discover_ollama)
    fut_servers = [POOL.submit(probe_server, *s) for s in OPENAI_SERVERS]
    fut_files = POOL.submit(discover_files)
    ollama, models = fut_ollama.result()
    servers = []
    for f in fut_servers:
        st, ms = f.result()
        servers.append(st)
        models += ms
    folders, files = fut_files.result()
    models += files
    models += P.cloud_models(PRIVACY["on"])        # cached lists, refreshed in the background
    if not PRIVACY["on"]:
        P.refresh_stale()
    with MODELS_LOCK:
        MODELS.clear()
        MODELS.update({m["id"]: m for m in models})
    return {"ollama": ollama, "servers": servers, "folders": folders, "models": models}


def find_model(model_id):
    with MODELS_LOCK:
        m = MODELS.get(model_id)
    if m is None:
        discover()
        with MODELS_LOCK:
            m = MODELS.get(model_id)
    return m


# --------------------------------------------------------------------- chat --

def strip_data_url(u):
    return u.split(",", 1)[1] if u.startswith("data:") else u


def chat_ollama(model, req, emit):
    msgs = []
    if req.get("system"):
        msgs.append({"role": "system", "content": req["system"]})
    for m in req.get("messages", []):
        o = {"role": m["role"], "content": m.get("content", "")}
        imgs = [strip_data_url(u) for u in m.get("images") or []]
        if imgs:
            o["images"] = imgs
        msgs.append(o)
    opts = req.get("options") or {}
    payload = {"model": model["name"], "messages": msgs, "stream": True,
               "options": {k: v for k, v in opts.items() if v is not None}}
    if "thinking" in (model.get("caps") or []) and req.get("think") is not None:
        payload["think"] = bool(req["think"])
    if isinstance(req.get("format"), dict):           # structured output (JSON schema)
        payload["format"] = req["format"]
    ka = req.get("keep_alive")
    if ka not in (None, ""):
        payload["keep_alive"] = int(ka) if str(ka).lstrip("-").isdigit() else ka

    t0 = time.time()
    first = None
    r = urllib.request.urlopen(urllib.request.Request(
        OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}), timeout=900)
    with r:
        for line in r:
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj.get("error"):
                emit({"type": "error", "message": obj["error"]})
                return
            msg = obj.get("message") or {}
            thought, piece = msg.get("thinking") or "", msg.get("content") or ""
            if (thought or piece) and first is None:
                first = time.time() - t0
            if thought:
                emit({"type": "thinking", "text": thought})
            if piece:
                emit({"type": "content", "text": piece})
            if obj.get("done"):
                n = obj.get("eval_count") or 0
                dur = (obj.get("eval_duration") or 0) / 1e9
                emit({"type": "done", "stats": {
                    "tokens": n, "tps": (n / dur) if dur else None,
                    "prompt_tokens": obj.get("prompt_eval_count"),
                    "load": (obj.get("load_duration") or 0) / 1e9,
                    "total": time.time() - t0, "ttft": first}})
                return
    emit({"type": "done", "stats": {"total": time.time() - t0, "ttft": first}})


def chat_openai(model, req, emit, cloud=None):
    """OpenAI-style streaming chat. `cloud` (from providers.openai_request) points it at a
    cloud API with a key; without it, it talks to a local server."""
    msgs = []
    if req.get("system"):
        msgs.append({"role": "system", "content": req["system"]})
    for m in req.get("messages", []):
        imgs = m.get("images") or []
        if imgs:
            content = [{"type": "text", "text": m.get("content", "")}] + [
                {"type": "image_url", "image_url": {"url": u}} for u in imgs]
        else:
            content = m.get("content", "")
        msgs.append({"role": m["role"], "content": content})
    opts = req.get("options") or {}
    cloud = cloud or {}
    payload = {"model": model.get("api_id") or model["name"], "messages": msgs, "stream": True,
               "stream_options": {"include_usage": True}}
    if not cloud.get("no_sampling"):
        payload.update({"temperature": opts.get("temperature"), "top_p": opts.get("top_p")})
    if opts.get("num_predict"):
        payload[cloud.get("max_key", "max_tokens")] = int(opts["num_predict"])
    if isinstance(req.get("format"), dict):
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": req["format"]}}
    if cloud.get("effort_param") and req.get("think") is False and "thinking" in (model.get("caps") or []):
        payload["reasoning_effort"] = "low"
    payload = {k: v for k, v in payload.items() if v is not None}
    endpoint = cloud.get("endpoint") or model["url"] + "/v1/chat/completions"
    headers = {"Content-Type": "application/json", **(cloud.get("headers") or {})}

    def open_stream(p):
        return urllib.request.urlopen(urllib.request.Request(
            endpoint, data=json.dumps(p).encode(), headers=headers), timeout=900)

    # Servers and APIs differ in what they accept: on a 400/422 retry with fewer extras
    def lighter(p, level):
        p = dict(p)
        for k in ("stream_options", "response_format", "reasoning_effort"):
            p.pop(k, None)
        if level >= 2:
            p.pop("temperature", None)
            p.pop("top_p", None)
            if "max_tokens" in p:
                p["max_completion_tokens"] = p.pop("max_tokens")
        return p

    r = None
    for level in range(3):
        try:
            r = open_stream(payload if level == 0 else lighter(payload, level))
            break
        except urllib.error.HTTPError as e:
            if e.code not in (400, 422) or level == 2:
                if cloud:
                    raise P.ProviderError(P.error_text(e, cloud.get("who", "The API")))
                raise

    t0 = time.time()
    first = None
    chunks = 0
    usage = None
    with r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            if obj.get("error"):
                err = obj["error"]
                emit({"type": "error", "message": err.get("message") if isinstance(err, dict) else str(err)})
                return
            usage = obj.get("usage") or usage
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            thought = delta.get("reasoning_content") or delta.get("reasoning") or ""
            piece = delta.get("content") or ""
            if (thought or piece) and first is None:
                first = time.time() - t0
            if thought:
                emit({"type": "thinking", "text": thought})
            if piece:
                chunks += 1
                emit({"type": "content", "text": piece})
    total = time.time() - t0
    n = (usage or {}).get("completion_tokens") or chunks
    gen = total - (first or 0)
    emit({"type": "done", "stats": {
        "tokens": n, "tps": (n / gen) if gen > 0 else None,
        "prompt_tokens": (usage or {}).get("prompt_tokens"),
        "total": total, "ttft": first, "estimated": usage is None}})


def run_chat(req, emit):
    model = find_model(req.get("model_id", ""))
    if not model:
        emit({"type": "error", "message": "That model is gone. Refresh the model list."})
        return
    if not model.get("chattable"):
        emit({"type": "error", "message": model.get("reason") or "This model cannot chat right now."})
        return
    if PRIVACY["on"] and model["backend"] == "cloud":
        emit({"type": "error", "message": "Privacy mode is on: cloud models are off, so MTAI does not send them your chat."})
        return
    if PRIVACY["on"] and model.get("remote"):
        emit({"type": "error", "message": "Privacy mode is on: this Ollama model runs on ollama.com, so MTAI does not send it your chat."})
        return
    if PRIVACY["on"] and not is_loopback_url(OLLAMA_URL if model["backend"] == "ollama" else model.get("url", "")):
        emit({"type": "error", "message": "Privacy mode is on: this model runs on another machine, so MTAI does not send it your chat."})
        return
    if model["backend"] in ("ollama", "openai") and IG.W.proc and not IG.busy() and not req.get("keep_image"):
        IG.stop_worker()                       # give the GPU back to the chat model (not for a short image-prompt rewrite)
    try:
        if model["backend"] == "ollama":
            chat_ollama(model, req, emit)
        elif model["backend"] == "cloud" and P.PROV.get(model.get("provider"), {}).get("kind") == "anthropic":
            P.chat_anthropic(model, req, emit)
        elif model["backend"] == "cloud":
            chat_openai(model, req, emit, P.openai_request(model))
        else:
            chat_openai(model, req, emit)
    except P.ProviderError as e:
        emit({"type": "error", "message": str(e)})
    except urllib.error.HTTPError as e:
        emit({"type": "error", "message": http_error_text(e)})
    except urllib.error.URLError as e:
        emit({"type": "error", "message": f"Cannot reach {model.get('source')}: {e.reason}"})


def free_gpu_for_images():
    """Unload Ollama models so an image model fits in GPU memory. True when something was unloaded."""
    try:
        loaded = [m["name"] for m in http_json(OLLAMA_URL + "/api/ps", timeout=2).get("models", [])]
    except Exception:
        return False
    for name in loaded:
        try:
            http_json(OLLAMA_URL + "/api/generate", {"model": name, "keep_alive": 0}, timeout=30)
        except Exception:
            pass
    return bool(loaded)


# ------------------------------------------------------------ ollama admin --

def start_ollama():
    try:
        http_json(OLLAMA_URL + "/api/version", timeout=0.5)
        return {"ok": True, "already": True}
    except Exception:
        pass
    exe = ollama_exe()
    if not exe:
        return {"error": "Ollama is not installed. Get it from ollama.com."}
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    env = dict(os.environ)
    if "OLLAMA_MODELS" not in env and ollama_models_dir() != HOME / ".ollama" / "models":
        env["OLLAMA_MODELS"] = str(ollama_models_dir())
    with NG.allow("start the local Ollama server"):
        subprocess.Popen([exe, "serve"], creationflags=flags, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(0.4)
        try:
            http_json(OLLAMA_URL + "/api/version", timeout=0.5)
            return {"ok": True}
        except Exception:
            pass
    return {"error": "Ollama did not start within 16 seconds."}


def pull_model(name, emit):
    if PRIVACY["on"]:
        raise ValueError(PRIVACY_MSG)
    r = urllib.request.urlopen(urllib.request.Request(
        OLLAMA_URL + "/api/pull", data=json.dumps({"model": name, "stream": True}).encode(),
        headers={"Content-Type": "application/json"}), timeout=3600)
    PULLS.add(r)
    try:
        with r:
            for line in r:
                if PRIVACY["on"]:
                    raise ValueError(PRIVACY_MSG)
                if line.strip():
                    emit(json.loads(line))
    finally:
        PULLS.discard(r)


# ------------------------------------------------------------ run + preview --

RUNS_DIR = DATA_DIR / "runs"
SANDBOX_STATE = DATA_DIR / "sandbox.json"
FW.init(DATA_DIR, APP_DIR)
WR.init(DATA_DIR)
RUN_TIMEOUT = 60
LANG_ALIASES = {"python": "python", "py": "python", "python3": "python",
                "javascript": "javascript", "js": "javascript", "node": "javascript", "mjs": "javascript",
                "powershell": "powershell", "ps1": "powershell", "pwsh": "powershell"}
_env_cache = {}


def python_exe():
    return paths.python_exe() or "python"   # MTAI.exe without an installed Python: tool_env says no Python


def tool_env():
    """Which languages the Run button can use (looked up once)."""
    if not _env_cache:
        node = shutil.which("node")
        node_ver = None
        if node:
            try:
                with NG.allow("read the Node.js version"):
                    node_ver = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5,
                                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
            except Exception:
                node = None
        ps = shutil.which("powershell") or shutil.which("pwsh")
        _env_cache.update({"python": paths.python_version(), "javascript": node_ver if node else None,
                           "powershell": bool(ps), "_node": node, "_ps": ps})
    return {k: v for k, v in _env_cache.items() if not k.startswith("_")}


def run_code(lang, code):
    lang = LANG_ALIASES.get(str(lang).lower())
    env = tool_env()
    if not lang or not env.get(lang):
        return {"error": f"Cannot run {lang or 'this language'} on this PC."}
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    old = sorted(RUNS_DIR.glob("run-*"), key=lambda p: p.stat().st_mtime)
    for d in old[:-30]:                                  # keep the 30 newest run folders
        shutil.rmtree(d, ignore_errors=True)
    work = Path(tempfile.mkdtemp(prefix=time.strftime("run-%Y%m%d-%H%M%S-"), dir=RUNS_DIR))
    ext = {"python": ".py", "javascript": ".js", "powershell": ".ps1"}[lang]
    f = work / ("main" + ext)
    if lang == "powershell":   # PowerShell 5.1 reads BOM-less files as ANSI and prints in the OEM code page
        f.write_text("[Console]::OutputEncoding = [Text.Encoding]::UTF8\n" + code, "utf-8-sig")
    else:
        f.write_text(code, "utf-8")
    return run_process(run_cmd(lang, f), work)


def run_cmd(lang, f):
    return {"python": [python_exe(), "-u", str(f)],
            "javascript": [_env_cache.get("_node") or "node", str(f)],
            "powershell": [_env_cache.get("_ps") or "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(f)]}[lang]


def sandbox_ready(cmd, work):
    """Give the offline sandbox what this run needs: its folder (read/write) and, once, the
    Python folder (read only). Raises SB.SandboxError when the sandbox cannot run it."""
    exe = Path(cmd[0])
    if exe.stem.lower() == "node":
        raise SB.SandboxError("JavaScript files do not run in privacy mode: Node.js is installed in Program Files, "
                              "which Windows does not open to the offline sandbox. HTML pages still preview.")
    if exe.parent in (Path(sys.executable).parent, Path(python_exe()).parent):
        SB.grant(exe.parent, "(OI)(CI)(RX)", SANDBOX_STATE)        # read only, kept (Python must load)
    _sandbox_cleanup_once()
    SB.grant(work, "(OI)(CI)(M)")                                    # this run's folder only, revoked after the run
    if exe.stem.lower() in ("powershell", "pwsh") and "-File" in cmd:
        # PowerShell cannot set up its drives in the sandbox and starts in C:\ there, so move it to the run folder first
        # (Set-Location to the real path is refused: the sandbox may not list the folders above it; a drive works)
        f = Path(cmd[cmd.index("-File") + 1])
        q = lambda x: "'" + str(x).replace("'", "''") + "'"
        rel = f.relative_to(work) if work in f.parents else f
        cmd = [*cmd[:cmd.index("-File")], "-Command",
               f"$null = New-PSDrive -Name RUN -PSProvider FileSystem -Root {q(work)} -Scope Global; Set-Location RUN:; "
               f"& {q('RUN:' + chr(92) + str(rel)) if work in f.parents else q(f)}; exit $LASTEXITCODE"]
    return cmd


_SB_CLEAN = {"done": False}


def _sandbox_cleanup_once():
    """Older MTAI versions left the sandbox's write access on every run and workspace folder, so one run
    could read another. Take those grants back once (everything except the Python folder)."""
    if _SB_CLEAN["done"]:
        return
    _SB_CLEAN["done"] = True
    st = read_json(SANDBOX_STATE, {})
    for path, (sid, rights) in list(st.items()):
        if "(M)" in rights and Path(path).exists():
            SB.revoke(path, SANDBOX_STATE)
        elif "(M)" in rights:
            st.pop(path, None)
            write_json(SANDBOX_STATE, st)


def run_process(cmd, work):
    dec = lambda b: b.decode("utf-8", "replace")[-200_000:]
    t0 = time.time()
    if PRIVACY["on"]:
        # Offline sandbox: Windows refuses every connection of this program and of what it starts.
        try:
            cmd = sandbox_ready(cmd, work)
            try:
                out, err, rc, timed_out = SB.run(cmd, work, SB.base_env(work), RUN_TIMEOUT)
            finally:
                SB.revoke(work)                    # the next run (or another chat) cannot read this folder
            # PowerShell's own start-up note about drives it may not list in the sandbox, not from the code
            err = b"".join(ln for ln in err.splitlines(True) if b"InitializeDefaultDrives" not in ln)
        except (SB.SandboxError, OSError) as e:
            NG.note("process", " ".join(map(str, cmd))[:200], component="Code run", detail="no sandbox: not run")
            return {"error": f"Privacy mode: {e}", "privacy": True}
        return {"stdout": dec(out), "stderr": dec(err), "code": rc, "timed_out": timed_out, "sandboxed": True,
                "seconds": time.time() - t0, "cwd": str(work), "timeout": RUN_TIMEOUT}
    penv = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    timed_out = False
    p = subprocess.Popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                         env=penv, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    RUNNING.add(p)
    try:
        out, err = p.communicate(timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        timed_out = True
    finally:
        RUNNING.discard(p)
    rc = None if timed_out else p.returncode
    return {"stdout": dec(out), "stderr": dec(err), "code": rc, "timed_out": timed_out,
            "seconds": time.time() - t0, "cwd": str(work), "timeout": RUN_TIMEOUT}


PREVIEWS = {}                 # id -> (html, csp header or None), served by the preview server on its own port
PREVIEW_BASE = None

# Same console hook as PV_HOOK in app.js, for workspace pages served from disk.
WS_HOOK_JS = (
    "(()=>{const s=(t,a)=>{try{parent.postMessage({__mtai:1,type:t,args:a.map(x=>{if(x instanceof Error)return x.stack||String(x);"
    "try{return typeof x==='object'?JSON.stringify(x,null,1):String(x)}catch(e){return String(x)}})},'*')}catch(e){}};"
    "['log','info','warn','error','debug'].forEach(k=>{const o=console[k];console[k]=(...a)=>{s(k,a);o.apply(console,a)}});"
    "addEventListener('error',e=>s('error',[e.message+(e.lineno?' (line '+e.lineno+')':'')]));"
    "addEventListener('unhandledrejection',e=>s('error',['Unhandled promise rejection: '+((e.reason&&e.reason.message)||e.reason)]));})();")


class PreviewHandler(BaseHTTPRequestHandler):
    """Serves generated pages on a different port, so they cannot touch the app or its token."""

    def log_message(self, *a):
        pass

    def _out(self, code, body, ctype="text/html; charset=utf-8", csp=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if csp:
            self.send_header("Content-Security-Policy", csp)
        if PRIVACY["on"]:      # a second CSP header: the browser enforces both, so this only takes away
            self.send_header("Content-Security-Policy", PRIVACY_CSP)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/__mtai_hook.js":
            return self._out(200, WS_HOOK_JS.encode(), "application/javascript; charset=utf-8")
        if path.startswith("/w/"):                   # workspace files, so relative links between them work
            parts = path[3:].split("/", 1)
            ws, rel = parts[0], (parts[1] if len(parts) > 1 else "")
            try:
                root, f, rel = ws_path(ws, rel or "index.html")
                if f.is_dir():
                    f = f / "index.html"
            except ValueError:
                return self._out(404, b"bad path", "text/plain")
            if not f.is_file():
                return self._out(404, f"<h3 style='font-family:sans-serif'>{htmlmod.escape(rel)} does not exist yet.</h3>".encode())
            body = f.read_bytes()
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if ctype in ("text/html", "application/xhtml+xml"):
                text = body.decode("utf-8", "replace")
                tag = '<script src="/__mtai_hook.js"></script>'
                m = re.search(r"<head[^>]*>", text, re.I)
                text = text[:m.end()] + tag + text[m.end():] if m else tag + text
                body = text.encode("utf-8")
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            return self._out(200, body, ctype)
        pid = path.rstrip("/").rsplit("/", 1)[-1]
        entry = PREVIEWS.get(pid)
        if entry is None:
            return self._out(404, b"<h3 style='font-family:sans-serif'>Preview expired. Press reload in MTAI.</h3>")
        html_text, csp = entry
        self._out(200, html_text.encode("utf-8"), csp=csp)


def store_preview(html_text, pid=None, csp=None):
    if not (pid and ID_RE.match(pid)):
        pid = secrets.token_urlsafe(8).replace("-", "a").replace("_", "b")
    PREVIEWS.pop(pid, None)
    PREVIEWS[pid] = (html_text, csp)
    while len(PREVIEWS) > 60:
        PREVIEWS.pop(next(iter(PREVIEWS)))
    return {"id": pid, "url": f"{PREVIEW_BASE}/p/{pid}"}


# ---------------------------------------------------------------------- web --
# Search goes to DuckDuckGo (no account, no cookies sent). Pages are fetched by this
# process, scripts are removed, and the copy is shown from the preview server.

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def public_url(url):
    """Allow only http(s) links to public hosts: never this PC or the local network."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("Only http and https links can be opened.")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError(f"Cannot find {u.hostname}.")
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
            raise ValueError("Pages on this PC or the local network are not opened.")
    return url


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_WEB = urllib.request.build_opener(_SafeRedirect)


def web_get(url, data=None, timeout=12, limit=3_000_000):
    if PRIVACY["on"]:
        raise ValueError(PRIVACY_MSG)
    public_url(url)
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.7"})
    with _WEB.open(req, timeout=timeout) as r:
        raw = r.read(limit)
        ctype = r.headers.get("Content-Type", "")
        final = r.geturl()
    m = re.search(r"charset=([\w-]+)", ctype, re.I) or re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:6000], re.I)
    enc = (m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)) if m else "utf-8"
    try:
        text = raw.decode(enc, "replace")
    except LookupError:
        text = raw.decode("utf-8", "replace")
    return final, ctype.lower(), text


def clean_text(s):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def web_search(q, n=8):
    q = " ".join(str(q).split())[:300]
    if not q:
        return {"results": [], "engine": None}
    results, engine = [], "DuckDuckGo"
    try:
        _, _, page = web_get("https://lite.duckduckgo.com/lite/", data=urlencode({"q": q}).encode())
        links = list(re.finditer(r'<a[^>]+href="([^"]+)"[^>]*class=[\'"]result-link[\'"][^>]*>(.*?)</a>', page, re.S))
        for i, m in enumerate(links):
            href = htmlmod.unescape(m.group(1))
            if "uddg=" in href:
                href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
            if href.startswith("//"):
                href = "https:" + href
            host = urlparse(href).hostname or ""
            if not href.startswith("http") or host.endswith("duckduckgo.com"):
                continue                            # ads and internal links
            end = links[i + 1].start() if i + 1 < len(links) else len(page)
            sn = re.search(r'class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', page[m.end():end], re.S)
            results.append({"title": clean_text(m.group(2)), "url": href, "host": host.removeprefix("www."),
                            "snippet": clean_text(sn.group(1)) if sn else ""})
            if len(results) >= n:
                break
    except Exception:
        results = []
    if not results:                                # fallback: Wikipedia's own search
        engine = "Wikipedia"
        try:
            _, _, page = web_get("https://en.wikipedia.org/w/api.php?" + urlencode(
                {"action": "query", "list": "search", "srsearch": q, "format": "json", "srlimit": min(n, 6)}))
            for r in json.loads(page)["query"]["search"]:
                results.append({"title": r["title"], "url": "https://en.wikipedia.org/wiki/" + quote(r["title"].replace(" ", "_")),
                                "host": "en.wikipedia.org", "snippet": clean_text(r.get("snippet", ""))})
        except Exception as e:
            return {"results": [], "engine": None, "error": f"Web search failed: {e}"}
    return {"results": results, "engine": engine}


class _TextParser(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "aside", "form", "iframe", "button", "select", "template", "object"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "pre", "blockquote", "section", "article", "dd", "dt",
             "br", "table", "ul", "ol", "main", "figcaption", "header", "td", "th", "caption", "summary"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip, self.blocks, self.cur, self.title, self.in_title, self.prefix = 0, [], [], "", False, ""

    def flush(self):
        t = " ".join("".join(self.cur).split())
        if t:
            self.blocks.append(self.prefix + t)
        self.cur, self.prefix = [], ""

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
            return
        if tag == "title":
            self.in_title = True
        if tag in self.BLOCK:
            self.flush()
            if tag[0] == "h" and tag[1:].isdigit():
                self.prefix = "#" * int(tag[1]) + " "
            elif tag == "li":
                self.prefix = "- "
        elif tag in ("td", "th") and self.cur:
            self.cur.append(" | ")

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self.in_title = False
        elif tag in self.BLOCK:
            self.flush()

    def handle_data(self, d):
        if self.in_title:
            self.title += d
        elif not self.skip:
            self.cur.append(d)


STOP = set("the a an and or of to in on for is are was were be by with as at from that this it its what which who whom how why "
           "when where does do did can could should would will i you me my your we our about into than then there their them "
           "der die das und ist ein eine le la les et est un une des".split())


def terms(s):
    return {w for w in re.findall(r"[^\W_]{2,}", s.lower()) if w not in STOP}


def pick_text(blocks, q, budget):
    """Keep the intro and the paragraphs that match the question best, in page order."""
    seen, good = set(), []
    for b in blocks:
        if (len(b) > 40 or (b.startswith("#") and len(b) > 4)) and b not in seen:
            seen.add(b)
            good.append(b)
    if not good:
        return "", []
    qt = terms(q)
    scores = []
    for i, b in enumerate(good):
        bt = terms(b)
        s = len(qt & bt) / (1 + len(qt)) + 0.12 * (1 - i / len(good)) + (0.05 if re.search(r"\d", b) else 0)
        scores.append((s, i))
    chosen, used = set(), 0
    for i, b in enumerate(good):                   # the first real paragraphs say what the page is about
        if len(chosen) >= 2:
            break
        if len(b) > 80 and not b.startswith("#"):
            chosen.add(i)
            used += len(b)
    ranked = [i for s, i in sorted(scores, reverse=True)]
    for i in ranked:
        if used >= budget:
            break
        if i not in chosen:
            chosen.add(i)
            used += len(good[i])
    order = sorted(chosen)
    text = "\n".join(good[i] if len(good[i]) < 1500 else good[i][:1500] + "…" for i in order)
    hl = [good[i] for i in ranked[:8] if i in chosen and not good[i].startswith("#") and len(good[i]) > 60][:6]
    hl.sort(key=lambda b: good.index(b))
    return text[:budget + 1500], [h.lstrip("- ")[:90] for h in hl]


READER_JS = r"""(()=>{const H=__H__;const n=s=>(s||'').replace(/\s+/g,' ').trim().toLowerCase();
document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[href]');if(a){e.preventDefault();parent.postMessage({__mtai:1,type:'link',url:a.href},'*')}},true);
document.addEventListener('submit',e=>e.preventDefault(),true);
function go(){const els=[...document.querySelectorAll('p,li,h1,h2,h3,h4,h5,td,th,pre,blockquote,dd,dt,figcaption')].map(e=>[e,n(e.textContent)]);
const hits=[];for(const h of H){const k=n(h).slice(0,55);if(!k)continue;let best=null,bl=1e9;for(const[e,t]of els){if(t.length<bl&&t.includes(k)){best=e;bl=t.length}}if(best&&!hits.includes(best))hits.push(best)}
let i=0;const step=()=>{if(i>=hits.length){parent.postMessage({__mtai:1,type:'read-done'},'*');return}const e=hits[i++];e.classList.add('mtai-hl');e.scrollIntoView({behavior:'smooth',block:'center'});setTimeout(step,1250)};
if(hits.length)setTimeout(step,400);else{let y=0;const t=setInterval(()=>{y+=7;scrollTo(0,y);if(y>innerHeight*2.5||y>document.documentElement.scrollHeight){clearInterval(t);parent.postMessage({__mtai:1,type:'read-done'},'*')}},30)}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go();})();"""

HL_CSS = (".mtai-hl{background:rgba(250,204,21,.38)!important;box-shadow:0 0 0 4px rgba(250,204,21,.38)!important;"
          "border-radius:4px!important;transition:background .5s,box-shadow .5s;color:inherit!important}")


def browser_copy(raw, final_url, highlights):
    """The page without its scripts, plus our small reader script. Returns (html, csp)."""
    nonce = secrets.token_hex(8)
    h = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", raw, flags=re.S | re.I)
    h = re.sub(r"<script\b[^>]*>", "", h, flags=re.I)
    h = re.sub(r"<(meta[^>]+http-equiv=[\"']?(refresh|content-security-policy)[^>]*|base\b[^>]*)>", "", h, flags=re.I)
    inject = (f'<base href="{htmlmod.escape(final_url)}"><meta name="referrer" content="no-referrer">'
              f"<style>{HL_CSS}</style><script nonce=\"{nonce}\">{READER_JS.replace('__H__', json.dumps(highlights))}</script>")
    m = re.search(r"<head[^>]*>", h, re.I)
    h = h[:m.end()] + inject + h[m.end():] if m else inject + h
    csp = f"script-src 'nonce-{nonce}'; frame-src 'none'; object-src 'none'; form-action 'none'; base-uri {urlparse(final_url).scheme}:"
    return h, csp


def reader_copy(title, host, text, highlights):
    nonce = secrets.token_hex(8)
    paras = "".join(f"<h2>{htmlmod.escape(b.lstrip('# '))}</h2>" if b.startswith("#") else f"<p>{htmlmod.escape(b.lstrip('- '))}</p>"
                    for b in text.split("\n") if b.strip())
    page = (f"<!doctype html><html><head><meta charset='utf-8'><style>{HL_CSS}"
            "body{font:16px/1.65 Georgia,serif;max-width:720px;margin:0 auto;padding:36px 24px 80px;color:#1f1f23;background:#fbfaf7}"
            ".src{font:600 12px system-ui;color:#7c7c86;text-transform:uppercase;letter-spacing:.6px}h1{font:700 28px/1.25 system-ui}"
            "h2{font:650 19px system-ui;margin-top:28px}</style>"
            f"<script nonce='{nonce}'>{READER_JS.replace('__H__', json.dumps(highlights))}</script></head><body>"
            f"<div class='src'>Reader view · {htmlmod.escape(host)}</div><h1>{htmlmod.escape(title)}</h1>{paras}</body></html>")
    return page, f"script-src 'nonce-{nonce}'; frame-src 'none'; object-src 'none'"


def web_fetch(url, q="", chars=3000):
    chars = max(500, min(int(chars or 3000), 12000))
    final, ctype, raw = web_get(url)
    host = (urlparse(final).hostname or "").removeprefix("www.")
    if "html" not in ctype and not raw.lstrip()[:200].lower().startswith(("<!doctype", "<html")):
        if ctype.startswith("text/"):
            text = raw[:chars]
            page, csp = reader_copy(final.rsplit("/", 1)[-1] or host, host, text, [])
            return {"url": final, "title": host, "host": host, "text": text, "reader": True, "preview": store_preview(page, csp=csp)["url"]}
        raise ValueError(f"Not a web page ({ctype.split(';')[0] or 'unknown type'}).")
    p = _TextParser()
    try:
        p.feed(raw)
        p.close()
    except Exception:
        pass
    p.flush()
    title = " ".join(p.title.split()) or host
    text, hl = pick_text(p.blocks, q, chars)
    reader = len(text) < 400 or len(raw) > 2_500_000          # page built by JavaScript, or huge: show our reader copy
    page, csp = reader_copy(title, host, text, hl) if reader else browser_copy(raw, final, hl)
    return {"url": final, "title": title, "host": host, "text": text, "reader": reader, "preview": store_preview(page, csp=csp)["url"]}


# ---------------------------------------------------------------- workspace --
# Code mode: every chat gets its own folder. The model creates files and changes them with
# SEARCH/REPLACE edits, so it never has to rewrite a whole file.

WS_DIR = DATA_DIR / "workspaces"
WS_SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mtai"}
WS_RUNS = {}                  # ws -> {path: last run summary}
RUN_EXT = {".py": "python", ".pyw": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".ps1": "powershell"}


def ws_root(ws):
    if not ID_RE.match(str(ws)):
        raise ValueError("bad workspace")
    return WS_DIR / ws


def ws_path(ws, rel):
    rel = str(rel or "").strip().strip("\"'`").replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.lstrip("/")
    parts = rel.split("/")
    if not rel or ":" in rel or any(p in ("", ".", "..") for p in parts) or len(rel) > 200 or any(p in WS_SKIP for p in parts):
        raise ValueError(f"Bad file path: {rel or '(empty)'}")
    root = ws_root(ws)
    f = (root / rel).resolve()
    if root.resolve() not in f.parents:
        raise ValueError(f"Bad file path: {rel}")
    return root, f, rel


def read_text(f):
    b = f.read_bytes()
    if b"\0" in b[:8000]:
        return None
    return b.decode("utf-8-sig", "replace")


def ws_list(ws, content=False):
    root = ws_root(ws)
    files = []
    if root.is_dir():
        for f in sorted(root.rglob("*")):
            rel = f.relative_to(root).as_posix()
            if not f.is_file() or any(p in WS_SKIP for p in rel.split("/")):
                continue
            size = f.stat().st_size
            item = {"path": rel, "size": size}
            if size <= 400_000:
                t = read_text(f)
                if t is not None:
                    item["lines"] = t.count("\n") + (0 if t.endswith("\n") or not t else 1)
                    if content:
                        item["text"] = t
            files.append(item)
            if len(files) >= 400:
                break
    return {"files": files, "dir": str(root), "runs": WS_RUNS.get(ws, {})}


def diff_info(old, new):
    a = old.split("\n") if old else []
    b = new.split("\n")
    added = removed = 0
    changed = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            added += j2 - j1
            changed.extend(range(j1 + 1, j2 + 1))
        if tag in ("replace", "delete"):
            removed += i2 - i1
    return added, removed, changed[:3000]


def _indent(s):
    return s[:len(s) - len(s.lstrip())]


def apply_edit(text, search, replace):
    """Replace one SEARCH block. Exact match first, then ignoring trailing spaces, then ignoring indentation."""
    search = search.strip("\n")
    replace = replace.strip("\n")
    if not search.strip():
        if not text.strip():
            return replace + "\n"
        return None
    if search in text:
        return text.replace(search, replace, 1)
    tl, sl = text.split("\n"), search.split("\n")
    rl = replace.split("\n") if replace else []
    for loose in (False, True):
        key = (lambda s: s.strip()) if loose else (lambda s: s.rstrip())
        want = [key(s) for s in sl]
        for i in range(len(tl) - len(sl) + 1):
            if all(key(tl[i + k]) == want[k] for k in range(len(sl))):
                new = rl
                if loose:                             # give the new lines the file's indentation
                    pairs = {}
                    for k in range(len(sl)):
                        if sl[k].strip():
                            pairs.setdefault(_indent(sl[k]), _indent(tl[i + k]))
                    deltas = {len(f) - len(s) for s, f in pairs.items()}
                    ratios = [len(f) / len(s) for s, f in pairs.items() if s and f]
                    ch = "\t" if any("\t" in f for f in pairs.values()) else " "

                    def remap(r):
                        ind = _indent(r)
                        if not r.strip():
                            return r
                        if ind in pairs:
                            return pairs[ind] + r[len(ind):]
                        if len(deltas) == 1:              # whole block shifted by the same amount
                            n = max(0, len(ind) + next(iter(deltas)))
                        else:                             # other indent width (2 vs 4 spaces)
                            n = round(len(ind) * (sum(ratios) / len(ratios) if ratios else 1))
                        return ch * (n // 4 if ch == "\t" else n) + r[len(ind):]
                    new = [remap(r) for r in rl]
                return "\n".join(tl[:i] + new + tl[i + len(sl):])
    return None


def ws_apply(ws, op):
    kind = op.get("type")
    root, f, rel = ws_path(ws, op.get("path"))
    old = None
    crlf = False
    if f.is_file():
        old = read_text(f)
        if old is None:
            return {"ok": False, "path": rel, "type": kind, "errors": [f"{rel} is a binary file."]}
        crlf = "\r\n" in old
        old = old.replace("\r\n", "\n")
    errors = []
    if kind == "delete":
        if f.is_file():
            f.unlink()
        return {"ok": True, "path": rel, "type": kind, "deleted": old is not None, "removed": (old or "").count("\n") + 1 if old else 0}
    if kind == "write":
        new = str(op.get("content", ""))
    elif kind == "edit":
        new = old if old is not None else ""
        for k, pair in enumerate(op.get("edits") or []):
            out = apply_edit(new, str(pair.get("search", "")), str(pair.get("replace", "")))
            if out is None:
                errors.append(f"Edit {k + 1} in {rel}: the SEARCH text was not found" + (" (the file does not exist)" if old is None else "") + ".")
            else:
                new = out
        if old is None and new == "":
            return {"ok": False, "path": rel, "type": kind, "errors": errors or [f"{rel} does not exist."]}
    else:
        raise ValueError("unknown operation")
    if len(new) > 1_000_000:
        return {"ok": False, "path": rel, "type": kind, "errors": [f"{rel} would be larger than 1 MB."]}
    if new and not new.endswith("\n"):
        new += "\n"
    if new != (old or "") or old is None:
        f.parent.mkdir(parents=True, exist_ok=True)
        data = new.replace("\n", "\r\n") if crlf else new
        f.write_text(data, "utf-8-sig" if f.suffix.lower() == ".ps1" else "utf-8", newline="")
    added, removed, changed = diff_info(old, new)
    return {"ok": not errors, "path": rel, "type": kind, "created": old is None, "added": added, "removed": removed,
            "changed": changed, "content": new, "errors": errors}


def ws_run(ws, rel):
    root, f, rel = ws_path(ws, rel)
    if not f.is_file():
        return {"error": f"{rel} does not exist."}
    lang = RUN_EXT.get(f.suffix.lower())
    if f.suffix.lower() in (".html", ".htm"):
        return {"preview": f"{PREVIEW_BASE}/w/{ws}/{quote(rel)}", "path": rel}
    if not lang or not tool_env().get(lang):
        return {"error": f"MTAI cannot run {f.suffix or 'this'} files."}
    r = run_process(run_cmd(lang, f), root)
    r["path"] = rel
    tail = lambda s: s[-1500:]
    WS_RUNS.setdefault(ws, {})[rel] = {"code": r["code"], "timed_out": r["timed_out"], "stdout": tail(r["stdout"]),
                                      "stderr": tail(r["stderr"]), "time": time.time()}
    return r


# ---------------------------------------------------------------- storage --

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def list_chats():
    out = []
    if CHATS_DIR.is_dir():
        for f in CHATS_DIR.glob("*.json"):
            c = read_json(f, None)
            if not isinstance(c, dict):
                continue
            msgs = c.get("messages") or []
            last = next((m.get("content", "") for m in reversed(msgs) if m.get("content")), "")
            out.append({"id": c.get("id"), "title": c.get("title") or "New chat",
                        "updated": c.get("updated", 0), "model_name": c.get("model_name"),
                        "count": len(msgs), "preview": last[:140], "pinned": bool(c.get("pinned"))})
    out.sort(key=lambda c: c["updated"], reverse=True)
    return out


# ------------------------------------------------------------------ server --

class Handler(BaseHTTPRequestHandler):
    server_version = "MTAI/2"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _stream(self, fn):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def emit(obj):
            self.wfile.write((json.dumps(obj) + "\n").encode())
            self.wfile.flush()
        try:
            fn(emit)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass                                  # the app pressed Stop
        except urllib.error.HTTPError as e:
            try:
                emit({"type": "error", "error": http_error_text(e), "message": http_error_text(e)})
            except OSError:
                pass
        except Exception as e:
            try:
                emit({"type": "error", "error": str(e), "message": f"{type(e).__name__}: {e}"})
            except OSError:
                pass

    def _authed(self):
        return secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    # ---- static files
    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        f = (UI_DIR / unquote(path).lstrip("/")).resolve()
        if UI_DIR not in f.parents or not f.is_file():
            return self._send(404, b"not found", "text/plain")
        types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml",
                 ".png": "image/png", ".ico": "image/x-icon"}
        body = f.read_bytes()
        if f.name == "index.html":
            body = body.replace(b"{{TOKEN}}", TOKEN.encode())
        self._send(200, body, types.get(f.suffix, "application/octet-stream"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/img/"):                 # generated images (random names, shown in <img> tags)
            name = unquote(path[5:])
            f = P.IMG_DIR / name
            if not P.IMG_NAME_RE.match(name) or not f.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(name.rsplit(".", 1)[1].lower(), "image/png")
            return self._send(200, f.read_bytes(), ctype)
        if not path.startswith("/api/"):
            return self._static(path)
        if not self._authed():
            return self._json({"error": "forbidden"}, 403)
        if path == "/api/models":
            return self._json(discover())
        if path == "/api/cloud":
            return self._json(P.status())
        if path == "/api/images/backends":
            return self._json(P.image_backends(PRIVACY["on"]))
        if path == "/api/images/list":
            return self._json({"images": P.list_images()})
        if path == "/api/imagegen":
            return self._json(IG.status())
        if path == "/api/settings":
            return self._json({**DEFAULT_SETTINGS, **read_json(SETTINGS_FILE, {})})
        if path == "/api/privacy":
            return self._json(PC.status())
        if path == "/api/firewall":
            return self._json(firewall_info())
        if path == "/api/env":
            return self._json({**tool_env(), "preview_base": PREVIEW_BASE})
        if path == "/api/chats":
            return self._json({"chats": list_chats()})
        if path.startswith("/api/chats/"):
            cid = path.rsplit("/", 1)[1]
            c = read_json(CHATS_DIR / f"{cid}.json", None) if ID_RE.match(cid) else None
            return self._json(c or {"error": "not found"}, 200 if c else 404)
        self._json({"error": "unknown"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/") or not self._authed():
            return self._json({"error": "forbidden"}, 403)
        try:
            body = self._body()
        except ValueError:
            return self._json({"error": "bad json"}, 400)

        if path == "/api/chat":
            return self._stream(lambda emit: run_chat(body, emit))
        if PRIVACY["on"] and path in ("/api/ollama/pull", "/api/web/search", "/api/web/fetch"):
            return self._json({"error": PRIVACY_MSG, "privacy": True})
        if path.startswith("/api/cloud/"):
            pid = str(body.get("provider", ""))
            if pid and pid not in P.PROV:
                return self._json({"error": "Unknown provider"}, 400)
            try:
                if path == "/api/cloud/remove":
                    P.remove_key(pid)
                    return self._json(P.status())
                if PRIVACY["on"]:
                    return self._json({"error": PRIVACY_MSG, "privacy": True})
                if path == "/api/cloud/key":
                    old = P._store().get(pid)
                    P.set_key(pid, body.get("key") or None, body.get("base"), body.get("filter"), body.get("name"))
                    try:
                        n = P.refresh(pid)
                    except P.ProviderError as e:
                        if body.get("key") and re.search(r"did not accept|HTTP 40[13]", str(e)):
                            st = P._store()          # a wrong key is not kept
                            if old:
                                st[pid] = old
                            else:
                                st.pop(pid, None)
                            P._write_json(P.KEYS_FILE, st)
                        return self._json({"error": str(e), **P.status()})
                    return self._json({"ok": True, "count": n, **P.status()})
                if path == "/api/cloud/refresh":
                    errors = {}
                    for p in ([pid] if pid else [k for k in P.PROV if P.get_key(k)]):
                        try:
                            P.refresh(p)
                        except P.ProviderError as e:
                            errors[p] = str(e)
                    return self._json({"errors": errors, **P.status()})
            except P.ProviderError as e:
                return self._json({"error": str(e)})
            return self._json({"error": "unknown"}, 404)
        if path.startswith("/api/imagegen/"):
            mid = str(body.get("id", ""))
            try:
                if path == "/api/imagegen/download":
                    if PRIVACY["on"]:
                        return self._json({"error": PRIVACY_MSG, "privacy": True})
                    IG.start_download(mid)
                elif path == "/api/imagegen/cancel":
                    IG.cancel(mid)
                elif path == "/api/imagegen/delete":
                    IG.delete_model(mid)
                elif path == "/api/imagegen/delete-engine":
                    IG.delete_engine()
                elif path == "/api/imagegen/folder":
                    IG.set_root(str(body.get("path", "")))
                elif path == "/api/imagegen/open-folder":
                    r = IG.root()
                    r.mkdir(parents=True, exist_ok=True)
                    if os.name == "nt":
                        os.startfile(r)
                else:
                    return self._json({"error": "unknown"}, 404)
            except IG.GenError as e:
                return self._json({"error": str(e)})
            return self._json(IG.status())
        if path == "/api/images/generate":
            try:
                return self._json(P.generate_image(body, PRIVACY["on"], free_gpu_for_images))
            except P.ProviderError as e:
                return self._json({"error": str(e)})
            except Exception as e:
                return self._json({"error": f"{type(e).__name__}: {e}"})
        if path == "/api/images/delete":
            P.delete_image(str(body.get("name", "")))
            return self._json({"ok": True})
        if path == "/api/images/reveal":
            name = str(body.get("name", ""))
            f = P.IMG_DIR / name
            if os.name == "nt" and (P.IMG_NAME_RE.match(name) and f.is_file() or not name):
                if name:
                    with NG.allow("show a picture in Explorer"):
                        subprocess.Popen(["explorer", "/select,", str(f)])
                else:
                    P.IMG_DIR.mkdir(parents=True, exist_ok=True)
                    os.startfile(P.IMG_DIR)
            return self._json({"ok": True})
        if path == "/api/chats/pin":
            cid = str(body.get("id", ""))
            f = CHATS_DIR / f"{cid}.json"
            c = read_json(f, None) if ID_RE.match(cid) else None
            if c:
                c["pinned"] = bool(body.get("pinned"))
                write_json(f, c)
            return self._json({"ok": bool(c)})
        if path == "/api/ollama/pull":
            name = str(body.get("name", "")).strip()
            if not re.match(r"^[\w.\-/:]+$", name):
                return self._json({"error": "bad model name"}, 400)
            return self._stream(lambda emit: pull_model(name, emit))
        if path == "/api/ollama/start":
            return self._json(start_ollama())
        if path == "/api/ollama/delete":
            try:
                http_json(OLLAMA_URL + "/api/delete", {"model": body.get("name")}, method="DELETE", timeout=30)
                return self._json({"ok": True})
            except urllib.error.HTTPError as e:
                return self._json({"error": http_error_text(e)})
            except Exception as e:
                return self._json({"error": str(e)})
        if path == "/api/ollama/unload":
            try:
                http_json(OLLAMA_URL + "/api/generate", {"model": body.get("name"), "keep_alive": 0}, timeout=30)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"error": str(e)})
        if path == "/api/settings":
            s = {**DEFAULT_SETTINGS, **read_json(SETTINGS_FILE, {})}
            s.update({k: v for k, v in body.items() if k in DEFAULT_SETTINGS})
            s["privacy"] = bool(s.get("privacy"))
            was = PRIVACY["on"]
            set_privacy(s["privacy"])
            write_json(SETTINGS_FILE, s)
            if s["privacy"] != was:
                s = {**s, "_cut": NG.STATE.get("cut", 0)}   # how many open connections were cut (for the page)
            return self._json(s)
        if path == "/api/chats/save":
            c = body.get("chat") or {}
            if not ID_RE.match(str(c.get("id", ""))):
                return self._json({"error": "bad id"}, 400)
            write_json(CHATS_DIR / f"{c['id']}.json", c)
            return self._json({"ok": True})
        if path == "/api/chats/delete":
            cid = str(body.get("id", ""))
            if ID_RE.match(cid):
                (CHATS_DIR / f"{cid}.json").unlink(missing_ok=True)
                shutil.rmtree(WS_DIR / cid, ignore_errors=True)      # the chat's code-mode folder
            return self._json({"ok": True})
        if path == "/api/chats/rename":
            cid = str(body.get("id", ""))
            f = CHATS_DIR / f"{cid}.json"
            c = read_json(f, None) if ID_RE.match(cid) else None
            if c:
                c["title"] = str(body.get("title", ""))[:120]
                write_json(f, c)
            return self._json({"ok": bool(c)})
        if path == "/api/folders/add":
            p = str(body.get("path", "")).strip()
            if not p or not Path(p).is_dir():
                return self._json({"error": "That folder does not exist."})
            folders = custom_folders()
            if p not in folders:
                folders.append(p)
                write_json(FOLDERS_FILE, folders)
            return self._json({"ok": True})
        if path == "/api/folders/remove":
            folders = [f for f in custom_folders() if f != body.get("path")]
            write_json(FOLDERS_FILE, folders)
            return self._json({"ok": True})
        if path == "/api/run":
            return self._json(run_code(body.get("lang", ""), str(body.get("code", ""))))
        if path == "/api/preview":
            return self._json(store_preview(str(body.get("html", "")), body.get("id")))
        if path == "/api/web/search":
            return self._json(web_search(body.get("q", ""), min(int(body.get("n") or 8), 12)))
        if path == "/api/web/fetch":
            try:
                return self._json(web_fetch(str(body.get("url", "")), str(body.get("q", "")), body.get("chars")))
            except Exception as e:
                if isinstance(e, urllib.error.HTTPError):
                    msg = f"HTTP {e.code}" + (" (the site blocks downloads)" if e.code in (401, 403, 429) else "")
                else:
                    msg = str(getattr(e, "reason", None) or e)[:200]
                return self._json({"error": msg or type(e).__name__})
        if path.startswith("/api/ws/"):
            try:
                ws = str(body.get("ws", ""))
                if path == "/api/ws/list":
                    return self._json(ws_list(ws, bool(body.get("content"))))
                if path == "/api/ws/apply":
                    return self._json(ws_apply(ws, body.get("op") or {}))
                if path == "/api/ws/run":
                    return self._json(ws_run(ws, body.get("path")))
                if path == "/api/ws/open-folder":
                    root = ws_root(ws)
                    root.mkdir(parents=True, exist_ok=True)
                    if os.name == "nt":
                        os.startfile(root)
                    return self._json({"ok": True})
            except ValueError as e:
                return self._json({"error": str(e)})
        if path == "/api/open-folder":
            p = Path(str(body.get("path", ""))).resolve()
            if RUNS_DIR.resolve() in p.parents and p.is_dir() and os.name == "nt":
                os.startfile(p)
            return self._json({"ok": True})
        if path == "/api/open":
            url = str(body.get("url", ""))
            if PRIVACY["on"]:      # also this PC's pages: the system browser is outside MTAI's network block
                NG.note("open", url, component="Link", detail="system browser")
                return self._json({"error": PRIVACY_MSG + " Links do not open in your browser, because MTAI cannot "
                                   "keep your browser offline.", "privacy": True})
            if url.startswith(("http://", "https://")):
                webbrowser.open(url)
            return self._json({"ok": True})
        if path == "/api/privacy/verify":
            return self._json(PC.run(browser=body.get("browser")))
        if path == "/api/firewall/apply":
            return self._json(firewall_apply(body))
        if path == "/api/firewall/remove":
            return self._json(firewall_remove(body))
        if path == "/api/firewall/test":
            return self._json(firewall_test())
        if path == "/api/browser-runtime":
            return self._json(browser_runtime(body))
        if path == "/api/privacy/clear":
            NG.BLOCKED.clear()
            NG.COUNTS.clear()
            return self._json({"ok": True})
        self._json({"error": "unknown"}, 404)


# ------------------------------------------------------------------ window --

class JsApi:
    """Exposed to the page as window.pywebview.api (native dialogs)."""

    def __init__(self):
        self._window = None

    def pick_folder(self):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        res = self._window.create_file_dialog(kind)
        return res[0] if res else None

    def set_caption(self, bg, text=None):
        if self._window:
            dark_title_bar(self._window, bg, text or "#f0e8ee")
        return True

    def save_file(self, filename, text):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        res = self._window.create_file_dialog(kind, save_filename=filename)
        if not res:
            return None
        path = res if isinstance(res, str) else res[0]
        Path(path).write_text(text, "utf-8")
        return path

    def save_image(self, name, suggested=None):
        """Save As for a generated picture: copies the file from the images folder."""
        import shutil
        import webview
        name = str(name or "")
        src = P.IMG_DIR / name
        if not P.IMG_NAME_RE.match(name) or not src.is_file():
            raise ValueError("That picture is gone.")
        ext = name.rsplit(".", 1)[1].lower()
        base = re.sub(r"[^\w\- ]+", "", str(suggested or ""))[:60].strip().replace(" ", "-") or "mtai-picture"
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        res = self._window.create_file_dialog(kind, save_filename=f"{base}.{ext}",
                                              file_types=(f"Image (*.{ext})", "All files (*.*)"))
        if not res:
            return None
        path = res if isinstance(res, str) else res[0]
        if not Path(path).suffix:
            path += "." + ext
        shutil.copyfile(src, path)
        return path


def colorref(hex_color, fallback):
    """'#rrggbb' -> Windows COLORREF (0x00bbggrr)."""
    h = str(hex_color or "").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        return fallback
    return int(h[4:6] + h[2:4] + h[0:2], 16)


def dark_title_bar(window, bg="#07060b", text="#f0e8ee"):
    """Windows 11: caption in the theme's background colour."""
    try:
        import ctypes
        hwnd = window.native.Handle.ToInt64()
        dwm = ctypes.windll.dwmapi
        for attr, val in ((20, 1), (35, colorref(bg, 0x000B0607)), (36, colorref(text, 0x00EEE8F0)), (34, colorref(bg, 0x00241A2A))):
            v = ctypes.c_int(val)
            dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr, ctypes.byref(v), 4)
    except Exception:
        pass


def find_edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return str(p)
    return None


def ask_yes_no(title, text):
    try:
        return ctypes.windll.user32.MessageBoxW(None, text, title, 0x4 | 0x20 | 0x40000) == 6  # Yes/No, ?, topmost
    except Exception:
        return False


def load_webview():
    """Import pywebview. If this Python lacks it, offer to install it instead of silently using Edge."""
    try:
        import webview
        return webview
    except ImportError:
        pass
    exe = python_exe()
    msg = ("MTAI's private window needs the pywebview package, which is missing in this Python:\n\n"
           f"{exe}\n\nInstall it now? (about 20 MB, one time)\n\n"
           "No = open MTAI in an Edge window instead. Edge shows its own Microsoft features, "
           "like the menu when you select text.")
    if ask_yes_no("MTAI", msg):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run([exe, "-m", "pip", "install", "pywebview"], capture_output=True, text=True, creationflags=flags)
        if r.returncode == 0:
            try:
                import importlib, site
                importlib.invalidate_caches()
                site.main()
                import webview
                return webview
            except Exception:
                pass
        ctypes.windll.user32.MessageBoxW(None, "Installing pywebview failed:\n\n" + (r.stderr or r.stdout)[-800:]
                                         + "\n\nMTAI opens in Edge for now.", "MTAI", 0x10)
    print("pywebview is not installed (pip install pywebview). Opening in Edge.")
    return None


def use_private_runtime(webview):
    """When the user turned it on: run the window from MTAI's own WebView2 copy (a program path that
    a firewall rule can block without touching other programs). A newer copy made last time goes in first."""
    if not (read_json(SETTINGS_FILE, {}).get("firewall") or {}).get("private_browser"):
        return "system"
    try:
        WR.promote()
        st = WR.status()
        if st["outdated"] or not st["current"]:
            WR.make_copy()                    # in the background, used from the next start
        if st["current"]:
            webview.settings["WEBVIEW2_RUNTIME_PATH"] = str(WR.current())
            return "private"
    except Exception as e:
        print("MTAI: private WebView2 copy not used:", e)
    return "system"


def main():
    ap = argparse.ArgumentParser(description="MTAI - chat with your local AI models")
    ap.add_argument("--browser", action="store_true", help="open in a browser instead of a native window")
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    set_privacy(bool(read_json(SETTINGS_FILE, {}).get("privacy")))
    gate = NG.start_gate()                    # the browser's only way out; closed while privacy mode is on
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    global SERVER_PORT
    SERVER_PORT = server.server_address[1]
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    global PREVIEW_BASE
    pserver = ThreadingHTTPServer(("127.0.0.1", 0), PreviewHandler)
    pserver.daemon_threads = True
    PREVIEW_BASE = f"http://127.0.0.1:{pserver.server_address[1]}"
    threading.Thread(target=pserver.serve_forever, daemon=True).start()

    webview = None if args.browser else load_webview()

    if webview:
        # WebView2 flags: no SmartScreen URL checks, no implicit Microsoft account sign-in, no background calls.
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = NG.webview2_args(gate.port)
        BROWSER.update(mode="webview2", gate=gate.port, runtime=use_private_runtime(webview))
        api = JsApi()
        theme = read_json(SETTINGS_FILE, {}).get("theme") or {}
        bg = theme.get("bg") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(theme.get("bg"))) else "#07060B"
        win = webview.create_window("MTAI", url, width=1320, height=860, min_size=(900, 600),
                                    background_color=bg.upper(), js_api=api, text_select=True)
        api._window = win
        win.events.shown += lambda: dark_title_bar(win, bg)
        webview.start()
    else:
        edge = find_edge()
        if edge:
            # Own throwaway profile: no Microsoft account, sync, history or extensions from the user's Edge.
            with NG.allow("open MTAI in Edge"):
                subprocess.Popen([edge, f"--app={url}", "--window-size=1320,860",
                                  f"--user-data-dir={DATA_DIR / 'edge-profile'}", "--no-first-run",
                                  "--no-default-browser-check", "--disable-sync", "--disable-background-networking",
                                  "--disable-features=msSmartScreenProtection,Translate,msEdgeShopping",
                                  f"--proxy-server=http://127.0.0.1:{gate.port}",
                                  "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost , EXCLUDE 127.0.0.1 , EXCLUDE [::1]", "--disable-quic",
                                  "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
            BROWSER.update(mode="edge", gate=gate.port)
        else:
            BROWSER.update(mode="system", gate=None)  # the system browser: not behind the gate
            with NG.allow("open MTAI in the system browser"):
                _real_browser_open(url)
        print(f"MTAI is running at {url}  (Ctrl+C to quit)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    server.shutdown()


PC.bind(sys.modules[__name__])

if __name__ == "__main__":
    main()
