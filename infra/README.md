# Infrastructure boundaries

`local/` provisions the same non-root, read-only workload contract independently using Terraform's Docker provider. It is an IaC demonstration, not a second owner of the API-managed containers. It uses the `launchpad-terraform` label and an immutable image ID. Local lifecycle: init, validate, plan, apply, HTTP health check, plan (no changes), destroy. No cloud credentials needed.

PowerShell, from project root after building the workload:

```powershell
$env:TF_VAR_image_id = docker image inspect launchpad-workload:local --format '{{.Id}}'
terraform -chdir=infra/local init
terraform -chdir=infra/local validate
terraform -chdir=infra/local plan -out=local.tfplan
terraform -chdir=infra/local apply local.tfplan
Invoke-RestMethod http://127.0.0.1:8099/health
terraform -chdir=infra/local plan -detailed-exitcode
terraform -chdir=infra/local destroy
```

Linux: set `TF_VAR_docker_host=unix:///var/run/docker.sock`. Keep Terraform state private; it is ignored. Commit the provider lock file.

`azure/` is a standalone **workload-only reference**, not a functioning Azure control-plane adapter. It provisions a resource group, B1 Linux plan, HTTPS-only Web App, system identity and a health-check path for a published public workload image. Requires a unique app name, subscription, registry URL and image digest. Private ACR requires additional identity-based AcrPull configuration. Public ingress is intentional for the sample greeting workload, with no data or secrets. No Key Vault, certificates, VNet or production deployment claims are made. B1 incurs cost. No Azure plan or apply has been run. Syntax/provider validation, if recorded, is not deployment evidence.

App Service cannot execute this host Docker adapter. To support Azure deployments, implement `WorkloadRuntime` using managed identity and the ARM API, with asynchronous operation polling, deployment-slot routing, persisted operation IDs, health checks and compensation. The current interface does not claim that implementation exists.
