"""Consensus engine — compares AI mappings and generates the output CSV."""

import csv
from collections import Counter


def build_consensus(
    results: dict[str, dict[str, tuple[str, float]]],
    ocrolus_types: list[str],
) -> tuple[list[dict], list[dict]]:
    """Compare mappings from all AI services and split into consensus vs review.

    Args:
        results: Dict keyed by service name; values are {form_type: (container, confidence)}.
        ocrolus_types: The full list of Ocrolus form types.

    Returns:
        A tuple of (confident_rows, review_rows).
        - confident_rows: 2+ services agreed on the same container.
        - review_rows: No consensus; includes all per-service suggestions with
          confidences and a "best guess" (highest-confidence pick across services).
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
            confident.append({
                "ocrolus_type": form_type,
                "suggested_container": most_common_container,
                "agreed_services": ", ".join(agreeing),
                "avg_confidence": round(avg_confidence, 2),
            })
        else:
            # No consensus — pick best guess by highest confidence across services
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
    service_names: list[str],
    failed_services: dict[str, str] | None = None,
) -> None:
    """Write the final output CSV with two sections."""
    failed_services = failed_services or {}

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Note any failed services at the top
        if failed_services:
            writer.writerow(["NOTE: The following AI services failed and are excluded:"])
            for svc, err in failed_services.items():
                writer.writerow([f"  {svc}", err])
            writer.writerow([])

        # --- Confident Mappings Section ---
        writer.writerow([f"=== CONFIDENT MAPPINGS ({len(confident)} rows — 2+ AI services agree) ==="])
        writer.writerow([])
        writer.writerow(["Form Type", "Container Name", "Agreed Services", "Avg Confidence"])

        for row in confident:
            writer.writerow([
                row["ocrolus_type"],
                row["suggested_container"],
                row["agreed_services"],
                row["avg_confidence"],
            ])

        writer.writerow([])
        writer.writerow([])

        # --- Manual Review Section ---
        writer.writerow([f"=== MANUAL REVIEW NEEDED ({len(review)} rows — no consensus) ==="])
        writer.writerow([])

        per_svc_headers = []
        for svc in service_names:
            per_svc_headers += [f"{svc} Suggestion", f"{svc} Confidence"]

        writer.writerow(
            ["Form Type", "Best Guess", "Best Confidence", "Best Guess Service"]
            + per_svc_headers
        )

        for row in review:
            per_svc_values = []
            for svc in service_names:
                per_svc_values += [
                    row.get(f"{svc}_suggestion", ""),
                    row.get(f"{svc}_confidence", ""),
                ]
            writer.writerow(
                [
                    row["ocrolus_type"],
                    row["best_guess"],
                    row["best_confidence"],
                    row["best_guess_service"],
                ]
                + per_svc_values
            )
