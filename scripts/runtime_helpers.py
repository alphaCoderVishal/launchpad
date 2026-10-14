"""Ownership-checked cleanup for isolated local runtime checks."""
import json
import re
import subprocess
import time


def inspect(identifier):
    result = subprocess.run(['docker', 'inspect', identifier], capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        return json.loads(result.stdout)[0]
    if 'No such object' in result.stderr or 'No such container' in result.stderr:
        return None
    raise RuntimeError('Docker inspection failed: ' + result.stderr.strip())


def cleanup(namespace):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,24}', namespace):
        raise ValueError('Invalid namespace')
    listing = subprocess.run(['docker', 'ps', '-aq', '--filter', f'label=dev.launchpad.namespace={namespace}'],
                             capture_output=True, text=True, timeout=30, check=True)
    for identifier in listing.stdout.split():
        item = inspect(identifier)
        if item is None:
            continue
        if item['Config']['Labels'].get('dev.launchpad.namespace') != namespace:
            raise RuntimeError('Container namespace changed during cleanup')
        removal = subprocess.run(['docker', 'rm', '-f', identifier], timeout=60, capture_output=True, text=True)
        if removal.returncode != 0:
            # The killed worker may already have dispatched a Docker removal.
            # Confirm eventual absence rather than calling that race a failure.
            deadline = time.monotonic() + 30
            while inspect(identifier) is not None:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Cleanup failed: ' + removal.stderr.strip())
                time.sleep(.3)
