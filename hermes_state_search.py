"""Compatibility alias for :mod:`hermes_store.search.messages` (Full-text message search)."""

import sys

from hermes_cli.config import load_config_readonly
from hermes_store.search import messages as _impl
from hermes_store.common.config import set_config_loader

set_config_loader(load_config_readonly)
sys.modules[__name__] = _impl
