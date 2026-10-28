"""Venice ``/models`` metadata normalization."""

from __future__ import annotations

import pytest


def test_endpoint_metadata_reads_venice_nested_usd_rate_card():
    """Venice nests $/MTok rates under model_spec.pricing.<bucket>.usd and puts
    the output cap in model_spec.maxCompletionTokens."""
    from agent import model_metadata as mm
    from agent import usage_pricing as up

    model = {
        "id": "deepseek-v4-1-flash-1017",
        "context_length": 1_000_000,
        "model_spec": {
            "maxCompletionTokens": 131_072,
            "pricing": {
                "input": {"usd": 0.3},
                "output": {"usd": 1.2},
                "cache_input": {"usd": 0.0075},
                "cache_write": {"usd": 0.012},
            },
        },
    }
    meta = {"deepseek-v4-1-flash-1017": mm._endpoint_model_entry(model, "deepseek-v4-1-flash-1017", None)}
    assert meta["deepseek-v4-1-flash-1017"]["context_length"] == 1_000_000
    assert meta["deepseek-v4-1-flash-1017"]["max_completion_tokens"] == 131_072

    entry = up._pricing_entry_from_metadata(
        meta, "deepseek-v4-1-flash-1017", source_url="x", pricing_version="openai-compatible-models-api"
    )
    assert float(entry.input_cost_per_million) == pytest.approx(0.3)
    assert float(entry.output_cost_per_million) == pytest.approx(1.2)
    assert float(entry.cache_read_cost_per_million) == pytest.approx(0.0075)
    assert float(entry.cache_write_cost_per_million) == pytest.approx(0.012)
