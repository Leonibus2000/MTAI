"""
Where MTAI's files live.

From source (python local_ai_chat.py / MTAI.pyw):
    program files and the data/ folder sit next to the .py files.
From the MTAI.exe build (PyInstaller, sys.frozen):
    program files are inside the exe bundle (sys._MEIPASS), and user data goes to
    %LOCALAPPDATA%\\MTAI\\data, so it survives updates and the exe can live anywhere.
Set MTAI_DATA to use another data folder (for tests, or a portable copy).
"""

import os
import shutil
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent)

if os.environ.get("MTAI_DATA"):
    DATA_DIR = Path(os.environ["MTAI_DATA"]).resolve()
elif FROZEN:
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "MTAI" / "data"
else:
    DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_py = {}


def _registry_pythons():
    """Python installs from the registry (PEP 514), newest first. No process is started."""
    found = []
    try:
        import winreg
    except ImportError:
        return found
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (0, getattr(winreg, "KEY_WOW64_64KEY", 0)):
            try:
                core = winreg.OpenKey(hive, r"Software\Python\PythonCore", 0, winreg.KEY_READ | view)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    tag = winreg.EnumKey(core, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(core, tag + r"\InstallPath") as k:
                        try:
                            exe = winreg.QueryValueEx(k, "ExecutablePath")[0]
                        except OSError:
                            exe = str(Path(winreg.QueryValueEx(k, "")[0]) / "python.exe")
                    try:
                        with winreg.OpenKey(core, tag) as k:
                            ver = winreg.QueryValueEx(k, "Version")[0]
                    except OSError:
                        ver = tag.split("-")[0]
                except OSError:
                    continue
                if Path(exe).is_file():
                    found.append((ver, exe))
    def key(v):
        try:
            return tuple(int(x) for x in v[0].split(".")[:3])
        except ValueError:
            return (0,)
    return sorted(set(found), key=key, reverse=True)


def _find_python():
    """A real python.exe for code runs and the image engine when MTAI runs as an exe."""
    for ver, exe in _registry_pythons():
        if key_ok(ver):
            return exe, ver
    exe = shutil.which("python")
    if exe and "WindowsApps" not in exe:          # skip the Microsoft Store "install Python" stub
        return exe, ""
    return None, None


def key_ok(ver):
    try:
        return tuple(int(x) for x in ver.split(".")[:2]) >= (3, 9)
    except ValueError:
        return False


def python_exe():
    """python.exe to run code with. From source this is the Python running MTAI (python.exe, not
    pythonw.exe); in the exe build it is an installed Python, or None when there is none."""
    if not FROZEN:
        exe = Path(sys.executable)
        if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
            return str(exe.parent / "python.exe")
        return str(exe)
    if "exe" not in _py:
        _py["exe"], _py["ver"] = _find_python()
    return _py["exe"]


def python_version():
    """Version of python_exe(), or None when there is no Python to run code with."""
    if not FROZEN:
        return sys.version.split()[0]
    python_exe()
    return (_py.get("ver") or "installed") if _py.get("exe") else None
