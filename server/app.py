import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


def _read(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=503, detail="Pipeline has never run - no data available")
    return json.loads(path.read_text(encoding="utf-8"))


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI(title="onestopeurope")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

    @app.get("/api/stations")
    def stations() -> dict:
        return _read(data_dir / "stations.json")

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
