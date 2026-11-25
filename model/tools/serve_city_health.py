"""Loopback-only local city experiment; explicit requests run a registered Method.

The web root is a prepared city build, never the repository or private workspace.
Only declared compressed environmental display frames are exposed from the input
bundle. Participant files, weights, provenance archives and filesystem listings
are not static resources.
"""
import argparse
import copy
import json
import math
import mimetypes
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from canopy._io import read, digest
from canopy.assets.store import load as load_asset
from canopy.running.runner import run, prepare_request
from common.storage import Storage


def endpoint_request(template, selected):
    """Browser selects endpoints and departure; model and input policy stay fixed."""
    if not isinstance(selected, dict) or not {'origin', 'goal'} <= set(selected) or set(selected) - {'origin', 'goal', 'departure_s'}:
        raise ValueError('Supply origin, goal and optionally departure_s')
    if any(not isinstance(selected[k], str) or not 0 < len(selected[k]) <= 150 for k in ('origin','goal')):
        raise ValueError('Invalid walking node ID')
    if 'departure_s' in selected:
        value = selected['departure_s']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Departure must be finite non-negative seconds on the Health clock')
    request = copy.deepcopy(template)
    request['parameters'].update(selected)
    return request


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(args[2].site), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def log_request(self, code='-', size='-'):
        # Full city startup transfers thousands of files; keep errors visible.
        if str(code).startswith(('4', '5')):
            super().log_request(code, size)

    def api(self, value, status=200):
        data = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def list_directory(self, path):
        self.send_error(403, 'Directory listings are disabled')
        return None

    def translate_path(self, path):
        route = unquote(urlsplit(path).path)
        if route in self.server.fields:
            return str(self.server.fields[route])
        candidate = Path(super().translate_path(path)).resolve()
        if not candidate.is_relative_to(self.server.site):
            return str(self.server.site / '__unavailable__')
        return str(candidate)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/pedestrian/meta':
            return self.api(self.server.metadata)
        if path == '/api/health/status':
            return self.api({'mode': getattr(self.server, 'mode', 'local-city-health'), 'last_result': self.server.last_result,
                             'select_routes': getattr(self.server, 'select_routes', False),
                             'network_revision': self.server.metadata.get('network_revision'),
                             'temperature_search_limit_m': self.server.metadata.get('temperature_search_limit_m'),
                             'environment_estimation': self.server.metadata.get('environment_estimation'),
                             'departure_clock': self.server.metadata.get('departure_clock'),
                             'crossing_policy': self.server.metadata.get('crossing_policy'),
                             'time_coverage': self.server.metadata.get('time_coverage')})
        if path == '/api/health/recording' and getattr(self.server, 'recording', None):
            return self.api(self.server.recording)
        if path.startswith('/api/'):
            return self.api({'error': 'Unknown endpoint'}, 404)
        return super().do_GET()

    def do_POST(self):
        select_routes = getattr(self.server, 'select_routes', False)
        if getattr(self.server, 'mode', '') == 'current-city-recording' and not select_routes:
            return self.api({'error': 'Recorded preview is read-only; prepare new runs offline'}, 405)
        expected = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected or self.headers.get('Origin') not in (None, 'http://' + expected):
            return self.api({'error': 'Local same-origin requests only'}, 403)
        if self.headers.get('Content-Type') != 'application/json':
            return self.api({'error': 'JSON request required'}, 415)
        if urlsplit(self.path).path != ('/api/health/walk' if select_routes else '/api/pedestrian/plan'):
            return self.api({'error': 'Unknown endpoint'}, 404)
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size < 10000:
                raise ValueError('Invalid request size')
            parameters = json.loads(self.rfile.read(size))
            if not isinstance(parameters, dict):
                raise ValueError('Expected an object')
            if select_routes:
                request = endpoint_request(self.server.request, parameters)
            else:
                request = copy.deepcopy(self.server.request)
                request['parameters'] = parameters
            # Validation precedes execution; the browser cannot select a Method,
            # private path, executable or different input bundle.
            prepare_request(self.server.storage, request)
        except Exception as exc:
            return self.api({'error': str(exc)}, 400)
        if not self.server.lock.acquire(blocking=False):
            return self.api({'error': 'A route calculation is already running'}, 409)
        try:
            state = run(self.server.storage, request, retain=True)
            asset, manifest, path = load_asset(self.server.storage, request['scenario_id'], state['assets'][0])
            result = read(path.parent / ('recording.json' if select_routes else 'route.json'))
            result['recording'] = {'asset': state['assets'][0], 'derived_from': asset['derived_from'],
                                   'manifest_sha256': digest(path)}
            if not select_routes:
                result['recording']['alignment'] = self.server.metadata['alignment']
            self.server.last_result = result['recording']
            self.api(result)
        except ValueError as exc:
            self.api({'error': str(exc), **({'coverage_gap':exc.details} if hasattr(exc,'details') else {})}, 422)
        except Exception:
            import traceback
            traceback.print_exc()
            self.api({'error': 'Route calculation failed; see the local server log'}, 500)
        finally:
            self.server.lock.release()


def serve(workspace, site, port, recorded=False, recording_index='city-recorded-preview.json', select_routes=False, request_index='city-walk-request.json'):
    storage = Storage.load(Path(workspace).resolve())
    if recorded:
        return serve_recorded(storage, workspace, site, port, recording_index, select_routes, request_index)
    raise ValueError('Use --recorded with a prepared city result; the private planner is not included')


def serve_recorded(storage, workspace, site, port, recording_index='city-recorded-preview.json', select_routes=False, request_index='city-walk-request.json'):
    reference = read(Path(workspace) / recording_index)['result']
    asset, manifest, path = load_asset(storage, 'imperial_corridor_8km', reference)
    recording = read(path.parent / 'recording.json')
    recording['recording'] = {'asset': reference, 'derived_from': asset['derived_from'], 'manifest_sha256': digest(path)}
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.site = Path(site).resolve()
    if not (server.site / 'viewer/3d/index.html').is_file():
        raise ValueError('A prepared city build is required')
    # Verify that the visible terrain/geometry matches the recorded transform.
    for name, sha in recording['alignment']['files'].items():
        if name in ('network.json','profile.json'):
            continue  # Derived network and Scenario preset are retained inputs.
        if digest(server.site / name) != sha:
            raise ValueError('Visible city differs from recorded alignment: ' + name)
    server.fields, server.metadata = {}, {'mode': 'current-city-recording'}
    server.mode, server.recording = 'current-city-recording', recording
    server.last_result = recording['recording']
    server.select_routes = select_routes
    if select_routes:
        request = read(Path(workspace) / request_index)
        if (request['model_id'], request['method_id']) != ('healthy_route', 'city_walk'):
            raise ValueError('Endpoint selection requires the registered city_walk Method')
        request, _, _, inputs = prepare_request(storage, request)
        if request['inputs']['city'] != recording['inputs']['city']:
            raise ValueError('Selected-route request and saved preview must use the same pinned city Asset')
        if request['inputs']['physiology'] != recording.get('physiology_inputs', {}).get('physiology'):
            raise ValueError('Selected-route request and saved preview must use the same private model Asset')
        if not recording.get('physiology_policy') or any(request['parameters'][k] != v for k,v in recording['physiology_policy'].items()):
            raise ValueError('Selected-route policy must match the prepared physiology preview')
        network = read(inputs['city'][2].parent / 'network.json')
        from healthy_route.health_time import time_coverage
        from healthy_route.conditional_runtime import Runtime
        city_fields = read(inputs['city'][2].parent / 'city-inputs.json')['fields']
        timing = time_coverage(city_fields, request['parameters'], Runtime.template_horizon_s)
        components = {n: i for i, nodes in enumerate(network['components']) for n in nodes}
        server.metadata = dict(nodes=network['nodes'], node_components=components,
            roads=[edge['points'] for edge in network['edges']],
            network_revision=digest(inputs['city'][2].parent / 'network.json'),
            network_summary=network['summary'],
            temperature_search_limit_m=request['parameters']['max_temperature_fill_m'],
            crossing_policy=request['parameters'].get('crossing_policy','none'),
            environment_estimation={k:request['parameters'].get(k) for k in ['spatial_missing_method','max_pmx_fill_m','max_sunlight_fill_m']},
            example=[request['parameters']['origin'], request['parameters']['goal']],
            city_asset=request['inputs']['city'], speed_m_s=request['parameters']['speed_m_s'],
            departure_s=request['parameters']['departure_s'], time_coverage=timing,
            departure_clock=dict(origin_seconds=city_fields['sunlight']['clock_offset_s'],
                max_departure_s=max(0,timing['horizon_s']-max(1,request['parameters']['followup_until_elapsed_s'])),
                semantics='Illustrative scenario day clock, not UTC or live observations; route arrival must remain within Health coverage'))
        server.request, server.storage, server.lock = request, storage, threading.Lock()
    mimetypes.add_type('text/javascript', '.mjs')
    print(f'Current city recording: http://127.0.0.1:{port}/viewer/3d/?scene=imperial_corridor_8km&health=local&pedestrian=1&play=0&lite=0', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--port', default=8820, type=int)
    parser.add_argument('--recorded', action='store_true', help='Serve the prepared current-city recording; disable calculations')
    parser.add_argument('--recording-index', default='city-recorded-preview.json', help='Explicit local result index within the prepared workspace')
    parser.add_argument('--select-routes', action='store_true', help='Enable explicit endpoint calculations using the prepared current-city request')
    parser.add_argument('--request-index', default='city-walk-request.json', help='Explicit local request file within the prepared workspace')
    args = parser.parse_args()
    serve(args.workspace, args.site, args.port, args.recorded, args.recording_index, args.select_routes, args.request_index)
