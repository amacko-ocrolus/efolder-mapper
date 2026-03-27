"""Utility to extract a JSON object from potentially truncated or wrapped AI responses."""

import json
import re


def extract_json_object(raw: str) -> dict:
    """Best-effort extraction of a JSON object from an AI response."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines).strip()

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")

    text = raw[start:]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    repaired = _repair_truncated_json(text)
    try:
        data = json.loads(repaired)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', raw)
    if pairs:
        return dict(pairs)

    raise ValueError("Could not extract JSON object from response")


def _repair_truncated_json(text: str) -> str:
    in_string = False
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string

    if in_string:
        text += '"'

    text = text.rstrip()
    if text.endswith(","):
        text = text[:-1]

    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1

    if depth > 0:
        text += "}" * depth

    return text
