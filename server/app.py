import json
import unicodedata
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


def _read(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=503, detail="Pipeline has never run - no data available")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


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

    @app.get("/api/stations")
    def stations() -> dict:
        data = _read(data_dir / "stations.json")
        reach_ids = _reach_ids_on_disk(data_dir)
        return {"stations": _with_disk_has_reach(data["stations"], reach_ids)}

    @app.get("/api/stations/search")
    def search(q: str, limit: int = 10) -> dict:
        nq = normalize(q)
        reach_ids = _reach_ids_on_disk(data_dir)
        scored = []
        for s in _read(data_dir / "stations.json")["stations"]:
            if s["id"] not in reach_ids:
                continue
            name = normalize(s["name"])
            if name.startswith(nq):
                scored.append((0, len(name), s))
            elif nq in name:
                scored.append((1, len(name), s))
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

    return app


app = create_app(Path("data/out"))
