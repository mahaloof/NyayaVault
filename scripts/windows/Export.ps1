[CmdletBinding()]
param(
    [switch]$Legacy,
    [string]$OutputPath = ('transfer/export-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
)
. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    Assert-VaultDocker
    $fullPath = [IO.Path]::GetFullPath((Join-Path $VaultRoot $OutputPath))
    if (-not $fullPath.StartsWith($VaultRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Choose an output folder inside the project.' }
    $relative = $fullPath.Substring($VaultRoot.Length + 1).Replace('\', '/')
    $source = 'portable'
    if ($Legacy) { $source = 'legacy' }
    Invoke-VaultDocker -DockerArguments @('build', '--tag', $VaultToolsImage, '--file', (Join-Path $VaultRoot 'docker/portable-tools/Dockerfile'), $VaultRoot)
    Invoke-VaultDocker -DockerArguments @('run', '--rm', '--volume', "${VaultRoot}:/project", '--volume', '/var/run/docker.sock:/var/run/docker.sock', $VaultToolsImage, 'python', '/workspace/scripts/transfer.py', 'export', '--source', $source, '--output', "/project/$relative")
    Write-Host "Private transfer snapshot saved to $fullPath. Keep it private: it contains encryption keys and account/database data."
} catch { Write-Error $_.Exception.Message; exit 1 }
