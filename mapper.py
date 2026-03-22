#!/usr/bin/env python3
"""Container Mapping Tool — maps Ocrolus document form types to lender Encompass containers.

Usage:
    python mapper.py --ocrolus <path> --lender <path> [--output <path>]
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from services.ingestion import load_lender_containers, load_ocrolus_types
from services.consensus import build_consensus, write_output_csv
from services import ai_openai, ai_anthropic, ai_ollama


AI_SERVICES = [ai_openai, ai_anthropic, ai_ollama]


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Map Ocrolus document form types to lender Encompass container names using AI consensus."
    )
    parser.add_argument(
        "--ocrolus", required=True, help="Path to the Ocrolus form types CSV file."
    )
    parser.add_argument(
        "--lender", required=True, help="Path to the lender container names file (CSV or JSON)."
    )
    parser.add_argument(
        "--output", default="mapping_output.csv", help="Path for the output CSV (default: mapping_output.csv)."
    )
    args = parser.parse_args()

    # --- Ingest ---
    print("Loading Ocrolus form types...")
    ocrolus_types = load_ocrolus_types(args.ocrolus)
    print(f"  Found {len(ocrolus_types)} Ocrolus form types.")

    print("Loading lender container names...")
    lender_containers = load_lender_containers(args.lender)
    print(f"  Found {len(lender_containers)} lender containers.")

    # --- AI Mapping (parallel) ---
    print("\nQuerying AI services in parallel...")
    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=len(AI_SERVICES)) as executor:
        future_to_svc = {
            executor.submit(svc.get_mappings, ocrolus_types, lender_containers): svc
            for svc in AI_SERVICES
        }
        for future in as_completed(future_to_svc):
            svc = future_to_svc[future]
            name = svc.SERVICE_NAME
            try:
                results[name] = future.result()
                print(f"  {name}: received {len(results[name])} mappings.")
            except Exception as e:
                errors[name] = str(e)
                print(f"  {name}: ERROR — {e}", file=sys.stderr)

    if len(results) < 2:
        print(
            "\nFATAL: Need at least 2 AI services to succeed for consensus. "
            f"Only {len(results)} succeeded.",
            file=sys.stderr,
        )
        if errors:
            for svc_name, err in errors.items():
                print(f"  {svc_name}: {err}", file=sys.stderr)
        sys.exit(1)

    if errors:
        print(f"\nWARNING: {len(errors)} service(s) failed. Proceeding with {len(results)} results.")

    # --- Consensus ---
    print("\nBuilding consensus...")
    service_names = list(results.keys())
    confident, review = build_consensus(results, ocrolus_types)

    print(f"  Confident mappings: {len(confident)}")
    print(f"  Needs manual review: {len(review)}")

    # --- Output ---
    write_output_csv(args.output, confident, review, service_names)
    print(f"\nResults written to: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
