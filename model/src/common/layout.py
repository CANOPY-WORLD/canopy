"""Resolve domain directories while accepting original Physics4D checkouts."""
import os
from pathlib import Path


def repo_root():
    value=os.environ.get('UWM_ROOT')
    if value:return Path(value).expanduser().resolve()
    for root in Path(__file__).resolve().parents:
        if (root / 'AGENTS.md').is_file() and (schema_root(root) / 'run-manifest-v1.schema.json').is_file():
            return root
    raise ValueError('No metadata checkout found; pass --root or set UWM_ROOT')


def domain_layout(root):
    return (Path(root) / 'asset/schemas/run-manifest-v1.schema.json').is_file()


def schema_root(root):
    return Path(root) / ('asset/schemas' if domain_layout(root) else 'schemas')


def metadata_root(root):
    return Path(root) / ('scenario' if domain_layout(root) else 'project')


def source_root(root):
    return Path(root) / ('model/src' if domain_layout(root) else 'src')


def visualization_root(root):
    return Path(root) / ('visualizer/src/visualization' if domain_layout(root) else 'src/visualization')


def site_root(root):
    return Path(root) / 'visualizer/site' if domain_layout(root) else Path(root)


def examples_root(root):
    return Path(root) / ('model/tests/fixtures' if domain_layout(root) else 'examples')


def source_path(relative, root=None):
    """Resolve an imported script's logical path relative to its old src/ root."""
    root = Path(root) if root is not None else repo_root()
    path = Path(relative)
    if path.parts and path.parts[0] == 'visualization':
        return visualization_root(root).joinpath(*path.parts[1:])
    return source_root(root) / path


def agent_src():
    return source_path('urban_geometry/agent')


def authoring_path(relative=''):
    from .storage import Storage
    path=Path(relative)
    if path.parts and path.parts[0]=='src':
        return agent_src().joinpath(*path.parts[1:])
    return Storage.load().assets('south_ken','geometry')/'authoring'/path


def scene_input(scene, *parts):
    from .storage import Storage, within
    return within(Storage.load().assets(scene, 'input'), *parts)
