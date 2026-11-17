# Installs duckwork-vision-inline on Windows.
# Copies the plugin into %USERPROFILE%\.duckwork\plugins\duckwork-vision-inline and enables it.
$ErrorActionPreference = "Stop"

$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$duckworkHome = if ($env:DUCKWORK_HOME) { $env:DUCKWORK_HOME } else { Join-Path $env:USERPROFILE ".duckwork" }
$dest = Join-Path $duckworkHome "plugins\duckwork-vision-inline"

New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $src "__init__.py") $dest -Force
Copy-Item (Join-Path $src "plugin.yaml") $dest -Force
if (Test-Path (Join-Path $src "README.md")) { Copy-Item (Join-Path $src "README.md") $dest -Force }
if (Test-Path (Join-Path $src "docs")) { Copy-Item (Join-Path $src "docs") $dest -Recurse -Force }
Write-Host "copied plugin to $dest"

if (-not (Get-Command duckwork -ErrorAction SilentlyContinue)) {
    Write-Host "duckwork is not on PATH. Run this once it is:"
    Write-Host "  duckwork plugins enable duckwork-vision-inline"
    return
}

& duckwork plugins enable duckwork-vision-inline
if ($LASTEXITCODE -eq 0) {
    Write-Host "enabled. Restart the desktop backend to pick it up."
} else {
    Write-Host "enable failed. Add 'duckwork-vision-inline' to plugins.enabled in config.yaml by hand."
}
