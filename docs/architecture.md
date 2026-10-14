# Design decisions and failure analysis

## Why this project

The developer platform is focused on Java service APIs, lifecycle automation and delivery reliability. A narrow, real deployment mechanism is more feasible to verify locally than a broad incident assistant requiring external telemetry and an LLM evaluation dataset. This repository is personal lab code; no employer systems or code are included.

## Transaction boundaries

Service registration locks one quota row before checking owner service count, preventing two registrations from both consuming the last slot. Deployment submission locks the service row, checks owner/key replay, prevents another pending intent, then inserts intent and audit event together. A unique `(requested_by, request_key)` constraint handles concurrent key reuse across different services. Ownership is rechecked before submission; ownership is immutable in this implementation.

Approval/cancellation lock the same service row as submission and worker claim. Once the worker claims `DEPLOYING`, cancellation is rejected rather than racing an external Docker operation. Promotion updates the service route and deployment state in one transaction. No database transaction stays open while Docker starts or health checks wait.

The system assumes one process using the file database. H2 file locking prevents a second normal embedded connection process from opening it; this is not a substitute for distributed worker leases. Do not change the URL to a shared external database and scale replicas without adding leases/fencing and outbox/reconciliation semantics.

## Crash windows

| Window | Recovery behavior |
|---|---|
| Before intent commit | No deployment exists; client retries with the same idempotency key. |
| After commit, before worker claim | Persisted QUEUED row is read on the next tick/restart. |
| After DEPLOYING commit, before Docker run | Same UUID-derived candidate name is started. |
| After Docker run, before health/promotion | Worker inspects namespace label, starts/reuses existing candidate and repeats health checks. |
| After promotion commit, before old-container cleanup | New route survives in DB; terminal history is scanned and old container removal is retried. |
| During failed-candidate cleanup | Terminal failure/rollback stays durable; cleanup event appears only after confirmed removal. |

There is no atomic transaction spanning Docker and SQL. Deterministic operation names and reconciliation compensate for that boundary. The same UUID is used as a Docker label and audit ID. Runtime counters reset on process restart; durable deployment/audit history remains the source of truth.

## Health gate

The candidate must pass three consecutive `/health` responses with HTTP 200. Success counters reset after any non-200 or connection failure. The default is at most 60 attempts, spaced 500ms, with a 30-second health deadline after container start. A single request has 2-second connect/read bounds; finishing a request can extend the deadline slightly. Docker operations have a separate 60-second timeout. This is a sample probe policy, not an SLO.

The active route is unchanged while testing the candidate. An upgrade failure records ROLLED_BACK and removes the failed candidate; a first-release failure records FAILED and leaves no active endpoint. After promotion the previous container is retired. A request that already read the old port just before cleanup may fail; draining/in-flight request handling is a future extension. The greeting proxy is a demonstration API, not a production ingress gateway.

## Runtime trust boundary

The application invokes Docker via fixed argument arrays, never a shell. Client release values cannot introduce images, commands or mounts. The configured image is administrator-controlled; Docker does not pull at deployment time. Container ownership is checked by exact namespace labels before reuse/removal. Operators must choose distinct namespaces for independent databases. Labels protect against accidental cleanup, not a malicious host administrator.

Candidate ports bind only to loopback. The sample image runs with UID 10001, read-only root, 64MiB memory, 0.25 CPU, PIDs capped at 64, all capabilities dropped and no-new-privileges. Docker daemon access still confers broad host-level power on the control-plane process. Production should use a constrained remote runtime API, immutable artifact policy, identity federation and a separately secured ingress/data plane.

## Explicit tradeoffs

H2 enables a reproducible setup with no external DB; PostgreSQL and multi-worker support are future work. Static bearer principals demonstrate authorization, not identity lifecycle or rotation. A fixed sample image makes real rollout failure injection safe and deterministic; it is not a general container marketplace. Production policy shares one local slot with development. Terraform independently demonstrates the workload contract; the control-plane runtime currently calls Docker directly.

No Kubernetes, multi-region recovery, certificate issuance, private ACR authentication, Azure adapter, external LLM integration, alert delivery or persistent SLO dashboard is claimed. These can be added incrementally with evidence, rather than using scaffolding as a resume claim.
