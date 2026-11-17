Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$wrapper = Join-Path (Split-Path $PSScriptRoot -Parent) 'skills\senler-io-user\scripts\run-relay.ps1'
$beforeUtf8 = [Environment]::GetEnvironmentVariable('PYTHONUTF8', 'Process')
$beforeEncoding = $OutputEncoding
$global:RelayTestExit = 0
function global:Invoke-SenlerRelayTest {
    $global:RelayTestArgs = @($args)
    $global:RelayTestInput = @($input) -join "`n"
    $global:RelayTestUtf8 = $env:PYTHONUTF8
    $global:LASTEXITCODE = $global:RelayTestExit
    '{"configured":true}'
}
function Assert-True([bool]$condition, [string]$message) {
    if (-not $condition) { throw $message }
}
try {
    $text = -join ([char[]]@(0x41F, 0x440, 0x438, 0x432, 0x435, 0x442))
    $json = @{ instructions = $text; connection = @{ gateway_secret = 'fixture-secret' } } | ConvertTo-Json
    $output = $json | & $wrapper configure -EnableAutomation -DuckworkCommand 'Invoke-SenlerRelayTest'
    Assert-True ($global:RelayTestInput.Trim() -eq $json.Trim()) 'JSON stdin changed.'
    Assert-True (($global:RelayTestArgs -join ' ') -eq 'senler relay configure --enable-automation') 'Wrong native Duckwork command.'
    Assert-True ($global:RelayTestUtf8 -eq '1') 'UTF-8 was not enabled.'
    Assert-True ($output -eq '{"configured":true}') 'Credentials leaked into output.'
    Assert-True ([Environment]::GetEnvironmentVariable('PYTHONUTF8', 'Process') -eq $beforeUtf8) 'Python environment was not restored.'
    Assert-True ($OutputEncoding -eq $beforeEncoding) 'PowerShell encoding was not restored.'
    $null = '{"webhook_id":"fixture","expected_local_revision":1}' | & $wrapper resume -EnableAutomation -DuckworkCommand 'Invoke-SenlerRelayTest'
    Assert-True (($global:RelayTestArgs -join ' ') -eq 'senler relay resume --enable-automation') 'Resume authorization argument was lost.'
    $null = '{"webhook_id":"fixture"}' | & $wrapper instructions -DuckworkCommand 'Invoke-SenlerRelayTest'
    Assert-True (($global:RelayTestArgs -join ' ') -eq 'senler relay instructions') 'Instruction inspection was not passed to Duckwork.'
    $edit = @{ webhook_id = 'fixture'; instructions = $text; expected_local_revision = 1 } | ConvertTo-Json
    $null = $edit | & $wrapper update-instructions -DuckworkCommand 'Invoke-SenlerRelayTest'
    Assert-True (($global:RelayTestArgs -join ' ') -eq 'senler relay update-instructions') 'Instruction editing unexpectedly required reconfiguration.'
    Assert-True ($global:RelayTestInput.Trim() -eq $edit.Trim()) 'Edited Unicode instructions changed.'
    $null = & $wrapper notification-targets -DuckworkCommand 'Invoke-SenlerRelayTest'
    Assert-True (($global:RelayTestArgs -join ' ') -eq 'senler relay notification-targets') 'Target listing incorrectly requires stdin.'
    $null = '{"target":"telegram:12345"}' | & $wrapper resolve-notification-target -DuckworkCommand 'Invoke-SenlerRelayTest'
    Assert-True (($global:RelayTestArgs -join ' ') -eq 'senler relay resolve-notification-target') 'Notification resolution was not passed to Duckwork.'
    $global:RelayTestExit = 2
    $failed = $false
    try { $null = & $wrapper status -DuckworkCommand 'Invoke-SenlerRelayTest' } catch { $failed = $true }
    Assert-True $failed 'Native Duckwork failure was ignored.'
    $failed = $false
    try { $null = & $wrapper configure -DuckworkCommand 'Invoke-SenlerRelayTest' } catch { $failed = $true }
    Assert-True $failed 'Missing JSON input was accepted.'
    Write-Output 'PASS: relay CLI arguments, JSON stdin, Unicode, private credentials, UTF-8 restoration and failures.'
} finally {
    Remove-Item Function:\Invoke-SenlerRelayTest -ErrorAction SilentlyContinue
    Remove-Variable RelayTestArgs, RelayTestInput, RelayTestUtf8, RelayTestExit -Scope Global -ErrorAction SilentlyContinue
}
