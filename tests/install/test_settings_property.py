"""The host owns its settings: they are never created, overwritten or removed."""

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from install_helpers import load_installer, make_source

installer = load_installer()

contents = st.binary(max_size=200)


@given(contents, contents)
def test_install_leaves_settings_byte_for_byte_unchanged(
    json_bytes: bytes, md_bytes: bytes
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        source = make_source(base / "source")
        host = base / "host"
        (host / ".claude").mkdir(parents=True)
        (host / ".claude/surface.json").write_bytes(json_bytes)
        (host / ".claude/surface.md").write_bytes(md_bytes)

        assert installer.main([str(host)], source) == 0
        assert installer.main([str(host)], source) == 0
        installer.main(["--check", str(host)], source)

        assert (host / ".claude/surface.json").read_bytes() == json_bytes
        assert (host / ".claude/surface.md").read_bytes() == md_bytes


@given(contents)
def test_a_missing_settings_file_stays_missing(md_bytes: bytes) -> None:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        source = make_source(base / "source")
        host = base / "host"
        (host / ".claude").mkdir(parents=True)
        (host / ".claude/surface.md").write_bytes(md_bytes)

        assert installer.main([str(host)], source) == 0

        assert (host / ".claude/surface.md").read_bytes() == md_bytes
        assert not (host / ".claude/surface.json").exists()
