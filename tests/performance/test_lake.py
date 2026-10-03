"""Mutable lake identity must catch changes even when filesystem metadata is restored."""

import os

from benchmarks.lake import fingerprint_function


def test_lake_content_add_delete_and_order_are_authenticated(tmp_path):
    fingerprint = fingerprint_function()
    directory = tmp_path / "curated"
    directory.mkdir()
    a, b = directory / "a.parquet", directory / "b.parquet"
    a.write_bytes(b"SYNTHETIC-A")
    b.write_bytes(b"SYNTHETIC-B")
    before = fingerprint(tmp_path)
    stamp = a.stat()
    assert fingerprint(tmp_path) == before
    a.write_bytes(b"SYNTHETIC-C")
    os.utime(a, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    changed = fingerprint(tmp_path)
    assert changed != before  # same size, path and mtime cannot authorize reuse
    a.write_bytes(b"SYNTHETIC-A")
    assert fingerprint(tmp_path) == before
    b.unlink()
    assert fingerprint(tmp_path) != before
    b.write_bytes(b"SYNTHETIC-B")
    assert fingerprint(tmp_path) == before  # creation/iteration order irrelevant
    c = directory / "c.parquet"
    c.write_bytes(b"SYNTHETIC-C")
    assert fingerprint(tmp_path) != before
