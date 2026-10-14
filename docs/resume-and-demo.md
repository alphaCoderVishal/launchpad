# Resume-ready wording and a five-minute demonstration

Use only after reviewing `verification.md` and reproducing the demo yourself. Suggested project entry:

**Launchpad | Developer Deployment Control Plane** — Java, Spring Boot, Docker, Terraform

- Built a Spring Boot self-service deployment control plane with owner-scoped bearer APIs, request validation, transactional idempotency, production approval policy and a persistent audit timeline.
- Implemented health-gated promotion of real local Docker workloads, retaining the last healthy route on failed upgrades and reconciling interrupted deployments using durable state and deterministic container identities.
- Added automated integration tests, live Docker failure/recovery scenarios, Prometheus metrics and a Terraform workload module with locally verified create, health, no-drift and destroy checks.

Do not claim production traffic, business impact, zero downtime, Azure deployment, OIDC integration or GitHub CI success. The Azure module is a workload-only reference; provider validation does not establish deployed infrastructure.

## Five-minute demo

1. **Problem (30s):** explain the developer golden path and why a failed candidate must not replace a healthy service.
2. **Happy path (60s):** authenticate as developer, register a service, deploy v1 and call the active workload. Show its real Docker name and loopback port.
3. **Failure (60s):** deploy bad-health. While it is DEPLOYING, call v1. When ROLLED_BACK, show v1 is still active and the failed candidate CLEANED event.
4. **Approval (60s):** submit v2 with prod policy. Show it waits and the developer cannot approve. Reconnect as operator, approve, show the actor in the audit timeline and the v2 response.
5. **Recovery/evidence (60s):** show recovery script evidence that killing a worker mid-deployment reuses the same real container ID; explain the DB/Docker transaction boundary.
6. **Tradeoff (30s):** explain single-worker/H2 scope, fixed image policy, ingress draining limitation and why Azure adapter work is separate.

## Interview questions to prepare

- What happens if the client times out after the intent commit?
- What prevents two deployments from promoting different candidates concurrently?
- Why must the same idempotency key reject a different payload?
- What happens when the process dies after Docker run but before status update?
- What authority does the Docker socket grant, despite a non-root application image?
- How would you implement a lease/fencing token with PostgreSQL for multiple workers?
- How would an Azure adapter persist ARM operation IDs, verify slot health and compensate after failure?
- What would you measure to establish deployment latency or availability, and what test conditions would make those measurements meaningful?
