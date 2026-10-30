"""Provider endpoint defaults shared by auth, the registry, and model setup."""

from __future__ import annotations

DEFAULT_NOUS_PORTAL_URL = "https://portal.nousresearch.com"
DEFAULT_NOUS_INFERENCE_URL = "https://inference-api.nousresearch.com/v1"
DEFAULT_NOUS_CLIENT_ID = "hermes-cli"
NOUS_INFERENCE_INVOKE_SCOPE = "inference:invoke"
DEFAULT_NOUS_SCOPE = NOUS_INFERENCE_INVOKE_SCOPE
DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_XAI_OAUTH_BASE_URL = "https://api.x.ai/v1"
MINIMAX_OAUTH_CLIENT_ID = "78257093-7e40-4613-99e0-527b14b39113"
MINIMAX_OAUTH_SCOPE = "group_id profile model.completion"
MINIMAX_OAUTH_GLOBAL_BASE = "https://api.minimax.io"
MINIMAX_OAUTH_CN_BASE = "https://api.minimaxi.com"
MINIMAX_OAUTH_GLOBAL_INFERENCE = "https://api.minimax.io/anthropic"
MINIMAX_OAUTH_CN_INFERENCE = "https://api.minimaxi.com/anthropic"
DEFAULT_QWEN_BASE_URL = "https://portal.qwen.ai/v1"
DEFAULT_GITHUB_MODELS_BASE_URL = "https://api.githubcopilot.com"
DEFAULT_COPILOT_ACP_BASE_URL = "acp://copilot"
DEFAULT_OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
DEFAULT_ACTUAL_BASE_URL = "https://api.actual.inc/v1"
STEPFUN_STEP_PLAN_INTL_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
