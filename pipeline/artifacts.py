"""Shared helper for writing a JSON artifact alongside a pre-gzipped sibling.

Four endpoint families (`coverage`, `reach`, `cities`, `meta`) are served
verbatim by `server/app.py` -- byte-identical on every request, so gzipping
them once at pipeline-write time (instead of on every request) turns ~1.7s
of server CPU per page view into a `sendfile`. The plain `.json` stays the
source of truth; the `.json.gz` is purely a serving optimisation.

`stations.json` deliberately has no `.gz` sibling: the server merges it with
a live `has_reach` set on every request (see `server/app._cached_stations`),
so it is never served verbatim.
"""

import gzip
import os
from pathlib import Path


def write_json_with_gzip(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path`, plus a `path.name + ".gz"` sibling.

    The `.gz` sibling's mtime is bumped to match the plain file's, so a
    consumer comparing mtimes (`gz.stat().st_mtime >= path.stat().st_mtime`)
    can treat it as fresh regardless of filesystem mtime resolution or the
    order the two writes land in.
    """
    data = text.encode(encoding)
    path.write_bytes(data)
    gz_path = path.with_name(path.name + ".gz")
    gz_path.write_bytes(gzip.compress(data, compresslevel=6, mtime=0))
    mtime = path.stat().st_mtime
    os.utime(gz_path, (mtime, mtime))
