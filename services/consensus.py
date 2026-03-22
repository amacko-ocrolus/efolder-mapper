"""Consensus engine — compares AI mappings and generates the output CSV."""

import csv
from collections import Counter


def build_consensus(
    results: dict[str, dict[str, str]],
    ocrolus_types: list[str],
) -> tuple[list[dict], list[dict]]:
    """Compare mappings from all AI services and split into consensus vs review.

    Args:
        results: Dict keyed by service name, values are {ocrolus_type: container} dicts.
        ocrolus_types: The full list of Ocrolus form types.

    Returns:
        A tuple of (confident_rows, review_rows).
        - confident_rows: dicts with keys: ocrolus_type, suggested_container, agreed_services
        - review_rows: dicts with keys: ocrolus_type + one key per service name
    """
    service_names = list(results.keys())
    confident = []
    review = []

    for form_type in ocrolus_types:
        suggestions = {
            svc: results[svc].get(form_type, "NO_MATCH")
            for svc in service_names
        }

        # Count how many services suggested each container
        counts = Counter(suggestions.values())
        # Find the most common suggestion
        most_common, most_count = counts.most_common(1)[0]

        threshold = min(2, len(service_names))
        if most_count >= threshold and most_common != "NO_MATCH":
            agreed = [
                svc for svc, val in suggestions.items() if val == most_common
            ]
            confident.append({
                "ocrolus_type": form_type,
                "suggested_container": most_common,
                "agreed_services": ", ".join(agreed),
            })
        else:
            row = {"ocrolus_type": form_type}
            for svc in service_names:
                row[f"{svc}_suggestion"] = suggestions[svc]
            review.append(row)

    return confident, review


def write_output_csv(
    output_path: str,
    confident: list[dict],
    review: list[dict],
    service_names: list[str],
) -> None:
    """Write the final output CSV with two sections."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # --- Confident Mappings Section ---
        writer.writerow(["=== CONFIDENT MAPPINGS (2+ AI services agree) ==="])
        writer.writerow([])
        writer.writerow(["Form Type", "Container Name", "Agreed Services"])

        for row in confident:
            writer.writerow([
                row["ocrolus_type"],
                row["suggested_container"],
                row["agreed_services"],
            ])

        writer.writerow([])
        writer.writerow([])

        # --- Manual Review Section ---
        writer.writerow(["=== MANUAL REVIEW NEEDED (no consensus) ==="])
        writer.writerow([])
        review_headers = ["Form Type"] + [
            f"{svc} Suggestion" for svc in service_names
        ]
        writer.writerow(review_headers)

        for row in review:
            writer.writerow(
                [row["ocrolus_type"]]
                + [row.get(f"{svc}_suggestion", "") for svc in service_names]
            )

    return output_path
