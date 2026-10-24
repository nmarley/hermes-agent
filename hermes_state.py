"""Compatibility shim for the state facade: the implementation lives in ``hermes_store.api``.

``SessionDB`` is re-exported explicitly because the frozen old-updater surface resolves names
statically from this file. Replacing ``sys.modules`` makes the old and new import paths one
module object, so existing patch seams keep working during the migration.
"""

import sys

from hermes_store import api as _api
from hermes_store.api import SessionDB

__all__ = ["SessionDB"]


def _load_config_readonly():
    from hermes_cli.config import load_config_readonly
    return load_config_readonly()


_api.set_config_loader(_load_config_readonly)

sys.modules[__name__] = _api
