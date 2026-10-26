"""Manifest loads and every entry is well-formed."""

import pytest

from cyberhost.registry import Lockfile, Manifest, Tool

VALID_INSTALL = {"archive", "github_release", "jar", "pip", "npm", "script",
                 "docker", "google", "binary", "maven"}
VALID_SOURCE = {"github", "google", "pypi", "npm", "url", "maven"}


@pytest.fixture(scope="module")
def man():
    return Manifest.load()


def test_manifest_loads_tools(man):
    assert len(man.tools) >= 25
    names = [t.name for t in man.tools]
    assert len(names) == len(set(names)), "tool names must be unique"


def test_core_and_ondemand_split(man):
    # Check the `core` flag directly (platform-agnostic): man.core() is filtered
    # by the host OS, and several core tools are Windows-only in the manifest.
    for expected in ("platform-tools", "jadx", "apktool", "frida-tools", "mitmproxy"):
        t = man.get(expected)
        assert t is not None and t.core, f"{expected} should be core"
    # spec: these are on-demand (not core)
    for ondemand in ("mobsf", "ghidra", "nmap", "drozer"):
        t = man.get(ondemand)
        assert t is not None and not t.core, f"{ondemand} should be on-demand"


def test_core_available_on_windows(man):
    """On the Windows-first target, the key core tools resolve for the platform."""
    core_win = {t.name for t in man.core("windows")}
    for expected in ("platform-tools", "jadx", "apktool", "frida-tools", "mitmproxy"):
        assert expected in core_win


def test_every_tool_wellformed(man):
    for t in man.tools:
        assert t.name and isinstance(t.name, str)
        assert t.description, f"{t.name} missing description"
        assert t.install in VALID_INSTALL, f"{t.name} bad install {t.install}"
        assert t.source.get("type") in VALID_SOURCE, f"{t.name} bad source type"
        assert t.platforms, f"{t.name} has no platforms"


def test_github_sources_have_repo(man):
    for t in man.tools:
        if t.source.get("type") == "github":
            assert "repo" in t.source, f"{t.name} github source needs a repo"


def test_platform_filtering(man):
    win = man.for_platform("windows")
    assert all(t.supports("windows") for t in win)
    # python is windows-only in the manifest
    py = man.get("python")
    assert py.supports("windows")


def test_tool_from_dict_ignores_unknown_keys():
    t = Tool.from_dict({"name": "x", "description": "d", "bogus_field": 1})
    assert t.name == "x" and t.description == "d"


def test_lockfile_roundtrip(tmp_home):
    lock = Lockfile()
    assert not lock.is_installed("jadx")
    lock.record("jadx", version="1.5.6", url="http://x", install="archive")
    lock.save()
    reloaded = Lockfile()
    assert reloaded.is_installed("jadx")
    assert reloaded.installed_version("jadx") == "1.5.6"
    reloaded.remove("jadx")
    reloaded.save()
    assert not Lockfile().is_installed("jadx")
