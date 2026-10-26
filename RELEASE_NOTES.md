# CyberHost APE v0.1.0

The first release of **CyberHost APE** — an interactive, portable Android
penetration-testing framework console. Unzip and run; no VM, no installs.

## Highlights

- **Interactive console** (`cyberhost>`) with tab-completion, history, colored
  output, and a one-off command mode for scripting.
- **Bundled portable runtimes** (JDK 17 + Python 3.11) — nothing to install.
- **Core tools bundled & offline**: platform-tools, scrcpy, apktool, jadx/
  jadx-gui, dex2jar, smali/baksmali, JD-GUI, apkleaks, build-tools, Uber APK
  Signer, bundletool, Frida + frida-tools, objection, mitmproxy, plus a Frida
  script library (SSL-pinning bypass, root-detection bypass, common hooks).
- **On-demand installs** for heavy/occasional tools: MobSF, drozer, Ghidra, ZAP,
  nmap, tcpdump, quark, apkid, enjarify, apkeep, apkurlgrep, trufflehog,
  apk-mitm, RMS, house, medusa, fridump, nuclei.
- **Always-latest resolver**: no hardcoded versions/URLs — resolved live from
  each tool's official source (GitHub/Google/PyPI/npm) at build and update time.
- **Self-update engine** with checksum verification and atomic swaps:
  `update`, `update <tool>`, `update --self`.
- **Universal emulator support** (AVD, Genymotion, Waydroid, BlueStacks, Nox,
  MEmu, LDPlayer, or any adb endpoint) and a unified `devices` view.
- **Automatic per-ABI frida-server** management; **guided CA-cert** helper for
  Android 7+ user/system trust stores; **honest root** workflows.
- **Legal practice targets** (DIVA, InsecureBankv2, AndroGoat, Pivaa, MASTG
  crackmes) via `targets`.

## Install

Download `CyberHost-APE-0.1.0-windows.zip`, unzip, double-click `CyberHost.bat`.
See the README and `docs/QUICKSTART.md`.

## Credits

Each bundled tool is the work of its own authors.

> Authorized / educational use only.
