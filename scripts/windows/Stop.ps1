[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    Assert-VaultDocker
    Invoke-VaultCompose -ComposeArguments @('stop')
    Write-Host 'NyayaVault stopped. All database, evidence, keys and blockchain volumes were retained.'
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
