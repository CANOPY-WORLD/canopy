#!/usr/bin/env python3
"""Build Canopy from a clean main checkout; optionally push the Pages artifact."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from build_pages import ROOT, build
from check_publications import check


def git(*args, cwd=ROOT, env=None, input=None):
    return subprocess.check_output(['git', *args], cwd=cwd, env=env, input=input, text=True).strip()


def publish(push=False):
    if git('branch', '--show-current') != 'main' or git('status', '--porcelain'):
        raise ValueError('Publish from a clean, committed main checkout')
    source = git('rev-parse', 'HEAD')
    remote_main = git('ls-remote', 'origin', 'refs/heads/main').split()[0]
    if push and source != remote_main:
        raise ValueError('Push the reviewed main commit before publishing its website')
    # The PR gate and publication use the same limits and complete inventories.
    subprocess.run([sys.executable, str(ROOT / 'asset/tools/check_budgets.py'), '--verify-remote'],
                   cwd=ROOT, check=True)
    cache = ROOT / 'cache'
    cache.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='pages-release-', dir=cache))
    output = workspace / 'site'
    report = build(ROOT, output)
    # Link only to already deployed data. Large bytes never enter this artifact.
    report['remote_verification'] = check(ROOT)
    previous = git('ls-remote', 'origin', 'refs/heads/gh-pages')
    if previous:
        git('fetch', '--no-tags', 'origin', 'refs/heads/gh-pages')
        parent = git('rev-parse', 'FETCH_HEAD')
    else:
        parent = source
    # A separate index assembles the artifact without checking out or modifying
    # the source branch. Existing public blobs are reused from the same repository.
    env = dict(os.environ, GIT_INDEX_FILE=str(workspace / 'index'))
    prefix = ('--git-dir', git('rev-parse', '--absolute-git-dir'), '--work-tree', str(output))
    git(*prefix, 'read-tree', '--empty', cwd=output, env=env)
    git(*prefix, 'add', '--all', '--force', '.', cwd=output, env=env)
    tree = git(*prefix, 'write-tree', cwd=output, env=env)
    commit = git('commit-tree', tree, '-p', parent,
                 input=f'Deploy Canopy from main {source}\n\nShared website and verified Scenario data references.\n')
    report.update(source_commit=source, pages_commit=commit, artifact=str(output), pushed=False)
    if push:
        # Normal fast-forward only: a concurrent publication is rejected.
        git('push', 'origin', f'{commit}:refs/heads/gh-pages')
        report['pushed'] = True
    (workspace / 'publication.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--push', action='store_true', help='Publish the verified artifact to origin/gh-pages')
    args = parser.parse_args()
    print(json.dumps(publish(args.push), indent=2))
