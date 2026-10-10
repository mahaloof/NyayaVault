[CmdletBinding()]
param(
    [switch]$NoDemo,
    [ValidateRange(1024, 65535)][int]$FrontendPort = 3001,
    [ValidateRange(1024, 65535)][int]$BackendPort = 8001,
    [ValidateRange(1024, 65535)][int]$MinioConsolePort = 9001
)
. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    Assert-VaultDocker
    Initialize-VaultConfig -FrontendPort $FrontendPort -BackendPort $BackendPort -MinioConsolePort $MinioConsolePort
    Invoke-VaultCompose -ComposeArguments @('--profile', 'tools', 'build')
    Invoke-VaultCompose -ComposeArguments @('--profile', 'tools', 'run', '--rm', '--no-deps', 'fabric-bootstrap', 'init')
    Invoke-VaultCompose -ComposeArguments @('up', '-d', '--force-recreate')
    Invoke-VaultCompose -ComposeArguments @('--profile', 'tools', 'run', '--rm', '--no-deps', 'fabric-bootstrap', 'setup')
    Invoke-VaultCompose -ComposeArguments @('--profile', 'tools', 'run', '--rm', '--no-deps', 'tools', 'python', '/opt/nyayavault/config.py', 'wait', '--url', 'http://backend:8000/api/health', '--url', 'http://frontend:3000', '--timeout', '180')
    if (-not $NoDemo) {
        Invoke-VaultCompose -ComposeArguments @('--profile', 'tools', 'run', '--rm', '--no-deps', 'demo')
    }
    Write-Host 'NyayaVault is ready. Its database, encrypted evidence, identities and blockchain stay in Docker volumes.'
    Show-VaultUrls
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
