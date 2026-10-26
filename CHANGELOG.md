# Changelog

All notable changes to CyberHost APE are recorded here. Versions follow
[semantic versioning](https://semver.org/).

## [0.1.0] — 2026-10-26

First public release — an interactive, portable Android penetration-testing
framework console. Unzip and run; no VM, no installs.

### Added
- Interactive `cyberhost>` console (prompt_toolkit + rich) with tab-completion,
  persistent history, and a one-off command mode that shares the same command
  layer.
- Data-driven tool manifest (`tools.yaml`): core (bundled, offline) vs on-demand
  tools, each with official-source resolver metadata — no hardcoded versions or
  URLs.
- Always-latest resolver (GitHub Releases, the Google Android repository, PyPI,
  npm, Maven) with a self-update engine: checksum verification and atomic
  per-tool swaps.
- Bundled portable JDK 17 and a relocatable Python 3.11; all tools run on the
  bundled runtimes. Offline `bootstrap`/`repair` for relocated pip tools.
- Core toolkit bundled offline: platform-tools, scrcpy, apktool, jadx/jadx-gui,
  dex2jar, smali/baksmali, JD-GUI, apkleaks, build-tools, Uber APK Signer,
  bundletool, Frida + frida-tools, objection, mitmproxy, plus a Frida script
  library (SSL-pinning bypass, root-detection bypass, common hooks).
- On-demand tools via `install <name>`: MobSF, drozer, Ghidra, ZAP, nmap,
  tcpdump, quark, apkid, enjarify, apkeep, apkurlgrep, trufflehog, apk-mitm,
  RMS, house, medusa, fridump, nuclei.
- Universal emulator support (AVD, Genymotion, Waydroid, BlueStacks, Nox, MEmu,
  LDPlayer, or any adb endpoint) with a unified `devices` view.
- Automatic per-ABI frida-server management, a guided CA-certificate helper for
  the Android 7+ user/system trust stores, and an honest root workflow.
- Legal practice targets (DIVA, InsecureBankv2, AndroGoat, PIVAA, MASTG
  crackmes) via `targets`.
- Full documentation: README, quickstart, and a complete
  [user manual](docs/MANUAL.md).

[0.1.0]: https://github.com/thecyberhost/cyberhost-ape/releases/tag/v0.1.0
