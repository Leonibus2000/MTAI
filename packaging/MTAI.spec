# PyInstaller spec for MTAI.exe: one file, no console window.
# Build with packaging\build_exe.ps1 (or: python -m PyInstaller packaging\MTAI.spec --noconfirm).
# Program files are unpacked to a temp folder at start; user data goes to %LOCALAPPDATA%\MTAI (see paths.py).

from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "ui"), "ui"),
    (str(ROOT / "fwhelper.ps1"), "."),          # run as administrator by firewall.py
    (str(ROOT / "imagegen_worker.py"), "."),    # runs inside the image engine's own Python
    (str(ROOT / "netguard.py"), "."),           # imported by that worker, next to it
]

a = Analysis(
    [str(ROOT / "MTAI.pyw")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["anthropic", "psutil", "requests", "httpx"],
    excludes=["tkinter", "torch", "diffusers", "transformers", "numpy", "matplotlib", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MTAI",
    icon=str(ROOT / "packaging" / "mtai.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    console=False,
    upx=False,                                  # UPX-packed exes trip antivirus scanners more often
    runtime_tmpdir=None,
)
