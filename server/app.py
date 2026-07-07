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


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI(title="onestopeurope")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

    @app.get("/api/stations")
    def stations() -> dict:
        return _read(data_dir / "stations.json")

    @app.get("/api/stations/search")
    def search(q: str, limit: int = 10) -> dict:
        nq = normalize(q)
        scored = []
        for s in _read(data_dir / "stations.json")["stations"]:
            if not s.get("has_reach"):
                continue
            name = normalize(s["name"])
            if name.startswith(nq):
                scored.append((0, len(name), s))
            elif nq in name:
                scored.append((1, len(name), s))
        scored.sort(key=lambda x: (x[0], x[1]))
        return {"stations": [s for _, _, s in scored[:limit]]}

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
