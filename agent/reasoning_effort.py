"""Compatibility shim: reasoning vocabularies live in hermes_providers.reasoning."""

import sys

from hermes_providers import reasoning as _impl

sys.modules[__name__] = _impl
