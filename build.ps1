param(
    [switch]$Installer
)

$ErrorActionPreference = "Stop"
$metadata = Get-Content (Join-Path $PSScriptRoot "app_metadata.json") -Raw | ConvertFrom-Json
$appName = $metadata.app_name
$appVersion = $metadata.version
$appPublisher = $metadata.publisher
$exeName = $metadata.exe_name
$setupBaseName = $metadata.setup_base_name
$installerMetadataFile = Join-Path $PSScriptRoot "installer\\AppMetadata.iss.inc"

$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    throw "未找到 Python，请先安装 Python 并确保 python 或 py 命令可用。"
}

@"
#define MyAppName "$appName"
#define MyAppVersion "$appVersion"
#define MyAppPublisher "$appPublisher"
#define MyAppExeName "$exeName"
#define MySetupBaseFilename "$setupBaseName"
"@ | Set-Content $installerMetadataFile -Encoding UTF8

& $pythonCmd.Source -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "升级 pip 失败。"
}

& $pythonCmd.Source -m pip install --upgrade pyinstaller pystray Pillow customtkinter
if ($LASTEXITCODE -ne 0) {
    throw "安装/升级构建依赖失败。"
}

& $pythonCmd.Source -m PyInstaller .\QuickCli.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败。"
}

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
    Copy-Item (Join-Path $PSScriptRoot "dist\\$exeName") (Join-Path $installerDistDir $exeName) -Force
    Copy-Item .\icon.ico (Join-Path $installerDir "icon.ico") -Force

    Push-Location $installerDir
    try {
        & $iscc .\QuickCli.iss
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup 构建失败。"
        }
    }
    finally {
        Pop-Location
    }

    Copy-Item (Join-Path $installerDir "output\\$setupBaseName.exe") (Join-Path $rootOutputDir "$setupBaseName.exe") -Force
}
