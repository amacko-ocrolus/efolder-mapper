"""Ollama local LLM mapping service (OpenAI-compatible API)."""

import json

from openai import OpenAI

from prompts.mapping_prompt import build_mapping_prompt


SERVICE_NAME = "Ollama"

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "llama3.1"
BATCH_SIZE = 50  # smaller batches keep each Ollama call manageable


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, tuple[str, float]]:
    """Send the bulk mapping prompt to Ollama and return the parsed mapping.

    Batches inputs to keep each local inference call fast and avoid timeouts.
    """
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", timeout=600.0)
    merged = {}
    for i in range(0, len(ocrolus_types), BATCH_SIZE):
        batch = ocrolus_types[i : i + BATCH_SIZE]
        prompt = build_mapping_prompt(batch, lender_containers)
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        merged.update(_parse_response(raw, batch))
    return merged


def _parse_response(raw: str, ocrolus_types: list[str]) -> dict[str, tuple[str, float]]:
    """Parse the JSON response into (container, confidence) tuples."""
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
