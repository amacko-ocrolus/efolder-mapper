"""Ollama local LLM mapping service (OpenAI-compatible API)."""

import json

from openai import OpenAI

from prompts.mapping_prompt import build_mapping_prompt


SERVICE_NAME = "Ollama"

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "llama3.1"


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, str]:
    """Send the bulk mapping prompt to Ollama and return the parsed mapping."""
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    prompt = build_mapping_prompt(ocrolus_types, lender_containers)

    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    return _parse_response(raw, ocrolus_types)


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
        raise ValueError(f"Ollama returned invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Ollama response is not a JSON object")

    mapping = {}
    for form_type in ocrolus_types:
        value = data.get(form_type)
        if isinstance(value, str) and value.strip():
            mapping[form_type] = value.strip()
        else:
            mapping[form_type] = "NO_MATCH"

    return mapping
