"""Shared constants and helpers for the default config data."""


#: Image every container terminal backend (docker/modal/daytona, the singularity plugin) uses unless the
#: user pins one. LEGACY_SANDBOX_IMAGES are the plain defaults that preceded the desktop stack
#: (the 3.14 pin shipped between the two without a migration); a saved config still holding one
#: is the template copied, and the config migration unsets it, never a user's own pin.
DEFAULT_SANDBOX_IMAGE = "nousresearch/hermes-sandbox:desktop"
LEGACY_SANDBOX_IMAGES = ("nikolaik/python-nodejs:python3.11-nodejs20", "nikolaik/python-nodejs:python3.14-nodejs22")
LEGACY_SANDBOX_IMAGE = LEGACY_SANDBOX_IMAGES[0]
# Vercel Sandbox managed image (Vercel deprecated its `runtime` presets in Aug 2026).
DEFAULT_VERCEL_IMAGE = "vercel/sandbox/universal:latest"
LEGACY_VERCEL_RUNTIME = "node24"  # the seeded pre-49 default, never a user choice


def _aux(timeout, *, reasoning_effort=True, **extra):
    """Standard auxiliary-task model block (see DEFAULT_CONFIG["auxiliary"]).

    reasoning_effort=False omits that key (MoA blocks configure depth per slot);
    ``extra`` keys are appended after the standard ones.
    """
    d = {"provider": "auto", "model": "", "base_url": "", "api_key": "", "timeout": timeout, "extra_body": {}}
    if reasoning_effort:
        d["reasoning_effort"] = ""
    d.update(extra)
    return d
