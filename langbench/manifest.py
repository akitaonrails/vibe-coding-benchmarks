"""Versioned attempt definitions. Hidden expected values never belong here."""
import hashlib
import json
import math
from pathlib import Path
from .core import TASKS, IMPLEMENTED

FIELDS = {'schema_version','attempt_id','task','language','tests','model','effort','replicate','block_id',
          'base_seconds','continuation_seconds','max_nudges','auth_mode','initial_artifact_sha256',
          'environment_digest','usage_qualified','resolved_model'}

def validate(manifest):
    if not isinstance(manifest, dict) or set(manifest) != FIELDS:
        raise ValueError('manifest has missing or unknown fields')
    if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
        raise ValueError('unsupported schema version')
    for field in ('attempt_id','block_id','model','environment_digest'):
        if not isinstance(manifest[field],str) or not manifest[field] or any(c in manifest[field] for c in '\r\n\0'):
            raise ValueError(f'invalid {field}')
    if manifest['task'] not in TASKS or manifest['language'] not in IMPLEMENTED or manifest['tests'] not in ('T0','T1'):
        raise ValueError('invalid treatment')
    if manifest['effort'] not in ('low','medium','high') or manifest['auth_mode'] != 'chatgpt':
        raise ValueError('invalid model effort/auth mode')
    for field in ('replicate','base_seconds','continuation_seconds'):
        if type(manifest[field]) is not int or manifest[field] <= 0:
            raise ValueError(f'invalid {field}')
    if type(manifest['max_nudges']) is not int or manifest['max_nudges'] != 2:
        raise ValueError('main policy requires two nudges')
    if type(manifest['usage_qualified']) is not bool:
        raise ValueError('usage_qualified must be boolean')
    if manifest['resolved_model'] is not None and (not isinstance(manifest['resolved_model'],str) or not manifest['resolved_model']):
        raise ValueError('invalid resolved_model')
    value=manifest['initial_artifact_sha256']
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('invalid artifact digest')
    return manifest

def freeze(manifest, path):
    data=(json.dumps(validate(manifest),sort_keys=True,separators=(',',':'))+'\n').encode()
    with Path(path).open('xb') as handle:
        handle.write(data)
    return hashlib.sha256(data).hexdigest()

def load(path, expected_sha256):
    data=Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected_sha256:
        raise ValueError('manifest commitment mismatch')
    return validate(json.loads(data))
