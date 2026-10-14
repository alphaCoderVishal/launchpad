# Local verification record

Verified on 14 October 2026 (IST), Windows 11, Temurin Java 25.0.2, Maven 3.9.6, Python 3.12.2 and Docker Desktop engine 29.2.1 (Linux containers). Source targets Java 21; the packaging image runs Java 21. These are local functional checks, not production uptime/load measurements.

| Check | Observed result | Evidence |
|---|---|---|
| `mvn -B verify` | 17 tests, zero failures/errors; executable jar packaged | `evidence/integration-tests.txt`, `target/surefire-reports/`, `evidence-build.log` |
| `python scripts/acceptance.py` | Nine live HTTP/Docker checks passed | `evidence/runtime-demo.json`, `evidence/acceptance-server.log` |
| `python scripts/recovery.py` | Abrupt kill while DEPLOYING; same real container ID reused; RECONCILED then SUCCEEDED; healthy v1 greeting | `evidence/runtime-recovery.json` |
| Dashboard through Edge | Developer/operator login, service registration, deployment submission/completion, active response and rollback audit timeline inspected | `evidence/dashboard.png` |
| Control-plane image | Image built from verified jar; non-root UID 10001; health UP, bearer identity API and OpenAPI contract 200 with worker disabled | `evidence/package-smoke.json`, `docker-build.log` |
| Terraform local module | Init and validate; apply created one container; real `/health` 200; next plan exit 0 with no changes; destroy removed one resource | `terraform-local.log`, `terraform-apply.log`, `terraform-drift.log`, `terraform-destroy.log` |
| Terraform Azure reference | Init and provider validation succeeded using azurerm 4.81.0 | `terraform-azure.log`; no plan/apply/cloud resources |
| JavaScript/Python/contracts | Node syntax check, Python compilation, OpenAPI YAML and workflow YAML parsing; Terraform formatting check | Commands recorded below |

## Live acceptance assertions

### Remote GitHub verification

The [GitHub Actions run 38583306582](https://github.com/alphaCoderVishal/launchpad/actions/runs/38583306582) completed successfully on 14 October 2026 for commit `cd733049daac98d0fc432b06cdbfb47cc8015abf`. It passed integration tests/packaging, the real workload image build, control-plane image packaging, live Docker acceptance and evidence upload on an Ubuntu runner. The run metadata is retained in `evidence/github-ci.json`. Subsequent documentation-only publication updates do not change the tested application source. Abrupt-restart recovery and Terraform lifecycle checks remain locally verified; they are not part of this remote workflow.

1. Control-plane readiness and unauthenticated 401.
2. Cross-team service reads return 404.
3. Unsupported release is rejected with 400.
4. Same idempotency key/payload returns the same deployment UUID; conflicting payload returns 409.
5. A real healthy v1 container is promoted and returns its greeting.
6. bad-health upgrade records ROLLED_BACK while the real v1 response remains healthy.
7. Production waits for approval, developer gets 403, operator approval is attributable, and v2 serves after promotion.
8. Failed first deployment has state FAILED and response API returns 503 with no invented active workload.
9. Operator metrics include deployment counters/queue gauge; developer scrape is rejected with 403.

## Defects found through verification

- Spring's repository exception-translation proxy made direct field access incorrect; JDBC is accessed through a method, and all API/state-machine tests pass.
- Windows process argument handling affected a Docker template with nested quotes; ownership checks now parse `{{json .Config.Labels}}`.
- Cold Docker Desktop starts exceeded the initial probe/command window. Health has a bounded 30-second window and CLI commands a bounded 60-second timeout. Under resource contention a healthy candidate can still miss the gate; retaining the old route is the intended failure behavior. Acceptance should run on a quiet local engine.
- This Windows MSIX environment failed Java NIO Unix socket initialization. The start script's non-existent `jdk.net.unixdomain.tmpdir` triggers JDK TCP fallback. Native Java service startup was then observed; no system protection settings were changed.
- Browser QA found a stale timeline when changing service/identity; those views now reset and ignore stale audit responses.
- Acceptance teardown could race a removal already dispatched by the worker. The cleanup helper now checks exact ownership and confirms eventual absence before treating the race as a failure.
- A multi-stage source container build failed because Docker could not resolve Maven Central. The verified artifact-based Dockerfile builds successfully. `Dockerfile.source` is retained as an alternative and not represented as verified.

## Reproduce

```powershell
mvn -B verify
python scripts/acceptance.py
python scripts/recovery.py
node --check src/main/resources/static/app.js
python -m py_compile scripts/acceptance.py scripts/demo.py scripts/recovery.py scripts/runtime_helpers.py workload/server.py
terraform fmt -check -recursive infra
```

Stop a running native jar before repackaging it on Windows; otherwise Maven cannot rename the locked jar. Acceptance/recovery use ports 8091/8090 and unique namespaces/databases. The dashboard defaults to 8088. See `infra/README.md` for Terraform commands.

Runtime JSON files and host logs are ignored/excluded from the source archive. The compact `evidence/summary.json` and integration report provide portable evidence. Resume bullets are based on observed local functionality. This record describes checks completed before GitHub publication; remote workflow results are separate from these local results. No Azure deployment, paid cloud resource, job application or recruiter message was performed.
