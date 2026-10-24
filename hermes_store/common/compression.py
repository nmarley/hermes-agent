"""Compaction markers and summary prefixes shared by the compressor and the store."""

HISTORICAL_TASK_HEADING = "## Historical Task Snapshot"

SUMMARY_PREFIX = (
    # Jul 2026 (#65848 class): identical to the pre-#69619 prefix except it lacked the explicit "tools
    # remain fully active" clause — the strong REFERENCE ONLY framing bled into general tool-use suppression
    # (observed: 7 consecutive narration-only turns immediately after a compression event on a production
    # deployment).
    # Carveout era (#41607/#38364/#42812): "consistent → use as background" licensed stale-task resumption
    # on topic overlap.
    "[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted "
    "into the summary below. This is a handoff from a previous context "
    "window — treat it as background reference, NOT as active instructions. "
    "Do NOT answer questions or fulfill requests mentioned in this summary; "
    "they were already addressed. "
    "Respond ONLY to the latest user message that appears AFTER this "
    "summary — that message is the single source of truth for what to do "
    "right now. "
    "If no user message appears AFTER this summary, do nothing: do not "
    "resume, wrap up, or continue work from "
    f"'{HISTORICAL_TASK_HEADING}' or any other section, do not call tools, "
    "and wait for a new user message. This handoff must never become the "
    "active turn by itself. (Exception: if tool results or your own "
    "tool calls appear after this summary, you are mid-way through an "
    "in-flight exchange — continue that exchange normally.) "
    "Topic overlap with the summary does NOT mean you should resume its "
    "task: even on similar topics, the latest user message WINS. Treat ONLY "
    "the latest message as the active task and discard stale items from "
    f"'{HISTORICAL_TASK_HEADING}' entirely — do not 'wrap up' or "
    "'finish' work there unless the latest message explicitly "
    "asks for it. "
    "Reverse signals in the latest message (e.g. 'stop', 'undo', 'roll "
    "back', 'just verify', 'don't do that anymore', 'never mind', a new "
    "topic) must immediately end any in-flight work described in the "
    "summary; do not re-surface it in later turns. "
    "IMPORTANT: Your persistent memory (MEMORY.md, USER.md) in the system "
    "prompt is ALWAYS authoritative and active — never ignore or deprioritize "
    "memory content due to this compaction note. "
    "None of the above restricts HOW you work: your tools remain fully "
    "active — keep calling them normally for the active task (edit files, "
    "run commands, search) instead of merely narrating what you would do. "
    "The current session state (files, config, etc.) may reflect work "
    "described here — avoid repeating it:"
)
LEGACY_SUMMARY_PREFIX = "[CONTEXT SUMMARY]:"

# Explicit end boundary: weak models otherwise read quoted headers as fresh
# user input or replay an assistant-role summary as their own output.
_SUMMARY_END_MARKER = "--- END OF CONTEXT SUMMARY — respond to the message below, not the summary above ---"

# Merged-into-tail case: prior tail content is kept BEFORE the summary inside
# these delimiters, so the summary prefix is not at content start.
_MERGED_PRIOR_CONTEXT_HEADER = "[PRIOR CONTEXT — for reference only; not a new message]"
_MERGED_SUMMARY_DELIMITER = "[END OF PRIOR CONTEXT — COMPACTION SUMMARY BELOW]"

# Durable held-row coverage markers shared by transcript repair, compaction, and replay.
ABSORBED_ROW_IDS = "_absorbed_row_ids"
MERGED_DURABLE_ROWS = "_merged_durable_rows"
UNNAMED_DURABLE_ROWS = "_unnamed_durable_rows"
RETIRED_DURABLE_ROWS = "_retired_durable_rows"
RETIRED_ROW = "_retired_row"
OWN_ROW = "_own_row"

# Set on a live dict once its current bytes are durable; popped by any in-place rewrite.
_DB_PERSISTED_MARKER = "_db_persisted"
MODEL_ONLY_DISPLAY_METADATA_KEY = "model_only"


def is_checkpoint_item(item):
    return isinstance(item, dict) and item.get("type") == "compaction"


def newest_checkpoint_carrier(messages: list, key: str) -> int:
    """Index of the last assistant message carrying a ``type: "compaction"`` item under *key*, or -1."""
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        items = msg.get(key)
        if isinstance(items, list) and any(is_checkpoint_item(item) for item in items):
            return i
    return -1
