#!/usr/bin/env python3
"""Assemble the CyberHost APE distributable and produce the Windows ZIP.

The build:
  1. stages the framework (package + launchers + docs + assets),
  2. installs the bundled runtimes (portable JDK + relocatable Python) at the
     CURRENT latest version resolved from each official source,
  3. installs the core tools offline-ready into ./tools/ (pip tools get their
     wheels cached for relocation),
  4. pre-bundles frida-server for every common Android ABI, and
  5. zips it all into dist/CyberHost-APE-<version>-windows.zip.

Nothing is hardcoded: every version/URL is resolved live at build time, so each
build is current. Run `python build.py --help` for options.

    python build.py                 # full build + zip (heavy: downloads GBs)
    python build.py --stage-only    # just the framework code/docs/launchers
    python build.py --skip-runtime  # tools only (reuse existing runtime)
    python build.py --tools jadx,apktool   # a subset, for testing
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE / "cyberhost"

STAGE_INCLUDE_FILES = [
    "CyberHost.bat", "cyberhost.sh", "README.md", "LICENSE",
    "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "requirements.txt",
]
STAGE_INCLUDE_DIRS = ["assets", "docs"]


# Windows legacy consoles are cp1252; make build output UTF-8 safe once.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass


def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def _ignore(_dir, names):
    return [n for n in names if n in ("__pycache__", ".cyberhost_history") or n.endswith(".pyc")]


def stage_framework(stage: Path) -> None:
    log(f"staging framework → {stage}")
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    shutil.copytree(PKG, stage / "cyberhost", ignore=_ignore)
    for f in STAGE_INCLUDE_FILES:
        src = HERE / f
        if src.exists():
            shutil.copy2(src, stage / f)
    for d in STAGE_INCLUDE_DIRS:
        src = HERE / d
        if src.exists():
            shutil.copytree(src, stage / d, ignore=_ignore)
    (stage / "tools").mkdir(exist_ok=True)
    (stage / "targets").mkdir(exist_ok=True)


def bundled_py(stage: Path):
    """Return the staged bundled python, importing fresh so it is discovered."""
    from cyberhost.platform_utils import bundled_python
    return bundled_python()


def install_into_stage(stage: Path, *, skip_runtime: bool, only: list[str] | None,
                       core_only: bool) -> None:
    os.environ["CYBERHOST_HOME"] = str(stage)
    # Import after setting CYBERHOST_HOME so all paths resolve into the stage.
    sys.path.insert(0, str(HERE))
    from cyberhost import frida_helper, updater
    from cyberhost.registry import Lockfile, Manifest

    man = Manifest.load()
    lock = Lockfile()

    def want(name: str) -> bool:
        if only:
            return name in only
        return True

    # --- runtimes ----------------------------------------------------------
    runtime = [t for t in man.for_platform() if t.category == "runtime"]
    if not skip_runtime:
        for t in runtime:
            if want(t.name):
                log(f"installing runtime: {t.name}")
                _install_runtime(stage, t, updater, lock)
        _install_cyberhost_deps(stage)

    # --- core tools --------------------------------------------------------
    core = [t for t in man.core() if t.category != "runtime"]
    for t in core:
        if not want(t.name):
            continue
        log(f"installing core tool: {t.name}  ({t.install})")
        try:
            updater.install_tool(t, lock=lock, cache_wheels=(t.install == "pip"))
        except Exception as e:  # keep building the rest
            log(f"  !! {t.name} failed: {e}")

    # --- frida-server for every ABI ---------------------------------------
    if (not only or "frida-tools" in (only or [])) and not core_only:
        try:
            log("pre-bundling frida-server for all ABIs")
            frida_helper.prebundle_servers()
        except Exception as e:
            log(f"  !! frida-server prebundle failed: {e}")

    updater.record_install_path()
    log("install phase complete")


def _install_runtime(stage: Path, tool, updater, lock) -> None:
    # Runtimes are plain archives; reuse the archive installer path.
    try:
        updater.install_tool(tool, lock=lock)
        # Normalize: ensure runtime/<jdk|python> layout.
        _normalize_runtime(stage, tool.name)
    except Exception as e:
        log(f"  !! runtime {tool.name} failed: {e}")


def _normalize_runtime(stage: Path, name: str) -> None:
    """Move an installed runtime from tools/<name> to runtime/<name>."""
    src = stage / "tools" / name
    dst = stage / "runtime" / name
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.move(str(src), str(dst))
        log(f"  runtime placed at runtime/{name}")


def _install_cyberhost_deps(stage: Path) -> None:
    """Install CyberHost's own deps into the bundled python so it can run.

    Verifies the imports afterward and raises on failure — a packaged build that
    can't import its own deps would not boot, so we never ship one silently.
    """
    import subprocess

    from cyberhost.platform_utils import bundled_python
    bp = bundled_python()
    if not bp:
        raise SystemExit("[build] FATAL: bundled python not found; cannot install deps")
    req = HERE / "requirements.txt"
    log("installing CyberHost deps into bundled python")
    subprocess.run([str(bp), "-m", "ensurepip", "--upgrade"], check=False)
    subprocess.run([str(bp), "-m", "pip", "install", "--upgrade", "pip"], check=False)
    r = subprocess.run([str(bp), "-m", "pip", "install", "-r", str(req)])
    if r.returncode != 0:
        raise SystemExit("[build] FATAL: failed to install CyberHost deps into bundled python")
    # Verify the bundled interpreter can actually import them.
    check = subprocess.run([str(bp), "-c", "import yaml, rich, prompt_toolkit"])
    if check.returncode != 0:
        raise SystemExit("[build] FATAL: bundled python cannot import yaml/rich/prompt_toolkit")
    log("bundled python deps verified (yaml, rich, prompt_toolkit)")


def make_zip(stage: Path, version: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"CyberHost-APE-{version}-windows.zip"
    log(f"zipping → {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in stage.rglob("*"):
            z.write(p, Path("CyberHost-APE") / p.relative_to(stage))
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    log(f"done: {zip_path}  ({size_mb:.1f} MiB)")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the CyberHost APE distributable")
    ap.add_argument("--output", default=str(HERE / "dist"), help="output directory")
    ap.add_argument("--stage-only", action="store_true", help="only stage framework code")
    ap.add_argument("--skip-runtime", action="store_true", help="do not fetch JDK/Python")
    ap.add_argument("--core-only", action="store_true", help="skip frida-server prebundle")
    ap.add_argument("--tools", default="", help="comma-separated subset of tools")
    ap.add_argument("--no-zip", action="store_true", help="assemble but do not zip")
    args = ap.parse_args()

    sys.path.insert(0, str(HERE))
    from cyberhost import __version__

    out_dir = Path(args.output)
    stage = out_dir / "CyberHost-APE"
    stage_framework(stage)

    if not args.stage_only:
        only = [t.strip() for t in args.tools.split(",") if t.strip()] or None
        install_into_stage(stage, skip_runtime=args.skip_runtime, only=only,
                           core_only=args.core_only)

    if not args.no_zip:
        make_zip(stage, __version__, out_dir)
    else:
        log(f"assembled at {stage} (zip skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
