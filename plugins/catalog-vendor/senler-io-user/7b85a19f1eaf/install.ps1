[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$DuckworkHome,
    [string]$DuckworkCommand = 'duckwork'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-DuckworkChecked {
    param([string[]]$CommandArguments)
    & $DuckworkCommand @CommandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Duckwork command failed (exit $LASTEXITCODE): $($CommandArguments -join ' ')"
    }
}

$packageRoot = $PSScriptRoot

if (-not $DuckworkHome) {
    if ($env:DUCKWORK_HOME) {
        $DuckworkHome = $env:DUCKWORK_HOME
    } elseif ($env:LOCALAPPDATA) {
        $DuckworkHome = Join-Path $env:LOCALAPPDATA 'duckwork'
    } else {
        throw 'Pass -DuckworkHome with the directory containing your Duckwork config.yaml.'
    }
}
$DuckworkHome = [IO.Path]::GetFullPath($DuckworkHome)
if (-not (Test-Path -LiteralPath (Join-Path $DuckworkHome 'config.yaml') -PathType Leaf)) {
    throw "Duckwork config.yaml was not found in $DuckworkHome. Pass the correct directory with -DuckworkHome."
}
$null = Get-Command -Name $DuckworkCommand -ErrorAction Stop
$pluginsRoot = Join-Path $DuckworkHome 'plugins'
$destination = Join-Path $pluginsRoot 'senler-io-user'
if (Test-Path -LiteralPath $destination) {
    throw "Plugin directory already exists: $destination. Existing files were preserved. See README.md for updating."
}

$packageFiles = @('plugin.yaml', '__init__.py', 'senler_connection.py', 'senler_chat.py', 'senler_relay.py', 'senler_relay_store.py', 'senler_relay_setup.py', 'senler_relay_actions.py', 'senler_notifications.py', 'mcp-server.json', 'LICENSE', 'README.md', 'assets', 'skills', 'docs')
foreach ($relative in $packageFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $relative))) {
        throw "Incomplete package: $relative is missing. Extract the entire ZIP first."
    }
}

if (-not $PSCmdlet.ShouldProcess($destination, 'Validate, install and enable the Senler.io User plugin')) {
    return
}

$previousDuckworkHome = [Environment]::GetEnvironmentVariable('DUCKWORK_HOME', 'Process')
$staging = Join-Path $DuckworkHome ('.senler-install-' + [Guid]::NewGuid().ToString('N'))
try {
    $env:DUCKWORK_HOME = $DuckworkHome
    Invoke-DuckworkChecked -CommandArguments @('plugins', 'validate', $packageRoot)
    $null = New-Item -ItemType Directory -Path $staging
    foreach ($relative in $packageFiles) {
        Copy-Item -LiteralPath (Join-Path $packageRoot $relative) -Destination $staging -Recurse
    }
    $null = New-Item -ItemType Directory -Path $pluginsRoot -Force
    # Directory.Move refuses an existing destination, including a racing install.
    [IO.Directory]::Move($staging, $destination)
    try {
        Invoke-DuckworkChecked -CommandArguments @('plugins', 'enable', 'senler-io-user')
    } catch {
        throw "Files are installed at $destination, but enabling failed. Retry 'duckwork plugins enable senler-io-user' in the same Duckwork home. $($_.Exception.Message)"
    }
    Write-Host "Installed: $destination"
    Write-Host 'Next: when Duckwork loads the enabled plugin, senler-io-user is prepared in Connections / MCP. Select Authorize, or ask Connect Senler in a new chat.'
    Write-Host 'Terminal alternative: duckwork senler connect. The MCP address is bundled in the plugin.'
    Write-Host 'No webhook subscription or authorization was performed by the installer.'
} finally {
    [Environment]::SetEnvironmentVariable('DUCKWORK_HOME', $previousDuckworkHome, 'Process')
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
