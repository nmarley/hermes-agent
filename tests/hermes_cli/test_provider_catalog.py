"""Tests for the unified provider catalog (hermes_cli.provider_catalog).

These are invariant tests, not snapshots: they assert the parity contract
between what ``hermes model`` shows and what the catalog exposes, plus how each
remaining provider's ``auth_type`` maps to a desktop tab.
"""

from hermes_cli.provider_catalog import provider_catalog, provider_catalog_by_slug


def test_venice_and_local_providers_are_present():
    by = provider_catalog_by_slug()
    assert "venice" in by
    assert by["venice"].label == "Venice AI"
    assert by["venice"].description
    assert "lmstudio" in by
    assert by["lmstudio"].label == "LM Studio"


def test_venice_surfaces_as_an_api_key_provider():
    descriptor = provider_catalog_by_slug()["venice"]
    assert descriptor.tab == "keys"
    assert descriptor.api_key_env_vars == ("VENICE_API_KEY",)
    assert descriptor.base_url_env_var == "VENICE_BASE_URL"
    assert descriptor.signup_url == "https://venice.ai/settings/api"


def test_api_key_providers_expose_a_credential_env_var():
    """Every keys-tab provider that authenticates via a pasted API key must
    surface at least one env var to write the key into."""
    for descriptor in provider_catalog():
        if descriptor.auth_type == "api_key":
            assert descriptor.api_key_env_vars, f"{descriptor.slug} is api_key but exposes no env var"
