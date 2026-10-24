"""Compatibility alias for :mod:`hermes_store.search.index` (FTS index setup)."""

import sys

from hermes_cli.config import load_config_readonly
from hermes_store.search import index as _impl
from hermes_store.common.config import set_config_loader

set_config_loader(load_config_readonly)
sys.modules[__name__] = _impl
