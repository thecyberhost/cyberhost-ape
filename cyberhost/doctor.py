"""Environment diagnostics — `doctor`.

Verifies the bundled runtimes and core tools are present and usable, and warns
about the classic footgun: a conflicting *system* adb server on a different
version, which can hijack device connections away from the bundled adb.
"""

from __future__ import annotations

import shutil
import subprocess

from .banner import console, err, info, ok, warn
from .platform_utils import (bundled_jdk, bundled_python, java_bin, subprocess_env, tools_dir)
from .registry import Lockfile, Manifest


def _probe(cmd: list[str]) -> str:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                            env=subprocess_env())
        return (cp.stdout or cp.stderr).strip().splitlines()[0] if (cp.stdout or cp.stderr) else ""
    except Exception as e:
        return f"error: {e}"


def run() -> bool:
    console.rule("[bold cyan]CyberHost APE — doctor")
    healthy = True

    # --- bundled runtimes ---------------------------------------------------
    jdk = bundled_jdk()
    if jdk:
        ok(f"bundled JDK: {jdk}")
        info("  " + _probe([java_bin(), "-version"]))
    else:
        warn("bundled JDK not found — jar tools will fall back to system Java if present")
        healthy = False

    py = bundled_python()
    if py:
        ok(f"bundled Python: {py}")
    else:
        warn("bundled Python not found — running under system interpreter (dev mode)")

    # --- adb (bundled first-class, system conflict check) -------------------
    bundled_adb = None
    for d in (tools_dir() / "platform-tools" / "platform-tools",):
        cand = d / ("adb.exe")
        if cand.exists():
            bundled_adb = str(cand)
    if bundled_adb:
        ok(f"bundled adb: {bundled_adb}")
        info("  " + _probe([bundled_adb, "version"]))
    else:
        warn("bundled adb not found — run `install platform-tools`")
        healthy = False

    system_adb = shutil.which("adb")
    if system_adb and (not bundled_adb or system_adb.lower() != bundled_adb.lower()):
        warn(f"a SYSTEM adb is also on PATH: {system_adb}")
        warn("  conflicting adb servers can hijack device connections.")
        info("  CyberHost always invokes the bundled adb; if `devices` misbehaves, run "
             "`adb kill-server` once to reset the shared server.")

    # --- core tool install status ------------------------------------------
    man = Manifest.load()
    lock = Lockfile()
    missing = [t.name for t in man.core() if not lock.is_installed(t.name)]
    if missing:
        warn(f"core tools not yet installed: {', '.join(missing)}")
        info("  (expected in a freshly-cloned dev tree; the built ZIP ships them)")
    else:
        ok("all core tools installed")

    console.rule()
    if healthy:
        ok("core environment looks good")
    else:
        err("some components are missing — see warnings above")
    return healthy
