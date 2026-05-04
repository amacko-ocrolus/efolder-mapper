"""Consensus engine — compares AI mappings and generates the output CSV."""

import csv
from collections import Counter

# Mappings where 2+ services agree but avg confidence is below this threshold
# are demoted to the manual review section rather than the confident list.
CONFIDENCE_THRESHOLD = 0.85


def build_consensus(
    results: dict[str, dict[str, tuple[str, float]]],
    ocrolus_types: list[str],
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[list[dict], list[dict]]:
    """Compare mappings from all AI services and split into consensus vs review.

    Args:
        results: Dict keyed by service name; values are {form_type: (container, confidence)}.
        ocrolus_types: The full list of Ocrolus form types.
        confidence_threshold: Avg confidence required to be listed as confident.
            Agreed mappings below this score are demoted to manual review.

    Returns:
        A tuple of (confident_rows, review_rows).
        - confident_rows: 2+ services agreed AND avg confidence >= threshold.
        - review_rows: No consensus OR avg confidence below threshold.
    """
    service_names = list(results.keys())
    confident = []
    review = []

    for form_type in ocrolus_types:
        # {svc: (container, confidence)}
        suggestions = {
            svc: results[svc].get(form_type, ("NO_MATCH", 0.0))
            for svc in service_names
        }

        # Check for container-level consensus (ignore confidence for vote count)
        container_votes = Counter(
            container for container, _ in suggestions.values()
        )
        most_common_container, most_count = container_votes.most_common(1)[0]

        if most_count >= 2 and most_common_container != "NO_MATCH":
            agreeing = [
                svc for svc, (container, _) in suggestions.items()
                if container == most_common_container
            ]
            avg_confidence = sum(
                conf for svc, (container, conf) in suggestions.items()
                if container == most_common_container
            ) / len(agreeing)

            if avg_confidence >= confidence_threshold:
                confident.append({
                    "ocrolus_type": form_type,
                    "suggested_container": most_common_container,
                    "agreed_services": ", ".join(agreeing),
                    "avg_confidence": round(avg_confidence, 2),
                })
                continue

        # No consensus OR confidence below threshold — pick best guess
        best_svc = max(service_names, key=lambda s: suggestions[s][1])
        best_container, best_conf = suggestions[best_svc]

        row = {
            "ocrolus_type": form_type,
            "best_guess": best_container,
            "best_confidence": round(best_conf, 2),
            "best_guess_service": best_svc,
        }
        for svc in service_names:
            container, conf = suggestions[svc]
            row[f"{svc}_suggestion"] = container
            row[f"{svc}_confidence"] = round(conf, 2)
        review.append(row)

    return confident, review


def write_output_csv(
    output_path: str,
    confident: list[dict],
    review: list[dict],
    attachment_names: dict[str, str] | None = None,
) -> None:
    """Write the final output CSV — single flat table, no section headers.

    Uses utf-8-sig encoding (UTF-8 with BOM) so Excel opens it correctly
    without garbling special characters.
    """
    attachment_names = attachment_names or {}

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        writer.writerow(["Form Type", "Attachment Name", "Container Name", "Confidence Score"])

        for row in confident:
            writer.writerow([
                row["ocrolus_type"],
                attachment_names.get(row["ocrolus_type"], ""),
                row["suggested_container"],
                row["avg_confidence"],
            ])

        for row in review:
            writer.writerow([
                row["ocrolus_type"],
                attachment_names.get(row["ocrolus_type"], ""),
                row["best_guess"],
                row["best_confidence"],
            ])
