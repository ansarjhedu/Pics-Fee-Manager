$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path $python)) {
    throw "Python 3.12 was not found."
}

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $iscc) {
    throw "Inno Setup 6 is not installed."
}

$common = @(
    "--noconfirm",
    "--windowed",
    "--paths", ".",
    "--collect-submodules", "pics_fee",
    "--collect-submodules", "uvicorn",
    "--collect-submodules", "fastapi",
    "--collect-submodules", "starlette",
    "--collect-submodules", "cryptography",
    "--hidden-import", "pics_fee.server",
    "--hidden-import", "pics_fee.services",
    "--icon", (Join-Path $PSScriptRoot "assets\pics-fee.ico"),
    "--add-data", ((Join-Path $PSScriptRoot "assets\pics-fee.ico") + ";.")
)

& $python -m PyInstaller @common --distpath "dist\setup-stage\principal" --workpath "build\setup-principal" --specpath "build" --name "PICS Fee Principal" run_principal.py
if ($LASTEXITCODE -ne 0) { throw "The principal app did not build." }

& $python -m PyInstaller @common --distpath "dist\setup-stage\clerk" --workpath "build\setup-clerk" --specpath "build" --name "PICS Fee Clerk" run_clerk.py
if ($LASTEXITCODE -ne 0) { throw "The clerk app did not build." }

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:winexe /win32icon:"assets\pics-fee.ico" /r:System.Windows.Forms.dll /out:"installer\clerk-setup.stub.exe" "installer\ClerkSetupStub.cs"
if ($LASTEXITCODE -ne 0) { throw "The clerk setup stub did not compile." }

& $iscc "/DClerkBuild=1" "installer\PICSFeeDesk.iss"
if ($LASTEXITCODE -ne 0) { throw "The clerk setup base did not compile." }

& $iscc "installer\PICSFeeDesk.iss"
if ($LASTEXITCODE -ne 0) { throw "The setup wizard did not compile." }

Write-Host "Setup wizard: dist\PICS Fee Desk Setup.exe"
