"""
MTAI privacy self-test and diagnostics.

run() makes real connection attempts to harmless public test hosts (example.com,
1.1.1.1, echo.websocket.org) and grades each one:

  privacy on:   PASS = MTAI's guard refused it, FAIL = it got through,
                UNVERIFIED = it failed, but not provably because of MTAI
  privacy off:  PASS = it connected (normal networking is back), FAIL = blocked,
                UNVERIFIED = it failed for another reason (no internet, no IPv6)

Nothing from the user is sent: the requests carry no chats, files, keys or names.
The browser probes run in the page (privacy.js) and are sent here to be graded
against the gate's own log, so a probe counts as blocked only when the gate (or
the preview's CSP) is seen refusing it.
"""
import json
import os
import socket
import ssl
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import netguard as NG

L = None                                   # the app module (local_ai_chat), set by bind()
LAST = {"run": None, "ok_run": None}
# PASS: proven blocked (or working, where it should work). FAIL: proven wrong. UNVERIFIED: could not be proven
# either way. UNPROTECTED: known not to be blocked (a local AI program without firewall rules). INFO: a fact.
RESULTS = ("PASS", "FAIL", "UNVERIFIED", "UNPROTECTED", "INFO")
_lock = threading.Lock()
HOSTS = {"fetch": "example.com", "xhr": "example.net", "ws": "echo.websocket.org", "img": "example.org",
         "script": "www.example.com", "iframe": "www.iana.org", "beacon": "www.example.net"}

LIMITS = [
    "Local AI programs (Ollama, LM Studio, llama.cpp, ComfyUI...) are separate programs. MTAI blocks them only "
    "with the optional Windows Firewall rules (Privacy diagnostics > Local AI programs). Without the rules they "
    "can still go online by themselves, and the status is not green.",
    "Windows Firewall rules work per program file. If a local AI program starts a different program (a plugin "
    "that runs git.exe or curl.exe, for example), that program is not covered. The connection watcher reports "
    "such programs and their outside connections; it cannot stop them.",
    "Windows looks host names up for every program through its DNS Client service, so a blocked program can "
    "still have a name looked up (no connection follows). Firewall rules cannot stop that.",
    "When the rules go in, MTAI closes the restricted programs' open IPv4 connections. Open IPv6 connections "
    "cannot be closed (Windows has no call for it); they are reported. New ones are blocked.",
    "The rules do nothing while Windows Firewall is off for the active network or a company policy ignores "
    "local rules. MTAI checks both and then does not show a green status.",
    "MTAI does not turn on Windows Firewall logging, so blocked attempts of other programs are not listed one by "
    "one; the firewall tests and the connection watcher show what happened instead.",
    "JavaScript files do not run in privacy mode (Node.js cannot start in the offline sandbox). Python and "
    "PowerShell run in it; HTML pages preview in MTAI's own browser behind the gate.",
    "Sandboxed code runs cannot reach anything, not even this PC's own servers (localhost). They can only read "
    "and write their own run folder and read the Python folder.",
    "The audit hook sees what Python's socket module does. A native library that opened sockets itself would "
    "not be stopped by it. The connection watcher (every 3 s) would report it, so a very short connection "
    "between two looks can be missed.",
    "WebView2 (MTAI's window) contains Microsoft sign-in code that uses Windows' own networking and can go "
    "around the gate; it was seen connecting to outlook.office.com. Only a firewall rule stops it, and only when "
    "MTAI's window runs from its own WebView2 copy (about 600 MB in MTAI's data folder, updated at the next start "
    "after Windows updates WebView2). Until then the browser is shown as not protected.",
    "WebRTC in MTAI's browser may not use UDP in either mode (so it cannot slip past the gate).",
    "No IPv6 route on this PC means IPv6 can only be checked in the 'blocked' direction.",
]


def bind(app):
    global L
    L = app
    try:
        saved = json.loads(_file().read_text("utf-8"))
        LAST.update(run=saved.get("run"), ok_run=saved.get("ok_run"))
    except Exception:
        pass


def _file():
    return L.DATA_DIR / "privacy-verify.json"


# ---------------------------------------------------------------- grading --

def _guard_blocked(e, depth=0):
    if e is None or depth > 8:
        return False
    if isinstance(e, NG.Blocked) or "MTAI privacy mode blocked" in str(e):
        return True
    for nxt in (getattr(e, "__cause__", None), getattr(e, "__context__", None), getattr(e, "reason", None)):
        if isinstance(nxt, BaseException) and _guard_blocked(nxt, depth + 1):
            return True
    return any(isinstance(a, BaseException) and _guard_blocked(a, depth + 1) for a in getattr(e, "args", ()))


def attempt(fn):
    try:
        return "ok", fn()
    except Exception as e:
        return ("blocked" if _guard_blocked(e) else "failed"), e


def grade(on, outcome, value):
    if on:
        if outcome == "blocked":
            return "PASS", "Refused by MTAI's guard: " + str(value)[:160]
        if outcome == "ok":
            return "FAIL", "Got through: " + str(value)[:160]
        return "UNVERIFIED", "Failed, but not because of MTAI's guard: " + f"{type(value).__name__}: {value}"[:200]
    if outcome == "ok":
        return "PASS", "Connected: " + str(value)[:160]
    if outcome == "blocked":
        return "FAIL", "Still blocked with privacy mode off: " + str(value)[:160]
    return "UNVERIFIED", "Could not connect (no internet or no route?): " + f"{type(value).__name__}: {value}"[:200]


def R(group, cid, name, result, detail):
    return {"group": group, "id": cid, "name": name, "result": result, "detail": detail}


# ------------------------------------------------------------- the probes --

DNS_QUERY = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01"


def _udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(4)
        s.sendto(DNS_QUERY, ("1.1.1.1", 53))
        return f"DNS answer of {len(s.recvfrom(512)[0])} bytes"
    finally:
        s.close()


def _tcp(host, port=443):
    s = socket.create_connection((host, port), timeout=6)
    peer = s.getpeername()
    s.close()
    return peer


def _raw(fam, addr):
    s = socket.socket(fam, socket.SOCK_STREAM)
    try:
        s.settimeout(4)
        s.connect(addr)
        return s.getpeername()
    finally:
        s.close()


def _bind_any():
    s = socket.socket()
    try:
        s.bind(("0.0.0.0", 0))
        return f"listening possible on {s.getsockname()}"
    finally:
        s.close()


def _url(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "MTAI-selftest"}), timeout=8) as r:
        return f"HTTP {r.status}"


def _requests():
    import requests
    return f"HTTP {requests.get('https://example.com', timeout=8).status_code}"


def _httpx():
    import httpx
    return f"HTTP {httpx.get('https://example.com', timeout=8).status_code}"


def _websocket():
    raw = socket.create_connection(("echo.websocket.org", 443), timeout=8)
    s = ssl.create_default_context().wrap_socket(raw, server_hostname="echo.websocket.org")
    try:
        s.sendall(b"GET / HTTP/1.1\r\nHost: echo.websocket.org\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n")
        line = s.recv(200).split(b"\r\n", 1)[0].decode("latin-1")
        if " 101 " not in line + " ":
            raise OSError("no WebSocket upgrade: " + line)
        return line
    finally:
        s.close()


def _curl():
    r = subprocess.run(["curl.exe", "-sS", "-m", "8", "-o", "NUL", "-w", "%{http_code}", "https://example.com"],
                       capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise OSError(f"curl exit {r.returncode}: {r.stderr.strip()[:120]}")
    return "curl HTTP " + r.stdout.strip()


def _gate():
    if not NG.GATE:
        raise RuntimeError("no gate")
    s = socket.create_connection(("127.0.0.1", NG.GATE.port), timeout=8)
    try:
        s.sendall(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        return s.recv(200).split(b"\r\n", 1)[0].decode("latin-1")
    finally:
        s.close()


SANDBOX_PY = r'''
import socket, subprocess, urllib.request
print("RAN")
def t(name, fn):
    try:
        fn(); print(name, "CONNECTED")
    except Exception as e:
        print(name, "FAILED", type(e).__name__)
t("tcp4", lambda: socket.create_connection(("1.1.1.1", 443), timeout=5).close())
t("dns", lambda: socket.getaddrinfo("example.com", 443))
t("https", lambda: urllib.request.urlopen("https://example.com", timeout=6).read(10))
t("ip-https", lambda: urllib.request.urlopen("https://1.1.1.1", timeout=6).read(10))
def curl():
    r = subprocess.run(["curl.exe", "-sS", "-m", "6", "-o", "NUL", "https://1.1.1.1"], capture_output=True, timeout=15)
    if r.returncode: raise OSError(r.returncode)
t("child-curl", curl)
'''

SANDBOX_PS = r'''
Write-Output "RAN"
try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 6 https://example.com; Write-Output "iwr CONNECTED" } catch { Write-Output "iwr FAILED" }
try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("1.1.1.1", 443); Write-Output "tcp CONNECTED"; $c.Close() } catch { Write-Output "tcp FAILED" }
'''

SANDBOX_JS = r'''
console.log("RAN");
fetch("https://example.com").then(r => console.log("fetch CONNECTED", r.status)).catch(e => console.log("fetch FAILED", e.message));
'''


def _code(on, lang, code, name):
    r = L.run_code(lang, code)
    if r.get("error"):
        if on and r.get("privacy"):
            return "PASS", "Refused, not run: " + r["error"][:200]
        return ("FAIL" if not on else "UNVERIFIED"), r["error"][:200]
    out = (r.get("stdout") or "") + (r.get("stderr") or "")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    hits = [ln for ln in lines if "CONNECTED" in ln]
    if "RAN" not in out:
        return "UNVERIFIED", "The program did not start: " + out[-200:]
    if on:
        if not r.get("sandboxed"):
            return "FAIL", "Ran outside the sandbox"
        if hits:
            return "FAIL", "Got through inside the sandbox: " + "; ".join(hits)[:200]
        return "PASS", "Ran in the offline sandbox, every attempt failed: " + "; ".join(lines[1:])[:200]
    if hits:
        return "PASS", "Ran normally and connected: " + "; ".join(hits)[:200]
    return "UNVERIFIED", "Ran, but could not connect: " + "; ".join(lines[1:])[:200]


def _cloud_refused():
    fake = {"id": "cloud|mtai-selftest", "name": "selftest", "backend": "cloud", "provider": "openai",
            "api_id": "selftest", "chattable": True, "source": "selftest"}
    with L.MODELS_LOCK:
        L.MODELS[fake["id"]] = fake
    events = []
    try:
        L.run_chat({"model_id": fake["id"], "messages": [{"role": "user", "content": "selftest"}]}, events.append)
    finally:
        with L.MODELS_LOCK:
            L.MODELS.pop(fake["id"], None)
    msg = next((e.get("message", "") for e in events if e.get("type") == "error"), "")
    return ("PASS", "Refused before anything was sent: " + msg[:160]) if "Privacy" in msg else \
        ("FAIL", "Not refused: " + json.dumps(events)[:200])


def python_checks(on):
    out = []
    for cid, name, fn in [
        ("py-tcp4", "TCP to 1.1.1.1:443 (IPv4, direct IP)", lambda: _tcp("1.1.1.1")),
        ("py-tcp6", "TCP to [2606:4700:4700::1111]:443 (IPv6)", lambda: _tcp("2606:4700:4700::1111")),
        ("py-raw4", "Raw socket.connect to 1.1.1.1:443 (no lookup)", lambda: _raw(socket.AF_INET, ("1.1.1.1", 443))),
        ("py-raw6", "Raw socket.connect to [2606:4700:4700::1111]:443", lambda: _raw(socket.AF_INET6, ("2606:4700:4700::1111", 443))),
        ("py-lan", "TCP to a local network address (192.168.1.1:80)", lambda: _raw(socket.AF_INET, ("192.168.1.1", 80))),
        ("py-dns", "DNS lookup of example.com (getaddrinfo)", lambda: socket.getaddrinfo("example.com", 443)[0][4]),
        ("py-dns2", "DNS lookup (gethostbyname)", lambda: socket.gethostbyname("example.org")),
        ("py-udp", "UDP DNS query to 1.1.1.1:53", _udp),
        ("py-bind", "Listen on all network interfaces (0.0.0.0)", _bind_any),
        ("py-http", "urllib http://example.com", lambda: _url("http://example.com")),
        ("py-https", "urllib https://example.com", lambda: _url("https://example.com")),
        ("py-iphttps", "urllib https://1.1.1.1 (direct IP)", lambda: _url("https://1.1.1.1")),
        ("py-requests", "requests https://example.com", _requests),
        ("py-httpx", "httpx https://example.com (used by the Claude SDK)", _httpx),
        ("py-ws", "WebSocket handshake with echo.websocket.org", _websocket),
    ]:
        o, v = attempt(fn)
        if isinstance(v, ModuleNotFoundError):
            out.append(R("Python in MTAI", cid, name, "UNVERIFIED", "Not installed in this Python"))
            continue
        res, det = grade(on, o, v)
        if cid in ("py-tcp6",) and not on and res == "UNVERIFIED":
            det = "This PC has no IPv6 route, so only the blocked direction can be checked. " + det
        if cid == "py-bind" and not on and o == "ok":
            res, det = "PASS", "Allowed again: " + str(v)
        out.append(R("Python in MTAI", cid, name, res, det))
    return out


def process_checks(on):
    out = []
    o, v = attempt(_curl)
    out.append(R("Other programs", "proc-curl", "Start curl.exe https://example.com from MTAI", *grade(on, o, v)))
    if on:
        o, v = attempt(lambda: os.system("curl.exe -s -m 5 https://example.com >NUL"))
        out.append(R("Other programs", "proc-system", "os.system with curl", *grade(on, o, v)))
        o, v = attempt(lambda: os.startfile("https://example.com/"))
        out.append(R("Other programs", "proc-open", "Open a web link in the system browser", *grade(on, o, v)))
        ok = L._safe_browser_open("https://example.com/") is False
        out.append(R("Other programs", "proc-link", "Links from pages (pywebview new window)",
                     "PASS" if ok else "FAIL", "Refused" if ok else "Opened"))
    else:
        out.append(R("Other programs", "proc-open", "Open a web link in the system browser", "UNVERIFIED",
                     "Not tried with privacy mode off: it would open your browser"))
    return out


def code_checks(on):
    return [R("Code runs", "code-py", "Python code that tries TCP, DNS, HTTPS and curl", *_code(on, "python", SANDBOX_PY, "py")),
            R("Code runs", "code-ps", "PowerShell code that tries Invoke-WebRequest and TCP", *_code(on, "powershell", SANDBOX_PS, "ps")),
            R("Code runs", "code-js", "JavaScript (Node.js) fetch", *_code(on, "javascript", SANDBOX_JS, "js"))]


SANDBOX_BOUNDS = r'''
import ctypes, os, socket, subprocess, winreg
from ctypes import wintypes as W
P = __PATHS__
def t(cid, name, want, fn):
    try:
        r = fn(); got = "allowed"
    except Exception as e:
        r = type(e).__name__; got = "denied"
    print("BOUND|%s|%s|%s|%s|%s" % (cid, name, want, got, str(r)[:80].replace("|", "/")))
t("docs", "read your Documents folder", "deny", lambda: os.listdir(P["docs"])[:1])
t("settings", "read MTAI's settings", "deny", lambda: open(P["settings"], "rb").read(10))
t("other", "read another chat's workspace", "deny", lambda: open(P["other"], "rb").read(10))
t("runs", "list the other run folders", "deny", lambda: os.listdir(P["runs"])[:1])
t("pyread", "read the Python folder", "allow", lambda: os.listdir(P["py"])[:1])
t("pywrite", "write into the Python folder", "deny", lambda: open(os.path.join(P["py"], "mtai-sandbox-test.txt"), "w").write("x"))
t("own", "write its own run folder", "allow", lambda: open("own.txt", "w").write("x"))
t("reg", "write to the registry (HKCU Software)", "deny", lambda: winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\MTAI-sandbox-test"))
t("loop", "connect to MTAI or Ollama on 127.0.0.1", "deny", lambda: socket.create_connection(("127.0.0.1", P["port"]), timeout=3).close())
def openproc():
    h = ctypes.windll.kernel32.OpenProcess(0x0410, False, P["pid"])
    if not h:
        raise PermissionError("OpenProcess failed")
    ctypes.windll.kernel32.CloseHandle(h); return "opened"
t("proc", "read MTAI's process memory", "deny", openproc)
adv = ctypes.WinDLL("advapi32"); k = ctypes.windll.kernel32
k.GetCurrentProcess.restype = W.HANDLE
adv.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)]
adv.GetTokenInformation.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD)]
tok = W.HANDLE(); adv.OpenProcessToken(k.GetCurrentProcess(), 0x0008, ctypes.byref(tok))
v = W.DWORD(); n = W.DWORD()
adv.GetTokenInformation(tok, 29, ctypes.byref(v), 4, ctypes.byref(n))
print("TOKEN|appcontainer|%d" % v.value)
r = subprocess.run(["whoami", "/priv", "/fo", "csv", "/nh"], capture_output=True, encoding="oem", errors="replace")
print("TOKEN|privs|" + ";".join(l.split(",")[0].strip('"') for l in r.stdout.splitlines() if l.strip()))
r = subprocess.run(["whoami", "/groups", "/fo", "csv", "/nh"], capture_output=True, encoding="oem", errors="replace")
print("TOKEN|integrity|" + ";".join(l.split('","')[2].strip('"') for l in r.stdout.splitlines() if "S-1-16-" in l))
print("TOKEN|env|" + ";".join(sorted(k for k in os.environ if any(w in k.upper() for w in ("KEY", "TOKEN", "SECRET", "PASS")))))
'''
DANGEROUS = ("SeDebugPrivilege", "SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege",
             "SeImpersonatePrivilege", "SeLoadDriverPrivilege", "SeTcbPrivilege", "SeAssignPrimaryTokenPrivilege",
             "SeCreateTokenPrivilege", "SeSecurityPrivilege", "SeManageVolumePrivilege")


def sandbox_bounds():
    """File, registry, process and privilege limits of the code sandbox (privacy mode only)."""
    import secrets as _s
    import shutil as _sh
    import winreg
    other = L.WS_DIR / ("mtai-boundary-" + _s.token_hex(4))
    other.mkdir(parents=True, exist_ok=True)
    (other / "secret.txt").write_text("not for the sandbox", "utf-8")
    port = getattr(L, "SERVER_PORT", None) or int(urllib.request.urlparse(L.OLLAMA_URL).port or 11434)
    pydir = Path(L.python_exe()).parent
    paths = {"docs": str(Path.home() / "Documents"), "settings": str(L.SETTINGS_FILE), "other": str(other / "secret.txt"),
             "runs": str(L.RUNS_DIR), "py": str(pydir), "port": port, "pid": os.getpid()}
    try:
        r = L.run_code("python", SANDBOX_BOUNDS.replace("__PATHS__", json.dumps(paths)))
    finally:
        _sh.rmtree(other, ignore_errors=True)
        (pydir / "mtai-sandbox-test.txt").unlink(missing_ok=True)    # only there if the sandbox could write
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\MTAI-sandbox-test")
        except OSError:
            pass
    if r.get("error") or not r.get("sandboxed"):
        return [R("Code sandbox", "sb-run", "Sandbox boundary test", "UNVERIFIED" if r.get("error") else "FAIL",
                  r.get("error") or "Ran outside the sandbox")]
    out = r.get("stdout") or ""
    rows = []
    for line in out.splitlines():
        if line.startswith("BOUND|"):
            _, cid, name, want, got, det = (line.split("|") + [""] * 6)[:6]
            ok = (want == "deny") == (got == "denied")
            # denied only counts when Windows refused it (not when the target just was not there)
            sure = want == "allow" or got == "allowed" or det.startswith(("PermissionError", "TimeoutError", "OSError"))
            rows.append(R("Code sandbox", "sb-" + cid, ("Cannot " if want == "deny" else "Can ") + name,
                          ("PASS" if sure else "UNVERIFIED") if ok else "FAIL", f"{got}: {det}"))
    tok = dict(ln.split("|", 2)[1:] for ln in out.splitlines() if ln.startswith("TOKEN|"))
    if tok:
        rows.append(R("Code sandbox", "sb-ac", "Runs as an AppContainer", "PASS" if tok.get("appcontainer") == "1" else "FAIL",
                      "TokenIsAppContainer=" + tok.get("appcontainer", "?")))
        privs = [p for p in tok.get("privs", "").split(";") if p]
        bad = [p for p in privs if p in DANGEROUS]
        rows.append(R("Code sandbox", "sb-priv", "No powerful Windows privileges", "FAIL" if bad else "PASS",
                      ("has " + ", ".join(bad)) if bad else "privileges: " + (", ".join(privs) or "none")))
        integ = tok.get("integrity", "")
        rows.append(R("Code sandbox", "sb-il", "Low integrity level", "PASS" if "S-1-16-4096" in integ else "UNVERIFIED",
                      integ or "not reported"))
        env = [e for e in tok.get("env", "").split(";") if e]
        rows.append(R("Code sandbox", "sb-env", "No API keys or tokens in its environment", "FAIL" if env else "PASS",
                      ", ".join(env) or "none"))
    if not rows:
        rows.append(R("Code sandbox", "sb-run", "Sandbox boundary test", "UNVERIFIED", (out + (r.get("stderr") or ""))[-200:]))
    return rows


NET_DLLS = (b"ws2_32.dll", b"winhttp.dll", b"wininet.dll", b"system.net.sockets", b"system.net.http")
PY_NET = {"_socket.pyd", "_ssl.pyd", "select.pyd", "_overlapped.pyd", "_asyncio.pyd", "_multiprocessing.pyd"}


def native_review():
    """Which native modules loaded in MTAI can open network connections without Python's socket module.
    The audit hook cannot see those; the connection watcher (MTAI's own process tree) is what covers them."""
    try:
        import psutil
        maps = {m.path for m in psutil.Process().memory_maps() if m.path}
    except Exception as e:
        return [R("Native code", "native", "Native modules review", "UNVERIFIED", f"{type(e).__name__}: {e}")]
    sysroot = os.environ.get("SystemRoot", r"C:\Windows").lower()
    hits = []
    for p in sorted(maps):
        low = p.lower()
        name = Path(p).name.lower()
        if low.startswith(sysroot) or not low.endswith((".pyd", ".dll")) or name in PY_NET:
            continue
        try:
            with open(p, "rb") as f:
                data = f.read(40_000_000).lower()
        except OSError:
            continue
        if any(d in data for d in NET_DLLS):
            hits.append(Path(p).name)
    return [R("Native code", "native", "Native modules that could open sockets outside the audit hook",
              "INFO", (", ".join(hits) or "none") + ". Python's own socket modules report to the audit hook; "
              "for everything else the connection watcher is the backstop.")]


def watch_checks(on):
    import backends as BK
    rows = []
    if not on:
        return rows
    since = NG.STATE.get("changed") or 0
    w = BK.WATCH
    mine = [e for e in BK.events_since(since) if e["kind"] == "outside connection" and e["who"] == "MTAI"]
    name = "No outside connection from MTAI's processes (watched)"
    if not w["on"] or not w["samples"]:
        rows.append(R("Connection watcher", "watch-mtai", name, "UNVERIFIED",
                      w.get("error") or "The watcher has not taken a sample yet"))
    else:
        rows.append(R("Connection watcher", "watch-mtai", name, "FAIL" if mine else "PASS",
                      ", ".join(f"{e['name']} {e['remote']}" for e in mine)[:200] if mine else
                      f"{w['samples']} looks at the TCP/UDP table since privacy mode went on, "
                      f"{(w.get('last') or {}).get('mtai', 0)} MTAI processes"))
    rc = NG.STATE.get("recheck")
    if rc is not None:
        if rc.get("error"):
            rows.append(R("Connection watcher", "recheck", "Open connections checked when privacy mode went on",
                          "UNVERIFIED", rc["error"]))
        else:
            left = [c for c in rc.get("conns", []) if c["who"] == "MTAI"]
            rows.append(R("Connection watcher", "recheck", "Open connections checked when privacy mode went on",
                          "FAIL" if left else "PASS",
                          ", ".join(f"{c['name']} {c['remote']}" for c in left)[:200] if left else
                          f"{NG.STATE.get('cut', 0)} stopped, none of MTAI's left open (looked again after stopping)"))
    return rows


_DISC = {"t": 0, "v": None}


def discover_cached(max_age=30):
    import backends as BK
    if not _DISC["v"] or time.time() - _DISC["t"] > max_age:
        _DISC.update(t=time.time(), v=BK.discover() + _mtai_browser())
    return _DISC["v"]


def _mtai_browser():
    """MTAI's own window as a program the firewall can block: only when it has its private WebView2 copy."""
    import webview_runtime as WR
    st = WR.status()
    if not st["current"]:
        return []
    exe = WR.private_exe()
    used = WR.in_use_by(os.getpid())
    return [{"id": "mtai-browser", "name": "MTAI's browser (its own WebView2 copy)", "running": used, "main": [exe],
             "exes": [{"path": exe, "name": Path(exe).name, "sources": ["MTAI's private copy of WebView2 " + st["current"]["version"]],
                       "pids": [], "running": used, "selectable": True, "default": True,
                       "note": None if used else "used from the next start of MTAI"}]}]


def _browser_native(good, fw):
    """WebView2's own sign-in code goes around the gate (seen connecting to outlook.office.com). Only a
    firewall rule on MTAI's private WebView2 copy blocks it."""
    import webview_runtime as WR
    mode = L.BROWSER.get("mode")
    name = "MTAI's browser cannot connect around the gate (Microsoft sign-in code in WebView2)"
    if mode not in ("webview2", "edge"):
        return []
    if mode == "edge":
        return [R("Browser", "br-native", name, "UNPROTECTED", "MTAI runs in Microsoft Edge (msedge.exe is shared with your "
                  "own Edge, so MTAI cannot firewall it). Its sign-in code can connect outside the gate.")]
    exe = WR.private_exe().lower()
    if not WR.in_use_by(os.getpid()):
        return [R("Browser", "br-native", name, "UNPROTECTED", "WebView2 contains Microsoft sign-in code (OneAuth) that uses "
                  "Windows' own networking, not the browser's, so the gate does not see it. Fix: Privacy diagnostics > "
                  "Local AI programs > run MTAI's window from its own WebView2 copy and block it.")]
    if exe not in good:
        return [R("Browser", "br-native", name, "UNPROTECTED", "The window runs from MTAI's own WebView2 copy, but there is no "
                  "firewall rule for it yet (Privacy diagnostics > Local AI programs).")]
    if not fw["firewall_on"]:
        return [R("Browser", "br-native", name, "FAIL", "Windows Firewall is off for the active network")]
    return [R("Browser", "br-native", name, "PASS", "The window runs from MTAI's own WebView2 copy, which Windows Firewall "
              "blocks everywhere except 127.0.0.1 and ::1 (the gate)")]


def backend_checks(on):
    """Local AI programs (Ollama etc.) and the optional Windows Firewall rules for them."""
    import backends as BK
    import firewall as FW
    rows = []
    if not on:
        return rows
    try:
        found = discover_cached()
        fw = FW.status()
    except Exception as e:
        return [R("Local AI programs", "bk", "Local AI programs", "UNVERIFIED", f"{type(e).__name__}: {e}")]
    good = {str(e["program"]).lower() for e in fw["ledger"] if e["ok"] and not e.get("probe")}
    events = BK.events_since(NG.STATE.get("changed") or 0)
    tested_template = False
    rows += _browser_native(good, fw)
    for b in found:
        if b["id"] == "mtai-browser":
            continue
        grp = f"{b['name']} (Windows Firewall)"
        want = [e for e in b["exes"] if e["default"]]
        if not want:
            continue
        missing = [e for e in want if e["path"].lower() not in good]
        title = f"{b['name']} cannot reach the internet"
        if missing:
            rows.append(R(grp, "bk-" + b["id"], title, "UNPROTECTED",
                          "Not restricted: " + ", ".join(e["name"] for e in missing) +
                          ". Turn on its Windows Firewall rules in Privacy diagnostics."))
        elif not fw["firewall_on"]:
            rows.append(R(grp, "bk-" + b["id"], title, "FAIL",
                          "Windows Firewall is off (or ignores local rules) for the active network, so the rules do nothing"))
        else:
            rows.append(R(grp, "bk-" + b["id"], f"{b['name']}: firewall rules in force", "PASS",
                          f"{len(want)} program(s) blocked outside 127.0.0.1 and ::1: " + ", ".join(e["name"] for e in want)))
            if not tested_template:
                tested_template = True
                port = getattr(L, "SERVER_PORT", None) or int(urllib.request.urlparse(L.OLLAMA_URL).port or 11434)
                rows += [R(*x) for x in FW.test_rule_template(port)]
            if b["id"] == "ollama" and b["running"]:
                exe = next((e["path"] for e in want if e["name"].lower() == "ollama.exe"), None)
                rows += [R(*x) for x in FW.test_ollama(L.OLLAMA_URL, exe)]
        paths = {x["path"].lower() for x in b["exes"]}
        leaks = [e for e in events if e["kind"] == "outside connection" and e["who"] == "backend"
                 and str(e.get("exe") or "").lower() in paths]
        if leaks:
            rows.append(R(grp, "bk-leak-" + b["id"], f"No outside connection from {b['name']} (watched)",
                          "UNPROTECTED" if missing else "FAIL",
                          ", ".join(f"{e['name']} {e['remote']}" for e in leaks)[:200]))
        kids = [e for e in events if e["kind"] == "unrestricted child process"]
        if kids and not missing:
            rows.append(R(grp, "bk-kids-" + b["id"], f"Programs started by {b['name']} are restricted", "UNPROTECTED",
                          ", ".join(f"{e['name']} ({e['exe']})" for e in kids)[:200]))
    if good and not tested_template and fw["firewall_on"]:      # only MTAI's browser copy is restricted
        port = getattr(L, "SERVER_PORT", None) or int(urllib.request.urlparse(L.OLLAMA_URL).port or 11434)
        rows += [R(*x) for x in FW.test_rule_template(port)]
    return rows


def browser_checks(on, probes, since):
    out = []
    mode = L.BROWSER.get("mode")
    o, v = attempt(_gate)
    if o == "ok":
        good = (" 403 " in v + " ") if on else (" 200 " in v + " ")
        out.append(R("Browser", "gate", "Gate proxy answer to CONNECT example.com:443", "PASS" if good else "FAIL", v))
    else:
        out.append(R("Browser", "gate", "Gate proxy answer", "FAIL", f"{type(v).__name__}: {v}"))
    if mode in ("webview2", "edge"):
        try:
            procs = NG.browser_processes(L.BROWSER["gate"])
            out.append(R("Browser", "browser-args", "Browser processes started behind the gate",
                         "PASS" if procs else "FAIL",
                         f"{len(procs)} {mode} process(es) carry --proxy-server for the gate" if procs
                         else "No browser process carries the gate's proxy switch"))
        except Exception as e:
            out.append(R("Browser", "browser-args", "Browser processes started behind the gate", "UNVERIFIED", str(e)[:200]))
    elif mode == "system":
        out.append(R("Browser", "browser-args", "Browser behind the gate", "FAIL",
                     "MTAI runs in your normal browser (no pywebview, no Edge): MTAI cannot keep it offline"))
    else:
        out.append(R("Browser", "browser-args", "Browser behind the gate", "UNVERIFIED", "No MTAI window is open"))
    blocks = [e for e in NG.BLOCKED if e["t"] >= since and e["kind"] == "browser"]
    fwd = [e for e in (NG.GATE.recent if NG.GATE else []) if e["t"] >= since]
    for p in probes or []:
        host = str(p.get("host", ""))
        # the gate's log must match this probe's host inside this probe's own time window
        try:
            lo, hi = float(p.get("t0")) / 1000 - 0.5, float(p.get("t1")) / 1000 + 1.5
        except (TypeError, ValueError):
            lo, hi = since, time.time()
        gate_block = any(e["target"].rsplit(":", 1)[0] == host and lo <= e["t"] <= hi for e in blocks)
        gate_fwd = any(e["host"] == host and lo <= e["t"] <= hi for e in fwd)
        where = str(p.get("where", "page"))
        name = f"{p.get('name', p.get('id'))} ({where})"
        if on:
            if p.get("ok"):
                res, det = "FAIL", "Loaded: " + str(p.get("detail", ""))[:150]
            elif p.get("csp"):
                res, det = "PASS", "Refused by the privacy CSP" + (" (the gate saw it too)" if gate_block else "") + ": " + str(p.get("csp"))[:140]
            elif gate_block:
                res, det = "PASS", "Refused by the gate: " + str(p.get("detail", ""))[:150]
            elif p.get("never_proxied"):
                res, det = ("PASS", str(p.get("detail", ""))[:200])
            else:
                res, det = "UNVERIFIED", "Failed, but the gate did not see it: " + str(p.get("detail", ""))[:150]
        else:
            reused = not gate_fwd and not p.get("csp") and any(e["host"] == host for e in fwd)
            if p.get("ok") or gate_fwd:
                res, det = "PASS", ("Loaded" if p.get("ok") else "Went out through the gate") + ": " + str(p.get("detail", ""))[:140]
            elif reused:
                res, det = "PASS", ("No privacy CSP, and the browser reused the connection the gate opened for this host "
                                    "a moment earlier: " + str(p.get("detail", ""))[:100])
            elif gate_block or p.get("csp"):
                res, det = "FAIL", "Still blocked with privacy mode off"
            elif p.get("never_proxied"):
                res, det = ("PASS", str(p.get("detail", ""))[:200])
            else:
                res, det = "UNVERIFIED", "Did not load: " + str(p.get("detail", ""))[:150]
        out.append(R("Browser", "br-" + str(p.get("id")) + "-" + where, name, res, det))
    return out


ENGINE_PROBE = ("import socket, sys; sys.path.insert(0, sys.argv[1]); import netguard; "
                "netguard.install(always=True, component_name='Image engine')\n"
                "try:\n    socket.create_connection(('1.1.1.1', 443), timeout=5); print('CONNECTED')\n"
                "except Exception as e:\n"
                "    print('BLOCKED' if isinstance(e, netguard.Blocked) else 'FAILED ' + type(e).__name__)")


def _engine_guard():
    """The image worker's guard, in the engine's own Python, the same way the worker installs it."""
    py = L.IG.engine_python()
    if not Path(py).is_file():
        return "UNVERIFIED", "The image engine is not installed"
    with NG.allow("self-test: image engine guard"):
        r = subprocess.run([str(py), "-c", ENGINE_PROBE, str(L.APP_DIR)], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = (r.stdout + r.stderr).strip()
    if "BLOCKED" in out:
        return "PASS", "The engine's Python refused 1.1.1.1:443 by itself (both modes)"
    if "CONNECTED" in out:
        return "FAIL", "The engine's Python reached 1.1.1.1:443"
    return "UNVERIFIED", out[-200:]


def model_checks(on):
    out = [R("Local models", "engine-guard", "Image engine blocks outside connections", *_engine_guard())]
    o, v = attempt(lambda: L.http_json(L.OLLAMA_URL + "/api/version", timeout=2).get("version"))
    out.append(R("Local models", "ollama-local", "Ollama on 127.0.0.1 still answers",
                 "PASS" if o == "ok" else ("FAIL" if o == "blocked" else "UNVERIFIED"),
                 f"Ollama {v}" if o == "ok" else f"{type(v).__name__}: {v}"[:160]))
    if on:
        out.append(R("Cloud and downloads", "cloud-chat", "Chat with a cloud model", *_cloud_refused()))
        try:
            L.pull_model("tinyllama", lambda e: None)
            out.append(R("Cloud and downloads", "ollama-pull", "Ollama model download", "FAIL", "Not refused"))
        except ValueError as e:
            out.append(R("Cloud and downloads", "ollama-pull", "Ollama model download", "PASS", "Refused: " + str(e)[:120]))
        try:
            L.web_get("https://example.com")
            out.append(R("Cloud and downloads", "web", "Web search / deep research page fetch", "FAIL", "Not refused"))
        except ValueError as e:
            out.append(R("Cloud and downloads", "web", "Web search / deep research page fetch", "PASS", "Refused: " + str(e)[:120]))
        o, v = attempt(lambda: L.P._http("https://api.openai.com/v1/models", timeout=8))
        out.append(R("Cloud and downloads", "cloud-api", "Cloud API request from the providers module (no key sent)", *grade(on, o, v)))
        o, v = attempt(lambda: L.IG._hf_files("stabilityai/sd-turbo"))
        out.append(R("Cloud and downloads", "hf", "Image model download list from Hugging Face", *grade(on, o, v)))
    return out


# ---------------------------------------------------------------- running --

def run(browser=None, since=None):
    """One full self-test in the current mode. `browser` = probe results from the page."""
    with _lock:
        on = bool(L.PRIVACY["on"])
        t0 = time.time()
        since = since or (browser or {}).get("since") or t0 - 60
        if isinstance(since, (int, float)) and since > 1e12:
            since /= 1000                                       # the page sends milliseconds
        probes = (browser or {}).get("probes") if isinstance(browser, dict) else None
        results = []
        with NG.component("Self-test"):
            parts = [python_checks, process_checks, code_checks, model_checks, watch_checks, backend_checks]
            if on:
                parts += [lambda _on: sandbox_bounds(), lambda _on: native_review()]
            for part in parts:
                try:
                    results += part(on)
                except Exception as e:
                    results.append(R("Self-test", part.__name__, part.__name__, "UNVERIFIED", f"Test crashed: {type(e).__name__}: {e}"))
            results += browser_checks(on, probes, since)
        counts = {k: sum(1 for r in results if r["result"] == k) for k in RESULTS}
        run_ = {"t": time.time(), "seconds": round(time.time() - t0, 1), "privacy": on, "browser_probes": bool(probes),
                "counts": counts, "results": results}
        LAST["run"] = run_
        if on and counts["FAIL"] == 0 and counts["UNVERIFIED"] == 0 and counts["UNPROTECTED"] == 0 and probes:
            LAST["ok_run"] = {k: run_[k] for k in ("t", "counts", "browser_probes")}
        try:
            L.write_json(_file(), {"run": run_, "ok_run": LAST["ok_run"]})
        except Exception:
            pass
        return run_


def suite_summary():
    f = L.DATA_DIR / "privacy-tests" / "latest.json"
    try:
        d = json.loads(f.read_text("utf-8"))
        return {"t": d.get("t"), "counts": d.get("counts"), "phases": d.get("phase_counts")}
    except Exception:
        return None


COMPONENTS = [  # name, how, result groups (or "#row id") that prove it
    ("MTAI (Python)", "Audit hook refuses non-loopback sockets, DNS, UDP, listening and new programs; a watcher reads "
     "the connection table for anything that goes around it", ["Python in MTAI", "Other programs", "Connection watcher"]),
    ("Browser (WebView2)", "All traffic forced through the gate, which refuses it; no DNS, QUIC or WebRTC UDP", ["Browser"]),
    ("Code runs", "Python and PowerShell in an offline AppContainer that can only use its own run folder; JavaScript refused",
     ["Code runs", "Code sandbox"]),
    ("Image engine", "Own guard: no outside connections and no new programs, in both modes", ["#engine-guard"]),
    ("Cloud AI, web, downloads", "Refused by MTAI before any request is made", ["Cloud and downloads"]),
]


def _state(rows):
    if not rows:
        return "unverified"
    res = {r["result"] for r in rows}
    return ("failed" if "FAIL" in res else "unprotected" if "UNPROTECTED" in res
            else "unverified" if "UNVERIFIED" in res else "protected")


def status():
    import backends as BK
    on = bool(L.PRIVACY["on"])
    last = LAST["run"]
    changed = NG.STATE.get("changed") or 0
    fresh = bool(last and last.get("privacy") == on and last["t"] >= changed)
    # outside connections seen by the watcher after the last test: MTAI's own, or of a program MTAI restricted
    live = [e for e in BK.events_since(max(changed, (last or {}).get("t", 0)))
            if e["kind"] == "outside connection" and (e["who"] == "MTAI" or e.get("restricted"))] if on else []
    rows = ((last or {}).get("results") or []) if fresh else []
    comps = []
    for name, how, groups in COMPONENTS:
        mine = [r for r in rows if r["group"] in groups or ("#" + r["id"]) in groups]
        comps.append({"name": name, "how": how, "state": "off" if not on else _state(mine) if fresh else "unchecked"})
    backend_groups = sorted({r["group"] for r in rows if r["group"].endswith("(Windows Firewall)")})
    for g in backend_groups:
        comps.append({"name": g.replace(" (Windows Firewall)", ""), "backend": True, "state": _state([r for r in rows if r["group"] == g]),
                      "how": "Separate program on this PC; blocked outside 127.0.0.1 and ::1 only by MTAI's optional "
                             "Windows Firewall rules"})
    if on and not fresh:
        comps.append({"name": "Local AI programs", "backend": True, "state": "unchecked",
                      "how": "Separate programs (Ollama, LM Studio...); blocked only by the optional Windows Firewall rules"})
    if live:
        comps[0]["state"] = "failed"
    c = (last or {}).get("counts") or {}
    if not on:
        level = "off"
    elif not fresh:
        level = "unchecked"
    elif c.get("FAIL") or live:
        level = "failed"
    elif (c.get("UNVERIFIED") or c.get("UNPROTECTED") or not last.get("browser_probes")
          or any(x["state"] != "protected" for x in comps)):
        level = "partly"
    else:
        level = "verified"
    return {"on": on, "level": level, "fresh": fresh, "changed": changed, "browser": L.BROWSER.get("mode"),
            "gate": NG.GATE.port if NG.GATE else None, "last": last, "last_ok": LAST["ok_run"], "live_leaks": live,
            "suite": suite_summary(), "blocked": list(NG.BLOCKED)[-150:], "counts": dict(NG.COUNTS),
            "watch": {k: BK.WATCH[k] for k in ("on", "since", "samples", "error")},
            "fw_rules": _fw_count(), "components": comps, "limits": LIMITS}


def _fw_count():
    try:
        import firewall as FW
        return len(FW.ledger()["rules"])
    except Exception:
        return 0


def SB_ok():
    try:
        import sandbox
        return sandbox.available()
    except Exception:
        return False
