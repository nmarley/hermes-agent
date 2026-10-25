"""Compatibility alias for :mod:`hermes_store.media.retirement` (Media retirement)."""

import hermes_state  # installs the media hooks
import sys

from hermes_store.media import retirement as _impl

sys.modules[__name__] = _impl
