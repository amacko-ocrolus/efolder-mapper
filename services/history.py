"""GCS-backed run history. No-ops gracefully if GCS_BUCKET_NAME is not set."""

import os
import re
from datetime import datetime, timedelta, timezone


GCS_BUCKET = os.environ.get("GCS_BUCKET_NAME", "")


def is_configured() -> bool:
    return bool(GCS_BUCKET)


def _client():
    from google.cloud import storage
    return storage.Client()


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", os.path.splitext(name)[0])[:60]


def save_run(
    lender_filename: str,
    confident_count: int,
    review_count: int,
    services_used: str,
    csv_bytes: bytes,
) -> str:
    """Upload csv_bytes to GCS and return the blob name (run ID)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    blob_name = f"runs/{ts}_{_sanitize(lender_filename)}.csv"
    bucket = _client().bucket(GCS_BUCKET)
    blob = bucket.blob(blob_name)
    blob.metadata = {
        "lender_filename": lender_filename,
        "confident_count": str(confident_count),
        "review_count": str(review_count),
        "services_used": services_used,
    }
    blob.upload_from_string(csv_bytes, content_type="text/csv")
    return blob_name


def list_runs() -> list[dict]:
    """Return runs from the last 180 days, sorted newest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    blobs = _client().list_blobs(GCS_BUCKET, prefix="runs/")
    runs = []
    for blob in blobs:
        if blob.time_created < cutoff:
            continue
        blob.reload()
        meta = blob.metadata or {}
        runs.append({
            "blob_name": blob.name,
            "created": blob.time_created,
            "lender_filename": meta.get("lender_filename", os.path.basename(blob.name)),
            "confident_count": int(meta.get("confident_count", 0)),
            "review_count": int(meta.get("review_count", 0)),
            "services_used": meta.get("services_used", ""),
        })
    return sorted(runs, key=lambda r: r["created"], reverse=True)


def get_run_bytes(blob_name: str) -> bytes:
    """Download and return the CSV bytes for a given run."""
    return _client().bucket(GCS_BUCKET).blob(blob_name).download_as_bytes()
