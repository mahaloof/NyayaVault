[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    Assert-VaultDocker
    Invoke-VaultCompose -ComposeArguments @('--profile', 'tools', 'build', 'tools')
    Invoke-VaultCompose -ComposeArguments @('--profile', 'tools', 'run', '--rm', '--no-deps', '--volume', "${VaultRoot}:/project", '--env', 'NYAYAVAULT_TEST_API=http://backend:8000/api', '--env', 'NYAYAVAULT_TEST_PROVIDER=fabric', '--env', 'NYAYAVAULT_TEST_REPORT=/project/docs/portability-workflow-results.json', 'tools', 'python', '/workspace/scripts/smoke-docker.py')
    Write-Host 'Upload, encryption, verification, custody, permissions, download and real Fabric commit checks passed. The test case was archived automatically.'
} catch { Write-Error $_.Exception.Message; exit 1 }
