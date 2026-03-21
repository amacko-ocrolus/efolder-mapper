"""Shared prompt template used by all three AI services."""


def build_mapping_prompt(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> str:
    """Build the bulk mapping prompt sent to each AI service.

    The prompt instructs the AI to match each Ocrolus document form type
    to the single best-matching lender document container name, returning
    the result as a JSON object.
    """
    ocrolus_list = "\n".join(f"  - {t}" for t in ocrolus_types)
    container_list = "\n".join(f"  - {c}" for c in lender_containers)

    return f"""You are an expert in mortgage document classification. Your task is to map Ocrolus document form types to the most appropriate lender document container names from an ICE Encompass environment.

**Ocrolus Document Form Types:**
{ocrolus_list}

**Lender Encompass Document Container Names:**
{container_list}

**Instructions:**
1. For each Ocrolus form type listed above, select the single best-matching lender document container name from the lender list.
2. Base your matching on semantic similarity — the container that would most logically hold that type of document in a mortgage workflow.
3. If no container is a reasonable match for an Ocrolus type, use the value "NO_MATCH" for that type.
4. Return ONLY a valid JSON object where each key is an Ocrolus form type (exactly as written above) and each value is the matching lender container name (exactly as written above) or "NO_MATCH".
5. Do not add any explanation, commentary, or markdown formatting. Return raw JSON only.

Example output format:
{{
  "W-2": "Tax Documents",
  "Bank Statement": "Asset Statements"
}}

Return the complete JSON mapping now:"""
