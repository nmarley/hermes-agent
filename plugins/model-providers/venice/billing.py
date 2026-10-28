"""Venice account balance and usage for ``/usage``.

The billing API is beta, so every failure fails open: a missing balance never
blocks chat or the rest of the usage block.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.account_usage import AccountUsageSnapshot

logger = logging.getLogger(__name__)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _get(client: Any, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = client.get(url, params=params) if params else client.get(url)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        logger.debug("Venice billing request failed for %s: %s", url, exc, exc_info=True)
        return {}


def _sum_rows(rows: Any, key: str) -> float | None:
    if not isinstance(rows, list):
        return None
    total = 0.0
    seen = False
    for row in rows:
        value = _number(row.get(key)) if isinstance(row, dict) else None
        if value is not None:
            total += value
            seen = True
    return total if seen else None


def _top_model(rows: Any) -> tuple[str, float] | None:
    if not isinstance(rows, list):
        return None
    best: tuple[str, float] | None = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("modelName") or "").strip()
        cost = _number(row.get("totalUsd"))
        if name and cost is not None and (best is None or cost > best[1]):
            best = (name, cost)
    return best


def _resolve_credentials(
    base_url: str | None, api_key: str | None
) -> tuple[str, str] | None:
    resolved_key = (api_key or "").strip()
    resolved_base = (base_url or "").strip()
    if not resolved_key or not resolved_base:
        try:
            from hermes_cli.auth import resolve_api_key_provider_credentials

            credentials = resolve_api_key_provider_credentials("venice")
        except Exception:
            logger.debug("Venice credential resolution failed", exc_info=True)
            credentials = {}
        resolved_key = resolved_key or str(credentials.get("api_key") or "").strip()
        resolved_base = resolved_base or str(credentials.get("base_url") or "").strip()
    if not resolved_key:
        return None
    from .catalog import DEFAULT_BASE_URL

    return resolved_key, (resolved_base or DEFAULT_BASE_URL).rstrip("/")


def fetch_venice_account_usage(
    *, base_url: str | None = None, api_key: str | None = None
) -> AccountUsageSnapshot | None:
    from agent.account_usage import AccountUsageSnapshot, AccountUsageWindow

    credentials = _resolve_credentials(base_url, api_key)
    if credentials is None:
        return None
    key, base = credentials
    import httpx

    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    with httpx.Client(timeout=5.0, headers=headers) as client:
        balance = _get(client, f"{base}/billing/balance")
        analytics = _get(client, f"{base}/billing/usage-analytics", params={"lookback": "7d"})

    windows: list[AccountUsageWindow] = []
    details: list[str] = []
    balances = balance.get("balances") if isinstance(balance.get("balances"), dict) else {}

    usd = _number(balances.get("usd"))
    if usd is not None:
        details.append(f"USD balance: ${usd:,.2f}")
    diem = _number(balances.get("diem"))
    if diem is not None:
        details.append(f"DIEM balance: {diem:,.2f}")
    for label, field in (("Bundled credits", "bundledCredits"), ("Earned credits", "earnedCredits")):
        value = _number(balances.get(field))
        if value is not None:
            details.append(f"{label}: ${value:,.2f}")

    allocation = _number(balance.get("diemEpochAllocation"))
    if allocation and allocation > 0 and diem is not None:
        used = max(0.0, min(100.0, (allocation - diem) / allocation * 100.0))
        windows.append(
            AccountUsageWindow(
                label="DIEM epoch",
                used_percent=used,
                detail=f"{diem:,.2f} of {allocation:,.2f} DIEM remaining",
            )
        )

    if balance.get("canConsume") is False:
        details.append("Status: cannot consume, top up required")

    usd_used = _sum_rows(analytics.get("byDate"), "USD")
    diem_used = _sum_rows(analytics.get("byDate"), "DIEM")
    if usd_used is not None or diem_used is not None:
        parts = []
        if usd_used is not None:
            parts.append(f"${usd_used:,.2f}")
        if diem_used is not None and diem_used > 0:
            parts.append(f"{diem_used:,.2f} DIEM")
        if parts:
            details.append(f"Usage (7d): {' / '.join(parts)}")
    top = _top_model(analytics.get("byModel"))
    if top is not None:
        details.append(f"Top model: {top[0]} (${top[1]:,.2f})")

    if not windows and not details:
        return None
    return AccountUsageSnapshot(
        provider="venice",
        source="billing_api",
        fetched_at=datetime.now(UTC),
        title="Venice balance",
        plan=str(balance.get("consumptionCurrency") or "").strip() or None,
        windows=tuple(windows),
        details=tuple(details),
        raw={"balance": balance, "usage": analytics},
    )
