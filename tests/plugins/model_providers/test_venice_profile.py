"""Venice AI provider profile and catalog tests."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def catalog():
    import model_tools

    from plugins.model_providers.venice import catalog as venice_catalog

    return venice_catalog


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


CATALOG = {
    "data": [
        {
            "id": "deepseek-v4-1-flash-1017",
            "type": "text",
            "context_length": 1_000_000,
            "model_spec": {
                "maxCompletionTokens": 131_072,
                "pricing": {
                    "input": {"usd": 0.3},
                    "output": {"usd": 1.2},
                    "cache_input": {"usd": 0.0075},
                },
                "capabilities": {
                    "supportsFunctionCalling": True,
                    "supportsReasoning": True,
                    "supportsReasoningEffort": True,
                    "reasoningEffortOptions": ["none", "low", "high", "max"],
                    "supportsVision": True,
                },
                "traits": [],
            },
        },
        {
            "id": "z-ai-glm-5-3-flash",
            "type": "text",
            "context_length": 1_048_576,
            "model_spec": {
                "maxCompletionTokens": 131_072,
                "capabilities": {
                    "supportsFunctionCalling": True,
                    "supportsReasoning": True,
                    "supportsReasoningEffort": False,
                    "supportsVision": True,
                },
                "traits": ["default"],
            },
        },
        {
            "id": "qwen-3-8-27b",
            "type": "text",
            "context_length": 262_144,
            "model_spec": {
                "maxCompletionTokens": 65_536,
                "capabilities": {
                    "supportsFunctionCalling": True,
                    "supportsReasoning": False,
                    "supportsReasoningEffort": False,
                    "supportsVision": True,
                },
                "traits": ["default_vision"],
            },
        },
        {"id": "venice-image-1", "type": "image", "model_spec": {}},
    ]
}


@pytest.fixture
def venice_profile():
    import model_tools
    import providers

    profile = providers.get_provider_profile("venice")
    assert profile is not None, "venice provider profile must be registered"
    return profile


@pytest.fixture
def loaded_catalog(catalog, monkeypatch):
    calls = []

    def fake_open(request, timeout=8.0):
        calls.append((request.full_url, timeout))
        return _Response(CATALOG)

    catalog.reset_cache()
    monkeypatch.setattr(catalog, "open_credentialed_url", fake_open)
    items = catalog.fetch_catalog(api_key="test-key", force_refresh=True)
    yield items, calls
    catalog.reset_cache()


def test_profile_is_registered_with_api_key_and_chat_wire(venice_profile):
    assert venice_profile.name == "venice"
    assert venice_profile.auth_type == "api_key"
    assert venice_profile.api_mode == "chat_completions"
    assert venice_profile.env_vars[:1] == ("VENICE_API_KEY",)
    assert venice_profile.base_url == "https://api.venice.ai/api/v1"
    assert venice_profile.supports_streaming is True
    assert venice_profile.supports_prompt_cache_key is False


def test_catalog_fetch_filters_generation_models_and_caches(catalog, loaded_catalog):
    items, calls = loaded_catalog
    assert len(items) == 4
    assert calls[0][0] == "https://api.venice.ai/api/v1/models"
    assert catalog.chat_models(items) == [
        "deepseek-v4-1-flash-1017",
        "z-ai-glm-5-3-flash",
        "qwen-3-8-27b",
    ]

    catalog.fetch_catalog(api_key="test-key")
    assert len(calls) == 1
    catalog.fetch_catalog(api_key="test-key", force_refresh=True)
    assert len(calls) == 2


def test_catalog_exposes_context_output_pricing_and_traits(catalog, loaded_catalog):
    assert catalog.context_length("deepseek-v4-1-flash-1017") == 1_000_000
    assert catalog.max_completion_tokens("deepseek-v4-1-flash-1017") == 131_072
    assert catalog.trait_model("default") == "z-ai-glm-5-3-flash"
    assert catalog.trait_model("default_vision") == "qwen-3-8-27b"
    assert catalog.vision_model() == "qwen-3-8-27b"


def test_catalog_reasoning_efforts_and_clamping(loaded_catalog, venice_profile):
    assert venice_profile.supported_reasoning_efforts("deepseek-v4-1-flash-1017") == (
        "none",
        "low",
        "high",
        "max",
    )
    assert venice_profile.supported_reasoning_efforts("z-ai-glm-5-3-flash") == ()
    assert venice_profile.supported_reasoning_efforts("does-not-exist") is None

    extra, top = venice_profile.build_api_kwargs_extras(
        reasoning_config={"enabled": True, "effort": "medium"},
        model="deepseek-v4-1-flash-1017",
    )
    assert extra == {}
    assert top == {"reasoning_effort": "low"}

    extra, top = venice_profile.build_api_kwargs_extras(
        reasoning_config={"enabled": False},
        model="deepseek-v4-1-flash-1017",
    )
    assert extra == {}
    assert top == {"reasoning_effort": "none"}

    extra, top = venice_profile.build_api_kwargs_extras(
        reasoning_config={"enabled": True, "effort": "high"},
        model="z-ai-glm-5-3-flash",
    )
    assert extra == {}
    assert top == {}


def test_catalog_aux_and_vision_defaults(loaded_catalog, venice_profile):
    assert venice_profile.resolve_aux_model() == "z-ai-glm-5-3-flash"
    assert venice_profile.resolve_aux_model(vision=True) == "qwen-3-8-27b"
    assert venice_profile.default_vision_model() == "qwen-3-8-27b"
    assert venice_profile.get_max_tokens("qwen-3-8-27b") == 65_536
    assert venice_profile.get_model_context_length("qwen-3-8-27b") == 262_144


def test_registry_and_default_model_are_wired(venice_profile):
    from hermes_cli.auth import PROVIDER_REGISTRY
    from hermes_cli.models import get_default_model_for_provider

    row = PROVIDER_REGISTRY["venice"]
    assert row.auth_type == "api_key"
    assert row.inference_base_url == "https://api.venice.ai/api/v1"
    assert row.api_key_env_vars[0] == "VENICE_API_KEY"
    assert PROVIDER_REGISTRY["venice-ai"] is row
    assert get_default_model_for_provider("venice") == "deepseek-v4-1-flash-1017"
