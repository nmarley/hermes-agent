"""Root compatibility shims are aliases of their package implementations."""

from __future__ import annotations

import importlib
import sys


def test_root_shims_are_aliases_not_copies():
    import hermes_constants
    import hermes_state
    import utils

    assert sys.modules["hermes_state"] is importlib.import_module("hermes_store.api")
    assert sys.modules["hermes_constants"] is importlib.import_module("hermes_platform.constants")
    assert sys.modules["utils"] is importlib.import_module("hermes_platform.utils")
