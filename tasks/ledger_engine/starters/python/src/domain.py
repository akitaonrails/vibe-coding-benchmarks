"""Logical values and lossless JSON ownership."""
from copy import deepcopy
from dataclasses import dataclass

Key = tuple[str, str]

@dataclass
class Entry:
    version: int
    row: dict | None


def record(tenant, request):
    result = {'tenant': tenant, 'id': request['id'], 'value': request['value']}
    for field in ('alias', 'note'):
        if field in request:
            result[field] = deepcopy(request[field])
    return result


def project(row, version):
    result = deepcopy(row)
    if result is not None and version == 1:
        result.pop('tenant')
    return result
