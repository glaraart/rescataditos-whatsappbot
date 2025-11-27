import re
import json
from typing import Optional, Tuple

# Heuristics to extract the first JSON-like object or array from LLM free-form text
# and to normalize common problems so json.loads can parse it.

JSON_LIKE_RE = re.compile(r"(\{[\s\S]*?\}|\[[\s\S]*?\])", re.MULTILINE)

# Replace single quotes with double quotes only when safe; handle True/False/None -> true/false/null
RE_KEY_UNQUOTED = re.compile(r"(?P<prefix>[{,\s])(?P<key>[A-Za-z0-9_\-]+)\s*:")


def find_first_json(text: str) -> Optional[str]:
    """Return the substring of the first JSON object or array found in text, or None."""
    if not text:
        return None
    m = JSON_LIKE_RE.search(text)
    if not m:
        return None
    return m.group(1)


def cleanup_json_text(s: str) -> str:
    """Try to normalize common LLM issues so the string becomes valid JSON.

    Heuristics applied (non-exhaustive):
    - Trim leading/trailing backticks and triple-backtick fences
    - Convert single quotes to double quotes when they are used as JSON quotes
    - Replace Python booleans/None with JSON equivalents
    - Remove trailing commas before } or ]
    - Ensure keys are quoted
    """
    if not s:
        return s

    # Trim markdown code fences and surrounding whitespace
    s = s.strip()
    # remove ```json or ```
    s = re.sub(r"^```(?:json)?\n", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\n```$", "", s, flags=re.IGNORECASE)

    # Remove single backticks around the JSON
    if s.startswith("`") and s.endswith("`"):
        s = s[1:-1].strip()

    # Replace Python-style booleans and None
    s = re.sub(r"\bNone\b", "null", s)
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)

    # Remove trailing commas before } or ]
    s = re.sub(r",\s*(?=[}\]])", "", s)

    # Attempt to fix unquoted keys: { key: 1 } -> { "key": 1 }
    # This is a conservative attempt: only keys that follow { or , and are simple identifiers
    def _quote_keys(m: re.Match) -> str:
        prefix = m.group('prefix')
        key = m.group('key')
        return f"{prefix}\"{key}\":"

    s = re.sub(r"(?P<prefix>[{,\s])(?P<key>[A-Za-z0-9_\-]+)\s*:\s*", _quote_keys, s)

    # Convert single-quoted strings to double quotes when safe
    # Only replace when there are no nested double quotes inside
    def _single_to_double(m: re.Match) -> str:
        inner = m.group(1)
        inner = inner.replace('"', '\\"')
        return '"' + inner + '"'

    s = re.sub(r"'([^']*)'", _single_to_double, s)

    return s


def parse_json_from_text(text: str) -> Tuple[Optional[object], Optional[str]]:
    """Try to extract and parse JSON from LLM text.

    Returns: (parsed_obj or None, error message or None)
    """
    if not text:
        return None, "empty input"

    candidate = find_first_json(text)
    if not candidate:
        # As a last resort, try the whole text
        candidate = text

    cleaned = cleanup_json_text(candidate)
    try:
        return json.loads(cleaned), None
    except Exception as e:
        # As fallback, try to be more permissive: remove everything before first { or [ again
        # and try once more
        m = re.search(r"([\{\[])[\s\S]*$", cleaned)
        if m:
            cleaned2 = cleaned[m.start():]
            try:
                return json.loads(cleaned2), None
            except Exception:
                return None, f"json.loads failed: {e}"
        return None, f"json.loads failed: {e}"
