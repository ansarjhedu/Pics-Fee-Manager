$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path $python)) {
    $python = "py"
}

& $python -m pip install -r requirements.txt

$common = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--paths", ".",
    "--collect-submodules", "pics_fee",
    "--collect-submodules", "uvicorn",
    "--collect-submodules", "fastapi",
    "--collect-submodules", "starlette",
    "--collect-submodules", "cryptography",
    "--hidden-import", "pics_fee.server",
    "--hidden-import", "pics_fee.services"
)

& $python -m PyInstaller @common --name "PICS Fee Principal" run_principal.py
& $python -m PyInstaller @common --name "PICS Fee Clerk" run_clerk.py

Write-Host "Built dist\PICS Fee Principal and dist\PICS Fee Clerk"
