"""Provider identity and catalogue facts shared by the provider runtime."""

from __future__ import annotations

# Aliases: human-friendly and legacy provider names -> canonical id. The catalog table is the
# single source of truth; model normalization only needs the lookup.
PROVIDER_ALIASES = dict((
    ("glm", "zai"), ("z-ai", "zai"), ("z.ai", "zai"), ("zhipu", "zai"), ("github", "copilot"),
    ("github-copilot", "copilot"), ("github-models", "copilot"), ("github-model", "copilot"),
    ("github-copilot-acp", "copilot-acp"), ("copilot-acp-agent", "copilot-acp"), ("google", "gemini"),
    ("google-gemini", "gemini"), ("google-ai-studio", "gemini"), ("google-vertex", "vertex"), ("vertex-ai", "vertex"),
    ("gcp-vertex", "vertex"), ("vertexai", "vertex"), ("kimi", "kimi-coding"), ("moonshot", "kimi-coding"),
    ("kimi-cn", "kimi-coding-cn"), ("moonshot-cn", "kimi-coding-cn"), ("step", "stepfun"),
    ("stepfun-coding-plan", "stepfun"), ("arcee-ai", "arcee"), ("arceeai", "arcee"), ("gmi-cloud", "gmi"),
    ("gmicloud", "gmi"), ("fireworks-ai", "fireworks"), ("fw", "fireworks"), ("actual-computer", "actual"),
    ("actualcomputer", "actual"), ("aci", "actual"), ("nebius", "nebius-token-factory"),
    ("nebius-tokenfactory", "nebius-token-factory"), ("nebius-tf", "nebius-token-factory"),
    ("token-factory", "nebius-token-factory"), ("tokenfactory", "nebius-token-factory"),
    ("minimax-china", "minimax-cn"), ("minimax_cn", "minimax-cn"), ("minimax-portal", "minimax-oauth"),
    ("minimax-global", "minimax-oauth"), ("minimax_oauth", "minimax-oauth"), ("claude", "anthropic"),
    ("claude-code", "anthropic"), ("deep-seek", "deepseek"), ("opencode", "opencode-zen"), ("zen", "opencode-zen"),
    ("go", "opencode-go"), ("opencode-go-sub", "opencode-go"), ("aigateway", "ai-gateway"), ("vercel", "ai-gateway"),
    ("vercel-ai-gateway", "ai-gateway"), ("kilo", "kilocode"), ("kilo-code", "kilocode"),
    ("kilo-gateway", "kilocode"), ("dashscope", "alibaba"), ("aliyun", "alibaba"), ("qwen", "alibaba"),
    ("alibaba-cloud", "alibaba"), ("qwen-portal", "qwen-oauth"), ("hf", "huggingface"),
    ("hugging-face", "huggingface"), ("huggingface-hub", "huggingface"), ("novita-ai", "novita"),
    ("novitaai", "novita"), ("mimo", "xiaomi"), ("xiaomi-mimo", "xiaomi"), ("tencent", "tencent-tokenhub"),
    ("tokenhub", "tencent-tokenhub"), ("tencent-cloud", "tencent-tokenhub"), ("tencentmaas", "tencent-tokenhub"),
    ("tokenplan", "tencent-tokenplan"), ("tencent-lkeap", "tencent-tokenplan"), ("aws", "bedrock"),
    ("aws-bedrock", "bedrock"), ("amazon-bedrock", "bedrock"), ("amazon", "bedrock"), ("grok", "xai"),
    ("grok-oauth", "xai-oauth"), ("xai-oauth", "xai-oauth"), ("x-ai-oauth", "xai-oauth"),
    ("xai-grok-oauth", "xai-oauth"), ("x-ai", "xai"), ("x.ai", "xai"), ("nim", "nvidia"), ("nvidia-nim", "nvidia"),
    ("build-nvidia", "nvidia"), ("nemotron", "nvidia"), ("lmstudio", "lmstudio"), ("lm-studio", "lmstudio"),
    ("lm_studio", "lmstudio"), ("chatgpt", "openai-codex"), ("chatgpt-codex", "openai-codex"),
    ("ollama", "custom"),  # bare "ollama" = local; use "ollama-cloud" for cloud
    ("ollama_cloud", "ollama-cloud"),
    # Local OpenAI-compatible servers route through the generic "custom" provider
    # (parity with hermes_cli.auth and hermes_cli.providers). Issue #62213. The llamacpp
    # aliases stay unmapped: they are the managed local runtime's picker id, and the model
    # validator must reach its staged-library branch before the custom one.
    ("local", "custom"), ("vllm", "custom"),
))


COPILOT_MODEL_ALIASES = dict((
    ("openai/gpt-5", "gpt-5-mini"), ("openai/gpt-5-chat", "gpt-5-mini"), ("openai/gpt-5-mini", "gpt-5-mini"),
    ("openai/gpt-5-nano", "gpt-5-mini"), ("openai/gpt-4.1", "gpt-4.1"), ("openai/gpt-4.1-mini", "gpt-4.1"),
    ("openai/gpt-4.1-nano", "gpt-4.1"), ("openai/gpt-4o", "gpt-4o"), ("openai/gpt-4o-mini", "gpt-4o-mini"),
    ("openai/o1", "gpt-5.2"), ("openai/o1-mini", "gpt-5-mini"), ("openai/o1-preview", "gpt-5.2"),
    ("openai/o3", "gpt-5.3-codex"), ("openai/o3-mini", "gpt-5-mini"), ("openai/o4-mini", "gpt-5-mini"),
    ("anthropic/claude-opus-4.6", "claude-opus-4.6"), ("anthropic/claude-sonnet-5", "claude-sonnet-5"),
    ("anthropic/claude-sonnet-4.6", "claude-sonnet-4.6"), ("anthropic/claude-sonnet-4", "claude-sonnet-4"),
    ("anthropic/claude-sonnet-4.5", "claude-sonnet-4.5"), ("anthropic/claude-haiku-4.5", "claude-haiku-4.5"),
    ("claude-sonnet-5", "claude-sonnet-5"), ("claude-opus-4-6", "claude-opus-4.6"),
    ("claude-sonnet-4-6", "claude-sonnet-4.6"), ("claude-sonnet-4-0", "claude-sonnet-4"),
    ("claude-sonnet-4-5", "claude-sonnet-4.5"), ("claude-haiku-4-5", "claude-haiku-4.5"),
    ("anthropic/claude-opus-4-6", "claude-opus-4.6"), ("anthropic/claude-sonnet-4-6", "claude-sonnet-4.6"),
    ("anthropic/claude-sonnet-4-0", "claude-sonnet-4"), ("anthropic/claude-sonnet-4-5", "claude-sonnet-4.5"),
    ("anthropic/claude-haiku-4-5", "claude-haiku-4.5"),
))


NVIDIA_MODELS: list[str] = [
        "nvidia/nemotron-3.5-super-vl-120b-a12b", "nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-3.5-lightning-30b-a3b", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "z-ai/glm-5.3", "z-ai/glm-5.2", "moonshotai/kimi-k2.6", "minimaxai/minimax-m3",
    ]

OPENCODE_FAMILIES = ("opencode-go", "opencode-zen")
