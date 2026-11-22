"""
Local AI backends (Ollama, LM Studio, llama.cpp, ComfyUI, AUTOMATIC1111, KoboldCpp) as
programs on this PC: where their executables really are, which processes run, and what
they connect to. Used by privacy mode (firewall.py restricts them, privacy_check.py tests).

Discovery never guesses a path. An executable is listed only when one of these shows it:
  * a running process (its real image path from Windows),
  * the process that listens on a backend's port (11434, 1234, 8080, 8188, 7860, 5001),
  * the program search path (PATH),
  * an uninstall entry in the registry (InstallLocation / DisplayIcon),
and the file exists. Every other .exe in the same install folder is listed as an
alternative executable (Ollama's tray app, its bundled llama-server.exe and so on),
because those can make their own connections. A shared interpreter (python.exe that is
not inside the backend's folder) is never offered: blocking it would hit other programs.

watch() runs while privacy mode is on: every few seconds it reads the TCP/UDP table
(psutil) and records any outside connection of MTAI's own process tree or of a backend
process tree, plus backend child processes whose executable is not restricted.
"""
import collections
import ipaddress
import os
import shutil
import threading
import time
from pathlib import Path

try:
    import psutil
except ImportError:                          # the watcher and process discovery need it
    psutil = None

BACKENDS = [
    {"id": "ollama", "name": "Ollama", "exes": ["ollama.exe", "ollama app.exe"], "ports": [11434],
     "which": ["ollama"], "reg": ["ollama"]},
    {"id": "lmstudio", "name": "LM Studio", "exes": ["lm studio.exe", "lms.exe"], "ports": [1234],
     "which": ["lms"], "reg": ["lm studio", "lm-studio"]},
    {"id": "llamacpp", "name": "llama.cpp", "exes": ["llama-server.exe", "llama-cli.exe"], "ports": [8080],
     "which": ["llama-server", "llama-cli"], "reg": []},
    {"id": "koboldcpp", "name": "KoboldCpp", "exes": ["koboldcpp.exe", "koboldcpp_cu12.exe"], "ports": [5001],
     "which": ["koboldcpp"], "reg": []},
    {"id": "comfyui", "name": "ComfyUI", "exes": ["comfyui.exe"], "ports": [8188], "which": [], "reg": ["comfyui"],
     "cmd": ["comfyui"]},
    {"id": "a1111", "name": "AUTOMATIC1111 / Forge", "exes": [], "ports": [7860], "which": [], "reg": [],
     "cmd": ["stable-diffusion-webui", "webui.py", "launch.py"]},
]
SHARED = {"python.exe", "pythonw.exe", "py.exe", "node.exe", "cmd.exe", "powershell.exe", "pwsh.exe"}
HARMLESS = {"conhost.exe", "werfault.exe"}      # Windows' console host and crash reporter, started for many programs
UNINSTALL = ("unins", "uninstall")

EVENTS = collections.deque(maxlen=300)       # outside connections / unrestricted children seen while watching
WATCH = {"on": False, "since": None, "samples": 0, "last": None, "error": None, "restricted": set()}
_lock = threading.Lock()


def _norm(p):
    try:
        return str(Path(p).resolve())
    except OSError:
        return str(p)


def _outside(ip):
    try:
        a = ipaddress.ip_address(str(ip).split("%", 1)[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return not (a.is_loopback or a.is_unspecified)


# --------------------------------------------------------------- discovery --

def _registry_dirs(words):
    out = []
    if os.name != "nt" or not words:
        return out
    import winreg
    roots = [(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            k = winreg.OpenKey(hive, path)
        except OSError:
            continue
        for i in range(4000):
            try:
                sub = winreg.EnumKey(k, i)
            except OSError:
                break
            try:
                with winreg.OpenKey(k, sub) as s:
                    name = str(winreg.QueryValueEx(s, "DisplayName")[0])
                    if not any(w in name.lower() for w in words):
                        continue
                    loc = icon = None
                    try:
                        loc = winreg.QueryValueEx(s, "InstallLocation")[0]
                    except OSError:
                        pass
                    try:
                        icon = str(winreg.QueryValueEx(s, "DisplayIcon")[0]).split(",")[0].strip('"')
                    except OSError:
                        pass
                    d = loc if loc and Path(loc).is_dir() else (str(Path(icon).parent) if icon and Path(icon).is_file() else None)
                    if d:
                        out.append((name, d))
            except OSError:
                continue
    return out


def _listeners():
    """port -> pid of processes listening on 127.0.0.1 / all interfaces."""
    out = {}
    if not psutil:
        return out
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.pid:
                out.setdefault(c.laddr.port, c.pid)
    except (psutil.AccessDenied, OSError):
        pass
    return out


def _exes_in(folder, limit=60):
    out = []
    try:
        for root, dirs, files in os.walk(folder):
            if root.count(os.sep) - str(folder).count(os.sep) > 4:
                dirs[:] = []
                continue
            for f in files:
                if f.lower().endswith(".exe"):
                    out.append(os.path.join(root, f))
                    if len(out) >= limit:
                        return out
    except OSError:
        pass
    return out


def discover():
    """List of backends found on this PC, each with real executable paths and why each was found."""
    procs = []
    if psutil:
        for p in psutil.process_iter(["pid", "ppid", "name", "exe", "cmdline"]):
            try:
                procs.append({"pid": p.info["pid"], "ppid": p.info["ppid"], "name": (p.info["name"] or "").lower(),
                              "exe": p.info["exe"], "cmd": " ".join(p.info["cmdline"] or []).lower()})
            except Exception:
                continue
    listen = _listeners()
    by_pid = {p["pid"]: p for p in procs}
    result = []
    for b in BACKENDS:
        exes = {}                                         # path -> {"sources": set, "pids": set}

        def add(path, why, pid=None):
            if not path or not Path(path).is_file():
                return
            e = exes.setdefault(_norm(path), {"sources": set(), "pids": set()})
            e["sources"].add(why)
            if pid:
                e["pids"].add(pid)
        for p in procs:
            if p["name"] in b["exes"] or any(w in p["cmd"] for w in b.get("cmd", [])):
                add(p["exe"], "running process", p["pid"])
        for port in b["ports"]:
            pid = listen.get(port)
            if pid and pid in by_pid:
                p = by_pid[pid]
                if p["name"] in b["exes"] or any(w in p["cmd"] for w in b.get("cmd", [])) or b["id"] in ("llamacpp",):
                    if b["id"] != "llamacpp" or p["name"].startswith("llama"):
                        add(p["exe"], f"listens on port {port}", pid)
        for w in b["which"]:
            add(shutil.which(w), "on PATH")
        roots = set()
        for name, d in _registry_dirs(b["reg"]):
            roots.add(_norm(d))
            for f in b["exes"]:
                add(os.path.join(d, f), f"installed ({name})")
        for path, e in list(exes.items()):
            if Path(path).name.lower() not in SHARED:
                roots.add(str(Path(path).parent))
        main = [p for p in exes]
        for r in sorted(roots):
            for f in _exes_in(r):
                if _norm(f) not in exes:
                    add(f, "in the same install folder")
        # child processes of running backend processes
        pids = {pid for e in exes.values() for pid in e["pids"]}
        for p in procs:
            if p["ppid"] in pids and p["exe"] and _norm(p["exe"]) not in exes:
                add(p["exe"], "child process", p["pid"])
        if not exes:
            continue
        items = []
        for path, e in sorted(exes.items(), key=lambda kv: (Path(kv[0]).name.lower() not in b["exes"], kv[0])):
            name = Path(path).name.lower()
            win = path.lower().startswith(os.environ.get("SystemRoot", r"C:\Windows").lower() + os.sep)
            shared = win or (name in SHARED and not any(str(Path(path)).startswith(r + os.sep) for r in roots if r != str(Path(path).parent)))
            uninst = name.startswith(UNINSTALL)
            items.append({"path": path, "name": Path(path).name, "sources": sorted(e["sources"]),
                          "pids": sorted(e["pids"]), "running": bool(e["pids"]),
                          "selectable": not shared,
                          "default": not shared and not uninst,
                          "note": ("Windows component: not restricted (it would affect every program)" if win
                                   else "Shared interpreter: blocking it would also block other programs" if shared
                                   else "Uninstaller" if uninst else None)})
        result.append({"id": b["id"], "name": b["name"], "exes": items, "main": main,
                       "running": any(i["running"] for i in items)})
    return result


# ----------------------------------------------------------------- watcher --

def _tree(root_pids, procs_children):
    seen, stack = set(), list(root_pids)
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(procs_children.get(p, ()))
    return seen


def scan(restricted_paths=(), own_pid=None):
    """One look at the network table. Returns outside connections of MTAI's tree and of backend trees,
    and backend child processes that run an executable that is not restricted."""
    if not psutil:
        raise RuntimeError("psutil is missing")
    own_pid = own_pid or os.getpid()
    children, exe_of, names, born = collections.defaultdict(list), {}, {}, {}
    rows = []
    for p in psutil.process_iter(["pid", "ppid", "exe", "name", "create_time"]):
        try:
            rows.append((p.info["pid"], p.info["ppid"], p.info["create_time"] or 0))
            exe_of[p.info["pid"]] = _norm(p.info["exe"]) if p.info["exe"] else None
            names[p.info["pid"]] = p.info["name"]
            born[p.info["pid"]] = p.info["create_time"] or 0
        except Exception:
            continue
    for pid, ppid, t in rows:
        # a parent PID can be reused by an unrelated process after the parent exited: a real child is
        # never older than its parent, so other programs' processes are not counted as MTAI's
        if ppid in born and t + 1 >= born[ppid]:
            children[ppid].append(pid)
    mtai = _tree([own_pid], children)
    restricted = {_norm(x) for x in restricted_paths}
    roots = [pid for pid, exe in exe_of.items() if exe and exe in restricted and pid not in mtai]
    backend = _tree(roots, children) - mtai
    conns, extra = [], []
    for c in psutil.net_connections(kind="inet"):
        if not c.pid or not c.raddr or not _outside(c.raddr.ip):
            continue
        if c.status not in (psutil.CONN_ESTABLISHED, psutil.CONN_SYN_SENT, psutil.CONN_NONE):
            continue
        who = "MTAI" if c.pid in mtai else "backend" if c.pid in backend else None
        if who:
            conns.append({"who": who, "pid": c.pid, "name": names.get(c.pid), "exe": exe_of.get(c.pid),
                          "remote": f"{c.raddr.ip}:{c.raddr.port}", "status": c.status,
                          "restricted": exe_of.get(c.pid) in restricted})
    for pid in backend:
        exe = exe_of.get(pid)
        if exe and exe not in restricted and (names.get(pid) or "").lower() not in HARMLESS:
            extra.append({"pid": pid, "name": names.get(pid), "exe": exe})
    return {"t": time.time(), "mtai": len(mtai), "backend": len(backend), "conns": conns, "unrestricted_children": extra}


def _loop(get_restricted, interval):
    seen = set()
    while WATCH["on"]:
        try:
            r = scan(get_restricted())
            WATCH["samples"] += 1
            WATCH["last"] = r
            WATCH["error"] = None
            for c in r["conns"]:
                key = ("conn", c["pid"], c["remote"])
                if key not in seen:
                    seen.add(key)
                    EVENTS.append({"t": r["t"], "kind": "outside connection", **c})
            for x in r["unrestricted_children"]:
                key = ("child", x["pid"])
                if key not in seen:
                    seen.add(key)
                    EVENTS.append({"t": r["t"], "kind": "unrestricted child process", **x})
        except Exception as e:
            WATCH["error"] = f"{type(e).__name__}: {e}"
        for _ in range(int(interval * 10)):
            if not WATCH["on"]:
                break
            time.sleep(0.1)


def watch(on, get_restricted=lambda: (), interval=3.0):
    with _lock:
        if on and not WATCH["on"]:
            WATCH.update(on=True, since=time.time(), samples=0, last=None, error=None)
            threading.Thread(target=_loop, args=(get_restricted, interval), daemon=True, name="privacy-watch").start()
        elif not on:
            WATCH["on"] = False


def events_since(t):
    return [e for e in EVENTS if e["t"] >= t]
