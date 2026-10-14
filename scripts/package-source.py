"""Create a shareable source archive without runtime databases, tokens or host logs."""
import hashlib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
excluded = {'target', 'data', '.tools', '.terraform', '__pycache__', '.git'}
archive = root.parent / 'launchpad-source.zip'
files = []
for path in root.rglob('*'):
    if not path.is_file():
        continue
    relative = path.relative_to(root)
    if any(part in excluded for part in relative.parts):
        continue
    if path.suffix in {'.log', '.tfplan', '.tfvars'} or '.tfstate' in path.name or path.name == '.env' or path.name.startswith('runtime-'):
        continue
    files.append(path)
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(files):
        bundle.write(path, 'launchpad/' + path.relative_to(root).as_posix())
print(f'Packaged {len(files)} files: {archive}')
print('SHA256:', hashlib.sha256(archive.read_bytes()).hexdigest())
