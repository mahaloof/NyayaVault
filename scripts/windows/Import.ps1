[CmdletBinding()]
param([string]$TransferPath = 'transfer/current')
. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    Assert-VaultDocker
    $fullPath = [IO.Path]::GetFullPath((Join-Path $VaultRoot $TransferPath))
    if (-not $fullPath.StartsWith($VaultRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep the transfer folder inside this project.' }
    if (-not (Test-Path -LiteralPath (Join-Path $fullPath 'manifest.json'))) { throw 'The transfer manifest was not found. Extract the complete private transfer package first.' }
    $relative = $fullPath.Substring($VaultRoot.Length + 1).Replace('\', '/')
    Invoke-VaultDocker -DockerArguments @('build', '--tag', $VaultToolsImage, '--file', (Join-Path $VaultRoot 'docker/portable-tools/Dockerfile'), $VaultRoot)
    Invoke-VaultDocker -DockerArguments @('run', '--rm', '--volume', "${VaultRoot}:/project", '--volume', '/var/run/docker.sock:/var/run/docker.sock', $VaultToolsImage, 'python', '/workspace/scripts/transfer.py', 'restore', '--input', "/project/$relative")
    & (Join-Path $PSScriptRoot 'Start.ps1') -NoDemo
    if ($LASTEXITCODE -ne 0) { throw 'Portable startup failed. The source backup remains unchanged.' }
    Invoke-VaultDocker -DockerArguments @('run', '--rm', '--volume', "${VaultRoot}:/project", '--volume', '/var/run/docker.sock:/var/run/docker.sock', $VaultToolsImage, 'python', '/workspace/scripts/portable_verify.py', '--container', 'nyayavault-portable-backend-1', '--baseline', "/project/$relative/baseline.json", '--outputfile', '/project/docs/portability-restore-results.json')
    Write-Host 'The original users, cases, encrypted evidence and Fabric histories match the transfer snapshot.'
    Show-VaultUrls
} catch { Write-Error $_.Exception.Message; exit 1 }
