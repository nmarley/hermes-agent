"""Venice billing snapshot tests."""

from __future__ import annotations

import pytest


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _BillingClient:
    def __init__(self, payloads):
        self._payloads = payloads

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, params=None):
        return _Response(self._payloads[url.rstrip("/")])


@pytest.fixture
def billing():
    import model_tools

    from plugins.model_providers.venice import billing as venice_billing

    return venice_billing


def test_billing_snapshot_reports_balance_and_seven_day_usage(billing, monkeypatch):
    import httpx

    balance = {
        "canConsume": True,
        "consumptionCurrency": "DIEM",
        "balances": {"diem": 90.5, "usd": 25.0, "bundledCredits": 10.0, "earnedCredits": 5.0},
        "diemEpochAllocation": 100.0,
    }
    analytics = {
        "lookback": "7d",
        "byDate": [{"USD": 1.5, "DIEM": 1.5}, {"USD": 2.5, "DIEM": 2.5}],
        "byModel": [{"modelName": "GLM 5.3", "totalUsd": 3.0}, {"modelName": "DeepSeek V4.1", "totalUsd": 1.0}],
    }
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: _BillingClient(
            {
                "https://api.venice.ai/api/v1/billing/balance": balance,
                "https://api.venice.ai/api/v1/billing/usage-analytics": analytics,
            }
        ),
    )

    snapshot = billing.fetch_venice_account_usage(api_key="test-key")

    assert snapshot is not None
    assert snapshot.provider == "venice"
    assert snapshot.source == "billing_api"
    assert snapshot.plan == "DIEM"
    assert snapshot.windows[0].label == "DIEM epoch"
    assert snapshot.windows[0].used_percent == pytest.approx(9.5)
    assert "USD balance: $25.00" in snapshot.details
    assert "DIEM balance: 90.50" in snapshot.details
    assert "Bundled credits: $10.00" in snapshot.details
    assert "Usage (7d): $4.00 / 4.00 DIEM" in snapshot.details
    assert "Top model: GLM 5.3 ($3.00)" in snapshot.details


def test_billing_failure_fails_open(billing, monkeypatch):
    import httpx

    class _Broken:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            raise RuntimeError("network down")

    monkeypatch.setattr(httpx, "Client", _Broken)

    assert billing.fetch_venice_account_usage(api_key="test-key") is None
