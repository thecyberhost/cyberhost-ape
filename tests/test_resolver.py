"""Resolver resolves latest versions/URLs per source type (network mocked)."""

import pytest

from cyberhost import resolver
from cyberhost.registry import Tool
from cyberhost.resolver import ResolutionError, resolve


def test_subst_tokens():
    out = resolver._subst("x-{version}-{os}", version="v1.2.3")
    assert "1.2.3" in out
    assert resolver.current_os() in out


def test_github_asset_match(monkeypatch):
    monkeypatch.setattr(resolver, "_get_json", lambda url: {
        "tag_name": "v1.5.6",
        "assets": [
            {"name": "jadx-gui-1.5.6.zip", "browser_download_url": "http://x/gui.zip"},
            {"name": "jadx-1.5.6.zip", "browser_download_url": "http://x/jadx.zip"},
        ],
    })
    t = Tool(name="jadx", install="archive",
             source={"type": "github", "repo": "skylot/jadx",
                     "asset_pattern": r"jadx-[0-9].*\.zip$"})
    r = resolve(t)
    assert r.version == "1.5.6"
    assert r.url == "http://x/jadx.zip"
    assert r.resolved_online


def test_github_no_asset_match_raises(monkeypatch):
    monkeypatch.setattr(resolver, "_get_json", lambda url: {
        "tag_name": "v1.0", "assets": [{"name": "other.txt", "browser_download_url": "u"}]})
    t = Tool(name="x", source={"type": "github", "repo": "a/b",
                               "asset_pattern": r"nope\.zip$"})
    with pytest.raises(ResolutionError):
        resolve(t)


def test_github_url_template(monkeypatch):
    monkeypatch.setattr(resolver, "_get_json", lambda url: {"tag_name": "v12.3.0", "assets": []})
    t = Tool(name="mitmproxy", source={
        "type": "github", "repo": "mitmproxy/mitmproxy",
        "url_template": "https://downloads.mitmproxy.org/{version}/m-{version}.zip"})
    r = resolve(t)
    assert r.version == "12.3.0"
    assert r.url == "https://downloads.mitmproxy.org/12.3.0/m-12.3.0.zip"


def test_pypi(monkeypatch):
    monkeypatch.setattr(resolver, "_get_json", lambda url: {"info": {"version": "2.6.3"}})
    t = Tool(name="apkleaks", install="pip", source={"type": "pypi", "package": "apkleaks"})
    r = resolve(t)
    assert r.version == "2.6.3"


def test_npm(monkeypatch):
    monkeypatch.setattr(resolver, "_get_json", lambda url: {"version": "1.3.0"})
    t = Tool(name="apk-mitm", install="npm", source={"type": "npm", "package": "apk-mitm"})
    r = resolve(t)
    assert r.version == "1.3.0"


def test_google_platform_tools():
    t = Tool(name="platform-tools", install="archive",
             source={"type": "google", "google_product": "platform-tools"})
    r = resolve(t)
    assert "platform-tools-latest" in r.url


def test_offline_fallback(monkeypatch):
    def boom(url):
        raise OSError("no network")
    monkeypatch.setattr(resolver, "_get_json", boom)
    t = Tool(name="x", version="9.9.9",
             source={"type": "github", "repo": "a/b", "asset_pattern": r"x\.zip",
                     "url": "http://snap/x.zip"})
    r = resolve(t, offline_ok=True)
    assert r.resolved_online is False
    assert r.version == "9.9.9"


def test_maven_reads_release_from_metadata(monkeypatch):
    meta = ("<metadata><versioning><release>3.0.10</release>"
            "<latest>3.0.10</latest></versioning></metadata>")
    monkeypatch.setattr(resolver, "_get_text", lambda url: meta)
    t = Tool(name="smali", install="maven", source={
        "type": "maven", "base": "https://dl.google.com/android/maven2",
        "artifacts": ["com.android.tools.smali:smali-baksmali"]})
    r = resolve(t)
    assert r.version == "3.0.10"
    assert r.url.endswith("smali-baksmali/3.0.10/smali-baksmali-3.0.10.jar")


def test_build_tools_parses_url_and_sha1(monkeypatch):
    xml = """
    <remotePackage path="build-tools;37.0.0">
      <archives>
        <archive>
          <complete>
            <checksum type="sha1">deadbeef</checksum>
            <url>build-tools_r37_windows.zip</url>
          </complete>
          <host-os>windows</host-os>
        </archive>
        <archive>
          <complete><url>build-tools_r37_linux.zip</url></complete>
          <host-os>linux</host-os>
        </archive>
      </archives>
    </remotePackage>"""
    monkeypatch.setattr(resolver, "_get_text", lambda url: xml)
    monkeypatch.setattr(resolver, "current_os", lambda: "windows")
    t = Tool(name="build-tools", install="archive",
             source={"type": "google", "google_product": "build-tools"})
    r = resolve(t)
    assert r.version == "37.0.0"
    assert r.url.endswith("build-tools_r37_windows.zip")
    assert r.sha1 == "deadbeef"


def test_unknown_source_type():
    t = Tool(name="x", source={"type": "carrier-pigeon"})
    with pytest.raises(ResolutionError):
        resolve(t)
