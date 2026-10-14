param([int]$Port = 8088, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    docker info --format '{{.ServerVersion}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first.' }
    if (-not $SkipBuild) {
        docker build -t launchpad-workload:local workload
        if ($LASTEXITCODE -ne 0) { throw 'Workload image build failed.' }
        mvn -B verify
        if ($LASTEXITCODE -ne 0) { throw 'Build/tests failed.' }
    }
    $env:PORT = "$Port"
    Write-Host "Dashboard: http://127.0.0.1:$Port"
    Write-Host 'Local demo developer token: local-developer-token-change-me'
    Write-Host 'Use custom DEVELOPER_TOKEN/OTHER_TOKEN/OPERATOR_TOKEN for any non-demo use.'
    # A non-existent Unix socket directory makes Windows JDK PipeImpl fall back to TCP.
    # This avoids an MSIX-launched Java NIO issue without changing system settings.
    $nioFallback = Join-Path $PWD '.nio-tcp-fallback'
    if (Test-Path -LiteralPath $nioFallback) { throw 'The NIO fallback path must not exist.' }
    java "-Djdk.net.unixdomain.tmpdir=$nioFallback" -jar target/launchpad-1.0.0.jar
    if ($LASTEXITCODE -ne 0) { throw 'Control plane exited with an error.' }
} finally { Pop-Location }
