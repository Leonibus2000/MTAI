"""
Optional Windows Firewall integration for privacy mode: blocks the internet for local AI
backends (Ollama, LM Studio, llama.cpp, ComfyUI...) that run as their own programs.

Rules of the road:
  * Only programs found by backends.discover() (real paths, never guessed) and picked by
    the user. MTAI shows the exact list and asks before anything happens; Windows then
    shows its own administrator prompt (UAC). Nothing is changed without both.
  * One outbound Block rule per program, remote addresses = everything except 127.0.0.0/8
    and ::1, so the program keeps talking to MTAI on this PC. Name MTAI-Privacy-<hash of
    path>, group "MTAI Privacy". Firewall profiles and other rules are never changed.
  * Every rule name goes into data/firewall-rules.json BEFORE it is made, so rules can be
    found and removed after a crash. Removal deletes only names in that list whose group
    is "MTAI Privacy" (fwhelper.ps1 checks both).
  * The rule template is tested on this PC with a probe (a copy of Windows' curl.exe under
    its own rule): direct IPv4, host name, IPv6, local network must fail, 127.0.0.1 and ::1
    must still work. The real backends are tested too where possible (Ollama pull).

Windows limits worth knowing: name lookups are made by Windows' DNS Client service for
every program, so a restricted program can still have a host name looked up (no
connection follows); rules apply to new connections, so open IPv4 connections are
closed by the helper and IPv6 ones are reported; a firewall turned off or a policy that
ignores local rules makes the rules do nothing (both are checked).
"""
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import time
from ctypes import wintypes as W
from pathlib import Path

import netguard as NG

GROUP = "MTAI Privacy"
REMOTE = ["0.0.0.0-126.255.255.255", "128.0.0.0-255.255.255.255", "::", "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"]
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DATA = None
APP = None


class Declined(RuntimeError):
    pass


class FwError(RuntimeError):
    pass


def init(data_dir, app_dir):
    global DATA, APP
    DATA, APP = Path(data_dir), Path(app_dir)


def _ledger_file():
    return DATA / "firewall-rules.json"


def ledger():
    try:
        d = json.loads(_ledger_file().read_text("utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("rules"), list) else {"rules": []}
    except Exception:
        return {"rules": []}


def _save(led):
    f = _ledger_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(led, indent=1), "utf-8")
    os.replace(tmp, f)


def rule_name(path):
    return "MTAI-Privacy-" + hashlib.sha1(str(Path(path)).lower().encode("utf-8")).hexdigest()[:16]


def probe_path():
    return DATA / "fwprobe" / "mtai-fwprobe.exe"


def ensure_probe():
    """A copy of Windows' curl.exe at MTAI's own path, so a rule can be tested without touching curl."""
    src = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
    if not src.is_file():
        raise FwError("Windows' curl.exe is missing, so the rule cannot be tested.")
    dst = probe_path()
    if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return dst


# ------------------------------------------------------------- read state --

PS_STATE = r"""
$ErrorActionPreference = 'SilentlyContinue'
$rules = @(Get-NetFirewallRule -PolicyStore ActiveStore -Group 'MTAI Privacy')
$out = @()
foreach ($r in $rules) {
  $app = ($r | Get-NetFirewallApplicationFilter).Program
  $adr = @(($r | Get-NetFirewallAddressFilter).RemoteAddress)
  $out += [ordered]@{ name = $r.Name; enabled = "$($r.Enabled)"; action = "$($r.Action)"; direction = "$($r.Direction)";
                      profile = "$($r.Profile)"; program = $app; remote = $adr }
}
$prof = @(Get-NetFirewallProfile -PolicyStore ActiveStore | ForEach-Object { [ordered]@{ name = $_.Name; enabled = "$($_.Enabled)"; local_rules = "$($_.AllowLocalFirewallRules)" } })
$cats = @(Get-NetConnectionProfile | ForEach-Object { "$($_.NetworkCategory)" })
[ordered]@{ rules = $out; profiles = $prof; categories = $cats } | ConvertTo-Json -Depth 5 -Compress
"""


def state():
    """What Windows really has: MTAI's rules in the active policy, firewall profiles, network categories."""
    with NG.allow("read Windows Firewall state"):
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_STATE], capture_output=True,
                           text=True, timeout=60, creationflags=NOWIN, encoding="utf-8", errors="replace")
    try:
        d = json.loads(r.stdout.strip() or "{}")
    except ValueError:
        raise FwError("Could not read the Windows Firewall state: " + (r.stderr or r.stdout)[-200:])
    rules = d.get("rules") or []
    if isinstance(rules, dict):
        rules = [rules]
    for x in rules:
        if isinstance(x.get("remote"), str):
            x["remote"] = [x["remote"]]
    d["rules"] = rules
    for k in ("profiles", "categories"):
        if isinstance(d.get(k), (dict, str)):
            d[k] = [d[k]]
    active = {"DomainAuthenticated": "Domain", "Private": "Private", "Public": "Public"}
    want = {active.get(c, c) for c in d.get("categories") or []}
    d["active_profiles_on"] = all(str(p.get("enabled")).lower() == "true" and str(p.get("local_rules")).lower() != "false"
                                  for p in d.get("profiles") or [] if p.get("name") in want) and bool(want)
    return d


def _rule_ok(rule, program):
    rem = sorted(str(a).lower() for a in rule.get("remote") or [])
    # Windows writes the ranges back in its own spelling; check what matters: loopback is not in them
    covers_loop = any(a in ("any", "127.0.0.1", "127.0.0.0/8", "::1") or a.startswith("127.") for a in rem)
    return (str(rule.get("enabled")).lower() == "true" and rule.get("action") == "Block" and rule.get("direction") == "Outbound"
            and str(rule.get("program") or "").lower() == str(program).lower() and len(rem) >= 3 and not covers_loop)


def status():
    led = ledger()
    try:
        st = state()
        err = None
    except Exception as e:
        st, err = {"rules": [], "profiles": [], "active_profiles_on": False}, str(e)
    have = {r["name"]: r for r in st["rules"]}
    rows = []
    for e in led["rules"]:
        r = have.get(e["name"])
        rows.append({**e, "present": bool(r), "ok": bool(r) and _rule_ok(r, e["program"]), "rule": r})
    strangers = [n for n in have if n not in {e["name"] for e in led["rules"]}]
    return {"ledger": rows, "profiles": st.get("profiles"), "categories": st.get("categories"),
            "firewall_on": st.get("active_profiles_on"), "error": err, "unknown_group_rules": strangers,
            "pending": led.get("pending")}


# --------------------------------------------------------------- elevation --

class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("fMask", W.ULONG), ("hwnd", W.HWND), ("lpVerb", W.LPCWSTR), ("lpFile", W.LPCWSTR),
                ("lpParameters", W.LPCWSTR), ("lpDirectory", W.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", W.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", W.LPCWSTR), ("hkeyClass", W.HKEY), ("dwHotKey", W.DWORD),
                ("hIconOrMonitor", W.HANDLE), ("hProcess", W.HANDLE)]


def run_elevated(job, timeout=240):
    """Run fwhelper.ps1 as administrator. Windows shows the UAC prompt; saying No raises Declined."""
    jobs = DATA / "firewall-jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    f = jobs / f"job-{int(time.time() * 1000)}.json"
    f.write_text(json.dumps(job), "utf-8")
    res = Path(str(f) + ".result.json")
    ps = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    params = f'-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "{APP / "fwhelper.ps1"}" -Job "{f}"'
    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = 0x40 | 0x100                     # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    sei.lpVerb, sei.lpFile, sei.lpParameters, sei.nShow = "runas", str(ps), params, 0
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        e = ctypes.get_last_error()
        f.unlink(missing_ok=True)
        if e == 1223:
            raise Declined("The administrator prompt was declined, so nothing was changed.")
        raise FwError(f"Windows did not start the firewall helper ({ctypes.FormatError(e).strip()}).")
    k32 = ctypes.WinDLL("kernel32")
    k32.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    k32.WaitForSingleObject(sei.hProcess, timeout * 1000)
    k32.CloseHandle(sei.hProcess)
    try:
        out = json.loads(res.read_text("utf-8-sig"))
    except Exception:
        raise FwError("The firewall helper did not report back.")
    finally:
        f.unlink(missing_ok=True)
        res.unlink(missing_ok=True)
    for k, v in list(out.items()):           # PowerShell 5.1 writes some arrays as {"value": [...], "Count": n}
        if isinstance(v, dict) and "value" in v:
            v = v["value"]
        if k in ("created", "existed", "removed", "missing", "closed", "left", "errors"):
            out[k] = [] if v is None else v if isinstance(v, list) else [v]
    return out


# ------------------------------------------------------------- operations --

def apply(programs, with_probe=True, close=True):
    """Make the rules (one UAC prompt). programs: real paths picked by the user."""
    progs = []
    for p in programs:
        p = str(Path(p))
        if not Path(p).is_file():
            raise FwError(f"{p} does not exist.")
        if p.lower().startswith(os.environ.get("SystemRoot", r"C:\Windows").lower() + os.sep):
            raise FwError(f"{p} is part of Windows; MTAI does not restrict it.")
        progs.append(p)
    if with_probe:
        progs.append(str(ensure_probe()))
    led = ledger()
    known = {e["name"] for e in led["rules"]}
    for p in progs:                                     # written down before Windows is asked
        n = rule_name(p)
        if n not in known:
            led["rules"].append({"name": n, "program": p, "probe": p == str(probe_path()), "made": time.time(), "state": "requested"})
            known.add(n)
    led["pending"] = {"action": "apply", "t": time.time()}
    _save(led)
    try:
        out = run_elevated({"action": "apply", "close": close,
                            "rules": [{"name": rule_name(p), "program": p} for p in progs]})
    except Exception:
        _reconcile()
        raise
    _reconcile()
    return out


def remove(names=None):
    """Delete MTAI's rules (one UAC prompt). Only names in the ledger are ever sent."""
    led = ledger()
    mine = [e["name"] for e in led["rules"]]
    names = [n for n in (names or mine) if n in mine]
    if not names:
        return {"ok": True, "removed": [], "missing": []}
    led["pending"] = {"action": "remove", "t": time.time()}
    _save(led)
    try:
        out = run_elevated({"action": "remove", "names": names})
    finally:
        _reconcile()
    return out


def _reconcile():
    """Make the ledger match Windows: keep every name that still exists, drop names that are gone."""
    led = ledger()
    try:
        have = {r["name"] for r in state()["rules"]}
    except Exception:
        return led
    keep = []
    for e in led["rules"]:
        if e["name"] in have:
            e["state"] = "active"
            keep.append(e)
    led["rules"] = keep
    led.pop("pending", None)
    _save(led)
    return led


def restricted_programs():
    return [e["program"] for e in ledger()["rules"]]


# ------------------------------------------------------------------- tests --

def _curl(exe, *args, timeout=12):
    with NG.allow("firewall test"):
        r = subprocess.run([str(exe), "-sS", "-o", "NUL", "-w", "%{http_code}", "-m", "8", *args], capture_output=True,
                           text=True, timeout=timeout, creationflags=NOWIN)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


PROBES = [  # (id, name, curl args, should work while restricted)
    ("fw-ip4", "Direct IPv4 (https://1.1.1.1)", ["https://1.1.1.1"], False),
    ("fw-host", "Host name (https://example.com: DNS + connect)", ["https://example.com"], False),
    ("fw-ip6", "Direct IPv6 (https://[2606:4700:4700::1111])", ["-g", "https://[2606:4700:4700::1111]"], False),
    ("fw-lan", "Local network (http://192.168.1.1)", ["http://192.168.1.1"], False),
    ("fw-loop4", "Loopback 127.0.0.1 (MTAI on this PC)", None, True),
    ("fw-loop6", "Loopback ::1", None, True),
]


def _loop6_server():
    import http.server
    import socket as _s
    import threading as _t

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    class S6(http.server.HTTPServer):
        address_family = _s.AF_INET6
    try:
        srv = S6(("::1", 0), H)
    except OSError:
        return None
    _t.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_rule_template(loop_port):
    """Proves on this Windows what the rule does: the probe (under its own MTAI rule) against plain curl."""
    rows = []
    probe = probe_path()
    sys_curl = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
    st = status()
    entry = next((e for e in st["ledger"] if e.get("probe")), None)
    if not probe.is_file() or not entry or not entry["ok"]:
        return [("Firewall rule test", "fw-template", "Rule template tested with the probe", "UNVERIFIED",
                 "The probe rule is not in place (apply the firewall rules first)")]
    v6 = _loop6_server()                     # MTAI and Ollama listen on 127.0.0.1 only: a small ::1 listener for the test
    for cid, name, args, should in PROBES:
        if args is None:
            if cid == "fw-loop4":
                args = ["-g", f"http://127.0.0.1:{loop_port}/"]
            elif v6:
                args = ["-g", f"http://[::1]:{v6.server_address[1]}/"]
            else:
                rows.append(("Firewall rule test", cid, name, "UNVERIFIED", "Could not open a test listener on ::1"))
                continue
        rc, code, err = _curl(probe, *args)
        crc, ccode, cerr = _curl(sys_curl, *args)
        worked, control = rc == 0, crc == 0
        if should:
            res = "PASS" if worked else ("FAIL" if control else "UNVERIFIED")
            det = f"restricted probe: {'answered ' + code if worked else err[:90]}; plain curl: {'answered' if control else cerr[:60]}"
        else:
            if worked:
                res, det = "FAIL", f"the restricted probe got through (HTTP {code})"
            elif not control:
                res, det = "UNVERIFIED", f"plain curl fails too, so this PC cannot reach it anyway: {cerr[:90]}"
            else:
                res, det = "PASS", f"blocked ({err[:90]}); plain curl got HTTP {ccode}"
        rows.append(("Firewall rule test", cid, name, res, det))
    if v6:
        v6.shutdown()
        v6.server_close()
    # name lookups go through the Windows DNS Client service, not the program: a Windows limitation, shown as such
    rc, code, err = _curl(probe, "--connect-timeout", "4", "http://mtai-dns-check.example.com/")
    resolved = "Could not resolve" not in err
    rows.append(("Firewall rule test", "fw-dns", "Name lookup by a restricted program",
                 "INFO", ("Windows still looks host names up for it (DNS Client service), the connection is blocked: " + err[:80])
                 if resolved else "Name lookup failed: " + err[:80]))
    return rows


def test_ollama(ollama_url, ollama_exe):
    """The real backend: ask Ollama to fetch a model name that does not exist, by host name and by IP.
    Restricted, Ollama must fail with a socket/permission error before it gets an answer from the registry."""
    rows = []
    st = status()
    entry = next((e for e in st["ledger"] if str(e["program"]).lower() == str(ollama_exe or "").lower()), None)
    if not ollama_exe or not entry or not entry["ok"]:
        return [("Ollama (Windows Firewall)", "ol-rule", "Ollama restricted by a firewall rule", "UNVERIFIED",
                 "No working MTAI rule for ollama.exe")]
    import urllib.request
    for cid, name, model in [("ol-host", "Ollama reaches its registry (host name)", "mtai-selftest/does-not-exist:1"),
                             ("ol-ip", "Ollama reaches a direct IP (1.1.1.1)", "1.1.1.1/mtai-selftest/does-not-exist:1")]:
        req = urllib.request.Request(ollama_url + "/api/pull", data=json.dumps({"model": model, "stream": False}).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8", "replace")
        except Exception as e:
            body = getattr(e, "read", lambda: b"")().decode("utf-8", "replace") or str(e)
        low = body.lower()
        blocked = any(w in low for w in ("forbidden by its access permissions", "zugriffsberechtigungen", "access permissions",
                                         "wsaeacces", "an attempt was made to access a socket",
                                         "zugriffsrechte des sockets", "10013"))
        answered = any(w in low for w in ("file does not exist", "manifest unknown", "not found", "unauthorized", "pull access denied"))
        if blocked:
            rows.append(("Ollama (Windows Firewall)", cid, name, "PASS", "Windows refused Ollama's connection: " + body[:140]))
        elif answered:
            rows.append(("Ollama (Windows Firewall)", cid, name, "FAIL", "Ollama got an answer from outside: " + body[:140]))
        else:
            rows.append(("Ollama (Windows Firewall)", cid, name, "UNVERIFIED", body[:160]))
    return rows
