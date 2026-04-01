"""OpenAI GPT mapping service."""

import os

from openai import OpenAI

from prompts.mapping_prompt import build_mapping_prompt
from services.json_repair import extract_json_object


SERVICE_NAME = "OpenAI"

BATCH_SIZE = 150


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, tuple[str, float]]:
    """Send the bulk mapping prompt to OpenAI and return the parsed mapping."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    merged = {}
    for i in range(0, len(ocrolus_types), BATCH_SIZE):
        batch = ocrolus_types[i : i + BATCH_SIZE]
        prompt = build_mapping_prompt(batch, lender_containers)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=16384,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        merged.update(_parse_response(raw, batch))
    return merged


def _parse_response(raw: str, ocrolus_types: list[str]) -> dict[str, tuple[str, float]]:
    """Parse the JSON response into (container, confidence) tuples."""
    try:
        data = extract_json_object(raw)
    except ValueError as e:
        raise ValueError(f"OpenAI returned invalid JSON: {e}") from e

    mapping = {}
    for form_type in ocrolus_types:
        value = data.get(form_type)
        if isinstance(value, dict):
            container = str(value.get("container", "")).strip()
            try:
                confidence = float(value.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                confidence = 0.5
            mapping[form_type] = (container or "NO_MATCH", confidence)
        elif isinstance(value, str) and value.strip():
            mapping[form_type] = (value.strip(), 0.5)
        else:
            mapping[form_type] = ("NO_MATCH", 0.0)
    return mapping
