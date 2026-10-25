"""Root helper — honest and safe.

Emulators: where feasible we automate. Google-APIs / AOSP emulator images allow
`adb root` directly; for Play-image AVDs we point users at the rootAVD + Magisk
flow. Physical devices: we DO NOT pretend one-click rooting exists. Rooting a
physical phone is device-specific, unlocks the bootloader (which wipes data),
and is sometimes impossible. We provide a guided, well-documented Magisk
workflow and clear warnings instead.
"""

from __future__ import annotations

from .banner import console, err, info, ok, step, warn
from .device import adb, getprop, list_devices


def check(serial: str | None = None) -> dict:
    """Report the root / trust status of the connected device."""
    devs = list_devices()
    if not devs:
        err("no device connected")
        return {}
    serial = serial or devs[0].serial
    info(f"inspecting {serial}")

    fingerprint = getprop(serial, "ro.build.fingerprint")
    is_emu = getprop(serial, "ro.kernel.qemu") == "1" or serial.startswith("emulator-")
    secure = getprop(serial, "ro.secure")
    debuggable = getprop(serial, "ro.debuggable")
    tags = getprop(serial, "ro.build.tags")

    # Try adb root (works on emulator eng/userdebug images).
    adb_root = adb("root", serial=serial, check=False)
    adb_root_ok = "restarting adbd as root" in (adb_root.stdout + adb_root.stderr).lower() \
        or "already running as root" in (adb_root.stdout + adb_root.stderr).lower()

    # Check for an su binary (Magisk / userspace root).
    su = adb("shell", "which", "su", serial=serial, check=False)
    has_su = bool(su.stdout.strip())

    # Magisk presence
    magisk = adb("shell", "pm", "list", "packages", serial=serial, check=False)
    has_magisk = "com.topjohnwu.magisk" in magisk.stdout

    status = {
        "serial": serial,
        "emulator": is_emu,
        "build_tags": tags,
        "ro.secure": secure,
        "ro.debuggable": debuggable,
        "adb_root_available": adb_root_ok,
        "su_binary": has_su,
        "magisk_installed": has_magisk,
        "rooted": has_su or adb_root_ok or has_magisk,
        "fingerprint": fingerprint,
    }

    console.print("")
    for k, v in status.items():
        console.print(f"  [cyan]{k:20}[/cyan] {v}")
    console.print("")
    if status["rooted"]:
        ok("device appears to have root access available")
    else:
        warn("device does not appear rooted")
        if is_emu:
            step("emulator: try `cyberhost root --guide` for the rootAVD/Magisk flow, "
                 "or use a Google-APIs (not Play) image which allows `adb root`")
        else:
            step("physical device: run `cyberhost root --guide` for the Magisk walkthrough")
    return status


def guide(serial: str | None = None) -> None:
    """Print a device-aware root walkthrough."""
    devs = list_devices()
    is_emu = False
    model = brand = ""
    if devs:
        serial = serial or devs[0].serial
        is_emu = devs[0].is_emulator or getprop(serial, "ro.kernel.qemu") == "1"
        model = getprop(serial, "ro.product.model")
        brand = getprop(serial, "ro.product.brand")

    console.rule("[bold cyan]CyberHost Root Guide")
    if is_emu or not devs:
        _emulator_guide()
    else:
        _physical_guide(brand, model)


def _emulator_guide() -> None:
    console.print("""[bold]Emulator rooting (Android Studio AVD)[/bold]

[green]Easiest — Google-APIs / AOSP image:[/green]
  1. Create an AVD using a *Google APIs* system image (NOT "Google Play").
  2. Launch it, then:  [cyan]adb root[/cyan]   → you get a root shell directly.
     CyberHost can do this for you: [cyan]cyberhost root --check[/cyan]

[green]Full Magisk root (needed for Play images / realistic root):[/green]
  1. Launch the AVD with a writable system:
       [cyan]cyberhost emulator launch <avd>[/cyan]   (adds -writable-system)
  2. Use rootAVD to patch the ramdisk with Magisk:
       [cyan]git clone https://gitlab.com/newbit/rootAVD && cd rootAVD[/cyan]
       [cyan]./rootAVD.sh ListAllAVDs[/cyan]   then run it against your AVD's ramdisk.img
  3. Reboot; install the Magisk app to manage root.

[dim]rootAVD is third-party and not bundled (it is emulator-image-specific).[/dim]""")
    ok("emulator root guide complete")


def _physical_guide(brand: str, model: str) -> None:
    dev = f"{brand} {model}".strip() or "your device"
    console.print(f"""[bold red]⚠ Rooting a physical device is risky and device-specific.[/bold red]

Detected device: [bold]{dev}[/bold]

[red]Before you start — READ THIS:[/red]
  • Unlocking the bootloader [bold]ERASES ALL DATA[/bold] on the device.
  • It usually voids your warranty and may trip Knox/SafetyNet permanently.
  • Some carrier/locked models [bold]cannot[/bold] be unlocked at all.
  • There is NO universal one-click root. Steps differ per manufacturer.

[bold]General Magisk workflow:[/bold]
  1. Enable Developer Options → USB debugging + OEM unlocking.
  2. Unlock the bootloader (manufacturer-specific):
       Pixel/OnePlus:   [cyan]fastboot flashing unlock[/cyan]
       Xiaomi:          Mi Unlock tool (waiting period applies)
       Samsung:         Download mode + Odin (no fastboot)
  3. Obtain the EXACT boot.img for your firmware build.
  4. Copy boot.img to the device, install the Magisk app, "Install" →
     "Select and Patch a File" → pick boot.img → get magisk_patched.img.
  5. Pull it back and flash:
       [cyan]fastboot flash boot magisk_patched.img[/cyan]
  6. Reboot. Verify with [cyan]cyberhost root --check[/cyan].

[dim]Consult the XDA thread for YOUR exact model + firmware before flashing.
CyberHost intentionally does not automate this — a wrong boot.img can brick
the device.[/dim]""")
    warn("follow a model-specific guide; the above is the general shape only")
