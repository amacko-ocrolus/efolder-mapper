"""File ingestion module for CSV and JSON input files."""

import csv
import json
import os


def load_ocrolus_types(file_path: str) -> list[str]:
    """Load Ocrolus document form type names from a CSV file.

    Auto-detects which column contains the form type names by looking for
    a column with 'name', 'type', 'form', or 'document' in the header.
    If only one column exists, uses that column directly.

    Returns a sorted list of unique form type name strings.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Ocrolus file not found: {file_path}")

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        if not fieldnames:
            raise ValueError(f"CSV file has no headers: {file_path}")

        # If single column, use it directly
        if len(fieldnames) == 1:
            target_col = fieldnames[0]
        else:
            # Try to find the most likely column
            target_col = _find_best_column(
                fieldnames, ["name", "type", "form", "document"]
            )
            if target_col is None:
                # Fall back to first column
                target_col = fieldnames[0]

        types = []
        for row in reader:
            value = row[target_col].strip()
            if value:
                types.append(value)

    if not types:
        raise ValueError(f"No form type names found in {file_path}")

    return sorted(set(types))


def load_lender_containers(file_path: str) -> list[str]:
    """Load lender Encompass document container names from a CSV or JSON file.

    Auto-detects file format by extension (.csv or .json).
    Auto-detects which column/field contains container names.

    Returns a sorted list of unique container name strings.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Lender file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        return _load_lender_csv(file_path)
    elif ext == ".json":
        return _load_lender_json(file_path)
    else:
        raise ValueError(
            f"Unsupported file format '{ext}'. Use .csv or .json"
        )


def _load_lender_csv(file_path: str) -> list[str]:
    """Load container names from a CSV file."""
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        if not fieldnames:
            raise ValueError(f"CSV file has no headers: {file_path}")

        if len(fieldnames) == 1:
            target_col = fieldnames[0]
        else:
            target_col = _find_best_column(
                fieldnames, ["container", "name", "document", "title", "label"]
            )
            if target_col is None:
                target_col = fieldnames[0]

        containers = []
        for row in reader:
            value = row[target_col].strip()
            if value:
                containers.append(value)

    if not containers:
        raise ValueError(f"No container names found in {file_path}")

    return sorted(set(containers))


def _load_lender_json(file_path: str) -> list[str]:
    """Load container names from a JSON file.

    Supports:
    - A flat array of strings: ["Container A", "Container B"]
    - An array of objects: [{"name": "Container A"}, ...]
    - An object with an array value: {"containers": ["Container A", ...]}
    """
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    containers = _extract_strings_from_json(data)

    if not containers:
        raise ValueError(f"No container names found in {file_path}")

    return sorted(set(containers))


def _extract_strings_from_json(data) -> list[str]:
    """Recursively extract container name strings from JSON data."""
    # Flat array of strings
    if isinstance(data, list):
        if all(isinstance(item, str) for item in data):
            return [s.strip() for s in data if s.strip()]
        # Array of objects — find the best field
        if all(isinstance(item, dict) for item in data) and data:
            keys = list(data[0].keys())
            target_key = _find_best_column(
                keys, ["container", "name", "document", "title", "label"]
            )
            if target_key is None:
                target_key = keys[0]
            return [
                row[target_key].strip()
                for row in data
                if isinstance(row.get(target_key), str) and row[target_key].strip()
            ]

    # Object with an array value — find the array and recurse
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and value:
                result = _extract_strings_from_json(value)
                if result:
                    return result

    return []


def _find_best_column(columns: list[str], keywords: list[str]) -> str | None:
    """Find the column whose name best matches the given keywords."""
    lower_cols = {col: col.lower() for col in columns}

    # Exact match first
    for kw in keywords:
        for col, lower in lower_cols.items():
            if lower == kw:
                return col

    # Substring match
    for kw in keywords:
        for col, lower in lower_cols.items():
            if kw in lower:
                return col

    return None
