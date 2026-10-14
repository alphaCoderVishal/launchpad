"""Start an isolated real stack, kill the control plane mid-deployment, then recover.

Only child Java processes and Docker containers in this run's unique namespace are stopped.
"""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from runtime_helpers import cleanup

root = Path(__file__).resolve().parents[1]
namespace = 'lp-recovery-' + uuid.uuid4().hex[:6]
base = 'http://127.0.0.1:8090'
token = os.getenv('DEVELOPER_TOKEN', 'local-developer-token-change-me')
output = root / 'evidence/runtime-recovery.json'
process = None
handles = []


def request(path, body=None, key=None):
    headers = {'Authorization': 'Bearer ' + token}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if key:
        headers['Idempotency-Key'] = key
    with urlopen(Request(base + path, headers=headers, data=json.dumps(body).encode() if body is not None else None), timeout=5) as response:
        return json.loads(response.read())


def wait_for(action, accept, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            result = action()
            if accept(result):
                return result
        except (URLError, TimeoutError):
            pass
        time.sleep(.3)
    raise AssertionError('Timed out waiting for recovery scenario')


def start(delay):
    global process
    log = open(root / f'evidence/{namespace}-{delay}.log', 'w', encoding='utf-8')
    handles.append(log)
    args = ['java', f'-Djdk.net.unixdomain.tmpdir={root / ".nio-tcp-fallback"}', '-jar', 'target/launchpad-1.0.0.jar',
            '--server.port=8090', f'--launchpad.namespace={namespace}',
            f'--spring.datasource.url=jdbc:h2:file:./data/{namespace};DB_CLOSE_ON_EXIT=FALSE',
            f'--launchpad.health-delay-ms={delay}', '--launchpad.health-deadline-ms=30000',
            '--logging.level.dev.launchpad.DockerRuntime=DEBUG']
    child = subprocess.Popen(args, cwd=root, stdout=log, stderr=subprocess.STDOUT)
    process = child
    wait_for(lambda: request('/actuator/health'), lambda r: r['status'] == 'UP')
    return child


def inspect(name):
    result = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=25)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


try:
    (root / 'evidence').mkdir(exist_ok=True)
    process = start(10000)
    request('/api/services', {'name': 'recovery-demo'})
    deployment = request('/api/services/recovery-demo/deployments', {'release': 'v1', 'environment': 'dev'}, uuid.uuid4().hex)
    name = deployment['candidateContainer']
    container = wait_for(lambda: inspect(name), lambda r: r is not None and r['State']['Running'])
    state = request('/api/deployments/' + deployment['id'])
    assert state['status'] == 'DEPLOYING', state
    before = container['Id']
    process.kill()  # Exact child handle; simulate abrupt loss, without cancelling durable deployment.
    process.wait(timeout=10)
    process = start(500)
    result = wait_for(lambda: request('/api/deployments/' + deployment['id']), lambda r: r['status'] in ['SUCCEEDED', 'FAILED', 'ROLLED_BACK'])
    assert result['status'] == 'SUCCEEDED', result
    after = inspect(name)['Id']
    assert before == after, 'Recovery created a duplicate container'
    events = request('/api/deployments/' + deployment['id'] + '/events')
    assert any(e['type'] == 'RECONCILED' for e in events), events
    response = request('/api/services/recovery-demo/response')
    assert response['release'] == 'v1' and response['healthy']
    evidence = {'namespace': namespace, 'passed': True, 'killed_state': state['status'],
                'same_container_id': before, 'deployment_after_restart': result, 'events': events, 'workload': response}
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('PASS: abrupt process loss recovered the same real container and promoted its healthy route', flush=True)
finally:
    if process is not None and process.poll() is None:
        process.kill()
        process.wait(timeout=10)
    for handle in handles:
        handle.close()
    cleanup(namespace)
