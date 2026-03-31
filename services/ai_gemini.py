"""Google Gemini mapping service."""

import json
import os

from google import genai
from google.genai import types

from prompts.mapping_prompt import build_mapping_prompt


SERVICE_NAME = "Gemini"

GEMINI_MODEL = "gemini-2.0-flash"
BATCH_SIZE = 150


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, tuple[str, float]]:
    """Send the bulk mapping prompt to Gemini and return the parsed mapping."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    merged = {}
    for i in range(0, len(ocrolus_types), BATCH_SIZE):
        batch = ocrolus_types[i : i + BATCH_SIZE]
        prompt = build_mapping_prompt(batch, lender_containers)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()
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
        raise ValueError(f"Gemini returned invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Gemini response is not a JSON object")

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
