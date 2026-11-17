#!/usr/bin/env python3
"""Run a synthetic Method example in a disposable, separate metadata workspace."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'model/src'))

from common.storage import Storage
from canopy.cli import run_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--physics', nargs='*',
                        choices=['solar', 'flood', 'wind', 'temperature', 'pollution'],
                        default=['solar', 'flood', 'wind'])
    args = parser.parse_args()
    cache = Storage.load(ROOT).cache_root / 'examples'
    cache.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='methods-', dir=cache))
    (workspace / 'AGENTS.md').write_text('Disposable synthetic test workspace.\n')
    shutil.copytree(ROOT / 'asset/schemas', workspace / 'asset/schemas')
    # Browser code is read-only shared code; synthetic outputs stay in this workspace.
    (workspace / 'visualizer').mkdir()
    for name in ('src', 'site', 'guide'):
        source = ROOT / 'visualizer' / name
        if source.exists(): (workspace / 'visualizer' / name).symlink_to(source, target_is_directory=True)
    result = run_demo(Storage.load(workspace), 'demo', args.physics)
    print(json.dumps({'workspace': str(workspace), 'disposable': True, **result,
                      'serve': f'canopy --root {workspace} serve --port 8770'}, indent=2))


if __name__ == '__main__':
    main()
