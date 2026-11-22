# Builds dist\MTAI.exe (one file, no console) with PyInstaller.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
# Needs Python 3.10+ with: pip install -r requirements.txt pyinstaller pillow

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = if (Get-Command py -ErrorAction SilentlyContinue) { @("py", "-3") } else { @("python") }
$pyExe = $py[0]; $pyArgs = @($py | Select-Object -Skip 1)

if (-not (Test-Path "packaging\mtai.ico")) {
    & $pyExe @pyArgs packaging\make_icon.py
}

& $pyExe @pyArgs -m PyInstaller packaging\MTAI.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Get-Item "dist\MTAI.exe"
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
"{0}  {1}" -f $hash.ToLower(), $exe.Name | Set-Content "dist\MTAI.exe.sha256" -Encoding ascii
Write-Host ("Built {0} ({1:N1} MB)" -f $exe.FullName, ($exe.Length / 1MB))
Write-Host "SHA256 $hash"
