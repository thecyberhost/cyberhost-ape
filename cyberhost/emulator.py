"""Universal emulator manager.

CyberHost treats *any* emulator or device reachable over adb as a first-class
target — not just one vendor. It can:
  * detect & launch Android Studio AVDs (via a discovered SDK),
  * adb-connect to a host:port endpoint (Genymotion, Waydroid, BlueStacks, Nox,
    MEmu, LDPlayer, or anything else exposing adb), and
  * list everything reachable in one unified view.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .banner import err, info, ok, warn
from .device import adb, list_devices
from .platform_utils import exe, is_windows, subprocess_env

# Common default adb ports for popular emulators (best-effort connect helpers).
KNOWN_ENDPOINTS = {
    "genymotion": None,       # uses its own adb; point it at bundled adb instead
    "bluestacks": "127.0.0.1:5555",
    "nox": "127.0.0.1:62001",
    "memu": "127.0.0.1:21503",
    "ldplayer": "127.0.0.1:5555",
    "waydroid": None,          # local adb, appears automatically once started
}


# ---------------------------------------------------------------------------
# Android SDK / AVD discovery
# ---------------------------------------------------------------------------

def find_sdk() -> Path | None:
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        v = os.environ.get(env)
        if v and Path(v).exists():
            return Path(v)
    home = Path.home()
    candidates = [
        home / "AppData" / "Local" / "Android" / "Sdk",       # Windows
        home / "Library" / "Android" / "sdk",                  # macOS
        home / "Android" / "Sdk",                              # Linux
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _emulator_bin() -> str | None:
    sdk = find_sdk()
    if sdk:
        cand = sdk / "emulator" / exe("emulator")
        if cand.exists():
            return str(cand)
    return shutil.which("emulator")


def list_avds() -> list[str]:
    emu = _emulator_bin()
    if not emu:
        return []
    try:
        cp = subprocess.run([emu, "-list-avds"], capture_output=True, text=True,
                            timeout=30, env=subprocess_env())
        return [ln.strip() for ln in cp.stdout.splitlines() if ln.strip()]
    except subprocess.SubprocessError:
        return []


def launch_avd(avd: str, *, writable_system: bool = False, extra: list[str] | None = None) -> bool:
    """Launch an Android Studio AVD. writable_system eases CA/root workflows."""
    emu = _emulator_bin()
    if not emu:
        err("Android emulator binary not found — install Android Studio / SDK, "
            "or use `emulator connect` for a third-party emulator")
        return False
    if avd not in list_avds():
        err(f"unknown AVD {avd!r}; available: {', '.join(list_avds()) or '(none)'}")
        return False
    cmd = [emu, "-avd", avd]
    if writable_system:
        cmd.append("-writable-system")
    cmd += extra or []
    info(f"launching AVD {avd} (detached)")
    # Detach so the CLI returns immediately.
    kwargs = {"env": subprocess_env()}
    if is_windows():
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    ok(f"AVD {avd} starting — run `cyberhost devices` once it boots")
    return True


# ---------------------------------------------------------------------------
# Generic adb-endpoint connect
# ---------------------------------------------------------------------------

def connect(target: str) -> bool:
    """adb-connect to a host:port, or a known-emulator alias."""
    endpoint = target
    alias = KNOWN_ENDPOINTS.get(target.lower(), "missing")
    if alias is not None and alias != "missing":
        endpoint = alias
        info(f"{target} default endpoint: {endpoint}")
    elif alias is None:
        warn(f"{target} uses a local adb transport — just start it, then "
             f"`cyberhost devices` (no connect needed)")
        return False
    if ":" not in endpoint:
        endpoint += ":5555"
    cp = adb("connect", endpoint, check=False)
    txt = (cp.stdout + cp.stderr).strip()
    if "connected" in txt.lower():
        ok(f"connected to {endpoint}")
        return True
    err(f"could not connect to {endpoint}: {txt}")
    return False


def disconnect(target: str | None = None) -> None:
    adb("disconnect", *( [target] if target else [] ), check=False)
    ok(f"disconnected {target or 'all'}")


# ---------------------------------------------------------------------------
# Unified listing
# ---------------------------------------------------------------------------

@dataclass
class Reachable:
    devices: list
    avds: list[str]
    sdk: Path | None


def detect() -> Reachable:
    return Reachable(devices=list_devices(), avds=list_avds(), sdk=find_sdk())


def print_detection() -> None:
    r = detect()
    info(f"Android SDK: {r.sdk or 'not found'}")
    if r.avds:
        info("AVDs available to launch: " + ", ".join(r.avds))
    else:
        info("AVDs available to launch: (none — install via Android Studio)")
    if r.devices:
        ok(f"{len(r.devices)} device(s) reachable over adb:")
        for d in r.devices:
            info("  " + d.label)
    else:
        warn("no devices currently reachable over adb")
        info("start an emulator/AVD, or `cyberhost emulator connect <host:port>`")
