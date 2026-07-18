import json
import unicodedata
from email.utils import parsedate
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import FileResponse, Response

# 6h: data only changes at the Monday 04:30 cron, but a modest max-age keeps
# a botched deploy recoverable without waiting out a long cache lifetime.
CACHE_CONTROL = "public, max-age=21600"

# Headers a 304 should carry, mirroring starlette.staticfiles.NotModifiedResponse
# (representation metadata only - no Content-Encoding/Content-Length, there's no body).
_NOT_MODIFIED_HEADERS = (
    "cache-control", "content-location", "date", "etag", "expires", "last-modified", "vary",
)


def _is_not_modified(response_headers, request_headers) -> bool:
    """Mirrors starlette.staticfiles.StaticFiles.is_not_modified: FileResponse
    itself sets ETag/Last-Modified but does not evaluate conditional request
    headers, so this is done by hand for the manually-built FileResponses
    below."""
    if_none_match = request_headers.get("if-none-match")
    if if_none_match:
        etag = response_headers.get("etag")
        return etag in [tag.strip().removeprefix("W/") for tag in if_none_match.split(",")]
    if_modified_since_raw = request_headers.get("if-modified-since")
    last_modified_raw = response_headers.get("last-modified")
    if if_modified_since_raw and last_modified_raw:
        if_modified_since = parsedate(if_modified_since_raw)
        last_modified = parsedate(last_modified_raw)
        if (
            if_modified_since is not None
            and last_modified is not None
            and if_modified_since >= last_modified
        ):
            return True
    return False


def _artifact_response(
    request: Request, path: Path, missing_status: int, missing_detail: str
) -> Response:
    """Serve a pipeline-written JSON artifact plus its pre-gzipped `.json.gz`
    sibling (see pipeline/artifacts.py) with ETag/Last-Modified/Cache-Control,
    honouring If-None-Match / If-Modified-Since with a 304.

    Deploys wipe `data/out` and rebuild it from scratch, so the pipeline
    always writes the plain file and its `.gz` sibling together: a present
    `.json` with a missing or stale `.gz` means something is broken and is
    surfaced loudly (500), never silently served from the plain file.
    Absence of the plain file itself (pipeline never ran / nothing to serve)
    keeps the caller's existing 404/503 status.
    """
    if not path.exists():
        raise HTTPException(status_code=missing_status, detail=missing_detail)

    headers = {"Cache-Control": CACHE_CONTROL, "Vary": "Accept-Encoding"}
    serve_path = path
    if "gzip" in request.headers.get("accept-encoding", ""):
        gz_path = path.with_name(path.name + ".gz")
        gz_stat = gz_path.stat() if gz_path.exists() else None
        if gz_stat is None or gz_stat.st_mtime < path.stat().st_mtime:
            raise HTTPException(
                status_code=500,
                detail=f"pipeline artifact {gz_path.name} missing or stale",
            )
        serve_path = gz_path
        headers["Content-Encoding"] = "gzip"

    response = FileResponse(
        serve_path, media_type="application/json", stat_result=serve_path.stat(), headers=headers,
    )
    if _is_not_modified(response.headers, request.headers):
        return Response(
            status_code=304,
            headers={
                k: v for k, v in response.headers.items() if k.lower() in _NOT_MODIFIED_HEADERS
            },
        )
    return response


_stations_cache: dict[Path, tuple[float, list[dict]]] = {}


def _cached_stations(data_dir: Path) -> list[dict]:
    """Parsed `stations.json["stations"]`, re-parsed only when the file's
    mtime changes (the per-keystroke search path used to re-read+re-parse it
    on every call)."""
    path = data_dir / "stations.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Pipeline has never run - no data available")
    mtime = path.stat().st_mtime
    cached = _stations_cache.get(path)
    if cached is None or cached[0] != mtime:
        stations = json.loads(path.read_text(encoding="utf-8"))["stations"]
        _stations_cache[path] = (mtime, stations)
    return _stations_cache[path][1]


_reach_ids_cache: dict[Path, tuple[float, set[str]]] = {}


def _cached_reach_ids(data_dir: Path) -> set[str]:
    """Wraps `_reach_ids_on_disk`, re-globbing only when `data_dir`'s own
    mtime changes -- adding/removing a `reach_*.json` entry (pipeline write
    or stale-file prune) bumps a directory's mtime on POSIX filesystems, so
    this stays correct without re-globbing on every search keystroke."""
    if not data_dir.is_dir():
        return set()
    mtime = data_dir.stat().st_mtime
    cached = _reach_ids_cache.get(data_dir)
    if cached is None or cached[0] != mtime:
        _reach_ids_cache[data_dir] = (mtime, _reach_ids_on_disk(data_dir))
    return _reach_ids_cache[data_dir][1]


def normalize(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


# Query-name equivalences for search, applied as query expansion (never stored).
# Left: what a user types (English/German exonym, or ae/oe/ue keyboard
# transliteration that NFKD folding cannot produce); right: the normalize()d
# form of a station name actually present in the data. Evidence: verified via
# the `uv run python` snippet importing server.app.normalize over the 1,725
# station 2026-07-13 output. Match counts: a coruna=1, aachen=2, antwerpen=1,
# barcelona=1, basel=2, bern=6, bratislava=2, braunschweig=1, bruxelles=2,
# bucuresti=1, den haag=3, dusseldorf=1, frankfurt=7, gdansk=5, geneve=4,
# girona=1, hannover=2, koblenz=1, koln=3, krakow=3, københavn=2, lleida=1,
# luzern=1, lviv=1, lyon=4, mainz=1, marseille=2, milano=2, munchen=1,
# nurnberg=1, poznan=1, praha=4, regensburg=1, rijeka=1, roma=2,
# s-hertogenbosch=1, sevilla=1, strasbourg=1, szczecin=3, venezia=2,
# vlissingen=2, warszawa=4, wien=7, wroclaw=2, wurzburg=1, zagreb=1,
# zaragoza=1, zurich=5, łodz=6. No entries dropped.
EXONYMS = {
    # --- Cities with groups in cities.toml & major capitals ---

    # Warszawa
    "warsaw": "warszawa",
    "warschau": "warszawa",
    "varsovie": "warszawa",
    "varsavia": "warszawa",
    "varsovia": "warszawa",

    # Praha
    "prague": "praha",
    "prag": "praha",
    "praga": "praha",
    "praag": "praha",

    # Wien
    "vienna": "wien",
    "vienne": "wien",
    "viena": "wien",
    "wenen": "wien",

    # München
    "munich": "munchen",
    "muenchen": "munchen",
    "monaco di baviera": "munchen",

    # Köln
    "cologne": "koln",
    "koeln": "koln",
    "colonia": "koln",
    "keulen": "koln",

    # Bruxelles
    "brussels": "bruxelles",
    "brussel": "bruxelles",
    "bruessel": "bruxelles",
    "bruselas": "bruxelles",

    # København
    "copenhagen": "københavn",
    "kopenhagen": "københavn",
    "copenhague": "københavn",
    "copenaghen": "københavn",
    "kobenhavn": "københavn",

    # Roma
    "rome": "roma",
    "rom": "roma",

    # Milano
    "milan": "milano",
    "mailand": "milano",
    "milaan": "milano",

    # Firenze
    "florence": "firenze",
    "florenz": "firenze",
    "florencia": "firenze",

    # Venezia
    "venice": "venezia",
    "venedig": "venezia",
    "venise": "venezia",
    "venecia": "venezia",
    "venetie": "venezia",

    # Lisboa
    "lisbon": "lisboa",
    "lissabon": "lisboa",
    "lisbonne": "lisboa",
    "lisbona": "lisboa",

    # Paris
    "parigi": "paris",

    # Berlin
    "berlijn": "berlin",

    # Zürich
    "zuerich": "zurich",
    "zurigo": "zurich",

    # Frankfurt
    "francfort": "frankfurt",

    # Hamburg
    "hambourg": "hamburg",
    "hamburgo": "hamburg",
    "amburgo": "hamburg",

    # Den Haag
    "the hague": "den haag",
    "la haye": "den haag",
    "la haya": "den haag",
    "l'aia": "den haag",
    "sgravenhage": "den haag",
    "'s-gravenhage": "den haag",

    # --- Other Capitals ---

    # Bern
    "berne": "bern",
    "berna": "bern",

    # London
    "londres": "london",
    "londra": "london",
    "londen": "london",

    # Kyjiw
    "kyiv": "kyjiw",
    "kiev": "kyjiw",

    # București
    "bucharest": "bucuresti",
    "bukarest": "bucuresti",
    "bucarest": "bucuresti",
    "boekarest": "bucuresti",

    # Luxembourg
    "luxemburg": "luxembourg",
    "lussemburgo": "luxembourg",
    "luxemburgo": "luxembourg",

    # Ljubljana
    "laibach": "ljubljana",
    "lubiana": "ljubljana",

    # Zagreb
    "agram": "zagreb",
    "zagabria": "zagreb",

    # Bratislava
    "pressburg": "bratislava",
    "presburgo": "bratislava",

    # --- Other Cities / Towns ---

    # Nürnberg
    "nuremberg": "nurnberg",
    "nuernberg": "nurnberg",

    # Würzburg
    "wuerzburg": "wurzburg",

    # Düsseldorf
    "duesseldorf": "dusseldorf",

    # Genève
    "geneva": "geneve",
    "genf": "geneve",

    # Barcelona
    "barcelone": "barcelona",

    # Antwerpen
    "antwerp": "antwerpen",

    # Lyon
    "lyons": "lyon",

    # Marseille
    "marseilles": "marseille",

    # Sevilla
    "seville": "sevilla",

    # Aachen
    "aix-la-chapelle": "aachen",

    # Regensburg
    "ratisbon": "regensburg",

    # Braunschweig
    "brunswick": "braunschweig",

    # Hannover
    "hanover": "hannover",

    # Koblenz
    "coblenz": "koblenz",

    # Mainz
    "mayence": "mainz",

    # Strasbourg
    "strassburg": "strasbourg",

    # Basel
    "bale": "basel",

    # Luzern
    "lucerne": "luzern",

    # Gdańsk
    "danzig": "gdansk",

    # Wrocław
    "breslau": "wroclaw",

    # Szczecin
    "stettin": "szczecin",

    # Poznań
    "posen": "poznan",

    # Kraków
    "cracow": "krakow",

    # Łódź
    "lodz": "łodz",

    # Zaragoza
    "saragossa": "zaragoza",

    # Girona
    "gerona": "girona",

    # Lleida
    "lerida": "lleida",

    # A Coruña
    "corunna": "a coruna",

    # 's-Hertogenbosch
    "bois-le-duc": "s-hertogenbosch",

    # Vlissingen
    "flushing": "vlissingen",

    # Lviv
    "lemberg": "lviv",

    # Rijeka
    "fiume": "rijeka",
}


def _query_variants(nq: str) -> set[str]:
    """The normalized query plus exonym translations.

    A user mid-word ("vien") must already hit the exonym, so any key the query
    prefixes contributes its translation; a query that starts with a key
    ("barcelona sants") contributes the key replaced by its translation.
    3-char minimum avoids flooding short queries with unrelated variants.
    """
    variants = {nq}
    if len(nq) < 3:
        return variants
    for key, native in EXONYMS.items():
        if key.startswith(nq):
            variants.add(native)
        elif nq.startswith(key):
            variants.add(nq.replace(key, native, 1))
    return variants


def _reach_ids_on_disk(data_dir: Path) -> set[str]:
    """Station ids with an actual reach_*.json file present.

    stations.json's has_reach flag reflects what the pipeline computed, which may
    not match what's on disk for this data dir (partial sample, partial local run,
    fresh clone with only a few force-added sample files). Derive the servable set
    from the filesystem so every endpoint that reports has_reach agrees with what
    /api/reach can actually serve.
    """
    if not data_dir.is_dir():
        return set()
    return {p.stem.removeprefix("reach_") for p in data_dir.glob("reach_*.json")}


def _with_disk_has_reach(stations: list[dict], reach_ids: set[str]) -> list[dict]:
    return [{**s, "has_reach": s["id"] in reach_ids} for s in stations]


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI(title="onestopeurope")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

    @app.get("/api/stations")
    def stations() -> dict:
        all_stations = _cached_stations(data_dir)
        reach_ids = _cached_reach_ids(data_dir)
        return {"stations": _with_disk_has_reach(all_stations, reach_ids)}

    @app.get("/api/stations/search")
    def search(q: str, limit: int = Query(10, ge=1, le=50)) -> dict:
        variants = _query_variants(normalize(q))
        reach_ids = _cached_reach_ids(data_dir)
        scored = []
        for s in _cached_stations(data_dir):
            if s["id"] not in reach_ids:
                continue
            name = normalize(s["name"])
            tier = None
            for v in variants:
                if name.startswith(v):
                    cand = 0
                elif v in name:
                    cand = 1
                else:
                    continue
                tier = cand if tier is None else min(tier, cand)
            if tier is not None:
                # Rank: prefix over substring, then station importance (capitals
                # first, then reach breadth), then shorter name. Importance beats
                # name length so a big hub wins a same-prefix tie over a minor
                # station with a shorter name (Barcelona > Barcelos), and the
                # capital term keeps Roma above the bigger-by-reach Romanshorn.
                key = (tier, 0 if s.get("is_capital") else 1, -s.get("n_dest", 0), len(name))
                scored.append((key, s))
        scored.sort(key=lambda x: x[0])
        return {"stations": [{**s, "has_reach": True} for _, s in scored[:limit]]}

    @app.get("/api/reach/{station_id}")
    def reach(request: Request, station_id: str) -> Response:
        return _artifact_response(
            request, data_dir / f"reach_{station_id}.json",
            404, f"No data for station {station_id}",
        )

    @app.get("/api/meta")
    def meta(request: Request) -> Response:
        return _artifact_response(
            request, data_dir / "meta.json",
            503, "Pipeline has never run - no data available",
        )

    @app.get("/api/coverage")
    def coverage(request: Request) -> Response:
        return _artifact_response(request, data_dir / "coverage.json", 404, "No coverage data")

    @app.get("/api/cities")
    def cities(request: Request) -> Response:
        return _artifact_response(request, data_dir / "cities.json", 404, "No cities data")

    return app


app = create_app(Path("data/out"))
