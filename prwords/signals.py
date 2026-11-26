"""Proxy for AI involvement in a pull request.

Authorship cannot be observed, so nothing here claims that a person or a model wrote
anything. One proxy is provided:

* ``ai_disclosed``: an explicit statement naming an AI tool (high precision, low recall).
"""
from __future__ import annotations

import re

# Whole words only: as a bare substring, "llm" matched human names such as "Willmer".
TOOLS = (
    r"\b(?:claude|anthropic|copilot|chatgpt|openai|gpt-?\d|gemini|cursor|codex|aider|devin|"
    r"windsurf|cline|junie|amazon q|codewhisperer|tabnine|llm)\b"
)

AI_DISCLOSURE = re.compile(
    rf"""
    co-authored-by:[^\n]*?{TOOLS}
    | noreply@anthropic\.com
    | generated\s+(?:with|by|using)\s+\[?{TOOLS}
    | \U0001F916\s*generated
    | assisted[- ]by:\s*\S+
    | \b(?:written|drafted|authored|created|implemented|coded|vibe[- ]?coded)\s+
      (?:(?:it|this|that|the\s+code|the\s+description)\s+)?
      (?:with|by|using)\s+(?:the\s+help\s+of\s+)?{TOOLS}
    | \bai[- ](?:assisted|generated|authored|written)\b
    """,
    re.I | re.X,
)


def find_ai_disclosure(text: str) -> str | None:
    """Return the matched snippet if the text names an AI tool in a disclosure line."""
    if not text:
        return None
    m = AI_DISCLOSURE.search(text)
    return m.group(0).strip()[:120] if m else None


_TOOL_ORDER = (
    ("claude", r"claude|anthropic"),
    ("copilot", r"copilot"),
    ("codex", r"codex"),
    ("chatgpt", r"chatgpt|openai|gpt-?\d"),
    ("gemini", r"gemini"),
    ("cursor", r"cursor"),
    ("devin", r"devin"),
    ("aider", r"aider"),
    ("windsurf", r"windsurf"),
    ("cline", r"cline"),
)


def extract_tool(match: str | None) -> str | None:
    """Name the tool in a disclosure snippet, or ``unspecified`` when it names none."""
    if not isinstance(match, str) or not match:
        return None
    low = match.lower()
    for name, pat in _TOOL_ORDER:
        if re.search(pat, low):
            return name
    return "unspecified"
