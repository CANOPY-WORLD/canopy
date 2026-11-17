"""Strict JSON, bounded paths and atomic metadata writes."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from jsonschema import Draft202012Validator

def read(path):
    from common.contract import read_json
    return read_json(Path(path))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def relative(base, value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError(f'Not a portable relative path: {value!r}')
    parts = PurePosixPath(value)
    if parts.is_absolute() or '..' in parts.parts:
        raise ValueError(f'Path escapes owner: {value}')
    base = Path(base).resolve(); target = (base / value).resolve()
    if not target.is_relative_to(base): raise ValueError(f'Path escapes owner: {value}')
    return target

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def check(value, name):
    Draft202012Validator(read(Path(__file__).parent / 'schemas' / f'{name}-v2.schema.json')).validate(value)
