"""Black-box acceptance against a running control plane and real Docker workloads.

Uses Python standard library only. Never prints bearer tokens.
"""
import argparse
import json
import os
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--base', default='http://127.0.0.1:8088')
parser.add_argument('--output', default='evidence/runtime-demo.json')
args = parser.parse_args()
dev = os.getenv('DEVELOPER_TOKEN', 'local-developer-token-change-me')
other = os.getenv('OTHER_TOKEN', 'local-other-token-change-me')
ops = os.getenv('OPERATOR_TOKEN', 'local-operator-token-change-me')
checks = []


def request(path, method='GET', body=None, token=dev, key=None, expect=200):
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if key:
        headers['Idempotency-Key'] = key
    req = Request(args.base + path, method=method, headers=headers,
                  data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(req, timeout=30) as response:
            status, raw = response.status, response.read().decode()
    except HTTPError as error:
        status, raw = error.code, error.read().decode()
    assert status == expect, (path, status, raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def check(name, evidence):
    checks.append({'check': name, 'passed': True, 'evidence': evidence})
    print('PASS:', name)


def terminal(deployment):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        current = request('/api/deployments/' + deployment['id'])
        if current['status'] in ('SUCCEEDED', 'FAILED', 'ROLLED_BACK', 'CANCELLED'):
            return current
        time.sleep(.4)
    raise AssertionError('Deployment timed out: ' + deployment['id'])


deadline = time.monotonic() + 60
while True:
    try:
        request('/actuator/health', token=None)
        break
    except (URLError, TimeoutError):
        if time.monotonic() >= deadline:
            raise
        time.sleep(.5)
services = request('/api/services')
suffix = uuid.uuid4().hex[:7]
service = 'demo-' + suffix
first_fail_service = 'failure-' + suffix
if len(services) > 3:
    raise SystemExit('Demo needs two free service slots (quota five). Use an isolated DATABASE_URL and namespace.')
request('/actuator/health', token=None)
request('/api/services', token=None, expect=401)
check('readiness and unauthenticated rejection', {'health': 'UP', 'anonymous': 401})
request('/api/services', 'POST', {'name': service}, expect=201)
request('/api/services/' + service, token=other, expect=404)
check('service ownership isolation', {'other_team': 404})
request('/api/services/' + service + '/deployments', 'POST', {'release': 'untrusted:latest', 'environment': 'dev'}, key=uuid.uuid4().hex, expect=400)
check('image/release policy rejection', {'unsupported_release': 400})
key = uuid.uuid4().hex
body = {'release': 'v1', 'environment': 'dev'}
first = request('/api/services/' + service + '/deployments', 'POST', body, key=key, expect=202)
replay = request('/api/services/' + service + '/deployments', 'POST', body, key=key, expect=202)
assert first['id'] == replay['id']
request('/api/services/' + service + '/deployments', 'POST', {'release': 'v2', 'environment': 'dev'}, key=key, expect=409)
check('idempotent replay and conflicting payload', {'same_id': first['id'], 'conflict': 409})
first = terminal(first)
assert first['status'] == 'SUCCEEDED', first
response = request('/api/services/' + service + '/response')
assert response['release'] == 'v1' and response['healthy']
check('real container startup and healthy baseline', {'deployment': first, 'workload': response})
bad = terminal(request('/api/services/' + service + '/deployments', 'POST', {'release': 'bad-health', 'environment': 'dev'}, key=uuid.uuid4().hex, expect=202))
assert bad['status'] == 'ROLLED_BACK', bad
response = request('/api/services/' + service + '/response')
assert response['release'] == 'v1' and response['healthy']
check('failed candidate preserves healthy route', {'deployment': bad, 'workload': response})
prod = request('/api/services/' + service + '/deployments', 'POST', {'release': 'v2', 'environment': 'prod'}, key=uuid.uuid4().hex, expect=202)
time.sleep(2)
assert request('/api/deployments/' + prod['id'])['status'] == 'WAITING_APPROVAL'
request('/api/deployments/' + prod['id'] + '/approve', 'POST', token=dev, expect=403)
request('/api/deployments/' + prod['id'] + '/approve', 'POST', token=ops)
prod = terminal(prod)
assert prod['status'] == 'SUCCEEDED', prod
response = request('/api/services/' + service + '/response')
assert response['release'] == 'v2'
events = request('/api/deployments/' + prod['id'] + '/events')
assert any(e['type'] == 'APPROVED' and e['actor'] == 'platform-ops' for e in events)
check('operator approval and healthy upgrade', {'deployment': prod, 'events': events, 'workload': response})
request('/api/services', 'POST', {'name': first_fail_service}, expect=201)
initial_bad = terminal(request('/api/services/' + first_fail_service + '/deployments', 'POST', {'release': 'bad-health', 'environment': 'dev'}, key=uuid.uuid4().hex, expect=202))
assert initial_bad['status'] == 'FAILED'
request('/api/services/' + first_fail_service + '/response', expect=503)
check('first release failure has no fabricated active workload', {'deployment': initial_bad, 'response_status': 503})
metrics = request('/actuator/prometheus', token=ops)
assert 'launchpad_deployments_total' in metrics and 'launchpad_queue_depth' in metrics
request('/actuator/prometheus', token=dev, expect=403)
check('authenticated observability', {'deployment_counter_present': True, 'queue_gauge_present': True, 'developer_denied': 403})
result = {'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'base': args.base,
          'service': service, 'failure_service': first_fail_service, 'checks': checks}
output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(f'{len(checks)} acceptance checks passed. Evidence: {output}')
