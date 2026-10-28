"""Venice-only builds do not admit late-registered vendor plugins into the picker."""

from providers import register_provider
from providers.base import ProviderProfile


def _profile(name: str) -> ProviderProfile:
    return ProviderProfile(name=name, display_name=name, description="late plugin (direct API)")


def test_late_registered_provider_does_not_reach_picker_catalog(monkeypatch):
    import hermes_cli.models_catalog_static as catalog
    from hermes_cli.models import list_available_providers

    monkeypatch.setattr(catalog, "CANONICAL_PROVIDERS", list(catalog.CANONICAL_PROVIDERS))
    monkeypatch.setattr(catalog, "_canonical_slugs", set(catalog._canonical_slugs))
    monkeypatch.setattr(catalog, "_PROVIDER_LABELS", dict(catalog._PROVIDER_LABELS))
    monkeypatch.setattr("hermes_cli.models.CANONICAL_PROVIDERS", catalog.CANONICAL_PROVIDERS)
    monkeypatch.setattr("hermes_cli.models._PROVIDER_LABELS", catalog._PROVIDER_LABELS)
    slug = "zz-late-plugin-provider"
    assert slug not in {r["id"] for r in list_available_providers()}

    import providers as registry
    registry.list_providers()
    monkeypatch.setitem(registry._REGISTRY, slug, _profile(slug))
    register_provider(_profile(slug))

    assert slug not in {r["id"] for r in list_available_providers()}
    assert slug not in catalog._PROVIDER_LABELS
    assert catalog.sync_plugin_provider_catalog() == 0
