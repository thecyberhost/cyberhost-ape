"""Guided CA-certificate helper for HTTPS interception.

Installing a proxy's CA onto Android changed a lot across versions. This helper
automates what can be automated and clearly guides the rest:

  * Android 7+ split the trust store into *user* and *system*. Apps targeting
    API 24+ ignore user CAs unless they opt in (networkSecurityConfig), so for
    most real-world apps the CA must land in the *system* store.
  * System-store install requires either a rooted device / Magisk, or an
    emulator booted with a writable system partition.

The helper converts a PEM to Android's hashed-name format, pushes it, and (when
the system store is writable) installs it there; otherwise it installs to the
user store and explains the limitation honestly.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .banner import err, info, ok, step, warn
from .device import adb, getprop
from .platform_utils import find_bundled


def _android_cert_hash(pem_path: Path) -> str:
    """Compute the old-style subject_hash_old name Android uses (<hash>.0)."""
    openssl = find_bundled("openssl")
    if openssl:
        try:
            cp = subprocess.run([openssl, "x509", "-inform", "PEM", "-subject_hash_old",
                                 "-in", str(pem_path)], capture_output=True, text=True, check=True)
            return cp.stdout.splitlines()[0].strip()
        except subprocess.SubprocessError:
            pass
    # Fallback: pure-python approximation is non-trivial; require openssl.
    raise RuntimeError("openssl required to compute Android cert hash; install openssl")


def api_level(serial: str | None = None) -> int:
    try:
        return int(getprop(serial or "", "ro.build.version.sdk") or 0)
    except ValueError:
        return 0


def system_store_writable(serial: str | None = None) -> bool:
    """Can we remount /system rw (rooted/Magisk or emulator writable-system)?"""
    adb("root", serial=serial, check=False)
    cp = adb("shell", "mount", "-o", "rw,remount", "/system", serial=serial, check=False)
    return cp.returncode == 0 and not (cp.stderr.strip())


def install(pem: str, serial: str | None = None, *, system: bool | None = None) -> bool:
    pem_path = Path(pem)
    if not pem_path.exists():
        err(f"certificate not found: {pem}")
        step("export your proxy CA as PEM first (mitmproxy: ~/.mitmproxy/mitmproxy-ca-cert.pem)")
        return False

    lvl = api_level(serial)
    info(f"device API level: {lvl or 'unknown'}")
    try:
        hashed = _android_cert_hash(pem_path)
    except RuntimeError as e:
        err(str(e))
        return False
    cert_name = f"{hashed}.0"
    info(f"certificate hashed name: {cert_name}")

    want_system = system if system is not None else (lvl >= 24)
    if want_system:
        if system_store_writable(serial):
            return _install_system(pem_path, cert_name, serial)
        warn("system store not writable (device not rooted / emulator not -writable-system)")
        warn("falling back to USER store — many apps (API 24+) will ignore it")
        step("for full coverage: root via `cyberhost root --guide`, or boot an AVD "
             "with `cyberhost emulator launch <avd>` (writable-system)")
    return _install_user(pem_path, serial)


def _install_system(pem_path: Path, cert_name: str, serial: str | None) -> bool:
    remote = f"/system/etc/security/cacerts/{cert_name}"
    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / cert_name
        staged.write_bytes(pem_path.read_bytes())
        if adb("push", str(staged), "/data/local/tmp/" + cert_name, serial=serial,
               check=False).returncode != 0:
            err("push failed")
            return False
    adb("shell", "mv", "/data/local/tmp/" + cert_name, remote, serial=serial, check=False)
    adb("shell", "chmod", "644", remote, serial=serial, check=False)
    ok(f"installed CA to SYSTEM store: {remote}")
    step("reboot the device/emulator to be safe: `adb reboot`")
    return True


def _install_user(pem_path: Path, serial: str | None) -> bool:
    # Push to Download and open the settings import flow.
    remote = "/sdcard/Download/" + pem_path.name
    adb("push", str(pem_path), remote, serial=serial, check=False)
    ok(f"certificate copied to device: {remote}")
    step("on the device: Settings → Security → Encryption & credentials → "
         "Install a certificate → CA certificate → pick the file")
    step("for apps that ignore user CAs, patch the APK with `cyberhost run apk-mitm` "
         "or use Frida SSL-pinning bypass (`cyberhost scripts`)")
    return True
