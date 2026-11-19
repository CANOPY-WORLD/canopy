#!/usr/bin/env python3
"""Enforce stored public Geometry and Physics State bytes per Scenario."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'visualizer/tools'))
from build_pages import bounded, publication_reference, publications  # noqa: E402

LIMIT = 150_000_000  # Decimal MB, not MiB. Equality passes; one byte over fails.
TOTAL_LIMIT = 200_000_000
GROUPS = ('geometry', 'physics_state')


def policy(root, scenario):
    path = root / 'scenario' / scenario / 'asset-budget.json'
    value = json.loads(path.read_bytes())
    if (set(value) != {'schema_version', 'scenario_id', 'groups'} or
            value['schema_version'] != '1.0.0' or value['scenario_id'] != scenario or
            not isinstance(value['groups'], dict) or set(value['groups']) != set(GROUPS)):
        raise ValueError(f'Invalid asset budget policy: {path}')
    for group, rules in value['groups'].items():
        if not isinstance(rules, dict) or set(rules) != {'prefixes', 'files'}:
            raise ValueError(f'Invalid classification rules: {scenario}/{group}')
        for key in ('prefixes', 'files'):
            names = rules[key]
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                raise ValueError('Budget rules must be lists of relative paths')
            if len(names) != len(set(names)):
                raise ValueError('Duplicate budget rule')
            for name in names:
                if key == 'prefixes':
                    if not name.endswith('/'):
                        raise ValueError('Budget prefixes must end at a directory boundary')
                    bounded(root, name[:-1])
                else:
                    bounded(root, name)
    return value['groups']


def classify(name, groups):
    matches = [group for group, rules in groups.items()
               if name in rules['files'] or any(name.startswith(p) for p in rules['prefixes'])]
    if len(matches) != 1:
        raise ValueError(f'Each payload needs exactly one budget category: {name} ({matches})')
    return matches[0]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Budget verification does not accept redirected inventory URLs')


def request_bytes(url, *, api=False):
    headers = {'User-Agent': 'Canopy-asset-budget/1', 'Accept-Encoding': 'identity'}
    if api:
        if urlsplit(url).netloc != 'api.github.com':
            raise ValueError('GitHub API credentials cannot be sent to a data host')
        headers['Accept'] = 'application/vnd.github+json'
        if token := os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'):
            headers['Authorization'] = 'Bearer ' + token
    with build_opener(NoRedirect).open(Request(url, headers=headers), timeout=45) as response:
        if response.status != 200:
            raise ValueError(f'Cannot verify public inventory: HTTP {response.status}')
        if response.geturl() != url:
            raise ValueError('Budget verification does not accept redirected inventory URLs')
        data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise ValueError('Inventory response exceeds verification limit')
        return data


def verify_tree(manifest, tree):
    """Verify actual Git blob sizes without downloading hundreds of MB in CI."""
    if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
        raise ValueError('Incomplete Git tree; cannot verify remote payload sizes')
    prefix = f"snapshots/{manifest['snapshot']}/"
    actual = {}
    for entry in tree['tree']:
        if not entry['path'].startswith(prefix) or entry['type'] == 'tree':
            continue
        name = entry['path'][len(prefix):]
        if name == 'manifest.json':
            continue
        if (entry['type'] != 'blob' or entry['mode'] not in ('100644', '100755') or
                type(entry.get('size')) is not int or entry['size'] < 0 or name in actual):
            raise ValueError(f'Invalid remote payload: {name}')
        actual[name] = entry['size']
    expected = {entry['path']: entry['bytes'] for entry in manifest['files']}
    if actual.keys() != expected.keys():
        raise ValueError('Pinned snapshot has missing or unlisted payloads')
    for name, size in expected.items():
        if actual[name] != size:
            raise ValueError(f'Remote size differs from manifest: {name}: {actual[name]} != {size}')


def verify_remote(manifest, reference):
    repo = urlsplit(reference['repository'])
    if repo.netloc != 'github.com' or not re.fullmatch(r'/[\w.-]+/[\w.-]+', repo.path):
        raise ValueError('Remote budget verification currently requires a pinned public GitHub repository')
    prefix = f"{repo.path}/{reference['revision']}/snapshots/{reference['snapshot']}/"
    urls = [f'https://raw.githubusercontent.com{prefix}manifest.json',
            reference['base_url'] + 'manifest.json']
    for url in urls:
        data = request_bytes(url)
        if hashlib.sha256(data).hexdigest() != reference['manifest']['sha256']:
            raise ValueError('Remote and locked publication manifests disagree')
    tree = json.loads(request_bytes(
        f"https://api.github.com/repos{repo.path}/git/trees/{reference['revision']}?recursive=1", api=True))
    verify_tree(manifest, tree)


def check(root=ROOT, *, remote=False):
    root = Path(root)
    # Reuse the publication boundary checks, including hashes, duplicates, sizes,
    # owner IDs, total reconciliation and extra local payload rejection.
    publications(root)
    paths = sorted((root / 'scenario').glob('*/data/manifest.json'))
    owners = {p.parent.parent.name for p in paths}
    referenced = {p.parent.name for p in (root / 'scenario').glob('*/publication.json')}
    index = json.loads((root / 'visualizer/site/scenes/index.json').read_bytes())
    displayed = {entry['id'] for entry in index['scenes']}
    if not displayed or not (displayed | referenced | {index['default']}) <= owners:
        raise ValueError('A public Scenario is missing its budgeted publication manifest')
    results = []
    for path in paths:
        scenario_root = path.parent.parent
        manifest = json.loads(path.read_bytes())
        rules = policy(root, scenario_root.name)
        reference = publication_reference(scenario_root)
        if remote and reference:
            verify_remote(manifest, reference)
        totals = {key: {'bytes': 0, 'files': 0, 'limit_bytes': LIMIT, 'largest_files': []}
                  for key in GROUPS}
        for entry in manifest['files']:
            group = totals[classify(entry['path'], rules)]
            group['bytes'] += entry['bytes']
            group['files'] += 1
            group['largest_files'].append({'path': entry['path'], 'bytes': entry['bytes']})
        for group in totals.values():
            group['over_bytes'] = max(0, group['bytes'] - LIMIT)
            group['passed'] = group['bytes'] <= LIMIT
            group['largest_files'] = sorted(group['largest_files'], key=lambda f: (-f['bytes'], f['path']))[:10]
        results.append({'scenario_id': scenario_root.name, 'snapshot': manifest.get('snapshot'),
                        'total_bytes': manifest['bytes'], 'total_limit_bytes': TOTAL_LIMIT,
                        'over_bytes': max(0, manifest['bytes'] - TOTAL_LIMIT),
                        'passed': manifest['bytes'] <= TOTAL_LIMIT and all(g['passed'] for g in totals.values()),
                        'verification': ('remote Git blob sizes and served manifest' if remote and reference
                                         else 'locked inventory' if reference else 'local payload sizes and hashes'),
                        'groups': totals})
    return {'schema_version': '1.0.0', 'unit': 'bytes', 'limit_bytes': LIMIT,
            'total_limit_bytes': TOTAL_LIMIT, 'passed': all(s['passed'] for s in results),
            'scenarios': results}


def markdown(report):
    lines = ['# Scenario asset budgets', '',
             'Per public Scenario: 200,000,000 bytes total; 150,000,000 bytes each for Geometry and Physics State.', '',
             '| Scenario | Category | Bytes | MB | Over budget | Result |',
             '| --- | --- | ---: | ---: | ---: | --- |']
    for scenario in report['scenarios']:
        lines.append(f"| {scenario['scenario_id']} | TOTAL | {scenario['total_bytes']:,} | "
                     f"{scenario['total_bytes'] / 1_000_000:.2f} | {scenario['over_bytes']:,} | "
                     f"{'PASS' if scenario['total_bytes'] <= TOTAL_LIMIT else 'FAIL'} |")
        for name, group in scenario['groups'].items():
            lines.append(f"| {scenario['scenario_id']} | {name} | {group['bytes']:,} | "
                         f"{group['bytes'] / 1_000_000:.2f} | {group['over_bytes']:,} | "
                         f"{'PASS' if group['passed'] else 'FAIL'} |")
    for scenario in report['scenarios']:
        lines.extend(['', f"{scenario['scenario_id']} verification: {scenario['verification']}."])
        for name, group in scenario['groups'].items():
            lines.extend(['', f'Largest {name} files:', ''])
            lines.extend(f"- `{f['path']}`: {f['bytes']:,} bytes" for f in group['largest_files'])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-remote', action='store_true', help='Verify pinned Git blob sizes and served manifests')
    parser.add_argument('--json', type=Path, help='Write the full report, including failures')
    parser.add_argument('--summary', type=Path, help='Append a Markdown report, e.g. GITHUB_STEP_SUMMARY')
    args = parser.parse_args()
    try:
        report = check(remote=args.verify_remote)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f'Asset budget verification failed: {error}', file=sys.stderr)
        return 1
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + '\n')
    summary = markdown(report)
    print(summary)
    if args.summary:
        with args.summary.open('a') as stream:
            stream.write(summary)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
