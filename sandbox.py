"""
MTAI code sandbox for privacy mode: runs a program in a Windows AppContainer.

An AppContainer is the sandbox Windows uses for Store apps. A process in one has
no network access unless it holds a network capability, and this one holds none,
so Windows refuses its connections (internet, local network and loopback), for
every program it starts too. It also cannot read your files: only the run folder
it gets, plus folders that grant "ALL APPLICATION PACKAGES" (Windows itself).

Python is not in such a folder (it lives in your user profile), so the first
sandboxed Python run gives this sandbox read-only access to the Python folder,
once. Undo with:  icacls "<python folder>" /remove *<sandbox SID> /T
"""
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes as W
from pathlib import Path

NAME = "MTAI.CodeSandbox"
_lock = threading.Lock()
_sid = {}


class SandboxError(RuntimeError):
    pass


if os.name == "nt":
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _adv = ctypes.WinDLL("advapi32", use_last_error=True)
    _uenv = ctypes.WinDLL("userenv")

    class SECURITY_CAPABILITIES(ctypes.Structure):
        _fields_ = [("AppContainerSid", ctypes.c_void_p), ("Capabilities", ctypes.c_void_p),
                    ("CapabilityCount", W.DWORD), ("Reserved", W.DWORD)]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [("cb", W.DWORD), ("lpReserved", W.LPWSTR), ("lpDesktop", W.LPWSTR), ("lpTitle", W.LPWSTR),
                    ("dwX", W.DWORD), ("dwY", W.DWORD), ("dwXSize", W.DWORD), ("dwYSize", W.DWORD),
                    ("dwXCountChars", W.DWORD), ("dwYCountChars", W.DWORD), ("dwFillAttribute", W.DWORD),
                    ("dwFlags", W.DWORD), ("wShowWindow", W.WORD), ("cbReserved2", W.WORD),
                    ("lpReserved2", ctypes.c_void_p), ("hStdInput", W.HANDLE), ("hStdOutput", W.HANDLE),
                    ("hStdError", W.HANDLE)]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [("hProcess", W.HANDLE), ("hThread", W.HANDLE), ("dwProcessId", W.DWORD), ("dwThreadId", W.DWORD)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", W.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", W.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD)]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    _uenv.CreateAppContainerProfile.argtypes = [W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, ctypes.c_void_p, W.DWORD,
                                                ctypes.POINTER(ctypes.c_void_p)]
    _uenv.CreateAppContainerProfile.restype = ctypes.c_long
    _uenv.DeriveAppContainerSidFromAppContainerName.argtypes = [W.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    _uenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
    _adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(W.LPWSTR)]
    _adv.ConvertSidToStringSidW.restype = W.BOOL
    _k32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, W.DWORD, W.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    _k32.InitializeProcThreadAttributeList.restype = W.BOOL
    _k32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, W.DWORD, ctypes.c_size_t, ctypes.c_void_p,
                                               ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    _k32.UpdateProcThreadAttribute.restype = W.BOOL
    _k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    _k32.CreateProcessW.argtypes = [W.LPCWSTR, W.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, W.BOOL, W.DWORD,
                                    ctypes.c_void_p, W.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(PROCESS_INFORMATION)]
    _k32.CreateProcessW.restype = W.BOOL
    _k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
    _k32.CreateJobObjectW.restype = W.HANDLE
    _k32.SetInformationJobObject.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD]
    _k32.SetInformationJobObject.restype = W.BOOL
    _k32.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
    _k32.AssignProcessToJobObject.restype = W.BOOL
    _k32.TerminateJobObject.argtypes = [W.HANDLE, W.UINT]
    _k32.ResumeThread.argtypes = [W.HANDLE]
    _k32.ResumeThread.restype = W.DWORD
    _k32.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    _k32.WaitForSingleObject.restype = W.DWORD
    _k32.GetExitCodeProcess.argtypes = [W.HANDLE, ctypes.POINTER(W.DWORD)]
    _k32.CloseHandle.argtypes = [W.HANDLE]
    _k32.CreatePipe.argtypes = [ctypes.POINTER(W.HANDLE), ctypes.POINTER(W.HANDLE), ctypes.c_void_p, W.DWORD]
    _k32.CreatePipe.restype = W.BOOL
    _k32.SetHandleInformation.argtypes = [W.HANDLE, W.DWORD, W.DWORD]
    _k32.ReadFile.argtypes = [W.HANDLE, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
    _k32.ReadFile.restype = W.BOOL

PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
CREATE_SUSPENDED = 0x00000004
STARTF_USESTDHANDLES = 0x00000100
HANDLE_FLAG_INHERIT = 0x1
JOB_KILL_ON_CLOSE = 0x2000
JOB_DIE_ON_UNHANDLED_EXCEPTION = 0x400
E_ALREADY_EXISTS = -2147024713          # HRESULT_FROM_WIN32(ERROR_ALREADY_EXISTS)


def available():
    return os.name == "nt"


def container_sid():
    """The sandbox's AppContainer SID as (pointer, "S-1-15-2-..."), created on first use."""
    if not available():
        raise SandboxError("The code sandbox needs Windows.")
    with _lock:
        if _sid:
            return _sid["p"], _sid["s"]
        p = ctypes.c_void_p()
        hr = _uenv.CreateAppContainerProfile(NAME, "MTAI code sandbox",
                                             "Runs code from MTAI chats without network access", None, 0, ctypes.byref(p))
        if hr == E_ALREADY_EXISTS:
            hr = _uenv.DeriveAppContainerSidFromAppContainerName(NAME, ctypes.byref(p))
        if hr != 0:
            raise SandboxError(f"Windows did not create the sandbox (0x{hr & 0xffffffff:08x}).")
        s = W.LPWSTR()
        if not _adv.ConvertSidToStringSidW(p, ctypes.byref(s)):
            raise SandboxError("Windows did not name the sandbox.")
        _sid.update(p=p, s=s.value)
        return p, s.value


def grant(path, rights="(OI)(CI)(M)", state_file=None):
    """Let the sandbox use a folder (icacls). Remembered in state_file, so it is done once per folder."""
    _, sid = container_sid()
    path = str(Path(path).resolve())
    st = {}
    if state_file:
        try:
            st = json.loads(Path(state_file).read_text("utf-8"))
        except Exception:
            st = {}
        if st.get(path) == [sid, rights]:
            return False
    import netguard
    with netguard.allow("grant the code sandbox a folder"):
        r = subprocess.run(["icacls", path, "/grant", f"*{sid}:{rights}", "/Q"], capture_output=True, text=True,
                           timeout=600, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise SandboxError(f"Could not give the sandbox access to {path}: {(r.stdout or r.stderr).strip()[:200]}")
    if state_file:
        st[path] = [sid, rights]
        Path(state_file).parent.mkdir(parents=True, exist_ok=True)
        Path(state_file).write_text(json.dumps(st, indent=1), "utf-8")
    return True


def revoke(path, state_file=None):
    """Take the sandbox's access to a folder away again (icacls /remove), and forget it in state_file."""
    _, sid = container_sid()
    path = str(Path(path).resolve())
    import netguard
    with netguard.allow("revoke the code sandbox's folder access"):
        r = subprocess.run(["icacls", path, "/remove:g", f"*{sid}", "/T", "/C", "/Q"], capture_output=True, text=True,
                           timeout=600, creationflags=CREATE_NO_WINDOW)
    if state_file:
        try:
            st = json.loads(Path(state_file).read_text("utf-8"))
            if st.pop(path, None) is not None:
                Path(state_file).write_text(json.dumps(st, indent=1), "utf-8")
        except Exception:
            pass
    return r.returncode == 0


def _pipe():
    r, w = W.HANDLE(), W.HANDLE()
    if not _k32.CreatePipe(ctypes.byref(r), ctypes.byref(w), None, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return r, w


def _reader(h, box, key, limit):
    buf = ctypes.create_string_buffer(65536)
    n = W.DWORD()
    chunks, size = [], 0
    while _k32.ReadFile(h, buf, 65536, ctypes.byref(n), None) and n.value:
        chunks.append(buf.raw[:n.value])
        size += n.value
        while size > limit and len(chunks) > 1:           # keep the end, like the normal runner
            size -= len(chunks.pop(0))
    box[key] = b"".join(chunks)


def _env_block(env):
    items = sorted(env.items(), key=lambda kv: kv[0].upper())
    return ctypes.create_unicode_buffer("".join(f"{k}={v}\0" for k, v in items) + "\0")


def run(cmd, cwd, env, timeout=60, limit=400_000):
    """Run cmd (a list) in the sandbox with cwd as its only writable folder. Returns
    (stdout bytes, stderr bytes, exit code or None, timed_out)."""
    psid, _ = container_sid()
    sc = SECURITY_CAPABILITIES(psid, None, 0, 0)
    pin_r, pin_w = _pipe()
    out_r, out_w = _pipe()
    err_r, err_w = _pipe()
    child = (W.HANDLE * 3)(pin_r, out_w, err_w)
    for h in child:
        _k32.SetHandleInformation(h, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT)
    _k32.CloseHandle(pin_w)                                  # stdin: empty, at end of file at once

    size = ctypes.c_size_t()
    _k32.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
    attrs = ctypes.create_string_buffer(size.value)
    if not _k32.InitializeProcThreadAttributeList(attrs, 2, 0, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    job = pi = None
    try:
        if not _k32.UpdateProcThreadAttribute(attrs, 0, PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
                                              ctypes.byref(sc), ctypes.sizeof(sc), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        if not _k32.UpdateProcThreadAttribute(attrs, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                              child, ctypes.sizeof(child), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        si.StartupInfo.dwFlags = STARTF_USESTDHANDLES
        si.StartupInfo.hStdInput, si.StartupInfo.hStdOutput, si.StartupInfo.hStdError = pin_r, out_w, err_w
        si.lpAttributeList = ctypes.cast(attrs, ctypes.c_void_p)
        pi = PROCESS_INFORMATION()
        line = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(c) for c in cmd]))
        envb = _env_block(env)
        flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW | CREATE_SUSPENDED
        if not _k32.CreateProcessW(None, line, None, None, True, flags, envb, str(cwd), ctypes.byref(si), ctypes.byref(pi)):
            e = ctypes.get_last_error()
            raise SandboxError(f"Windows did not start the program in the sandbox ({ctypes.FormatError(e).strip()}).")
        job = _k32.CreateJobObjectW(None, None)
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_KILL_ON_CLOSE | JOB_DIE_ON_UNHANDLED_EXCEPTION
        _k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        if not _k32.AssignProcessToJobObject(job, pi.hProcess):
            _k32.TerminateJobObject(job, 1)
            raise SandboxError("Windows did not put the sandboxed program in a job.")
        for h in (pin_r, out_w, err_w):                       # the child holds its own copies now
            _k32.CloseHandle(h)
        pin_r = out_w = err_w = None
        box = {}
        ts = [threading.Thread(target=_reader, args=(out_r, box, "out", limit), daemon=True),
              threading.Thread(target=_reader, args=(err_r, box, "err", limit), daemon=True)]
        for t in ts:
            t.start()
        _k32.ResumeThread(pi.hThread)
        timed_out = _k32.WaitForSingleObject(pi.hProcess, int(timeout * 1000)) != 0
        if timed_out:
            _k32.TerminateJobObject(job, 1)
            _k32.WaitForSingleObject(pi.hProcess, 5000)
        code = W.DWORD()
        _k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
        _k32.CloseHandle(job)                                 # kills anything the program left running
        job = None
        for t in ts:
            t.join(5)
        rc = None if timed_out else ctypes.c_int32(code.value).value
        return box.get("out", b""), box.get("err", b""), rc, timed_out
    finally:
        _k32.DeleteProcThreadAttributeList(attrs)
        for h in (pin_r, out_w, err_w):
            if h:
                _k32.CloseHandle(h)
        _k32.CloseHandle(out_r)
        _k32.CloseHandle(err_r)
        if job:
            _k32.TerminateJobObject(job, 1)
            _k32.CloseHandle(job)
        if pi is not None and pi.hProcess:
            _k32.CloseHandle(pi.hProcess)
            _k32.CloseHandle(pi.hThread)


def base_env(work):
    """A small environment for sandboxed programs: no API keys or user paths, temp files in the run folder."""
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    tmp = Path(work) / ".tmp"
    tmp.mkdir(exist_ok=True)
    import paths
    py = str(Path(paths.python_exe() or sys.executable).parent)
    env = {"SystemRoot": sysroot, "windir": sysroot, "SystemDrive": os.environ.get("SystemDrive", "C:"),
           "ComSpec": os.path.join(sysroot, "System32", "cmd.exe"),
           "PATHEXT": ".COM;.EXE;.BAT;.CMD;.PY;.PS1",
           "PATH": ";".join([py, os.path.join(py, "Scripts"), os.path.join(sysroot, "System32"), sysroot,
                             os.path.join(sysroot, "System32", "WindowsPowerShell", "v1.0")]),
           "TEMP": str(tmp), "TMP": str(tmp), "USERPROFILE": str(work), "HOME": str(work),
           "APPDATA": str(tmp), "LOCALAPPDATA": str(tmp),
           "NUMBER_OF_PROCESSORS": os.environ.get("NUMBER_OF_PROCESSORS", "4"),
           "PROCESSOR_ARCHITECTURE": os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64"), "OS": "Windows_NT",
           "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "MTAI_PRIVACY": "1", "MTAI_SANDBOX": "1"}
    return env
