<div align="center">

```
  ____      _               _   _           _
 / ___|   _| |__   ___ _ __| | | | ___  ___| |_
| |  | | | | '_ \ / _ \ '__| |_| |/ _ \/ __| __|
| |__| |_| | |_) |  __/ |  |  _  | (_) \__ \ |_
 \____\__, |_.__/ \___|_|  |_| |_|\___/|___/\__|
      |___/   A P E  ·  Android Pentesting Environment
```

**CyberHost APE** — an interactive, portable, self-updating Android
penetration-testing framework console. Unzip and run. No VM, no installs.

*by TCH · authorized / educational use only*

</div>

---

## What it is

CyberHost APE is a **text-based framework console** for Android security
testing — think `msfconsole` / `recon-ng`, but for mobile. You get a branded
`cyberhost>` prompt with tab-completion, inline help, and every everyday tool
already wired up and ready.

It is the spiritual successor to the classic **[Appie](https://github.com/dineshshetty/Android-Application-Penetration-Testing)**
(Android Pentesting Portable Integrated Environment) by Dinesh Shetty — the same
"everything in one portable folder" idea, brought up to date: current tool
versions, a self-update engine, no virtual machine, and a real interactive
shell.

```
cyberhost> use jadx
✓ using jadx — Dex→Java decompiler, includes jadx and jadx-gui
cyberhost (jadx)> target app.apk
✓ target set: app.apk
cyberhost (jadx)> run
```

## Why you'll like it

- **Unzip and go.** One ZIP, ~1.2–1.5 GB. Works immediately, **fully offline**.
- **Bundled runtimes.** A portable JDK 17 and Python 3.11 ship *inside* the
  folder — nothing to install, nothing touched on your system.
- **Core tools bundled, heavy tools on demand.** Everyday tools are in the ZIP;
  big/occasional ones install with one command so the core stays small.
- **Always latest.** No download URLs are ever hardcoded. Versions are resolved
  live from each tool's official source at build time and on every `update`.
- **Portable & clean.** Runs from a USB stick. Delete the folder — it's all gone.
- **Universal device support.** Any emulator or phone reachable over adb.

---

## Quick start (your first APK analysis in 5 minutes)

1. **Unzip** `CyberHost-APE-*.zip` anywhere.
2. **Double-click `CyberHost.bat`** (Windows). You land in the console.
3. Try:

   ```
   cyberhost> devices                 # see connected devices/emulators
   cyberhost> use apkleaks            # pick a tool
   cyberhost> target path\to\app.apk  # point it at an APK
   cyberhost> run                     # scan for secrets & endpoints
   cyberhost> use jadx                # decompile to Java
   cyberhost> run
   ```

Full walkthrough: **[docs/QUICKSTART.md](docs/QUICKSTART.md)**.

You can also run one-off commands from a normal terminal (handy for scripting):

```
CyberHost.bat install mobsf
CyberHost.bat list core
```

---

## Commands

| Command | What it does |
|---|---|
| `help [cmd]` | list commands, or help for one |
| `list [core\|on-demand\|installed]` | list tools and installed versions |
| `search <term>` | find a tool |
| `use <tool>` | select a tool to work with |
| `target <apk\|package>` | set what to operate on |
| `run [args]` | run the selected tool (auto-passes the target) |
| `info <tool>` | details about a tool |
| `devices` | list physical + emulator devices (unified) |
| `emulator <list\|connect\|launch>` | detect / connect / launch emulators |
| `cert install <ca.pem>` | install a proxy CA to the device |
| `frida setup` | push & run the matching frida-server |
| `scripts` | list the bundled Frida scripts |
| `proxy <on\|off\|burp>` | route device traffic to the interceptor |
| `install <tool\|all>` | install an on-demand tool |
| `update [<tool>\|--all\|--self]` | update tools or CyberHost itself |
| `targets [--install\|--deploy]` | legal vulnerable practice apps |
| `root <check\|guide>` | device root status / guided Magisk workflow |
| `doctor` | diagnose the environment |
| `bootstrap` | rebuild tool envs after moving the folder |
| `version` · `exit` | version · leave |

---

## Tool index

### Core — bundled in the ZIP, offline-ready

| Tool | Purpose |
|---|---|
| **platform-tools** | adb, fastboot (bundled adb is first-class) |
| **scrcpy** | mirror & control the device |
| **JDK 17** / **Python 3.11** | bundled portable runtimes |
| **apktool** | decode/rebuild APK resources & smali |
| **jadx / jadx-gui** | dex → Java decompiler |
| **dex2jar** | dex/apk → jar |
| **smali / baksmali** | dex assembler/disassembler |
| **JD-GUI** | Java decompiler GUI |
| **apkleaks** | URIs/endpoints/secrets scanner |
| **build-tools** | apksigner, zipalign, aapt2 (+ keytool via JDK) |
| **Uber APK Signer** | one-command (re)signing |
| **bundletool** | .aab / split-APK handling |
| **Frida + frida-tools** | instrumentation (per-ABI frida-server managed for you) |
| **objection** | runtime mobile exploration |
| **mitmproxy** | HTTPS intercepting proxy |
| **Frida scripts** | SSL-pinning bypass, root-detection bypass, common hooks |

### On-demand — one command, fetched at latest

`install mobsf` · `install drozer` · `install ghidra` · `install zap` ·
`install nmap` · `install tcpdump` · `install quark` · `install apkid` ·
`install enjarify` · `install apkeep` · `install apkurlgrep` ·
`install trufflehog` · `install apk-mitm` · `install rms` · `install house` ·
`install medusa` · `install fridump` · `install nuclei` · `install targets`

> **Burp Suite** is **not** bundled (licensing). Use `proxy burp <host:port>
> [ca.pem]` to point the device at your own Burp and install its CA.

---

## Emulator & device setup

CyberHost talks to **anything reachable over adb**:

- **Android Studio AVD** — `emulator list` detects your SDK and AVDs;
  `emulator launch <avd>` starts one (with a writable system, for CA/root work).
- **Genymotion** — set its `genymotion.adb_path` to the bundled adb
  (`tools/platform-tools/platform-tools/adb.exe`).
- **Waydroid / BlueStacks / Nox / MEmu / LDPlayer / anything** —
  `emulator connect <host:port>` (known emulators have built-in default ports).

`devices` shows everything in one unified list.

## HTTPS interception (cert/pinning)

```
cyberhost> proxy on                                  # device → this host:8080
cyberhost> run mitmproxy                             # start the interceptor
cyberhost> cert install ~/.mitmproxy/mitmproxy-ca-cert.pem
```

`cert install` handles the Android 7+ **user vs. system** trust store, detects
whether the system store is writable (rooted/Magisk or a `-writable-system`
emulator), and falls back to the user store with honest guidance when it isn't.
For apps that ignore user CAs, use `install apk-mitm` or a Frida pinning-bypass
script from `scripts`.

## Rooting (honest & safe)

- **Emulators:** `root check` tries `adb root`; `root guide` walks the
  rootAVD/Magisk flow for Play images.
- **Physical devices:** there is **no** one-click root. `root guide` gives a
  documented, model-aware Magisk workflow with clear **data-wipe / brick**
  warnings. We never pretend otherwise.

## Keeping it current

```
cyberhost> update            # update everything installed
cyberhost> update jadx       # just one
cyberhost> update --self     # update CyberHost + refresh resolver metadata
```

The update engine re-resolves the latest release from each tool's official
source (GitHub Releases / Google endpoints / PyPI / npm), verifies checksums
when available, and swaps atomically so an update can't break other tools.

---

## Building the distributable

Developers assemble the shippable ZIP with the included build script, which
fetches the bundled runtimes and core tools at their current latest versions:

```
python build.py                 # full build + Windows ZIP
python build.py --stage-only    # just the framework (fast)
python build.py --tools jadx,apktool   # a subset, for testing
```

See **[docs/BUILD.md](docs/BUILD.md)**.

## Requirements

The built ZIP needs **nothing** pre-installed (runtimes are bundled). To run
from source for development you need Python 3.11+; `pip install -r
requirements.txt`.

---

## ⚠ Authorized & educational use only

CyberHost APE is for **authorized security testing and education**. Only test
devices, emulators, and applications **you own or have explicit written
permission to assess**. The bundled practice targets are intentionally
vulnerable — run them **only** in an isolated environment or emulator, never on
a network you don't control. You are responsible for complying with all
applicable laws. The authors assume no liability for misuse.

## License

Apache-2.0 — see [LICENSE](LICENSE). Chosen over MIT for its explicit patent
grant and `NOTICE`/trademark clarity, which suit a widely-redistributed security
toolkit. Bundled third-party tools remain under their own licenses.

## Credits

- **Appie** by Dinesh Shetty — the original portable Android pentest kit and the
  inspiration for this project.
- Every bundled tool is the work of its respective authors and community.

## Contributing

PRs welcome — adding a tool is usually a few lines in
[`cyberhost/data/tools.yaml`](cyberhost/data/tools.yaml). See
[CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md).
