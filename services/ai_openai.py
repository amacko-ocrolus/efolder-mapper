"""OpenAI GPT mapping service."""

import json
import os

from openai import OpenAI

from prompts.mapping_prompt import build_mapping_prompt


SERVICE_NAME = "OpenAI"

BATCH_SIZE = 150  # stay well under gpt-4o's 16K output token limit


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, str]:
    """Send the bulk mapping prompt to OpenAI and return the parsed mapping.

    Batches large inputs to avoid hitting the model's output token limit.
    """
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
            max_tokens=16384,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        merged.update(_parse_response(raw, batch))
    return merged


def _parse_response(raw: str, ocrolus_types: list[str]) -> dict[str, str]:
    """Parse the JSON response and validate keys."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI returned invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("OpenAI response is not a JSON object")

    mapping = {}
    for form_type in ocrolus_types:
        value = data.get(form_type)
        if isinstance(value, str) and value.strip():
            mapping[form_type] = value.strip()
        else:
            mapping[form_type] = "NO_MATCH"

    return mapping
