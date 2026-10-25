"""Validation and row helpers shared by runtime transactions and terminal tombstones."""

import hashlib
import json

from hermes_store.keys import admission_fingerprint
from hermes_store.runtime.errors import RuntimeStoreError


def _text(value):
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise RuntimeStoreError('invalid_params')
    return value


def _json(value):
    if not isinstance(value, dict):
        raise RuntimeStoreError('invalid_params')
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise RuntimeStoreError('invalid_params') from exc


def _epoch(conn, epoch):
    row = conn.execute('SELECT epoch FROM runtime_epoch WHERE singleton=1').fetchone()
    if type(epoch) is not int or row is None or row[0] != epoch:
        raise RuntimeStoreError('stale_epoch')


def _row(row):
    if row is None:
        return None
    result = dict(row)
    result['payload'] = json.loads(result.pop('payload_json'))
    result.pop('payload_digest')
    result.pop('lineage_json')
    result.pop('retired_at', None)
    return result


def _secret_digest(secret):
    _text(secret)
    return hashlib.sha256(secret.encode('utf-8')).hexdigest()
