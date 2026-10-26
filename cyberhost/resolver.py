"""Always-latest resolution of versions and official download URLs.

Each manifest entry declares a *source* describing where the canonical latest
build lives. At build time and again on every `cyberhost update`, the resolver
re-queries the upstream of record (GitHub Releases, PyPI, Google's Android
repository) so versions are never hardcoded-stale. If the network is
unavailable it falls back to the manifest/lockfile snapshot and says so.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Any

from .platform_utils import current_arch, current_os
from .registry import Tool

_UA = {"User-Agent": "CyberHost-APE/0.1 (+https://github.com/cyberhost/cyberhost-ape)"}
_TIMEOUT = 30

# Google serves an always-latest convenience archive for platform-tools.
_GOOGLE_OS = {"windows": "windows", "macos": "darwin", "linux": "linux"}
_GOOGLE_REPO_XML = "https://dl.google.com/android/repository/repository2-3.xml"


@dataclass
class Resolved:
    version: str
    url: str
    sha256: str = ""
    sha1: str = ""
    source: str = ""
    resolved_online: bool = True


class ResolutionError(RuntimeError):
    pass


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={**_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310 (trusted hosts)
        return json.loads(r.read().decode("utf-8"))


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310
        return r.read().decode("utf-8", "replace")


def _subst(pattern: str, version: str = "") -> str:
    return (pattern
            .replace("{version}", version.lstrip("vV"))
            .replace("{os}", current_os())
            .replace("{arch}", current_arch())
            .replace("{goos}", _GOOGLE_OS.get(current_os(), current_os())))


# ---------------------------------------------------------------------------
# Per-source resolvers
# ---------------------------------------------------------------------------

def _resolve_github(tool: Tool) -> Resolved:
    repo = tool.source["repo"]
    data = _get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    version = (data.get("tag_name") or "").lstrip("vV") or data.get("name", "")
    assets = data.get("assets", [])
    # Some projects tag releases on GitHub but host the binaries on their own
    # CDN (e.g. mitmproxy). `url_template` builds the official URL from the tag.
    template = tool.source.get("url_template")
    if template:
        return Resolved(version=version, url=_subst(template, version), source="github")
    pattern = tool.source.get("asset_pattern")
    url = ""
    if pattern:
        rx = re.compile(_subst(pattern))
        for a in assets:
            if rx.search(a["name"]):
                url = a["browser_download_url"]
                break
        if not url:
            raise ResolutionError(
                f"{tool.name}: no release asset matched /{rx.pattern}/ "
                f"(latest tag {version!r})")
    else:
        # source archive of the tagged release
        url = data.get("tarball_url") or data.get("zipball_url", "")
    return Resolved(version=version, url=url, source="github")


def _resolve_pypi(tool: Tool) -> Resolved:
    pkg = tool.source.get("package", tool.name)
    data = _get_json(f"https://pypi.org/pypi/{pkg}/json")
    version = data["info"]["version"]
    # pip installs resolve their own wheels; url is informational here.
    url = f"https://pypi.org/project/{pkg}/{version}/"
    return Resolved(version=version, url=url, source="pypi")


def _resolve_google(tool: Tool) -> Resolved:
    product = tool.source.get("google_product", tool.name)
    if product == "platform-tools":
        goos = _GOOGLE_OS.get(current_os(), "linux")
        url = f"https://dl.google.com/android/repository/platform-tools-latest-{goos}.zip"
        # Latest convenience URL carries no version in the name; read it from
        # the live source.properties after download, so report "latest" here.
        return Resolved(version=tool.version or "latest", url=url, source="google")
    if product == "build-tools":
        return _resolve_google_build_tools(tool)
    raise ResolutionError(f"unknown google product {product!r}")


def _resolve_google_build_tools(tool: Tool) -> Resolved:
    """Parse Google's repository XML for the newest build-tools revision.

    The real archive filename + SHA1 live in the XML per host-os, so we read
    them instead of guessing (the historical ``build-tools_rNN-os.zip`` scheme
    no longer matches current releases).
    """
    xml = _get_text(_GOOGLE_REPO_XML)
    revs = sorted(
        set(re.findall(r"build-tools;(\d+\.\d+\.\d+)", xml)),
        key=lambda s: tuple(int(x) for x in s.split(".")),
    )
    if not revs:
        raise ResolutionError("could not find build-tools revisions in repo XML")
    latest = revs[-1]
    # Isolate this revision's <remotePackage> block, then its per-OS archive.
    start = xml.find(f'path="build-tools;{latest}"')
    block = xml[start:xml.find("</remotePackage>", start)]
    goos = {"windows": "windows", "macos": "macosx", "linux": "linux"}[current_os()]
    url = sha1 = ""
    for archive in re.findall(r"<archive>.*?</archive>", block, re.S):
        if f"<host-os>{goos}</host-os>" in archive:
            u = re.search(r"<url>(.*?)</url>", archive)
            s = re.search(r'<checksum type="sha1">(.*?)</checksum>', archive)
            if u:
                url = "https://dl.google.com/android/repository/" + u.group(1)
                sha1 = s.group(1) if s else ""
            break
    if not url:
        raise ResolutionError(f"no build-tools archive for host-os {goos}")
    return Resolved(version=latest, url=url, sha1=sha1, source="google")


def _resolve_maven(tool: Tool) -> Resolved:
    """Resolve a Maven-hosted tool from the repository's own metadata.

    The binary host is the source of truth for what's actually available (a
    GitHub tag may exist with no published artifact), so we read the primary
    artifact's maven-metadata.xml and take its <release> version. Used for tools
    (e.g. smali/baksmali) distributed only as Maven artifacts with no fat jar;
    the installer fetches the dependency jars too.
    """
    src = tool.source
    base = src.get("base", "https://repo1.maven.org/maven2").rstrip("/")
    primary = src.get("artifacts", [""])[0]  # group:artifact
    group, _, artifact = primary.partition(":")
    gpath = group.replace(".", "/")
    meta = _get_text(f"{base}/{gpath}/{artifact}/maven-metadata.xml")
    m = re.search(r"<release>(.*?)</release>", meta) or re.search(r"<latest>(.*?)</latest>", meta)
    if not m:
        vers = re.findall(r"<version>(.*?)</version>", meta)
        if not vers:
            raise ResolutionError(f"{tool.name}: no versions in maven-metadata")
        version = vers[-1]
    else:
        version = m.group(1)
    url = f"{base}/{gpath}/{artifact}/{version}/{artifact}-{version}.jar"
    return Resolved(version=version, url=url, source="maven")


def _resolve_npm(tool: Tool) -> Resolved:
    pkg = tool.source.get("package", tool.name)
    data = _get_json(f"https://registry.npmjs.org/{pkg}/latest")
    version = data["version"]
    url = f"https://www.npmjs.com/package/{pkg}/v/{version}"
    return Resolved(version=version, url=url, source="npm")


def _resolve_static(tool: Tool) -> Resolved:
    url = _subst(tool.source.get("url", ""))
    if not url:
        raise ResolutionError(f"{tool.name}: static source has no url")
    return Resolved(version=tool.version or "static", url=url, source="url")


_RESOLVERS = {
    "github": _resolve_github,
    "pypi": _resolve_pypi,
    "npm": _resolve_npm,
    "google": _resolve_google,
    "maven": _resolve_maven,
    "url": _resolve_static,
}


def resolve(tool: Tool, *, offline_ok: bool = True) -> Resolved:
    """Resolve the current latest version + official URL for *tool*.

    On network failure, falls back to the manifest snapshot (so the toolkit is
    still usable offline) with ``resolved_online=False``.
    """
    stype = tool.source.get("type", "github")
    fn = _RESOLVERS.get(stype)
    if fn is None:
        raise ResolutionError(f"{tool.name}: unknown source type {stype!r}")
    try:
        return fn(tool)
    except ResolutionError:
        raise
    except Exception as e:  # network / parse failure
        if offline_ok and (tool.version or tool.source.get("url")):
            return Resolved(
                version=tool.version or "snapshot",
                url=_subst(tool.source.get("url", "")),
                source=stype,
                resolved_online=False,
            )
        raise ResolutionError(f"{tool.name}: resolution failed ({e})") from e
