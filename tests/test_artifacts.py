import gzip

from pipeline.artifacts import write_json_with_gzip


def test_write_json_with_gzip_round_trips_and_gz_is_fresh(tmp_path):
    path = tmp_path / "thing.json"
    write_json_with_gzip(path, '{"a": 1}')

    gz = tmp_path / "thing.json.gz"
    assert path.read_text(encoding="utf-8") == '{"a": 1}'
    assert gzip.decompress(gz.read_bytes()) == b'{"a": 1}'
    assert gz.stat().st_mtime >= path.stat().st_mtime


def test_write_json_with_gzip_overwrite_keeps_gz_fresh(tmp_path):
    path = tmp_path / "thing.json"
    write_json_with_gzip(path, '{"a": 1}')
    write_json_with_gzip(path, '{"a": 2}')

    gz = tmp_path / "thing.json.gz"
    assert gzip.decompress(gz.read_bytes()) == b'{"a": 2}'
    assert gz.stat().st_mtime >= path.stat().st_mtime
