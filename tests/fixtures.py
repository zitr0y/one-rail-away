import io
import zipfile
from pathlib import Path

from pipeline.config import FeedConfig

CAL = (
    "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
    "S1,1,1,1,1,1,1,1,20260101,20261231\n"
)

LANDIA = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nL,Landia,https://l.example,Europe/Berlin\n",
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "st:1111111,Alpha Hbf,50.0,8.0\n"
        "st:2222222,Beta Hbf,50.0,9.0\n"
        "st:3333333,Gamma Hbf,50.0,10.0\n"
    ),
    "routes.txt": (
        "route_id,agency_id,route_short_name,route_type\n"
        "R100,L,IC 100,2\nR101,L,IC 101,2\nR300,L,IC 300,2\nRB1,L,RB 1,2\n"
    ),
    "trips.txt": (
        "route_id,service_id,trip_id\nR100,S1,T100\nR101,S1,T101\nR300,S1,T300\nRB1,S1,TRB1\n"
    ),
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T100,08:00:00,08:00:00,st:1111111,1\n"
        "T100,09:00:00,09:02:00,st:2222222,2\n"
        "T100,10:00:00,10:00:00,st:3333333,3\n"
        "T101,12:00:00,12:00:00,st:1111111,1\n"
        "T101,12:50:00,12:50:00,st:2222222,2\n"
        "T300,09:05:00,09:05:00,st:2222222,1\n"
        "T300,10:05:00,10:05:00,st:3333333,2\n"
        "TRB1,07:00:00,07:00:00,st:1111111,1\n"
        "TRB1,08:30:00,08:30:00,st:2222222,2\n"
    ),
    "calendar.txt": CAL,
}

BORDERIA = {
    "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nB,Borderia,https://b.example,Europe/Paris\n",
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "bs-3333333,Gamma Central,50.0001,10.0001\n"
        "bs-4444444,Delta Gare,50.0,11.0\n"
    ),
    "routes.txt": "route_id,agency_id,route_short_name,route_type\nRT10,B,TGV 10,2\n",
    "trips.txt": "route_id,service_id,trip_id\nRT10,S1,TT10\n",
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "TT10,10:30:00,10:30:00,bs-3333333,1\n"
        "TT10,12:00:00,12:00:00,bs-4444444,2\n"
    ),
    "calendar.txt": CAL,
}


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def make_fixture_feeds(dir: Path) -> dict[str, FeedConfig]:
    dir.mkdir(parents=True, exist_ok=True)
    (dir / "landia.zip").write_bytes(_zip(LANDIA))
    (dir / "borderia.zip").write_bytes(_zip(BORDERIA))
    return {
        "landia": FeedConfig(
            url="unused",
            country="LA",
            license="test",
            route_allow=["^IC\\b", "^TGV\\b"],
            uic_regex="(\\d{7})",
        ),
        "borderia": FeedConfig(
            url="unused",
            country="BO",
            license="test",
            route_allow=["^TGV\\b"],
            uic_regex="(\\d{7})",
        ),
    }
