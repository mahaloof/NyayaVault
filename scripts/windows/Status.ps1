[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    Assert-VaultDocker
    Invoke-VaultCompose -ComposeArguments @('ps', '-a')
    Show-VaultUrls
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
