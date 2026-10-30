"""Compatibility shim: model normalization lives in hermes_providers.model_normalize."""

import sys

from hermes_providers import model_normalize as _impl

sys.modules[__name__] = _impl
