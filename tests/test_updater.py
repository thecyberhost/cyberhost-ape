"""Update-engine internals: checksums, safe extraction, atomic swap, revisions."""

import zipfile
from pathlib import Path

import pytest

from cyberhost import updater
from cyberhost.updater import (InstallError, _atomic_replace, _extract,
                               _read_sdk_revision, is_archive, sha256_file)


def test_sha256_file(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    # sha256("hello")
    assert sha256_file(f) == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")


@pytest.mark.parametrize("url,expected", [
    ("http://x/a.zip", True),
    ("http://x/a.tar.gz", True),
    ("http://x/a.tgz", True),
    ("http://x/a.jar", False),
    ("http://x/file.exe", False),
    ("http://x/a.zip?token=1", True),
])
def test_is_archive(url, expected):
    assert is_archive(url) is expected


def _make_zip(path: Path, entries: dict[str, str]):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)


def test_extract_zip(tmp_path):
    arc = tmp_path / "t.zip"
    _make_zip(arc, {"dir/hello.txt": "hi"})
    dest = tmp_path / "out"
    _extract(arc, dest)
    assert (dest / "dir" / "hello.txt").read_text() == "hi"


def test_extract_detects_zip_without_extension(tmp_path):
    arc = tmp_path / "noext"
    _make_zip(arc, {"a.txt": "x"})
    dest = tmp_path / "out"
    _extract(arc, dest)  # content sniffing
    assert (dest / "a.txt").exists()


def test_extract_rejects_zip_slip(tmp_path):
    arc = tmp_path / "evil.zip"
    with zipfile.ZipFile(arc, "w") as z:
        z.writestr("../../escape.txt", "pwned")
    with pytest.raises(InstallError):
        _extract(arc, tmp_path / "out")


def test_atomic_replace_preserves_then_swaps(tmp_path):
    final = tmp_path / "tool"
    final.mkdir()
    (final / "old.txt").write_text("old")
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "new.txt").write_text("new")
    _atomic_replace(staged, final)
    assert (final / "new.txt").exists()
    assert not (final / "old.txt").exists()
    assert not staged.exists()
    assert not final.with_name("tool.old").exists()


def test_verify_sha256_and_sha1(tmp_path):
    from cyberhost.resolver import Resolved
    from cyberhost.updater import _verify
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    sha256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    sha1 = "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
    _verify(f, Resolved(version="1", url="u", sha256=sha256))  # ok
    _verify(f, Resolved(version="1", url="u", sha1=sha1))      # ok
    with pytest.raises(InstallError):
        _verify(f, Resolved(version="1", url="u", sha256="00"))
    with pytest.raises(InstallError):
        _verify(f, Resolved(version="1", url="u", sha1="00"))


def test_read_sdk_revision(tmp_path):
    home = tmp_path / "platform-tools"
    (home / "platform-tools").mkdir(parents=True)
    (home / "platform-tools" / "source.properties").write_text(
        "Pkg.UserSrc=false\nPkg.Revision=37.0.1\n")
    assert _read_sdk_revision(home) == "37.0.1"


def test_update_tool_skips_when_current(tmp_home, monkeypatch):
    from cyberhost.registry import Lockfile, Tool
    from cyberhost.resolver import Resolved
    t = Tool(name="demo", install="archive",
             source={"type": "github", "repo": "a/b"})
    monkeypatch.setattr(updater, "resolve", lambda tool: Resolved(version="1.0", url="u"))
    lock = Lockfile()
    lock.record("demo", version="1.0")
    # make the tool home exist so it's considered installed
    (tmp_home / "tools" / "demo").mkdir(parents=True)
    changed, res = updater.update_tool(t, lock=lock)
    assert changed is False
    assert res.version == "1.0"
