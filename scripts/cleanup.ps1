param([string]$Namespace = 'launchpad')
$ErrorActionPreference = 'Stop'
if ($Namespace -notmatch '^[a-z][a-z0-9-]{0,24}$') { throw 'Invalid namespace.' }
Write-Host 'Stop the control plane before cleanup. This removes only containers with the exact namespace label.'
$ids = @(docker ps -aq --filter "label=dev.launchpad.namespace=$Namespace")
if ($LASTEXITCODE -ne 0) { throw 'Docker listing failed.' }
foreach ($id in $ids) {
    if ($id -match '^[a-f0-9]{12,64}$') {
        $labelsJson = docker inspect --format '{{json .Config.Labels}}' $id
        if ($LASTEXITCODE -ne 0) { throw 'Container inspection failed.' }
        $labels = $labelsJson | ConvertFrom-Json
        if ($labels.'dev.launchpad.namespace' -ne $Namespace) { throw 'Container ownership check failed.' }
        docker rm -f $id
        if ($LASTEXITCODE -ne 0) { throw 'Container removal failed.' }
    }
}
