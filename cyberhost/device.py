"""Device & adb helper.

Wraps the *bundled* adb (first-class, always preferred over any system adb) and
exposes the device operations the rest of the toolkit builds on: list devices,
install/uninstall, push/pull, set the global HTTP proxy, read properties, pull
APKs off a device.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .banner import err, info, ok, warn
from .platform_utils import find_bundled, subprocess_env


@dataclass
class Device:
    serial: str
    state: str  # device | offline | unauthorized
    model: str = ""
    is_emulator: bool = False

    @property
    def label(self) -> str:
        kind = "emulator" if self.is_emulator else "device"
        model = f" ({self.model})" if self.model else ""
        return f"{self.serial}{model} [{kind}, {self.state}]"


def adb_path() -> str | None:
    """Locate adb, preferring the bundled platform-tools copy."""
    return find_bundled("adb")


class AdbError(RuntimeError):
    pass


def _adb() -> str:
    p = adb_path()
    if not p:
        raise AdbError("adb not found — run `cyberhost install` to fetch platform-tools")
    return p


def adb(*args: str, serial: str | None = None, check: bool = True,
        timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = [_adb()]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check,
                          timeout=timeout, env=subprocess_env())


def list_devices() -> list[Device]:
    try:
        out = adb("devices", "-l", check=False).stdout
    except (AdbError, subprocess.SubprocessError) as e:
        warn(str(e))
        return []
    devices: list[Device] = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        serial, state = parts[0], parts[1]
        model = ""
        for p in parts[2:]:
            if p.startswith("model:"):
                model = p.split(":", 1)[1]
        is_emu = serial.startswith("emulator-") or ":" in serial and serial.startswith(
            ("127.0.0.1", "localhost"))
        devices.append(Device(serial=serial, state=state, model=model, is_emulator=is_emu))
    return devices


def getprop(serial: str, prop: str) -> str:
    try:
        return adb("shell", "getprop", prop, serial=serial, check=False).stdout.strip()
    except subprocess.SubprocessError:
        return ""


def install_apk(path: str, serial: str | None = None, *, reinstall: bool = True) -> bool:
    args = ["install"]
    if reinstall:
        args.append("-r")
    args.append(path)
    cp = adb(*args, serial=serial, check=False)
    if cp.returncode == 0 and "Success" in cp.stdout:
        ok(f"installed {path}")
        return True
    err(f"install failed: {cp.stdout.strip() or cp.stderr.strip()}")
    return False


def uninstall(package: str, serial: str | None = None) -> bool:
    cp = adb("uninstall", package, serial=serial, check=False)
    if cp.returncode == 0 and "Success" in cp.stdout:
        ok(f"uninstalled {package}")
        return True
    err(f"uninstall failed: {cp.stdout.strip() or cp.stderr.strip()}")
    return False


def push(local: str, remote: str, serial: str | None = None) -> bool:
    cp = adb("push", local, remote, serial=serial, check=False)
    return cp.returncode == 0


def pull(remote: str, local: str, serial: str | None = None) -> bool:
    cp = adb("pull", remote, local, serial=serial, check=False)
    return cp.returncode == 0


def set_proxy(host_port: str, serial: str | None = None) -> bool:
    """Route device HTTP(S) traffic through host_port (e.g. 192.168.1.5:8080)."""
    cp = adb("shell", "settings", "put", "global", "http_proxy", host_port,
             serial=serial, check=False)
    if cp.returncode == 0:
        ok(f"proxy set to {host_port}")
        step_hint()
        return True
    err("failed to set proxy")
    return False


def clear_proxy(serial: str | None = None) -> bool:
    adb("shell", "settings", "put", "global", "http_proxy", ":0", serial=serial, check=False)
    cp = adb("shell", "settings", "delete", "global", "http_proxy", serial=serial, check=False)
    ok("proxy cleared")
    return cp.returncode == 0


def step_hint() -> None:
    info("next: install your CA with `cyberhost cert --install` so HTTPS can be intercepted")


def list_packages(serial: str | None = None, third_party_only: bool = True) -> list[str]:
    args = ["shell", "pm", "list", "packages"]
    if third_party_only:
        args.append("-3")
    cp = adb(*args, serial=serial, check=False)
    return sorted(ln.replace("package:", "").strip()
                  for ln in cp.stdout.splitlines() if ln.startswith("package:"))


def pull_apk(package: str, out_dir: str, serial: str | None = None) -> list[str]:
    """Pull every APK (base + splits) for *package* off the device."""
    import os
    cp = adb("shell", "pm", "path", package, serial=serial, check=False)
    paths = [ln.replace("package:", "").strip()
             for ln in cp.stdout.splitlines() if ln.startswith("package:")]
    if not paths:
        err(f"package not found on device: {package}")
        return []
    os.makedirs(out_dir, exist_ok=True)
    pulled: list[str] = []
    for i, remote in enumerate(paths):
        name = f"{package}.apk" if len(paths) == 1 else f"{package}.split{i}.apk"
        local = os.path.join(out_dir, name)
        if pull(remote, local, serial=serial):
            pulled.append(local)
            ok(f"pulled {name}")
    return pulled
