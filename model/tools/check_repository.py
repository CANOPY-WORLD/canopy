#!/usr/bin/env python3
"""Check the curated catalog, contributor references and review site without private data."""
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

from build_review_inventory import ROOT, SCENARIO, CATALOG, INVENTORY, encoded, inventory, read


def main():
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)

    curated = sorted(p.parent.name for p in (ROOT / 'scenario').glob('*/scenario.json'))
    require(curated == [SCENARIO], f'Expected one London Scenario, found {curated}')
    scene = read(ROOT / 'scenario' / SCENARIO / 'scenario.json')
    for name, key in [('visualizer/site/scenes/index.json', 'id'),
                      ('visualizer/src/visualization/public-scenes.json', 'scene_id')]:
        ids = [s[key] for s in read(ROOT / name)['scenes']]
        require(ids == [SCENARIO], f'Unexpected public Scenario catalog: {name}: {ids}')
    catalog = read(CATALOG)
    references = {a['reference']: a for a in catalog['assets']}
    require(set(references) == set(scene['assets']), 'Review Asset references differ from scenario.json')
    expected_selected = {(s['asset'], s['layer']) for s in scene['visualization']['layers']}
    catalog_selected = {(a['reference'], l['id']) for a in catalog['assets']
                        for l in a['layers'] if l['selected']}
    require(expected_selected == catalog_selected, 'Review selected layers differ from scenario.json')
    for a in catalog['assets']:
        require(set(a['derived_from']) <= references.keys(), f'Unknown Asset dependency: {a["reference"]}')
    data = inventory(catalog)
    require(INVENTORY.exists() and INVENTORY.read_text() == encoded(data), 'Stale review inventory; run build_review_inventory.py')
    require((ROOT / 'visualizer/guide/architecture.svg').read_bytes() ==
            (ROOT / 'visualizer/diagrams/architecture.svg').read_bytes(), 'Stale guide diagram')
    for group in data['models']:
        for method in group['methods']:
            for field in ('guide', 'example'):
                require((ROOT / method[field]).is_file(), f'Missing Method {field}: {method[field]}')
            example = read(ROOT / method['example'])
            require(example['model_id'] == method['model_id'] and example['method_id'] == method['method_id'],
                    f'Method example identity differs: {method["example"]}')
    for schema in (ROOT / 'asset/schemas').glob('*.json'):
        mirror = ROOT / 'model/src/canopy/schemas' / schema.name
        require(mirror.exists() and mirror.read_bytes() == schema.read_bytes(), f'Schema mirror differs: {schema.name}')
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    docs = [ROOT / n for n in sorted(set(names)) if n.endswith('.md') and (ROOT / n).is_file()]
    for doc in docs:
        text = doc.read_text()
        require(not re.search(r'[\u4e00-\u9fff]', text), f'Non-English documentation: {doc.relative_to(ROOT)}')
        # Ignore fenced examples; their links can intentionally illustrate a future path.
        text = re.sub(r'```[\s\S]*?```', '', text)
        for match in re.finditer(r'!?\[[^\]\n]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text):
            target = match[1].strip('<>')
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not parts.path or parts.path.startswith('/'):
                continue
            resolved = doc.parent / unquote(parts.path)
            require(resolved.exists(), f'Broken Markdown link: {doc.relative_to(ROOT)} → {target}')
    for component in ('model', 'asset', 'visualizer', 'scenario'):
        for file in ('README.md', 'CONTRIBUTING.md', 'AGENTS.md'):
            require((ROOT / component / file).is_file(), f'Missing {component}/{file}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Checked one London Scenario, {len(references)} Assets, '
          f'{sum(len(m["methods"]) for m in data["models"])} Methods, schema mirrors and {len(docs)} English documents.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
