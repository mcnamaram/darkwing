"""gcloud OAuth token retrieval with 50‑minute cache."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

_CACHE_FILE = Path.home() / ".darkwing" / "token_cache.json"


def get_token() -> str:
    """Return a fresh Google OAuth access token, caching for 50 minutes.

    The token is obtained by shelling out to ``gcloud auth print-access-token``.
    The result is cached in ``~/.darkwing/token_cache.json`` (created on first
    call) keyed by the token value and its acquisition time.  Subsequent calls
    within 50 minutes return the cached token without invoking gcloud again.
    """
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    cached = _load_cache()
    if cached is not None:
        token, acquired_at = cached
        if time.time() - acquired_at < 50 * 60:  # 50 minutes
            return token

    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("gcloud returned an empty token")

    _save_cache(token)
    return token


def _load_cache() -> Optional[tuple]:
    """Load (token, acquired_at) from cache file, or None if absent/corrupt."""
    if not _CACHE_FILE.exists():
        return None
    try:
        import json
        data = json.loads(_CACHE_FILE.read_text())
        return data["token"], data["acquired_at"]
    except Exception:
        return None


def _save_cache(token: str) -> None:
    """Persist (token, current_time) to the cache file."""
    import json
    _CACHE_FILE.write_text(json.dumps({
        "token": token,
        "acquired_at": time.time(),
    }))
