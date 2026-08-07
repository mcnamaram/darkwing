"""Submit observation records to the Google Apps Script webhook."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

from darkwing.auth import get_token
from darkwing.schema import ObservationRecord


def _get_apps_script_url() -> str:
    """Read DARKWING_APPS_SCRIPT_URL from the environment.

    Falls back to reading from ``.env`` if the env var is not set.
    """
    import os
    url = os.environ.get("DARKWING_APPS_SCRIPT_URL")
    if url:
        return url
    # Try .env file
    env_path = Path(".env")
    if env_path.exists():
        import dotenv
        dotenv.load_dotenv(env_path)
        url = os.environ.get("DARKWING_APPS_SCRIPT_URL")
        if url:
            return url
    raise EnvironmentError(
        "DARKWING_APPS_SCRIPT_URL not set. "
        "Add it to your .env file or environment."
    )


def submit_record(record: ObservationRecord) -> Dict:
    """POST a single observation record to the Apps Script webhook.

    Returns the JSON response body (dict).  Raises on HTTP errors.
    """
    url = _get_apps_script_url()
    token = get_token()
    payload = record.to_form_payload()

    resp = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def submit_csv_records(
    records: Iterable[ObservationRecord],
    dry_run: bool = False,
    batch_size: int = 1,
) -> List[Dict]:
    """Submit multiple records, one at a time.

    Parameters
    ----------
    records : iterable of ObservationRecord
        The observations to submit.
    dry_run : bool
        If True, print what would be submitted without actually POSTing.
    batch_size : int
        Currently unused (reserved for future batching).

    Returns
    -------
    list of dict
        The JSON response from each successful submission.
    """
    results: List[Dict] = []
    for rec in records:
        if dry_run:
            print(f"[DRY RUN] Would submit: {rec.tower} @ {rec.time_of_day}")
            results.append({"status": "dry-run", "tower": rec.tower})
            continue
        resp = submit_record(rec)
        results.append(resp)
    return results


def submit_csv_file(
    csv_path: Path,
    dry_run: bool = False,
    log_path: Optional[Path] = None,
) -> List[Dict]:
    """Load a CSV and submit all records. Convenience wrapper."""
    from darkwing.csv_io import read_csv, write_submission_log  # local import

    records = read_csv(csv_path)
    results = submit_csv_records(records, dry_run=dry_run)

    if log_path and not dry_run:
        # Only log successfully submitted records
        successful = [r for r in results if r.get("status") == "success"]
        if successful:
            # Re-read records to log; we only have results here, not records
            pass  # log path handled externally

    return results
