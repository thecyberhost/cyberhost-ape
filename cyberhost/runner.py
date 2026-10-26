"""Launch an installed tool with the bundled runtimes.

Resolves the right launch strategy from a tool's install method:
  * jar      → bundled java -jar <home>/<entry>
  * pip      → the console script inside the tool's isolated venv
  * script   → bundled python <home>/<repo>/<entry>
  * archive  → the native executable from the tool's bin list
  * docker   → docker run <image>
Everything runs with `subprocess_env()` so the bundled JDK/Python/adb win.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .banner import err, info
from .platform_utils import (
    exe,
    find_bundled,
    is_windows,
    java_bin,
    python_bin,
    subprocess_env,
    tool_home,
)
from .registry import Lockfile, Tool


class RunError(RuntimeError):
    pass


def _venv_script(tool: Tool) -> Path | None:
    home = tool_home(tool.name)
    scripts = home / "venv" / ("Scripts" if is_windows() else "bin")
    name = tool.entry or (tool.bin[0] if tool.bin else tool.name)
    for cand in (scripts / exe(name), scripts / name):
        if cand.exists():
            return cand
    return None


def _jar_path(tool: Tool) -> Path | None:
    home = tool_home(tool.name)
    if tool.entry and (home / tool.entry).exists():
        return home / tool.entry
    jars = sorted(home.glob("*.jar"))
    return jars[0] if jars else None


def _native_exe(tool: Tool) -> str | None:
    for name in (tool.bin or [tool.name]):
        p = find_bundled(name)
        if p:
            return p
    # look directly inside the tool home tree
    home = tool_home(tool.name)
    if home.exists():
        for name in (tool.bin or [tool.name]):
            hits = list(home.glob("**/" + exe(name)))
            if hits:
                return str(hits[0])
    return None


def build_command(tool: Tool, args: list[str]) -> list[str]:
    """Return the argv to launch *tool* with *args* (no execution)."""
    method = tool.install
    if method == "jar":
        jar = _jar_path(tool)
        if not jar:
            raise RunError(f"{tool.name}: jar not found — run `install {tool.name}`")
        jb = java_bin()
        if not jb:
            raise RunError("no Java runtime (bundled JDK missing and none on PATH)")
        return [jb, "-jar", str(jar), *args]

    if method == "maven":
        jb = java_bin()
        if not jb:
            raise RunError("no Java runtime (bundled JDK missing and none on PATH)")
        home = tool_home(tool.name)
        if not list(home.glob("*.jar")):
            raise RunError(f"{tool.name}: jars not found — run `install {tool.name}`")
        # Pick the main class for the requested bin (first bin when run bare).
        which = tool.bin[0] if tool.bin else tool.name
        if args and args[0] in tool.launch:
            which, args = args[0], args[1:]
        main = tool.launch.get(which)
        if not main:
            raise RunError(f"{tool.name}: no main class configured for {which!r}")
        sep = ";" if is_windows() else ":"
        classpath = sep.join(str(p) for p in sorted(home.glob("*.jar")))
        return [jb, "-cp", classpath, main, *args]

    if method == "pip":
        script = _venv_script(tool)
        if script:
            return [str(script), *args]
        # fall back to running the module with bundled python
        return [python_bin(), "-m", tool.entry or tool.name, *args]

    if method == "script":
        home = tool_home(tool.name)
        entry = None
        if tool.entry:
            hits = list(home.glob("**/" + tool.entry))
            entry = hits[0] if hits else None
        if not entry:
            raise RunError(f"{tool.name}: entry script not found — run `install {tool.name}`")
        return [python_bin(), str(entry), *args]

    if method == "docker":
        image = tool.source.get("docker_image") or tool.source.get("image", tool.name)
        docker = shutil.which("docker")
        if not docker:
            raise RunError("docker not found")
        return [docker, "run", "--rm", "-it", image, *args]

    # archive / github_release / url → native executable
    native = _native_exe(tool)
    if not native:
        raise RunError(f"{tool.name}: executable not found — run `install {tool.name}`")
    return [native, *args]


def run(tool: Tool, args: list[str], *, lock: Lockfile | None = None,
        check: bool = False) -> int:
    lock = lock or Lockfile()
    if not lock.is_installed(tool.name) and not tool_home(tool.name).exists():
        err(f"{tool.name} is not installed. Run:  install {tool.name}")
        return 127
    cmd = build_command(tool, args)
    info("exec: " + " ".join(cmd))
    try:
        cp = subprocess.run(cmd, env=subprocess_env(), check=check)
        return cp.returncode
    except FileNotFoundError as e:
        raise RunError(str(e)) from e
