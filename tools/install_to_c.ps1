param(
    [string]$InstallRoot = "C:\BitLifeSurvival",
    [switch]$PrintOnly,
    [switch]$CreateShortcut
)

$ErrorActionPreference = "Stop"

$sourceRepo = (Resolve-Path "$PSScriptRoot\..").Path
$targetRepo = Join-Path $InstallRoot "Vault_Bit_Survival"

$saveDir = Join-Path $InstallRoot "saves"
$logDir = Join-Path $InstallRoot "logs"
$configDir = Join-Path $InstallRoot "config"

Write-Host "Source repo: $sourceRepo"
Write-Host "Target repo: $targetRepo"

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
New-Item -ItemType Directory -Path $saveDir -Force | Out-Null
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
New-Item -ItemType Directory -Path $configDir -Force | Out-Null

$roboArgs = @(
    """$sourceRepo""",
    """$targetRepo""",
    "/E",
    "/R:2",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/XD", ".venv", ".git", "__pycache__", ".pytest_cache", "logs", "saves"
)

if ($PrintOnly) {
    Write-Host "Run this command to copy repository:"
    Write-Host ("robocopy " + ($roboArgs -join " "))
} else {
    Write-Host "Copying repo files to install path..."
    robocopy @roboArgs | Out-Null
}

if ($CreateShortcut) {
    $shortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Bit Life Survival.lnk"
    $targetCmd = Join-Path $targetRepo "tools\run_game.cmd"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetCmd
    $shortcut.WorkingDirectory = $targetRepo
    $shortcut.WindowStyle = 1
    $shortcut.Description = "Run Bit Life Survival"
    $shortcut.Save()
    Write-Host "Created desktop shortcut: $shortcutPath"
}

Write-Host ""
Write-Host "Runtime data initialized:"
Write-Host "  Saves:  $saveDir"
Write-Host "  Logs:   $logDir"
Write-Host "  Config: $configDir"
Write-Host ""
Write-Host "Run game command:"
Write-Host "  cd /d $targetRepo && python -m bit_life_survival.app.main"
