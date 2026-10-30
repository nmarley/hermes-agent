"""Canonical inference-provider registry: identity, auth shape, and endpoint defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hermes_providers.provider_defaults import (
    DEFAULT_ACTUAL_BASE_URL,
    DEFAULT_CODEX_BASE_URL,
    DEFAULT_COPILOT_ACP_BASE_URL,
    DEFAULT_GITHUB_MODELS_BASE_URL,
    DEFAULT_NOUS_CLIENT_ID,
    DEFAULT_NOUS_INFERENCE_URL,
    DEFAULT_NOUS_PORTAL_URL,
    DEFAULT_NOUS_SCOPE,
    DEFAULT_OLLAMA_CLOUD_BASE_URL,
    DEFAULT_QWEN_BASE_URL,
    DEFAULT_XAI_OAUTH_BASE_URL,
    MINIMAX_OAUTH_CN_BASE,
    MINIMAX_OAUTH_CN_INFERENCE,
    MINIMAX_OAUTH_CLIENT_ID,
    MINIMAX_OAUTH_GLOBAL_BASE,
    MINIMAX_OAUTH_GLOBAL_INFERENCE,
    MINIMAX_OAUTH_SCOPE,
    STEPFUN_STEP_PLAN_INTL_BASE_URL,
)

@dataclass
class ProviderConfig:
    """Describes a known inference provider."""
    id: str
    name: str
    auth_type: str  # "oauth_device_code", "oauth_external", "oauth_minimax", "api_key", ...
    portal_base_url: str = ""
    inference_base_url: str = ""
    client_id: str = ""
    scope: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    api_key_env_vars: tuple = ()  # API-key providers: env vars to check, in priority order
    base_url_env_var: str = ""  # optional env var overriding the base URL


def _api_key_provider(
    id: str, name: str, inference_base_url: str, api_key_env_vars: tuple,
    base_url_env_var: str = "", auth_type: str = "api_key") -> ProviderConfig:
    """Compact constructor for the common env-var-keyed provider shape."""
    return ProviderConfig(
        id=id, name=name, auth_type=auth_type, inference_base_url=inference_base_url,
        api_key_env_vars=api_key_env_vars, base_url_env_var=base_url_env_var)


# Registry rows in priority order (resolve_provider() scans api_key rows in this order). A tuple
# row is ``_api_key_provider(id, name, inference_base_url, api_key_env_vars[, base_url_env_var
# [, auth_type]])``; OAuth / bespoke rows are full ``ProviderConfig`` objects.
_REGISTRY_ROWS: tuple[Any, ...] = (
    ProviderConfig(
        "nous", "Nous Portal", "oauth_device_code", portal_base_url=DEFAULT_NOUS_PORTAL_URL,
        inference_base_url=DEFAULT_NOUS_INFERENCE_URL, client_id=DEFAULT_NOUS_CLIENT_ID,
        scope=DEFAULT_NOUS_SCOPE),
    ProviderConfig("openai-codex", "OpenAI Codex", "oauth_external", inference_base_url=DEFAULT_CODEX_BASE_URL),
    ("openai-api", "OpenAI API", "https://api.openai.com/v1", ("OPENAI_API_KEY",), "OPENAI_BASE_URL"),
    ProviderConfig(
        "xai-oauth", "xAI Grok OAuth (SuperGrok / Premium+)", "oauth_external",
        inference_base_url=DEFAULT_XAI_OAUTH_BASE_URL),
    ProviderConfig("qwen-oauth", "Qwen OAuth", "oauth_external", inference_base_url=DEFAULT_QWEN_BASE_URL),
    ("lmstudio", "LM Studio", "http://127.0.0.1:1234/v1", ("LM_API_KEY",), "LM_BASE_URL"),
    ("copilot", "GitHub Copilot", DEFAULT_GITHUB_MODELS_BASE_URL,
     ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"), "COPILOT_API_BASE_URL"),
    ProviderConfig(
        "copilot-acp", "GitHub Copilot ACP", "external_process",
        inference_base_url=DEFAULT_COPILOT_ACP_BASE_URL, base_url_env_var="COPILOT_ACP_BASE_URL"),
    ("gemini", "Google AI Studio", "https://generativelanguage.googleapis.com/v1beta",
     ("GOOGLE_API_KEY", "GEMINI_API_KEY"), "GEMINI_BASE_URL"),
    ("zai", "Z.AI / GLM", "https://api.z.ai/api/paas/v4",
     ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"), "GLM_BASE_URL"),
    # Legacy platform.moonshot.ai keys use this endpoint (OpenAI-compat); sk-kimi- (Kimi Code)
    # keys are auto-redirected to api.kimi.com/coding by _resolve_kimi_base_url().
    ("kimi-coding", "Kimi / Moonshot", "https://api.moonshot.ai/v1",
     ("KIMI_API_KEY", "KIMI_CODING_API_KEY"), "KIMI_BASE_URL"),
    ("kimi-coding-cn", "Kimi / Moonshot (China)", "https://api.moonshot.cn/v1", ("KIMI_CN_API_KEY",)),
    ("stepfun", "StepFun Step Plan", STEPFUN_STEP_PLAN_INTL_BASE_URL, ("STEPFUN_API_KEY",), "STEPFUN_BASE_URL"),
    ("arcee", "Arcee AI", "https://api.arcee.ai/api/v1", ("ARCEEAI_API_KEY",), "ARCEE_BASE_URL"),
    ("gmi", "GMI Cloud", "https://api.gmi-serving.com/v1", ("GMI_API_KEY",), "GMI_BASE_URL"),
    ("actual", "Actual Computer", DEFAULT_ACTUAL_BASE_URL, ("ACTUAL_API_KEY",), "ACTUAL_BASE_URL"),
    ("minimax", "MiniMax", "https://api.minimax.io/anthropic", ("MINIMAX_API_KEY",), "MINIMAX_BASE_URL"),
    ProviderConfig(
        "minimax-oauth", "MiniMax (OAuth \u00b7 minimax.io)", "oauth_minimax",
        portal_base_url=MINIMAX_OAUTH_GLOBAL_BASE, inference_base_url=MINIMAX_OAUTH_GLOBAL_INFERENCE,
        client_id=MINIMAX_OAUTH_CLIENT_ID, scope=MINIMAX_OAUTH_SCOPE,
        extra={"region": "global", "cn_portal_base_url": MINIMAX_OAUTH_CN_BASE,
               "cn_inference_base_url": MINIMAX_OAUTH_CN_INFERENCE}),
    # CLAUDE_CODE_OAUTH_TOKEN is NOT an API key despite auth_type="api_key": `claude setup-token`
    # yields an `sk-ant-oat01…` OAuth token (401s as x-api-key, 429s as bare Bearer). It stays in
    # this tuple because the tuple doubles as the credential-DISCOVERY list
    # (agent/credential_pool.py builds its env scan from it); the adapter routes it down the OAuth
    # path by prefix. Only ANTHROPIC_API_KEY and ANTHROPIC_TOKEN are usable as literal API keys.
    ("anthropic", "Anthropic", "https://api.anthropic.com",
     ("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"), "ANTHROPIC_BASE_URL"),
    ("alibaba", "Qwen Cloud", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
     ("DASHSCOPE_API_KEY",), "DASHSCOPE_BASE_URL"),
    ("alibaba-coding-plan", "Alibaba Cloud (Coding Plan)", "https://coding-intl.dashscope.aliyuncs.com/v1",
     ("ALIBABA_CODING_PLAN_API_KEY", "DASHSCOPE_API_KEY"), "ALIBABA_CODING_PLAN_BASE_URL"),
    ("minimax-cn", "MiniMax (China)", "https://api.minimaxi.com/anthropic", ("MINIMAX_CN_API_KEY",),
     "MINIMAX_CN_BASE_URL"),
    ("deepseek", "DeepSeek", "https://api.deepseek.com/v1", ("DEEPSEEK_API_KEY",), "DEEPSEEK_BASE_URL"),
    ("xai", "xAI", "https://api.x.ai/v1", ("XAI_API_KEY",), "XAI_BASE_URL"),
    ("nvidia", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1", ("NVIDIA_API_KEY",), "NVIDIA_BASE_URL"),
    ("ai-gateway", "Vercel AI Gateway", "https://ai-gateway.vercel.sh/v1", ("AI_GATEWAY_API_KEY",),
     "AI_GATEWAY_BASE_URL"),
    ("opencode-zen", "OpenCode Zen", "https://opencode.ai/zen/v1", ("OPENCODE_ZEN_API_KEY",),
     "OPENCODE_ZEN_BASE_URL"),
    # OpenCode Go mixes API surfaces by model (GLM/Kimi: OpenAI chat under /v1; MiniMax and
    # Qwen 3.7: Anthropic Messages under /v1/messages). Keep the base at /v1; api_mode is per-model.
    ("opencode-go", "OpenCode Go", "https://opencode.ai/zen/go/v1", ("OPENCODE_GO_API_KEY",),
     "OPENCODE_GO_BASE_URL"),
    ("kilocode", "Kilo Code", "https://api.kilo.ai/api/gateway", ("KILOCODE_API_KEY",), "KILOCODE_BASE_URL"),
    ("huggingface", "Hugging Face", "https://router.huggingface.co/v1", ("HF_TOKEN",), "HF_BASE_URL"),
    ("xiaomi", "Xiaomi MiMo", "https://api.xiaomimimo.com/v1", ("XIAOMI_API_KEY",), "XIAOMI_BASE_URL"),
    ("tencent-tokenhub", "Tencent TokenHub", "https://tokenhub.tencentmaas.com/v1", ("TOKENHUB_API_KEY",),
     "TOKENHUB_BASE_URL"),
    ("tencent-tokenplan", "Tencent TokenPlan", "https://api.lkeap.cloud.tencent.com/plan/anthropic",
     ("TOKENPLAN_API_KEY",), "TOKENPLAN_BASE_URL"),
    ("ollama-cloud", "Ollama Cloud", DEFAULT_OLLAMA_CLOUD_BASE_URL, ("OLLAMA_API_KEY",), "OLLAMA_BASE_URL"),
    ("bedrock", "AWS Bedrock", "https://bedrock-runtime.us-east-1.amazonaws.com", (), "BEDROCK_BASE_URL",
     "aws_sdk"),
    # No static inference_base_url: Vertex's endpoint is computed per request from project_id +
    # region (agent/vertex_adapter.py build_vertex_base_url), not a fixed host.
    ("vertex", "Google Vertex AI", "", (), "", "vertex"),
    ("azure-foundry", "Azure Foundry", "", ("AZURE_FOUNDRY_API_KEY",), "AZURE_FOUNDRY_BASE_URL"))
PROVIDER_REGISTRY: dict[str, ProviderConfig] = {
    p.id: p for p in (r if isinstance(r, ProviderConfig) else _api_key_provider(*r) for r in _REGISTRY_ROWS)
}
# The rows above, before any plugin touches the dict (a user plugin may override these; #48450).
BUILTIN_PROVIDER_IDS = frozenset(PROVIDER_REGISTRY)

