# Shared by the Windows PowerShell 5.1 entry points. No host language runtime required.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$VaultRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$VaultToolsImage = 'nyayavault-portable-tools:1.0'
$VaultComposeArgs = @('compose', '--project-name', 'nyayavault-portable', '--env-file', (Join-Path $VaultRoot '.env.portable'), '-f', (Join-Path $VaultRoot 'docker-compose.portable.yml'))

function Assert-VaultDocker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker was not found. Install Docker Desktop, start it, and reopen PowerShell.'
    }
    try {
        $engine = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $engine -ne 'linux') {
            throw 'Unavailable Linux engine'
        }
    } catch {
        throw 'Start Docker Desktop and select Linux containers (WSL 2 on Windows), then retry.'
    }
    & docker compose version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose v2 is required. Update Docker Desktop, then retry.'
    }
}

function Invoke-VaultDocker {
    param([Parameter(Mandatory = $true)][string[]]$DockerArguments)
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker could not complete this operation. The existing configuration and data were retained.'
    }
}

function Invoke-VaultCompose {
    param([Parameter(Mandatory = $true)][string[]]$ComposeArguments)
    if (-not (Test-Path -LiteralPath (Join-Path $VaultRoot '.env.portable') -PathType Leaf)) {
        throw 'Portable configuration is missing. Run Start.ps1 first, or restore the original .env.portable with your backup.'
    }
    # The portable file is authoritative. Shell variables otherwise take
    # precedence over --env-file and could silently replace retained AES keys.
    # Restore the caller's environment after this operation.
    $managedVariables = @('COMPOSE_FILE', 'COMPOSE_PROFILES', 'POSTGRES_PASSWORD', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY', 'JWT_SECRET', 'EVIDENCE_MASTER_KEY', 'FABRIC_GATEWAY_SECRET', 'FRONTEND_PORT', 'BACKEND_PORT', 'MINIO_CONSOLE_PORT')
    $savedEnvironment = @{}
    foreach ($name in $managedVariables) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    try {
        foreach ($name in $managedVariables) {
            [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        }
        Invoke-VaultDocker -DockerArguments ($VaultComposeArgs + $ComposeArguments)
    } finally {
        foreach ($name in $managedVariables) {
            [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
        }
    }
}

function Initialize-VaultConfig {
    param([int]$FrontendPort = 3001, [int]$BackendPort = 8001, [int]$MinioConsolePort = 9001)
    Invoke-VaultDocker -DockerArguments @('build', '--tag', $VaultToolsImage, '--file', (Join-Path $VaultRoot 'docker/portable-tools/Dockerfile'), $VaultRoot)
    Invoke-VaultDocker -DockerArguments @('run', '--rm', '--volume', "${VaultRoot}:/project", $VaultToolsImage, 'python', '/opt/nyayavault/config.py', 'ensure', '--frontend-port', "$FrontendPort", '--backend-port', "$BackendPort", '--minio-console-port', "$MinioConsolePort")
}

function Show-VaultUrls {
    Invoke-VaultDocker -DockerArguments @('run', '--rm', '--volume', "${VaultRoot}:/project:ro", $VaultToolsImage, 'python', '/opt/nyayavault/config.py', 'urls')
}
