"""Compatibility alias for :mod:`hermes_store.mutations.chat_pick` (Messaging chat picks)."""

import sys

from hermes_store.mutations import chat_pick as _impl

sys.modules[__name__] = _impl
