"""Frida orchestration — automatic per-ABI frida-server management.

`cyberhost frida --setup` detects the connected device's ABI, finds the exact
frida-server build matching the *installed* frida version, downloads it from the
official frida GitHub releases, decompresses it, pushes it to the device, and
starts it. It also exposes the bundled, ready-to-run Frida script library.
"""

from __future__ import annotations

import lzma
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from .banner import err, info, ok, step, warn
from .device import adb, getprop, list_devices
from .platform_utils import (android_abi_to_frida_arch, find_bundled, scripts_dir,
                             subprocess_env, tool_home)

_FRIDA_RELEASES = "https://api.github.com/repos/frida/frida/releases/latest"
_UA = {"User-Agent": "CyberHost-APE/0.1", "Accept": "application/json"}


def installed_frida_version() -> str | None:
    """Version of the frida-tools install managed by CyberHost (or system)."""
    frida = find_bundled("frida")
    if not frida:
        return None
    try:
        cp = subprocess.run([frida, "--version"], capture_output=True, text=True,
                            timeout=30, env=subprocess_env())
        return cp.stdout.strip() or None
    except subprocess.SubprocessError:
        return None


def device_abi(serial: str | None = None) -> str:
    abi = getprop(serial or "", "ro.product.cpu.abi")
    return abi or "arm64-v8a"


def _frida_server_asset(version: str | None, arch: str) -> tuple[str, str]:
    """Return (version, download_url) for the frida-server matching version+arch."""
    import json
    req = urllib.request.Request(_FRIDA_RELEASES, headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        data = json.loads(r.read().decode())
    latest = data["tag_name"].lstrip("v")
    want = version or latest
    # The matching release may not be "latest"; fetch the specific tag if needed.
    if want != latest:
        req = urllib.request.Request(
            f"https://api.github.com/repos/frida/frida/releases/tags/{want}", headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
                data = json.loads(r.read().decode())
        except Exception:
            warn(f"frida {want} release not found; using latest {latest}")
            want = latest
    rx = re.compile(rf"frida-server-{re.escape(want)}-android-{arch}\.xz$")
    for a in data.get("assets", []):
        if rx.search(a["name"]):
            return want, a["browser_download_url"]
    raise RuntimeError(f"no frida-server asset for {want}/android-{arch}")


def setup(serial: str | None = None) -> bool:
    devs = list_devices()
    if not devs:
        err("no device connected — start an emulator or connect a device first")
        return False
    serial = serial or devs[0].serial

    fv = installed_frida_version()
    if not fv:
        warn("frida not installed in the toolkit yet")
        step("run `cyberhost install` (installs frida + frida-tools)")
        return False
    abi = device_abi(serial)
    arch = android_abi_to_frida_arch(abi)
    info(f"device {serial}: ABI {abi} → frida arch {arch}; frida {fv}")

    try:
        version, url = _frida_server_asset(fv, arch)
    except Exception as e:
        err(f"could not resolve frida-server: {e}")
        return False

    cache = tool_home("frida-server")
    cache.mkdir(parents=True, exist_ok=True)
    local = cache / f"frida-server-{version}-android-{arch}"
    if not local.exists():
        with tempfile.TemporaryDirectory() as td:
            xz = Path(td) / "fs.xz"
            info(f"downloading frida-server {version} ({arch})")
            req = urllib.request.Request(url, headers={"User-Agent": "CyberHost-APE/0.1"})
            with urllib.request.urlopen(req, timeout=120) as r, open(xz, "wb") as f:  # noqa: S310
                f.write(r.read())
            local.write_bytes(lzma.decompress(xz.read_bytes()))
        ok(f"frida-server cached: {local.name}")

    remote = "/data/local/tmp/frida-server"
    if adb("push", str(local), remote, serial=serial, check=False).returncode != 0:
        err("push failed")
        return False
    adb("shell", "chmod", "755", remote, serial=serial, check=False)
    adb("root", serial=serial, check=False)
    # Launch detached in the background on the device.
    adb("shell", f"nohup {remote} >/dev/null 2>&1 &", serial=serial, check=False)
    ok("frida-server pushed and started on device")
    step("verify with `cyberhost run frida-ps -U`  (lists device processes)")
    step("bypass SSL pinning:  cyberhost run objection -g <pkg> explore  "
         "or load a script from `cyberhost scripts`")
    return True


def prebundle_servers(version: str | None = None, abis: list[str] | None = None) -> list[str]:
    """Download frida-server for several ABIs into tools/frida-server.

    Called by the build so the ZIP ships ready-to-push servers for arm64-v8a,
    x86_64, armeabi-v7a and x86 (no per-student download needed).
    """
    from .platform_utils import ANDROID_ABIS, android_abi_to_frida_arch
    abis = abis or list(ANDROID_ABIS)
    fv = version or installed_frida_version()
    cache = tool_home("frida-server")
    cache.mkdir(parents=True, exist_ok=True)
    got: list[str] = []
    seen: set[str] = set()
    for abi in abis:
        arch = android_abi_to_frida_arch(abi)
        if arch in seen:
            continue
        seen.add(arch)
        try:
            v, url = _frida_server_asset(fv, arch)
        except Exception as e:
            warn(f"frida-server {arch}: {e}")
            continue
        out = cache / f"frida-server-{v}-android-{arch}"
        if not out.exists():
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "CyberHost-APE/0.1"})
            with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
                out.write_bytes(lzma.decompress(r.read()))
        ok(f"bundled frida-server {out.name}")
        got.append(str(out))
    return got


# ---------------------------------------------------------------------------
# Bundled script library
# ---------------------------------------------------------------------------

def list_scripts() -> list[Path]:
    d = scripts_dir()
    return sorted(d.glob("*.js")) if d.exists() else []


def print_scripts() -> None:
    scripts = list_scripts()
    if not scripts:
        warn("no bundled scripts found")
        return
    info(f"bundled Frida scripts ({scripts_dir()}):")
    for s in scripts:
        first = ""
        try:
            for line in s.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("//") and "desc:" in line:
                    first = line.split("desc:", 1)[1].strip()
                    break
                if line.strip().startswith("//") and line.strip("/ ").strip():
                    first = line.strip("/ ").strip()
                    break
        except Exception:
            pass
        print(f"  • {s.name:32} {first}")
    step("run one:  cyberhost run frida -U -f <pkg> -l "
         f"\"{scripts_dir() / 'ssl-pinning-bypass.js'}\" --no-pause")
