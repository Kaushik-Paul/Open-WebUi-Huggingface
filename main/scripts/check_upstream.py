"""Verify archive provenance and list/reject unexpected snapshot changes."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--archive', type=Path)
parser.add_argument('--report', action='store_true', help='Report current changed paths for upgrade review')
args = parser.parse_args()
lock = json.loads((ROOT / 'upstream.lock.json').read_text())
archive = args.archive or Path('/tmp/owui-upstream-verified.tar.gz')
if not archive.exists():
    archive.write_bytes(urllib.request.urlopen(lock['archive_url'], timeout=60).read())
assert hashlib.sha256(archive.read_bytes()).hexdigest() == lock['sha256'], 'Archive checksum mismatch'
changed = []
with tarfile.open(archive) as source:
    for member in source.getmembers():
        if not member.isfile(): continue
        relative = str(Path(member.name).relative_to(Path(member.name).parts[0]))
        local = ROOT / 'main/upstream' / relative
        if not local.exists() or hashlib.sha256(local.read_bytes()).digest() != hashlib.sha256(source.extractfile(member).read()).digest():
            changed.append(relative)
if args.report:
    print(json.dumps(changed, indent=2))
else:
    assert all((ROOT / 'main/upstream' / name).is_file() for name in lock.get('added_files', [])), 'Missing custom helper'
    assert set(changed) == set(lock['customized_files']), 'Unexpected snapshot differences; run --report and review'
    print(f"Verified {lock['release']} ({lock['commit']}); {len(changed)} documented modified upstream files")
