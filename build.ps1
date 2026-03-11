param(
    [switch]$Installer
)

$ErrorActionPreference = "Stop"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    throw "未找到 Python，请先安装 Python 并确保 python 或 py 命令可用。"
}

& $pythonCmd.Source -m pip install --upgrade pip
& $pythonCmd.Source -m pip install pyinstaller
& $pythonCmd.Source -m PyInstaller .\QuickCli.spec --noconfirm --clean

if ($Installer) {
    $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        throw "未找到 Inno Setup 6，请先安装后再使用 -Installer。"
    }

    $installerDir = Join-Path $PSScriptRoot "installer"
    $installerDistDir = Join-Path $installerDir "dist"
    $rootOutputDir = Join-Path $PSScriptRoot "output"
    New-Item -ItemType Directory -Force -Path $installerDistDir | Out-Null
    New-Item -ItemType Directory -Force -Path $rootOutputDir | Out-Null
    Copy-Item .\dist\QuickCli.exe (Join-Path $installerDistDir "QuickCli.exe") -Force
    Copy-Item .\icon.ico (Join-Path $installerDir "icon.ico") -Force

    Push-Location $installerDir
    try {
        & $iscc .\QuickCli.iss
    }
    finally {
        Pop-Location
    }

    Copy-Item .\installer\output\QuickCli-Setup.exe .\output\QuickCli-Setup.exe -Force
}
