#!/usr/bin/env python3
"""Verify pinned remote manifests; optionally stream and hash every public payload."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from build_pages import ROOT, checksum, publication_reference, publications


def verify_url(url, expected_bytes, expected_hash):
    for attempt in range(4):
        try:
            request = Request(url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'Canopy-publication-check/1'})
            with urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise ValueError(f'Unexpected resource status: {response.status} {url}')
                total, digest = 0, hashlib.sha256()
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > expected_bytes:
                        raise ValueError(f'Remote resource exceeds declared size: {url}')
                    digest.update(chunk)
                if total != expected_bytes or digest.hexdigest() != expected_hash:
                    raise ValueError(f'Remote resource checksum/size mismatch: {url}')
                return total
        except HTTPError as error:
            if error.code not in (502, 503, 504) or attempt == 3:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
        time.sleep(0.2 * 2 ** attempt)


def check(root=ROOT, payloads=False):
    resources, _ = publications(root)
    manifests = []
    for path in sorted((root / 'scenario').glob('*/publication.json')):
        reference = publication_reference(path.parent)
        manifest_path = path.parent / reference['manifest']['path']
        expected_bytes, expected_hash = manifest_path.stat().st_size, checksum(manifest_path)
        verify_url(reference['base_url'] + 'manifest.json', expected_bytes, expected_hash)
        repo = urlsplit(reference['repository'])
        # The Pages snapshot and the recorded Git commit must identify the same bytes.
        if repo.netloc == 'github.com' and len(repo.path.strip('/').split('/')) == 2:
            pinned = (f'https://raw.githubusercontent.com{repo.path}/{reference["revision"]}'
                      f'/snapshots/{reference["snapshot"]}/manifest.json')
            verify_url(pinned, expected_bytes, expected_hash)
        manifests.append({'scenario_id': reference['scenario_id'], 'snapshot': reference['snapshot'],
                          'manifest_sha256': expected_hash, 'repository_revision': reference['revision']})
    remote = [r for r in resources.values() if r['source'] is None]
    verified_bytes = 0
    if payloads:
        with ThreadPoolExecutor(max_workers=6) as pool:
            verified_bytes = sum(pool.map(lambda r: verify_url(r['path'], r['bytes'], r['sha256']), remote))
    return {'manifests': manifests, 'remote_files': len(remote),
            'payloads_verified': len(remote) if payloads else 0, 'verified_payload_bytes': verified_bytes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payloads', action='store_true', help='Download and hash every declared remote file')
    args = parser.parse_args()
    print(json.dumps(check(payloads=args.payloads), indent=2))
