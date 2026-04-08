"""Google Gemini mapping service."""

import os
import time

from prompts.mapping_prompt import build_mapping_prompt
from services.json_repair import extract_json_object


SERVICE_NAME = "Gemini"

# Preferred models in priority order — first available one is used.
# Updated when Google deprecates models for new API keys.
_MODEL_PREFERENCE = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

BATCH_SIZE = 150
MAX_RETRIES = 4


def _pick_model(client) -> str:
    """Return the first preferred model that supports generateContent."""
    try:
        available = {
            m.name.replace("models/", "")
            for m in client.models.list()
            if hasattr(m, "supported_actions") and "generateContent" in (m.supported_actions or [])
            or hasattr(m, "supported_generation_methods") and "generateContent" in (m.supported_generation_methods or [])
        }
        for model in _MODEL_PREFERENCE:
            if model in available:
                return model
    except Exception:
        pass
    # Fall back to first preference if listing fails
    return _MODEL_PREFERENCE[0]


def get_mappings(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> dict[str, tuple[str, float]]:
    """Send the bulk mapping prompt to Gemini and return the parsed mapping."""
    # Lazy import — keeps module importable in environments without google-genai
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)
    model = _pick_model(client)

    merged = {}
    for i in range(0, len(ocrolus_types), BATCH_SIZE):
        batch = ocrolus_types[i : i + BATCH_SIZE]
        prompt = build_mapping_prompt(batch, lender_containers)
        raw = _generate_with_retry(client, prompt, types, model)
        merged.update(_parse_response(raw, batch))
    return merged


def _generate_with_retry(client, prompt: str, types, model: str) -> str:
    """Call Gemini with exponential backoff on rate-limit errors."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                if "limit: 0" in err:
                    raise RuntimeError(
                        "Gemini API quota is 0 — billing must be enabled at "
                        "https://aistudio.google.com before this service can be used."
                    ) from e
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                    last_exc = e
                    continue
            raise
    raise last_exc


def _parse_response(raw: str, ocrolus_types: list[str]) -> dict[str, tuple[str, float]]:
    """Parse the JSON response into (container, confidence) tuples."""
    try:
        data = extract_json_object(raw)
    except ValueError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}") from e

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
