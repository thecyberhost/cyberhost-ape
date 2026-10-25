"""Platform detection and portable path resolution.

Everything CyberHost installs lives under the toolkit root (the directory that
contains this package's parent), so the whole thing is relocatable: move the
folder, and every path still resolves relative to it. Nothing is written to
system-wide locations.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# OS / architecture identity
# ---------------------------------------------------------------------------

#: Canonical OS token used throughout the manifest: "windows" | "macos" | "linux".
def current_os() -> str:
    p = sys.platform
    if p.startswith("win"):
        return "windows"
    if p == "darwin":
        return "macos"
    return "linux"


#: Canonical architecture token: "x86_64" | "arm64" | "x86".
def current_arch() -> str:
    m = platform.machine().lower()
    if m in ("amd64", "x86_64", "x64"):
        return "x86_64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("i386", "i686", "x86"):
        return "x86"
    return m or "x86_64"


def is_windows() -> bool:
    return current_os() == "windows"


def exe(name: str) -> str:
    """Return the platform-appropriate executable filename for *name*."""
    return f"{name}.exe" if is_windows() else name


# ---------------------------------------------------------------------------
# Android ABI mapping (for frida-server and other device-side binaries)
# ---------------------------------------------------------------------------

#: Map an Android ABI (from `getprop ro.product.cpu.abi`) to a release token.
ANDROID_ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64", "x86")


def android_abi_to_frida_arch(abi: str) -> str:
    return {
        "arm64-v8a": "arm64",
        "armeabi-v7a": "arm",
        "x86_64": "x86_64",
        "x86": "x86",
    }.get(abi.strip(), "arm64")


# ---------------------------------------------------------------------------
# Toolkit root + well-known directories (all relocatable)
# ---------------------------------------------------------------------------

def toolkit_root() -> Path:
    """The folder CyberHost runs from.

    Overridable with $CYBERHOST_HOME for custom layouts; otherwise it is the
    parent of the installed `cyberhost` package.
    """
    env = os.environ.get("CYBERHOST_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def tools_dir() -> Path:
    return toolkit_root() / "tools"


def targets_dir() -> Path:
    return toolkit_root() / "targets"


def scripts_dir() -> Path:
    """Bundled, read-only Frida script library (ships inside the package)."""
    return Path(__file__).resolve().parent / "scripts"


def cache_dir() -> Path:
    return toolkit_root() / ".cache"


def tool_home(name: str) -> Path:
    """Isolated install directory for a single tool (updates stay contained)."""
    return tools_dir() / name


def runtime_dir() -> Path:
    """Where the bundled portable JDK and Python live."""
    return toolkit_root() / "runtime"


def bundled_jdk() -> Path | None:
    """Locate the bundled portable JDK home (contains bin/java)."""
    base = runtime_dir() / "jdk"
    if not base.exists():
        return None
    # The JDK archive extracts to a versioned subdir; find the one with bin/java.
    candidates = [base, *sorted(base.glob("*"))]
    for c in candidates:
        if (c / "bin" / exe("java")).exists():
            return c
        # macOS JDKs nest under Contents/Home
        mac = c / "Contents" / "Home"
        if (mac / "bin" / exe("java")).exists():
            return mac
    return None


def bundled_python() -> Path | None:
    """Locate the bundled portable Python interpreter."""
    base = runtime_dir() / "python"
    if not base.exists():
        return None
    for cand in (base / exe("python"), base / "bin" / exe("python"),
                 base / "bin" / "python3"):
        if cand.exists():
            return cand
    found = list(base.glob("**/" + exe("python")))
    return found[0] if found else None


def java_bin() -> str | None:
    jdk = bundled_jdk()
    if jdk:
        return str(jdk / "bin" / exe("java"))
    return shutil.which("java")


def python_bin() -> str:
    """The interpreter CyberHost itself runs under (bundled when packaged)."""
    bp = bundled_python()
    return str(bp) if bp else sys.executable


def data_file(name: str) -> Path:
    """A file shipped inside the package's data/ directory."""
    return Path(__file__).resolve().parent / "data" / name


def ensure_dirs() -> None:
    for d in (tools_dir(), targets_dir(), cache_dir()):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# PATH assembly — bundled binaries always win over system copies
# ---------------------------------------------------------------------------

def bundled_bin_dirs() -> list[Path]:
    """Directories to prepend to PATH so bundled tools shadow system ones.

    Bundled platform-tools (adb/fastboot) is deliberately first-class here.
    """
    dirs: list[Path] = []
    pt = tool_home("platform-tools") / "platform-tools"
    if pt.exists():
        dirs.append(pt)
    if not tools_dir().exists():
        return dirs
    venv_bin = "Scripts" if is_windows() else "bin"
    # Each tool exposes binaries at its root, in a bin/, or inside its venv.
    for t in sorted(tools_dir().glob("*")):
        if not t.is_dir():
            continue
        for cand in (t, t / "bin", t / "venv" / venv_bin):
            if cand.is_dir() and cand not in dirs:
                dirs.append(cand)
    return dirs


def subprocess_env() -> dict[str, str]:
    """An environment dict with bundled runtimes + binaries prepended to PATH.

    Bundled JDK and Python are put ahead of system copies, and JAVA_HOME is set,
    so every tool CyberHost launches uses the toolkit's own runtimes.
    """
    env = dict(os.environ)
    sep = os.pathsep
    dirs = [str(d) for d in bundled_bin_dirs()]
    jdk = bundled_jdk()
    if jdk:
        env["JAVA_HOME"] = str(jdk)
        dirs.insert(0, str(jdk / "bin"))
    bp = bundled_python()
    if bp:
        dirs.insert(0, str(bp.parent))
    if dirs:
        env["PATH"] = sep.join(dirs) + sep + env.get("PATH", "")
    return env


def find_bundled(name: str) -> str | None:
    """Locate *name* preferring bundled bin dirs, falling back to system PATH."""
    target = exe(name)
    for d in bundled_bin_dirs():
        cand = d / target
        if cand.exists():
            return str(cand)
    return shutil.which(name)
