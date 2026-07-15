import zipfile

from tests.fixtures import make_fixture_feeds

GTFS_REQUIRED = {"stops.txt", "trips.txt", "stop_times.txt", "routes.txt", "calendar.txt"}


def test_fixture_zips_are_valid_gtfs(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    assert set(cfgs) == {"landia", "borderia"}
    with zipfile.ZipFile(tmp_path / "landia.zip") as zf:
        assert set(zf.namelist()) >= GTFS_REQUIRED
    with zipfile.ZipFile(tmp_path / "borderia.zip") as zf:
        assert set(zf.namelist()) >= GTFS_REQUIRED
