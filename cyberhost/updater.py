"""Download → verify → atomic-swap install/update engine.

Each tool installs into its own isolated directory under ``tools/<name>`` so a
failed or in-progress update can never corrupt a sibling. Installs are staged
in a temporary location and swapped in atomically; the previous version is kept
as ``<name>.old`` until the swap succeeds, then removed.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .banner import info, ok, step, warn
from .platform_utils import is_windows, subprocess_env, tool_home
from .registry import Lockfile, Tool
from .resolver import Resolved, resolve

_UA = {"User-Agent": "CyberHost-APE/0.1"}


class InstallError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without the network)
# ---------------------------------------------------------------------------

def _hash_file(path: Path, algo: str, chunk: int = 1 << 20) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    return _hash_file(path, "sha256", chunk)


def _verify(archive: Path, res) -> None:
    """Verify whichever checksum the resolver supplied (sha256 or sha1)."""
    for algo in ("sha256", "sha1"):
        expected = getattr(res, algo, "")
        if expected:
            actual = _hash_file(archive, algo)
            if actual.lower() != expected.lower():
                raise InstallError(
                    f"checksum mismatch ({algo}): expected {expected}, got {actual}")


def is_archive(url: str) -> bool:
    low = url.lower().split("?", 1)[0]
    return low.endswith((".zip", ".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar"))


def _extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    # Prefer the extension, but fall back to content sniffing so that
    # extension-less CDN/redirect URLs (e.g. the Adoptium API) still work.
    is_zip = name.endswith(".zip") or zipfile.is_zipfile(archive)
    if is_zip:
        with zipfile.ZipFile(archive) as z:
            _safe_extract_zip(z, dest)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive, "r:*") as t:
            _safe_extract_tar(t, dest)
    else:
        raise InstallError(f"unrecognized archive format: {archive.name}")


def _safe_extract_zip(z: zipfile.ZipFile, dest: Path) -> None:
    root = dest.resolve()
    for member in z.namelist():
        target = (dest / member).resolve()
        if not str(target).startswith(str(root)):
            raise InstallError(f"unsafe path in archive: {member}")
    z.extractall(dest)


def _safe_extract_tar(t: tarfile.TarFile, dest: Path) -> None:
    root = dest.resolve()
    for member in t.getmembers():
        target = (dest / member.name).resolve()
        if not str(target).startswith(str(root)):
            raise InstallError(f"unsafe path in archive: {member.name}")
    # Python 3.12+ supports a data filter; use it when available.
    try:
        t.extractall(dest, filter="data")  # type: ignore[call-arg]
    except TypeError:
        t.extractall(dest)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download(url: str, dest: Path, *, quiet: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=_UA)
    if not quiet:
        info(f"downloading {url}")
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        total = int(r.headers.get("Content-Length", 0))
        read = 0
        with open(dest, "wb") as f:
            while True:
                buf = r.read(1 << 16)
                if not buf:
                    break
                f.write(buf)
                read += len(buf)
                if not quiet and total:
                    pct = read * 100 // total
                    print(f"\r  {pct:3d}%  {read >> 20} MiB", end="", flush=True)
        if not quiet and total:
            print()
    return dest


# ---------------------------------------------------------------------------
# Install methods
# ---------------------------------------------------------------------------

def _atomic_replace(staged: Path, final: Path) -> None:
    """Move *staged* into *final*, preserving the old copy until success."""
    old = final.with_name(final.name + ".old")
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    if final.exists():
        final.rename(old)
    try:
        staged.rename(final)
    except OSError:
        shutil.move(str(staged), str(final))
    shutil.rmtree(old, ignore_errors=True)


def _install_archive(tool: Tool, res: Resolved, tmp: Path) -> None:
    archive = download(res.url, tmp / Path(res.url.split("?", 1)[0]).name)
    _verify(archive, res)
    staged = tmp / "staged"
    _extract(archive, staged)
    _atomic_replace(staged, tool_home(tool.name))


def _install_jar(tool: Tool, res: Resolved, tmp: Path) -> None:
    jar = download(res.url, tmp / Path(res.url.split("?", 1)[0]).name)
    staged = tmp / "staged"
    staged.mkdir(parents=True, exist_ok=True)
    shutil.copy2(jar, staged / jar.name)
    # launcher shim so `cyberhost run <tool>` can exec it
    (staged / "jarname.txt").write_text(jar.name, encoding="utf-8")
    _atomic_replace(staged, tool_home(tool.name))


def _install_pip(tool: Tool, res: Resolved, tmp: Path, *, cache_wheels: bool = False) -> None:
    """Install a Python tool into its own isolated venv (scripts on PATH).

    The venv is created with the *bundled* interpreter when one is present (so
    a packaged build's venvs are relocatable via `repair`), else the running
    interpreter. With ``cache_wheels`` the exact wheels are also downloaded into
    ``<home>/wheels`` so the tool can be rebuilt offline after the kit is moved.
    """
    from .platform_utils import bundled_python, python_bin
    home = tool_home(tool.name)
    base_python = str(bundled_python()) if bundled_python() else python_bin()
    staged = tmp / "venv"
    subprocess.run([base_python, "-m", "venv", "--copies", str(staged)], check=True)
    py = staged / ("Scripts" if is_windows() else "bin") / ("python.exe" if is_windows() else "python")
    pkg = tool.source.get("package", tool.name)
    spec = f"{pkg}=={res.version}" if res.version and res.version not in ("latest", "snapshot") else pkg
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"],
                   check=True, env=subprocess_env())
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", spec],
                   check=True, env=subprocess_env())
    if cache_wheels:
        wheels = tmp / "wheels"
        subprocess.run([str(py), "-m", "pip", "download", spec, "-d", str(wheels)], check=False)
    _atomic_replace(staged, home / "venv")
    if cache_wheels and (tmp / "wheels").exists():
        _atomic_replace(tmp / "wheels", home / "wheels")


def _install_binary(tool: Tool, res: Resolved, tmp: Path) -> None:
    """Install a single standalone executable (not an archive)."""
    from .platform_utils import exe
    name = exe(tool.bin[0]) if tool.bin else Path(res.url.split("?", 1)[0]).name
    staged = tmp / "staged"
    staged.mkdir(parents=True, exist_ok=True)
    download(res.url, staged / name)
    try:  # best-effort executable bit on POSIX
        (staged / name).chmod(0o755)
    except Exception:
        pass
    _atomic_replace(staged, tool_home(tool.name))


def _maven_urls(group: str, artifact: str, version: str, bases: list[str], ext: str):
    gpath = group.replace(".", "/")
    name = f"{artifact}-{version}.{ext}"
    return [(f"{b}/{gpath}/{artifact}/{version}/{name}", name) for b in bases]


def _maven_fetch(group: str, artifact: str, version: str, bases: list[str],
                 ext: str, dest: Path) -> Path | None:
    """Download an artifact's jar/pom, trying each repo base in turn."""
    for url, name in _maven_urls(group, artifact, version, bases, ext):
        try:
            return download(url, dest / name, quiet=True)
        except Exception:
            continue
    return None


def _install_maven(tool: Tool, res: Resolved, tmp: Path) -> None:
    """Install a Maven-hosted tool as a classpath bundle (jars + their deps).

    For tools with no runnable fat jar (e.g. smali/baksmali): download the
    listed artifacts at the resolved version, then read each one's POM and fetch
    its compile/runtime dependencies (correct versions, no hardcoding) so the
    runner can launch a main class with the full classpath.
    """
    import re
    src = tool.source
    bases = [src.get("base", "https://repo1.maven.org/maven2").rstrip("/"),
             "https://repo1.maven.org/maven2"]
    staged = tmp / "staged"
    staged.mkdir(parents=True, exist_ok=True)

    own = {c.split(":")[1] for c in src.get("artifacts", [])}
    seen: set[tuple] = set()
    deps: list[tuple] = []

    # 1. primary artifacts + collect their POM dependencies
    for coord in src.get("artifacts", []):
        group, artifact = coord.split(":")
        _maven_fetch(group, artifact, res.version, bases, "jar", staged)
        pom = _maven_fetch(group, artifact, res.version, bases, "pom", tmp)
        if not pom:
            continue
        text = pom.read_text(encoding="utf-8", errors="replace")
        for block in re.findall(r"<dependency>(.*?)</dependency>", text, re.S):
            g = re.search(r"<groupId>(.*?)</groupId>", block)
            a = re.search(r"<artifactId>(.*?)</artifactId>", block)
            v = re.search(r"<version>(.*?)</version>", block)
            scope = re.search(r"<scope>(.*?)</scope>", block)
            if not (g and a and v):
                continue
            if scope and scope.group(1) in ("test", "provided", "system"):
                continue
            if a.group(1) in own or "${" in v.group(1):
                continue  # siblings handled; skip unresolved property versions
            key = (g.group(1), a.group(1), v.group(1))
            if key not in seen:
                seen.add(key)
                deps.append(key)

    # 2. fetch external dependency jars at the versions their POMs declared
    for group, artifact, version in deps:
        _maven_fetch(group, artifact, version, bases, "jar", staged)

    # drop stray .pom files; keep only jars
    for p in staged.glob("*.pom"):
        p.unlink(missing_ok=True)
    _atomic_replace(staged, tool_home(tool.name))


def _install_docker(tool: Tool, res: Resolved, tmp: Path) -> None:
    image = tool.source.get("image", tool.name)
    docker = shutil.which("docker")
    if not docker:
        raise InstallError(f"{tool.name}: docker not found; install Docker to use this backend")
    subprocess.run([docker, "pull", image], check=True)
    home = tool_home(tool.name)
    home.mkdir(parents=True, exist_ok=True)
    (home / "image.txt").write_text(image, encoding="utf-8")


_INSTALLERS = {
    "archive": _install_archive,
    "github_release": _install_archive,  # asset is an archive
    "jar": _install_jar,
    "pip": _install_pip,
    "binary": _install_binary,
    "maven": _install_maven,
    "docker": _install_docker,
}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def install_tool(tool: Tool, *, lock: Lockfile | None = None,
                 res: Resolved | None = None, force: bool = False,
                 cache_wheels: bool = False) -> Resolved:
    """Resolve (if needed), install, and record *tool* in the lockfile."""
    lock = lock or Lockfile()
    res = res or resolve(tool)
    if not res.resolved_online:
        warn(f"{tool.name}: using offline snapshot {res.version} (could not reach upstream)")

    method = tool.install if tool.install in _INSTALLERS else (
        "archive" if is_archive(res.url) else "github_release")
    installer = _INSTALLERS.get(method)
    if installer is None:
        raise InstallError(f"{tool.name}: no installer for method {method!r}")

    with tempfile.TemporaryDirectory(prefix=f"cyberhost-{tool.name}-") as td:
        if method == "pip":
            _install_pip(tool, res, Path(td), cache_wheels=cache_wheels)
        else:
            installer(tool, res, Path(td))

    # Google archives don't carry a version in the URL; read the real revision
    # from the SDK's source.properties so the lockfile records a true version.
    if res.version in ("latest", "static", "snapshot", ""):
        rev = _read_sdk_revision(tool_home(tool.name))
        if rev:
            res.version = rev

    sha = ""
    lock.record(tool.name, version=res.version, url=res.url, sha256=sha, install=method)
    lock.save()
    _write_marker(tool, res)
    ok(f"{tool.name} {res.version} installed")
    return res


def _read_sdk_revision(home: Path) -> str:
    """Read Pkg.Revision from an Android SDK component's source.properties."""
    for props in home.glob("**/source.properties"):
        try:
            for line in props.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Pkg.Revision="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            continue
    return ""


def _write_marker(tool: Tool, res: Resolved) -> None:
    import json
    home = tool_home(tool.name)
    home.mkdir(parents=True, exist_ok=True)
    (home / ".cyberhost_installed.json").write_text(
        json.dumps({"name": tool.name, "version": res.version, "url": res.url}, indent=2),
        encoding="utf-8")


def self_update() -> bool:
    """Update CyberHost APE itself and refresh resolver metadata.

    Pulls the latest release of the framework from its own repository. The
    manifest (tools.yaml) ships inside that release, so refreshing the framework
    is also how the resolver metadata (each tool → official-source mapping) stays
    current if a tool relocates its downloads.
    """
    from . import __version__
    info(f"CyberHost APE is at v{__version__}")
    try:
        data = _self_latest()
    except Exception as e:
        warn(f"could not check for updates: {e}")
        return False
    latest = data.get("tag_name", "").lstrip("vV")
    if latest and latest != __version__:
        ok(f"a newer release is available: v{latest}")
        asset = next((a["browser_download_url"] for a in data.get("assets", [])
                      if a["name"].endswith(".zip")), data.get("zipball_url"))
        info(f"download: {asset}")
        step("unzip over your current folder (your ./tools and ./targets are preserved)")
    else:
        ok("CyberHost APE is up to date; resolver metadata is current")
    return True


def _self_latest():
    import json
    req = urllib.request.Request(
        "https://api.github.com/repos/cyberlust/cyberhost-ape/releases/latest",
        headers={"User-Agent": "CyberHost-APE/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return json.loads(r.read().decode())


def repair_pip_tool(tool: Tool) -> bool:
    """Rebuild a pip tool's venv offline from its cached wheels.

    Used after the toolkit is unzipped to a new path (venvs embed absolute
    paths). Needs no network because the wheels were cached at build time.
    """
    home = tool_home(tool.name)
    wheels = home / "wheels"
    if not wheels.exists():
        return False
    from .platform_utils import bundled_python, python_bin
    base_python = str(bundled_python()) if bundled_python() else python_bin()
    with tempfile.TemporaryDirectory(prefix=f"cyberhost-repair-{tool.name}-") as td:
        staged = Path(td) / "venv"
        subprocess.run([base_python, "-m", "venv", "--copies", str(staged)], check=True)
        py = staged / ("Scripts" if is_windows() else "bin") / (
            "python.exe" if is_windows() else "python")
        pkg = tool.source.get("package", tool.name)
        subprocess.run([str(py), "-m", "pip", "install", "--no-index",
                        "--find-links", str(wheels), pkg], check=True, env=subprocess_env())
        _atomic_replace(staged, home / "venv")
    ok(f"{tool.name} venv rebuilt for this location")
    return True


def install_path_marker() -> Path:
    from .platform_utils import toolkit_root
    return toolkit_root() / "tools" / ".install_path"


def check_relocated() -> bool:
    """True if the kit was moved since the last build/bootstrap."""
    from .platform_utils import toolkit_root
    marker = install_path_marker()
    current = str(toolkit_root())
    if not marker.exists():
        return False
    return marker.read_text(encoding="utf-8").strip() != current


def record_install_path() -> None:
    from .platform_utils import toolkit_root
    m = install_path_marker()
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(str(toolkit_root()), encoding="utf-8")


def bootstrap(lock: Lockfile | None = None) -> bool:
    """Repair relocated pip venvs offline; no-op if paths are unchanged."""
    from .registry import Manifest
    if not check_relocated():
        return True
    warn("toolkit folder moved since build — rebuilding Python tool environments…")
    lock = lock or Lockfile()
    man = Manifest.load()
    rc = True
    for t in man.tools:
        if t.install == "pip" and (tool_home(t.name) / "wheels").exists():
            try:
                rc &= repair_pip_tool(t)
            except Exception as e:
                warn(f"{t.name}: repair failed ({e})")
                rc = False
    record_install_path()
    return rc


def update_tool(tool: Tool, *, lock: Lockfile | None = None) -> tuple[bool, Resolved]:
    """Re-resolve latest; install only if newer than the locked version.

    Returns (changed, resolved).
    """
    lock = lock or Lockfile()
    res = resolve(tool)
    current = lock.installed_version(tool.name)
    if current == res.version and tool_home(tool.name).exists():
        info(f"{tool.name} already at latest ({res.version})")
        return False, res
    install_tool(tool, lock=lock, res=res)
    return True, res
