"""
MTAI privacy mode: a private copy of the WebView2 runtime for MTAI's own window.

Why: the WebView2 runtime contains Microsoft code (OneAuth, the Edge sign-in and Copilot
parts) that opens connections with Windows' own HTTP stack. Those connections ignore the
browser switches MTAI uses (the gate proxy and the "resolve nothing" rule), so MTAI's
browser was seen connecting to outlook.office.com while privacy mode was on.

msedgewebview2.exe in Program Files is shared by every program that uses WebView2 (Windows
Search, other apps), so a firewall rule for it would cut them off too. Running MTAI's window
from its own copy gives MTAI's browser a program path of its own, which a Windows Firewall
rule can then block everywhere except 127.0.0.1/::1 (where the gate is), without touching
any other program.

Layout (fixed path, so the firewall rule stays valid across updates):
    data/webview-runtime/current/   the copy in use (msedgewebview2.exe and its files)
    data/webview-runtime/next/      a newer copy, made in the background while MTAI runs;
                                    it replaces current at the next start, before the window opens
The copy is only made after the user turned it on (Privacy diagnostics). Nothing in Windows
is changed: only MTAI's data folder, plus read/execute rights for Windows' AppContainer
groups on that folder (the browser's sandboxed renderers need them).
"""
import json
import os
import shutil
import subprocess
import threading
import time
import winreg
from pathlib import Path

import netguard as NG

WEBVIEW2_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
EXE = "msedgewebview2.exe"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ROOT = None
JOB = {"running": False, "done": 0, "total": 0, "error": None, "version": None}
_lock = threading.Lock()


def init(data_dir):
    global ROOT
    ROOT = Path(data_dir) / "webview-runtime"


def system_runtime():
    """The WebView2 runtime Windows has installed (from EdgeUpdate's own registry entry), or None."""
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for base in (r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients", r"SOFTWARE\Microsoft\EdgeUpdate\Clients"):
            try:
                with winreg.OpenKey(hive, base + "\\" + WEBVIEW2_ID) as k:
                    loc = winreg.QueryValueEx(k, "location")[0]
                    ver = winreg.QueryValueEx(k, "pv")[0]
            except OSError:
                continue
            folder = Path(loc) / ver
            if (folder / EXE).is_file():
                return {"version": ver, "folder": str(folder)}
    return None


def _meta(d):
    try:
        return json.loads((d / "mtai-runtime.json").read_text("utf-8"))
    except Exception:
        return None


def current():
    return ROOT / "current"


def private_exe():
    return str(current() / EXE)


def status():
    sysrt = system_runtime()
    cur, nxt = _meta(current()), _meta(ROOT / "next")
    return {"system": sysrt, "current": cur, "next": nxt, "exe": private_exe() if cur else None,
            "outdated": bool(sysrt and cur and cur.get("version") != sysrt["version"] and not (nxt and nxt.get("version") == sysrt["version"])),
            "job": dict(JOB), "size_mb": _size_mb(sysrt["folder"]) if sysrt and not cur else None}


_SIZE = {}


def _size_mb(folder):
    if folder not in _SIZE:
        _SIZE[folder] = round(sum(f.stat().st_size for f in Path(folder).rglob("*") if f.is_file()) / 1e6)
    return _SIZE[folder]


def promote():
    """At start-up, before the window exists: a finished newer copy replaces the old one."""
    nxt = ROOT / "next"
    if not _meta(nxt):
        return False
    cur = current()
    if cur.exists():
        old = ROOT / f"old-{int(time.time())}"
        try:
            cur.rename(old)                   # fails if something still runs from it: then keep the old copy
        except OSError:
            return False
        shutil.rmtree(old, ignore_errors=True)
    nxt.rename(cur)
    return True


def _grant(folder):
    # the browser's renderers run as AppContainers and must be able to read the runtime
    with NG.allow("let the WebView2 sandbox read MTAI's runtime copy"):
        subprocess.run(["icacls", str(folder), "/grant", "*S-1-15-2-1:(OI)(CI)(RX)", "*S-1-15-2-2:(OI)(CI)(RX)", "/T", "/C", "/Q"],
                       capture_output=True, timeout=300, creationflags=NOWIN)


def _copy(src, dst, version):
    files = [f for f in Path(src).rglob("*") if f.is_file()]
    JOB.update(total=len(files), done=0)
    tmp = dst.with_name(dst.name + ".partial")
    shutil.rmtree(tmp, ignore_errors=True)
    for f in files:
        t = tmp / f.relative_to(src)
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, t)
        JOB["done"] += 1
    _grant(tmp)
    (tmp / "mtai-runtime.json").write_text(json.dumps({"version": version, "from": str(src), "made": time.time()}), "utf-8")
    shutil.rmtree(dst, ignore_errors=True)
    tmp.rename(dst)


def make_copy(background=True):
    """Copy the installed runtime: into current/ the first time, into next/ when current is in use."""
    sysrt = system_runtime()
    if not sysrt:
        raise RuntimeError("No WebView2 runtime is installed for all users or this user.")
    with _lock:
        if JOB["running"]:
            return dict(JOB)
        JOB.update(running=True, error=None, version=sysrt["version"], done=0, total=0)
    dst = ROOT / ("next" if _meta(current()) else "current")

    def work():
        try:
            ROOT.mkdir(parents=True, exist_ok=True)
            _copy(sysrt["folder"], dst, sysrt["version"])
        except Exception as e:
            JOB["error"] = f"{type(e).__name__}: {e}"
        finally:
            JOB["running"] = False
    if background:
        threading.Thread(target=work, daemon=True, name="webview-runtime-copy").start()
    else:
        work()
    return dict(JOB)


def remove_copy():
    """Delete MTAI's copies (only works while MTAI's window does not run from them)."""
    errs = []
    for d in ROOT.glob("*") if ROOT and ROOT.exists() else []:
        try:
            shutil.rmtree(d)
        except OSError as e:
            errs.append(f"{d.name}: {e.strerror}")
    return errs


def in_use_by(pid):
    """Is the window of this MTAI process running from the private copy right now?"""
    try:
        import psutil
        exe = private_exe().lower()
        for c in psutil.Process(pid).children(recursive=True):
            try:
                if c.name().lower() == EXE and (c.exe() or "").lower() == exe:
                    return True
            except psutil.Error:
                continue
    except Exception:
        pass
    return False
