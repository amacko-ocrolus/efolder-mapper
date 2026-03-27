"""OpenAI GPT mapping service."""

import os

from openai import OpenAI

from prompts.mapping_prompt import build_mapping_prompt
from services.json_repair import extract_json_object


SERVICE_NAME = "OpenAI"


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, str]:
    """Send the bulk mapping prompt to OpenAI and return the parsed mapping."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    prompt = build_mapping_prompt(ocrolus_types, lender_containers)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=16384,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    return _parse_response(raw, ocrolus_types)


def _parse_response(raw: str, ocrolus_types: list[str]) -> dict[str, str]:
    """Parse the JSON response and validate keys."""
    try:
        data = extract_json_object(raw)
    except ValueError as e:
        raise ValueError(f"OpenAI: {e}") from e

    mapping = {}
    for form_type in ocrolus_types:
        value = data.get(form_type)
        if isinstance(value, str) and value.strip():
            mapping[form_type] = value.strip()
        else:
            mapping[form_type] = "NO_MATCH"

    return mapping
