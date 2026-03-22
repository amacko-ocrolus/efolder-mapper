"""Anthropic Claude mapping service."""

import json
import os

import anthropic

from prompts.mapping_prompt import build_mapping_prompt


SERVICE_NAME = "Anthropic"

BATCH_SIZE = 150  # keep output well under max_tokens limit


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, str]:
    """Send the bulk mapping prompt to Anthropic Claude and return the parsed mapping.

    Batches large inputs to avoid hitting the model's output token limit.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    merged = {}
    for i in range(0, len(ocrolus_types), BATCH_SIZE):
        batch = ocrolus_types[i : i + BATCH_SIZE]
        prompt = build_mapping_prompt(batch, lender_containers)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16384,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        raw = response.content[0].text.strip()
        merged.update(_parse_response(raw, batch))
    return merged


def _parse_response(raw: str, ocrolus_types: list[str]) -> dict[str, str]:
    """Parse the JSON response and validate keys."""
    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Anthropic returned invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Anthropic response is not a JSON object")

    mapping = {}
    for form_type in ocrolus_types:
        value = data.get(form_type)
        if isinstance(value, str) and value.strip():
            mapping[form_type] = value.strip()
        else:
            mapping[form_type] = "NO_MATCH"

    return mapping
