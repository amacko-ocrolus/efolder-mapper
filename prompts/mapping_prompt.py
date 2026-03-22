"""Shared prompt template used by all three AI services."""


def build_mapping_prompt(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> str:
    """Build the bulk mapping prompt sent to each AI service.

    Each service must return a JSON object where every Ocrolus form type maps to
    an object with a best-guess container and a confidence score (0.0–1.0).
    NO_MATCH is disallowed — services must always pick the closest available container.
    """
    ocrolus_list = "\n".join(f"  - {t}" for t in ocrolus_types)
    container_list = "\n".join(f"  - {c}" for c in lender_containers)

    return f"""You are an expert in mortgage document classification. Your task is to map Ocrolus document form types to the most appropriate lender document container names from an ICE Encompass environment.

**Ocrolus Document Form Types:**
{ocrolus_list}

**Lender Encompass Document Container Names:**
{container_list}

**Instructions:**
1. For each Ocrolus form type listed above, select the single best-matching lender document container name from the list above.
2. Base your matching on semantic similarity — the container that would most logically hold that type of document in a mortgage workflow.
3. Always provide a best-guess — never omit a form type or leave its container blank. Even if no container is a strong match, pick the closest option.
4. For each mapping, provide a confidence score from 0.0 (very uncertain) to 1.0 (very confident).
5. Return ONLY a valid JSON object. Each key is an Ocrolus form type (exactly as written above) and each value is an object with:
   - "container": the best-matching lender container name (must be exactly from the list above)
   - "confidence": a float from 0.0 to 1.0 representing your confidence in the match
6. Do not add any explanation, commentary, or markdown formatting. Return raw JSON only.

Example output format:
{{
  "W-2": {{"container": "Tax Documents", "confidence": 0.95}},
  "Unusual Form XYZ": {{"container": "Miscellaneous", "confidence": 0.15}}
}}

Return the complete JSON mapping now:"""
