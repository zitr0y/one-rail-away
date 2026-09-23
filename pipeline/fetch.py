"""Feed downloader with per-feed failure isolation.

A failure fetching one feed (network error, HTTP error status, etc.) never
aborts the others: it is logged with the feed name and recorded as not-ok
in fetch_meta.json, while remaining feeds continue to be fetched.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pipeline.config import FeedConfig

logger = logging.getLogger(__name__)


def fetch_all(
    feeds: dict[str, FeedConfig], raw_dir: Path, client: httpx.Client | None = None
) -> dict[str, bool]:
    """Download each feed to raw_dir/<name>.zip; write raw_dir/fetch_meta.json.

    Returns {name: ok} for every feed. One feed failing never prevents the
    others from being attempted.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    results: dict[str, bool] = {}
    meta: dict[str, dict] = {}
    try:
        for name, cfg in feeds.items():
            stamp = datetime.now(UTC).isoformat()
            try:
                resp = client.get(cfg.url)
                resp.raise_for_status()
                (raw_dir / f"{name}.zip").write_bytes(resp.content)
                results[name] = True
                logger.info("fetched %s (%d bytes)", name, len(resp.content))
            except Exception as exc:  # failure isolation: log, continue
                results[name] = False
                logger.error("failed to fetch feed %s: %s", name, exc)
            meta[name] = {"downloaded_at": stamp, "ok": results[name]}
    finally:
        if own_client:
            client.close()
    (raw_dir / "fetch_meta.json").write_text(json.dumps(meta, indent=2))
    return results


TRAINLINE_STATIONS_URL = (
    "https://raw.githubusercontent.com/trainline-eu/stations/master/stations.csv"
)


def fetch_trainline_stations(raw_dir: Path, client: httpx.Client | None = None) -> bool:
    """Download Trainline's open stations.csv (ODbL) to raw_dir/trainline_stations.csv.

    Used only to map stations to Trainline ids for the booking handoff. On
    failure the previous copy (if any) is kept and the run continues.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    try:
        resp = client.get(TRAINLINE_STATIONS_URL)
        resp.raise_for_status()
        tmp = raw_dir / "trainline_stations.csv.tmp"
        tmp.write_bytes(resp.content)
        tmp.replace(raw_dir / "trainline_stations.csv")
        logger.info("fetched trainline stations (%d bytes)", len(resp.content))
        return True
    except Exception as exc:  # never abort the pipeline over the booking lookup
        logger.error("failed to fetch trainline stations: %s", exc)
        return False
    finally:
        if own_client:
            client.close()
