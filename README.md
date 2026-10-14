# Launchpad

[![Verified local platform CI](https://github.com/alphaCoderVishal/launchpad/actions/workflows/ci.yml/badge.svg)](https://github.com/alphaCoderVishal/launchpad/actions/workflows/ci.yml)

**A developer self-service deployment control plane with a health gate, durable intent, owner isolation and an attributable recovery timeline.**

Java 21 / Spring Boot 3.5 / Spring Security / JDBC / Flyway / H2 / Docker / Prometheus / Terraform

Launchpad addresses a concrete platform problem: developers need a repeatable path to deploy a service, while the platform must retain the last healthy release when a candidate fails. This local lab provisions real constrained Docker containers, calls their real HTTP health endpoints, and atomically changes the active route only after three consecutive successes. A failed upgrade is recorded as `ROLLED_BACK`; the prior container continues serving. No LLM, API subscription or cloud account is required.

![Healthy local deployment](evidence/screenshots/01-healthy-deployment.png)

**For hiring managers:** [Screenshot walkthrough](docs/screenshots.md) · [Architecture and tradeoffs](docs/architecture.md) · [Verification evidence](docs/verification.md) · [Five-minute demo](docs/resume-and-demo.md)

## Quick start: Windows

Prerequisites: JDK 21 or 25, Maven 3.9+, Python 3.12+, Docker Desktop running Linux containers. The first build needs internet for Maven dependencies and the official workload base image. Subsequent deployment uses `--pull=never`.

From this directory:

```powershell
./scripts/start.ps1
```

Open [the dashboard](http://127.0.0.1:8088). Connect with `local-developer-token-change-me`. Register a service, deploy `v1`, call the active workload, then deploy `bad-health` and inspect the rollback timeline. Deploy `v2` with production policy; reconnect using `local-operator-token-change-me` to approve it. These are public **local demo tokens**. The second developer token `local-other-token-change-me` demonstrates ownership isolation.

The script builds the workload, runs tests, packages the service and starts it in the foreground. Ctrl+C stops the control plane; active workload containers intentionally survive so the persisted route still works after restarting. `./scripts/start.ps1 -SkipBuild` reuses the jar and image. It includes a verified Windows Java NIO workaround for MSIX-launched terminals, using a non-existent Unix socket path to trigger TCP fallback. Do not create `.nio-tcp-fallback/`.

Before non-demo use, set three unique randomly generated tokens (at least 24 characters), then launch. Tokens are read from the environment; they are not written by the dashboard or included in logs. Do not expose this lab to the internet.

```powershell
$env:DEVELOPER_TOKEN = '<random-developer-token>'
$env:OTHER_TOKEN = '<different-random-team-token>'
$env:OPERATOR_TOKEN = '<different-random-operator-token>'
./scripts/start.ps1 -SkipBuild
```

## Linux/macOS

```bash
docker build -t launchpad-workload:local workload
mvn -B verify
java -jar target/launchpad-1.0.0.jar
# Separate terminal:
python3 scripts/demo.py
```

Control plane and workload published ports bind to `127.0.0.1`. Default API port is 8088. Set `PORT` to change it. Workload ports are dynamically assigned by Docker. No Kubernetes cluster or Azure resources are provisioned.

## Verification and demos

```powershell
mvn -B verify
python scripts/demo.py
python scripts/acceptance.py
python scripts/recovery.py
```

The 17 integration tests use an in-memory database and a deterministic fake runtime; they cover the API and state machine, not the Docker daemon. The separate black-box acceptance script checks real Docker startup, release responses, failed health checks, rollback, approval, isolation, idempotency, first-release failure and authenticated metrics. It needs two free service slots and creates unique names. Team quota is five; use a fresh `DATABASE_URL` and `LAUNCHPAD_NAMESPACE` for repeated independent runs.

The recovery script owns an isolated child server on port 8090 and its own database/namespace. It kills that exact Java process while a real candidate is `DEPLOYING`, restarts against the same file DB, verifies the same Docker container ID was reused, checks the `RECONCILED` audit event, and confirms the healthy response. It removes only its own containers in `finally`. Port 8090 must be available.

`acceptance.py` runs the entire black-box suite against an isolated child server on port 8091 and cleans up that run's containers. It is the easiest repeatable acceptance command when your dashboard database already has demo history. Run acceptance and recovery sequentially on a quiet Docker Desktop engine; cold-start resource contention can make health gates fail legitimately.

Results and boundaries are recorded in [verification.md](docs/verification.md). Raw live evidence is generated into `evidence/runtime-*.json` (ignored so local identities/history do not accidentally publish); representative sanitized evidence can be included when publishing. CI performs Maven verification, both image builds and the live Docker acceptance script on an Ubuntu runner. The [first GitHub CI run passed](https://github.com/alphaCoderVishal/launchpad/actions/runs/38583306582) on 14 October 2026; its tested source commit is recorded in the verification report.

## API example

```powershell
$headers = @{ Authorization = 'Bearer local-developer-token-change-me' }
Invoke-RestMethod http://127.0.0.1:8088/api/services -Method Post -Headers $headers -ContentType application/json -Body '{"name":"payments-api"}'
$headers['Idempotency-Key'] = [guid]::NewGuid().ToString()
Invoke-RestMethod http://127.0.0.1:8088/api/services/payments-api/deployments -Method Post -Headers $headers -ContentType application/json -Body '{"release":"v1","environment":"dev"}'
```

POST returns 202 with a durable deployment ID. Retry the same payload with the same key to retrieve that intent. A different payload with that key returns 409. One pending/executing intent per service prevents promotion races. Status and audit events are available under `/api/deployments/{id}` and `/events`. See the [OpenAPI contract](src/main/resources/static/api-docs.yaml), also served at `/api-docs.yaml`.

## Architecture and recovery

```mermaid
flowchart LR
  UI[Dashboard / API client] -->|Bearer token| API[Spring Security + validated API]
  API -->|Transaction + service row lock| DB[(H2 + Flyway\nservices / intents / audit)]
  DB --> W[Single scheduled worker]
  W -->|Fixed argv / image allowlist| D[Local Docker engine]
  D --> C[Isolated candidate workload]
  W -->|HTTP /health x3| C
  W -->|Atomic active-route promotion| DB
  API -->|Read active port / HTTP greeting| A[Last healthy workload]
  W --> M[Metrics + structured log fields]
```

```mermaid
stateDiagram-v2
  [*] --> WAITING_APPROVAL: prod request
  [*] --> QUEUED: dev request
  WAITING_APPROVAL --> QUEUED: operator approval
  WAITING_APPROVAL --> CANCELLED: owner/operator cancel
  QUEUED --> CANCELLED: before execution
  QUEUED --> DEPLOYING: durable claim
  DEPLOYING --> DEPLOYING: restart reconciliation
  DEPLOYING --> SUCCEEDED: 3 consecutive healthy probes
  DEPLOYING --> ROLLED_BACK: failure + existing active route
  DEPLOYING --> FAILED: failure + no active route
```

Container names derive from the persisted UUID and configured namespace. A restarted worker inspects/starts that same candidate. Promotion and terminal status are committed in one DB transaction. Terminal deployment records act as a cleanup ledger: failed candidates and retired successful containers are removed after checking their namespace label; unsuccessful removal is retried. [Design decisions](docs/architecture.md) explain crash windows, ownership and tradeoffs.

## Observability

- `/actuator/health` is public and reports control-plane/DB health, not every workload's health.
- `/actuator/prometheus` requires the operator token. It exports queue depth, deployment outcome counters and deployment duration, alongside JVM/HTTP metrics.
- Logs include deployment UUID, service, result and bounded failure reason. Audit events persist requestor, approver, state transition and cleanup actor.
- Workload health is checked during deployment. An already promoted workload becoming unavailable yields 502 from the response API; ongoing self-healing or SLO guarantees are not implemented.

## Infrastructure and container packaging

[Terraform instructions](infra/README.md) include a verified local golden workload lifecycle and a provider-validated Azure **workload-only reference**. The API worker does not call Terraform; avoid having both Terraform and the API manage the same container. No Azure plan/apply or paid resource deployment has been performed.

After `mvn -B verify`, `docker build -t launchpad-control-plane:local .` packages the verified jar in a non-root Java 21 image with Docker CLI. `Dockerfile.source` is an alternative multi-stage source build (`docker build -f Dockerfile.source ...`) requiring Maven Central DNS/network access inside Docker; it has not completed successfully on this host. The adapter requires access to a local Docker daemon and the host's loopback network. On Linux, that means host networking and Docker socket access (a host-level trust boundary):

```bash
docker run --rm --network=host --group-add "$(stat -c '%g' /var/run/docker.sock)" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e BIND_ADDRESS=127.0.0.1 \
  launchpad-control-plane:local
```

This example is ephemeral unless `/app/data` is mounted to a writable persistent volume. The native Java launch is the verified full deployment path on Windows. A bridged control-plane container cannot reach sibling workload host ports via its own `127.0.0.1`; do not treat a health-only container smoke test as full adapter validation.

## Scope and security boundaries

- Local single-control-plane process, single scheduled worker, file-backed H2; no distributed lease or high availability.
- Five services per principal; constrained CPU, memory, PIDs, read-only filesystem, non-root UID, dropped capabilities and no-new-privileges for real workloads.
- Arbitrary images, shell commands, host mounts and user-defined environment variables are not accepted. Releases are the sample allowlist `v1`, `v2`, `bad-health`.
- Bearer role/ownership checks and strict JSON validation. No cookies/Basic/session auth, no permissive CORS; CSRF is disabled for explicit bearer credentials. Token identities are a lab implementation, not OIDC or Entra ID integration.
- `dev` and `prod` select approval policy on **one active slot per service**, not isolated environments.
- Rollback means preserving the prior active route; this lab does not perform rollback of external databases or irreversible application changes.
- Audit records are append-only through the API, not tamper-proof against a host/database administrator.
- Docker socket access is powerful. Run only on a trusted local development host. Workload ports are loopback-bound but directly accessible by local host processes.
- AI is intentionally omitted from the critical deployment path. Platform reliability evidence is the project focus.

Stop the service before cleanup:

```powershell
./scripts/cleanup.ps1
```

Cleanup removes only containers bearing the exact `launchpad` namespace label and preserves the database. After manual cleanup, historical active routes reference removed containers; start a new deployment or use a fresh database/namespace. No unrelated workspace files or containers are managed.

## Resume and interview evidence

See [resume bullets and demo narration](docs/resume-and-demo.md). Claim only implemented local features and distinguish local IaC verification from Azure validation. No throughput, uptime, business impact or cloud deployment metrics are invented.

References used for implementation: [Spring Boot system requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html), [Spring Security request authorization](https://docs.spring.io/spring-security/reference/6.5/servlet/authorization/authorize-http-requests.html), [Docker loopback port publishing](https://docs.docker.com/engine/network/port-publishing/), and [Azure Linux Web App provider contract](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/linux_web_app).
