"""Anthropic Claude mapping service."""

import os

import anthropic

from prompts.mapping_prompt import build_mapping_prompt
from services.json_repair import extract_json_object


SERVICE_NAME = "Anthropic"


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, str]:
    """Send the bulk mapping prompt to Anthropic Claude and return the parsed mapping."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_mapping_prompt(ocrolus_types, lender_containers)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16384,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    raw = response.content[0].text.strip()
    return _parse_response(raw, ocrolus_types)


def _parse_response(raw: str, ocrolus_types: list[str]) -> dict[str, str]:
    """Parse the JSON response and validate keys."""
    try:
        data = extract_json_object(raw)
    except ValueError as e:
        raise ValueError(f"Anthropic: {e}") from e

    mapping = {}
    for form_type in ocrolus_types:
        value = data.get(form_type)
        if isinstance(value, str) and value.strip():
            mapping[form_type] = value.strip()
        else:
            mapping[form_type] = "NO_MATCH"

    return mapping
