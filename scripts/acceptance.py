"""Run the real Docker acceptance suite on an isolated server/database, then clean up."""
import subprocess
import uuid
from pathlib import Path
from runtime_helpers import cleanup

root = Path(__file__).resolve().parents[1]
namespace = 'lp-accept-' + uuid.uuid4().hex[:6]
(root / 'evidence').mkdir(exist_ok=True)
with open(root / 'evidence/acceptance-server.log', 'w', encoding='utf-8') as log:
    process = subprocess.Popen([
        'java', f'-Djdk.net.unixdomain.tmpdir={root / ".nio-tcp-fallback"}', '-jar', 'target/launchpad-1.0.0.jar',
        '--server.port=8091', f'--launchpad.namespace={namespace}',
        f'--spring.datasource.url=jdbc:h2:file:./data/{namespace};DB_CLOSE_ON_EXIT=FALSE',
        '--logging.level.dev.launchpad.DockerRuntime=DEBUG'], cwd=root, stdout=log, stderr=subprocess.STDOUT)
    try:
        subprocess.run(['python', '-u', 'scripts/demo.py', '--base', 'http://127.0.0.1:8091'], cwd=root, check=True)
    finally:
        process.kill()
        process.wait(timeout=10)
        cleanup(namespace)
