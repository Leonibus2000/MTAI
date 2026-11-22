"""
MTAI network guard: what makes privacy mode enforceable instead of a hidden button.

Three layers, all switched by one flag (STATE["on"]):

  1. The audit hook (PEP 578, sys.addaudithook) in MTAI's own Python process.
     CPython raises an audit event before every socket connect, DNS lookup, UDP
     send, bind and process start. While privacy mode is on, the hook raises
     Blocked for anything that is not loopback (127.0.0.0/8, ::1, localhost), for
     IPv4, IPv6, host names, direct IPs and every network interface alike. This
     covers urllib, http.client, requests, httpx (the Anthropic SDK), raw sockets
     and anything else built on Python's socket module. New processes are refused
     unless MTAI's own code starts them inside `allow()` for a local job.

  2. The gate: a small HTTP proxy on 127.0.0.1 that the WebView2 browser is
     started with (--proxy-server). Chromium sends every non-loopback request
     there: pages, fetch, XHR, WebSockets, images, scripts, iframes. The gate
     refuses all of them while privacy mode is on and forwards them when it is
     off. Host name lookups in the browser are switched off by a resolver rule
     (the proxy does them), QUIC is off and WebRTC may not send UDP outside the
     proxy, so nothing goes around the gate.

  3. The sandbox: code from chats (the Run button, workspace runs) runs in a
     Windows AppContainer with no network capabilities while privacy mode is on.
     Windows itself refuses its connections, also for programs it starts, and it
     can only touch its own run folder.

Blocked attempts are kept in BLOCKED (newest last) for the diagnostics page.
The image worker imports this file and calls install(always=True): it never
needs the internet, so it is blocked in both modes.
"""
import collections
import ipaddress
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from urllib.parse import urlparse

STATE = {"on": False, "installed": False, "always": False, "changed": None, "component": "MTAI"}
BLOCKED = collections.deque(maxlen=400)
COUNTS = collections.Counter()
_tls = threading.local()
_ext_lock = threading.Lock()
_EXT = {}                      # socket handle -> (peer, time) for outside connections made while privacy was off


class Blocked(PermissionError):
    """Raised for a refused connection. It is an OSError, so urllib, requests and httpx
    report it as their usual connection error and MTAI's error paths keep working."""


# ------------------------------------------------------------------ helpers --

def is_loopback_host(host):
    if host is None:
        return True
    if isinstance(host, (bytes, bytearray)):
        host = host.decode("ascii", "replace")
    h = str(host).strip().strip("[]").rstrip(".").lower()
    if h == "localhost" or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h.split("%", 1)[0])
    except ValueError:
        return False                              # a host name that would need DNS, or "" (all interfaces)
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def is_loopback_url(url):
    try:
        u = urlparse(str(url))
    except Exception:
        return False
    return bool(u.hostname) and is_loopback_host(u.hostname)


def _is_ip(h):
    if isinstance(h, (bytes, bytearray)):
        h = h.decode("ascii", "replace")
    try:
        ipaddress.ip_address(str(h).strip("[]").split("%", 1)[0])
        return True
    except ValueError:
        return False


def _addr_host(address):
    """Host part of a socket address, or None for families without one (AF_UNIX paths)."""
    if isinstance(address, tuple) and address:
        return address[0]
    return None


def note(kind, target, component=None, detail=None):
    e = {"t": time.time(), "kind": kind, "target": str(target)[:300],
         "component": component or getattr(_tls, "component", None) or STATE["component"],
         "thread": threading.current_thread().name}
    if detail:
        e["detail"] = str(detail)[:200]
    BLOCKED.append(e)
    COUNTS[kind] += 1
    if STATE["always"]:                       # the image worker has no diagnostics page: say it in its log
        try:
            sys.stderr.write(f"[netguard] blocked {kind} {e['target']}\n")
        except Exception:
            pass
    return e


def active():
    return STATE["on"] or STATE["always"]


@contextmanager
def allow(reason):
    """Let MTAI's own code start a local process (Explorer, ollama serve, the image engine)."""
    old = getattr(_tls, "permit", None)
    _tls.permit = reason
    try:
        yield
    finally:
        _tls.permit = old


@contextmanager
def component(name):
    """Name the part of MTAI that makes the following calls, for the blocked list."""
    old = getattr(_tls, "component", None)
    _tls.component = name
    try:
        yield
    finally:
        _tls.component = old


# --------------------------------------------------------------- the hook --

_NET = {"socket.connect", "socket.sendto", "socket.sendmsg", "socket.bind",
        "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo"}
_PROC = {"subprocess.Popen", "os.system", "os.exec", "os.spawn", "os.posix_spawn", "_winapi.CreateProcess",
         "os.startfile", "os.startfile/2"}
_EVENTS = frozenset(_NET | _PROC)


def _hook(event, args):
    if event not in _EVENTS:
        return
    if event in _NET:
        _net(event, args)
    elif STATE["on"] or STATE["always"]:
        _proc(event, args)             # the image worker (always) may not start programs either


def _net(event, args):
    on = active()
    if event == "socket.connect":
        sock, address = args
        host = _addr_host(address)
        if host is None or is_loopback_host(host):
            return
        if on:
            note("connect", _fmt(address))
            raise Blocked(f"MTAI privacy mode blocked a connection to {_fmt(address)}")
        try:                                    # remember it, so turning privacy on can cut it
            with _ext_lock:
                _EXT[sock.fileno()] = (_fmt(address), time.time())
        except Exception:
            pass
        return
    if not on:
        return
    if event in ("socket.sendto", "socket.sendmsg"):
        host = _addr_host(args[1]) if len(args) > 1 else None
        if host is not None and not is_loopback_host(host):
            note("udp", _fmt(args[1]))
            raise Blocked(f"MTAI privacy mode blocked data to {_fmt(args[1])}")
    elif event == "socket.bind":
        host = _addr_host(args[1])
        if host is not None and not is_loopback_host(host):
            note("bind", _fmt(args[1]), detail="listening on a network interface")
            raise Blocked(f"MTAI privacy mode blocked listening on {_fmt(args[1])}")
    elif event == "socket.getaddrinfo":
        host = args[0]
        if host not in (None, "", b"") and not is_loopback_host(host):
            if _is_ip(host):                       # create_connection("1.1.1.1") looks up the literal first
                note("connect", _fmt((host, args[1])))
                raise Blocked(f"MTAI privacy mode blocked a connection to {_fmt((host, args[1]))}")
            note("dns", host)
            raise Blocked(f"MTAI privacy mode blocked a DNS lookup of {host}")
    elif event in ("socket.gethostbyname", "socket.gethostbyaddr"):
        host = args[0]
        if not is_loopback_host(host):
            note("dns", host)
            raise Blocked(f"MTAI privacy mode blocked a DNS lookup of {host}")
    elif event == "socket.getnameinfo":
        host = _addr_host(args[0])
        if host is not None and not is_loopback_host(host):
            note("dns", _fmt(args[0]))
            raise Blocked(f"MTAI privacy mode blocked a reverse lookup of {_fmt(args[0])}")


def _proc(event, args):
    if getattr(_tls, "permit", None):
        return
    if event.startswith("os.startfile"):
        path = str(args[0])
        if os.path.isdir(path):
            return                                   # a folder in Explorer is local
        note("open", path, detail="open in another program")
        raise Blocked("MTAI privacy mode blocked opening " + path[:120])
    what = args[0] if event in ("os.system",) else (args[1] if event == "subprocess.Popen" else args[:2])
    note("process", _short(what))
    raise Blocked("MTAI privacy mode blocked starting another program (" + _short(what)[:80] + ")")


def _fmt(address):
    if isinstance(address, tuple) and len(address) >= 2:
        h = str(address[0])
        return f"[{h}]:{address[1]}" if ":" in h else f"{h}:{address[1]}"
    return str(address)


def _short(x):
    if isinstance(x, (list, tuple)):
        x = " ".join(str(a) for a in x if a)
    return str(x)[:240]


def install(always=False, component_name=None):
    """Add the audit hook (once; audit hooks cannot be removed, so the flag does the switching)."""
    if component_name:
        STATE["component"] = component_name
    if always:
        STATE["always"] = True
    if not STATE["installed"]:
        sys.addaudithook(_hook)
        STATE["installed"] = True


def set_on(on):
    """Switch privacy enforcement. Turning it on cuts outside connections that are still open."""
    on = bool(on)
    was = STATE["on"]
    STATE["on"] = on
    if on != was or not STATE.get("changed"):   # saving other settings does not make the last check stale
        STATE["changed"] = time.time()
    cut = 0
    if on and not was:
        cut = cut_external()
        cut += GATE.close_all() if GATE else 0
    STATE["cut"] = cut
    return cut


def cut_external():
    """Shut down outside connections that MTAI opened before privacy mode was switched on.
    Only sockets that still point outside are touched (a handle number can be reused)."""
    with _ext_lock:
        items = list(_EXT.items())
        _EXT.clear()
    n = 0
    for fd, _ in items:
        s = None
        try:
            s = socket.socket(fileno=fd)
            peer = s.getpeername()
            if not is_loopback_host(_addr_host(peer)):
                s.shutdown(socket.SHUT_RDWR)
                n += 1
        except OSError:
            pass
        finally:
            if s is not None:
                try:
                    s.detach()                     # the owner closes it, not us
                except OSError:
                    pass
    return n


# --------------------------------------------------------------- the gate --

class _GateHandler(socketserver.BaseRequestHandler):
    def handle(self):
        c = self.request
        c.settimeout(30)
        head = b""
        try:
            while b"\r\n\r\n" not in head:
                d = c.recv(65536)
                if not d:
                    return
                head += d
                if len(head) > 131072:
                    return
        except OSError:
            return
        hdr, rest = head.split(b"\r\n\r\n", 1)
        lines = hdr.split(b"\r\n")
        try:
            method, target, ver = lines[0].decode("latin-1").split(" ", 2)
        except ValueError:
            return
        if method.upper() == "CONNECT":
            host, _, port = target.rpartition(":")
            host = host.strip("[]")
            first = None
        else:
            u = urlparse(target)
            if u.scheme != "http" or not u.hostname:
                return self._deny(c, 400, "Bad request")
            host, port = u.hostname, u.port or 80
            path = (u.path or "/") + ("?" + u.query if u.query else "")
            keep = [ln for ln in lines[1:] if not ln.lower().startswith((b"proxy-connection:", b"connection:", b"keep-alive:"))]
            first = b"\r\n".join([f"{method} {path} {ver}".encode("latin-1"), *keep, b"Connection: close"]) + b"\r\n\r\n" + rest
        try:
            port = int(port)
        except ValueError:
            return self._deny(c, 400, "Bad port")
        GATE.seen += 1
        if STATE["on"]:
            note("browser", f"{host}:{port}", component="Browser (WebView2)",
                 detail="tunnel" if first is None else "http")
            return self._deny(c, 403, "Blocked by MTAI privacy mode")
        if is_loopback_host(host):
            return self._deny(c, 403, "Loopback is not proxied")
        try:
            up = socket.create_connection((host, port), timeout=15)
        except OSError as e:
            return self._deny(c, 502, f"Cannot reach {host}: {e}")
        GATE.forwarded += 1
        GATE.recent.append({"t": time.time(), "host": host, "port": port})
        pair = (c, up)
        with GATE.lock:
            GATE.open.add(pair)
        try:
            if first is None:
                c.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                if rest:
                    up.sendall(rest)
            else:
                up.sendall(first)
            c.settimeout(None)
            up.settimeout(None)
            t = threading.Thread(target=_pipe, args=(up, c), daemon=True)
            t.start()
            _pipe(c, up)
            t.join(5)
        except OSError:
            pass
        finally:
            with GATE.lock:
                GATE.open.discard(pair)
            for s in pair:
                try:
                    s.close()
                except OSError:
                    pass

    @staticmethod
    def _deny(c, code, text):
        body = text.encode()
        try:
            c.sendall(f"HTTP/1.1 {code} {text}\r\nContent-Type: text/plain\r\nContent-Length: {len(body)}\r\n"
                      f"Connection: close\r\n\r\n".encode() + body)
        except OSError:
            pass


def _pipe(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            b.sendall(d)
    except OSError:
        pass
    for s in (a, b):
        try:
            s.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class Gate(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _GateHandler)
        self.port = self.server_address[1]
        self.lock = threading.Lock()
        self.open = set()
        self.seen = 0
        self.forwarded = 0
        self.recent = collections.deque(maxlen=200)    # forwarded hosts (memory only), for the self-test
        threading.Thread(target=self.serve_forever, daemon=True, name="privacy-gate").start()

    def close_all(self):
        with self.lock:
            pairs = list(self.open)
        for pair in pairs:
            for s in pair:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        return len(pairs)


GATE = None


def start_gate():
    global GATE
    if GATE is None:
        GATE = Gate()
    return GATE


# WebView2 features MTAI's window does not need that talk to Microsoft (SmartScreen, account sign-in).
# They only reduce traffic: the sign-in code inside WebView2 (OneAuth) uses Windows' own HTTP stack and
# goes around the gate, which is why MTAI can run its window from a private copy that a firewall rule blocks.
WEBVIEW2_OFF = ["msSmartScreenProtection", "msSingleSignOnOSForPrimaryAccountIsShared", "msOneAuthWAM",
                "msPrimaryOSAccountInfoCache", "msSeamlessWebToBrowserSignIn", "msQuickAuthToBrowserSignIn",
                "msWeb2NativeSignInRecommendation", "msEdgeAskCopilot", "msEdgeComposeCopilotChat"]


def webview2_args(port):
    return "--disable-features=" + ",".join(WEBVIEW2_OFF) + " --disable-background-networking " + browser_args(port)


def browser_args(port):
    """Chromium switches that send all of the browser's traffic through the gate."""
    return (f"--proxy-server=http://127.0.0.1:{port} "
            '"--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost , EXCLUDE 127.0.0.1 , EXCLUDE [::1]" '
            "--disable-quic --force-webrtc-ip-handling-policy=disable_non_proxied_udp "
            "--webrtc-ip-handling-policy=disable_non_proxied_udp")


def browser_processes(port):
    """Command lines of the running msedgewebview2/msedge processes that carry the gate's proxy
    switch, read from Windows. Used to verify the browser really was started behind the gate."""
    if os.name != "nt":
        return []
    ps = (f"Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe' OR Name='msedge.exe'\" | "
          f"Where-Object {{ $_.CommandLine -like '*--proxy-server=http://127.0.0.1:{port}*' }} | "
          "ForEach-Object { '' + $_.ProcessId + '|' + $_.CommandLine }")
    with allow("read browser process list"):
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = []
    for line in r.stdout.splitlines():
        pid, _, cmd = line.partition("|")
        if pid.strip().isdigit():
            out.append({"pid": int(pid), "cmd": cmd})
    return out
