import json
import unicodedata
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware


def _read(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=503, detail="Pipeline has never run - no data available")
    return json.loads(path.read_text(encoding="utf-8"))


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
    "prague": "praha",
    "prag": "praha",
    "vienna": "wien",
    "warsaw": "warszawa",
    "warschau": "warszawa",
    "venice": "venezia",
    "venedig": "venezia",
    "milan": "milano",
    "mailand": "milano",
    "munich": "munchen",
    "muenchen": "munchen",
    "cologne": "koln",
    "koeln": "koln",
    "nuremberg": "nurnberg",
    "nuernberg": "nurnberg",
    "wuerzburg": "wurzburg",
    "duesseldorf": "dusseldorf",
    "zuerich": "zurich",
    "geneva": "geneve",
    "genf": "geneve",
    # Flipped 2026-07-10: station renamed Barcelona-Sants (pipeline/station_names.toml
    # override); French spelling "barcelone" now finds the Spanish-named station.
    # Match count: barcelone still matches 1 station after rename (verified).
    "barcelone": "barcelona",
    "brussels": "bruxelles",
    "bruessel": "bruxelles",
    "rome": "roma",
    "antwerp": "antwerpen",
    "the hague": "den haag",
    "copenhagen": "københavn",
    "lyons": "lyon",
    "marseilles": "marseille",
    "seville": "sevilla",
    "aix-la-chapelle": "aachen",
    "ratisbon": "regensburg",
    "brunswick": "braunschweig",
    "hanover": "hannover",
    "coblenz": "koblenz",
    "mayence": "mainz",
    "francfort": "frankfurt",
    "strassburg": "strasbourg",
    "bale": "basel",
    "lucerne": "luzern",
    "berne": "bern",
    "bucharest": "bucuresti",
    "danzig": "gdansk",
    "breslau": "wroclaw",
    "stettin": "szczecin",
    "posen": "poznan",
    "cracow": "krakow",
    "lodz": "łodz",
    "saragossa": "zaragoza",
    "gerona": "girona",
    "lerida": "lleida",
    "corunna": "a coruna",
    "bois-le-duc": "s-hertogenbosch",
    "flushing": "vlissingen",
    "pressburg": "bratislava",
    "lemberg": "lviv",
    "zagabria": "zagreb",
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
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/api/stations")
    def stations() -> dict:
        data = _read(data_dir / "stations.json")
        reach_ids = _reach_ids_on_disk(data_dir)
        return {"stations": _with_disk_has_reach(data["stations"], reach_ids)}

    @app.get("/api/stations/search")
    def search(q: str, limit: int = 10) -> dict:
        variants = _query_variants(normalize(q))
        reach_ids = _reach_ids_on_disk(data_dir)
        scored = []
        for s in _read(data_dir / "stations.json")["stations"]:
            if s["id"] not in reach_ids:
                continue
            name = normalize(s["name"])
            best = None
            for v in variants:
                if name.startswith(v):
                    cand = (0, len(name))
                elif v in name:
                    cand = (1, len(name))
                else:
                    continue
                best = cand if best is None else min(best, cand)
            if best is not None:
                scored.append((*best, s))
        scored.sort(key=lambda x: (x[0], x[1]))
        return {"stations": [{**s, "has_reach": True} for _, _, s in scored[:limit]]}

    @app.get("/api/reach/{station_id}")
    def reach(station_id: str) -> dict:
        path = data_dir / f"reach_{station_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"No data for station {station_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/meta")
    def meta() -> dict:
        return _read(data_dir / "meta.json")

    @app.get("/api/coverage")
    def coverage() -> dict:
        path = data_dir / "coverage.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="No coverage data")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/cities")
    def cities() -> dict:
        path = data_dir / "cities.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="No cities data")
        return json.loads(path.read_text(encoding="utf-8"))

    return app


app = create_app(Path("data/out"))
