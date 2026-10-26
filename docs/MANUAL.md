# CyberHost APE — User Manual

This is the full manual: every command, every bundled tool, how to drive each
one from the console, and the end-to-end workflows they fit into. If you just
want to get moving, read [QUICKSTART.md](QUICKSTART.md) first and come back here
when you need the detail.

One rule before anything else: **only test apps, devices, and emulators you own
or have written permission to assess.** The practice targets in section 10 exist
so you have something legal to learn on.

---

## Table of contents

1. [Install and first run](#1-install-and-first-run)
2. [How the console works](#2-how-the-console-works)
3. [Command reference](#3-command-reference)
4. [The core toolkit (bundled)](#4-the-core-toolkit-bundled)
5. [On-demand tools and how to install them](#5-on-demand-tools-and-how-to-install-them)
6. [Devices and emulators](#6-devices-and-emulators)
7. [Intercepting HTTPS (proxy + certificates)](#7-intercepting-https-proxy--certificates)
8. [Going dynamic with Frida](#8-going-dynamic-with-frida)
9. [Rooting, honestly](#9-rooting-honestly)
10. [Practice targets](#10-practice-targets)
11. [Keeping everything current](#11-keeping-everything-current)
12. [Moving the folder / offline rebuild](#12-moving-the-folder--offline-rebuild)
13. [Troubleshooting](#13-troubleshooting)
14. [Where files live](#14-where-files-live)

---

## 1. Install and first run

There is nothing to install in the usual sense. CyberHost ships as a single
Windows ZIP with its own JDK 17 and Python 3.11 inside it, so it never touches
your system Python, JAVA_HOME, or PATH.

1. Download `CyberHost-APE-<version>-windows.zip` from the Releases page.
2. Unzip it anywhere you like — a folder, a USB stick, wherever. Avoid a path
   with unusual characters if you can; a plain `C:\Tools\CyberHost-APE\` is
   ideal.
3. Double-click **`CyberHost.bat`**. The banner comes up and you land at the
   prompt:

   ```
   12 core tools loaded · 0 device(s) connected
   cyberhost>
   ```

That first line is a quick health check — how many bundled tools were found and
how many devices are currently reachable over adb.

Everything runs offline. The only time CyberHost reaches the network is when you
ask it to (`install`, `update`, `targets --install`, `frida setup`), and even
then it only talks to the official source for whatever you requested.

### Running single commands without opening the console

Anything you can type at `cyberhost>` also works as a one-off from a normal
terminal, which is handy for scripts or a quick check:

```
CyberHost.bat list core
CyberHost.bat install mobsf
CyberHost.bat doctor
```

Same command layer, same behavior — the interactive shell and the one-off mode
can't drift apart because they share the code underneath.

### Linux/macOS from source

The ZIP is Windows-first. On Linux or macOS you can run from source: Python
3.11+, `pip install -r requirements.txt`, then `python -m cyberhost`. Tools that
are marked Windows-only in the manifest (scrcpy, jd-gui, mitmproxy binary, ZAP,
nmap) won't be offered on those platforms.

---

## 2. How the console works

CyberHost is a REPL, like `msfconsole` or `recon-ng`. You keep a small amount of
state between commands — a **selected tool** and a **target** — and most of your
work is a short loop of `use` → `target` → `run`.

```
cyberhost> use jadx
✓ using jadx — Dex→Java decompiler, includes jadx and jadx-gui
cyberhost (jadx)> target app.apk
✓ target set: app.apk
cyberhost (jadx)> run
```

Notice the prompt changes to `cyberhost (jadx)>` once a tool is selected, so you
always know what `run` will fire.

A few things that make it faster to live in:

- **Tab-completion** on command names and tool names. Hit Tab after `use ` to
  see what's available.
- **History** persists across sessions in `.cyberhost_history` in the folder.
  Up-arrow and Ctrl-R (reverse search) work.
- **`run` is smart about the target.** If you've set a target and run with no
  arguments, CyberHost passes the target to the tool for you. If you pass your
  own arguments, it uses those instead and leaves the target alone.
- **`run <tool> [args]`** lets you fire a specific tool without `use`-ing it
  first, e.g. `run adb devices`.
- **`exit`** (or `quit`) leaves; `help` or `?` is always there.

---

## 3. Command reference

Every command, what it does, and how you actually use it. Syntax uses
`<required>` and `[optional]`.

### help

```
help            # list every command with a one-line description
help run        # usage for a single command
```

### list

Show the tool catalog. Core tools ship in the ZIP; on-demand tools are fetched
when you ask. Installed tools show their resolved version.

```
list                 # everything, grouped by category
list core            # only the bundled tools
list on-demand       # only the install-on-request tools
list installed       # only what you've installed so far
```

`ls` is an alias.

### search

Find a tool by name, description, or category.

```
search decompile
search frida
search proxy
```

### use / target / run

The core loop.

```
use jadx                 # select a tool
target C:\apps\app.apk   # set what to operate on (APK path or package name)
run                      # run the selected tool against the target
```

`run` also takes a tool and arguments directly:

```
run adb devices                      # run a tool without selecting it
run apktool d app.apk -o app_src     # pass the tool's own flags
run frida-ps -U                      # list processes on a USB device
```

`target` with no argument prints the current target. If you give `run` explicit
arguments, the target is *not* auto-appended — your arguments win.

### info

Everything CyberHost knows about a tool: category, whether it's bundled, which
platforms it runs on, how it installs, its homepage, the installed version, and
the executables it provides.

```
info jadx
info mobsf
```

### devices

List everything reachable over adb — physical phones and every kind of emulator
— in one unified view.

```
devices
```

Empty list? Plug in a phone with USB debugging on, or start an emulator (see
section 6).

### emulator

Detect, launch, or connect emulators.

```
emulator list                      # show your Android SDK, AVDs, and live devices
emulator launch Pixel_6            # start an AVD (with a writable system)
emulator connect 127.0.0.1:5555    # adb-connect any host:port
emulator connect nox               # known emulators have built-in default ports
```

`emulator launch` adds `-writable-system` automatically, because that's what you
need for system-store certificate and root work.

### cert

Install a proxy's CA certificate onto the device so HTTPS can be decrypted.

```
cert install C:\Users\you\.mitmproxy\mitmproxy-ca-cert.pem
```

Details and the Android 7+ user-vs-system story are in section 7.

### proxy

Point the device's traffic at an intercepting proxy, or clear it.

```
proxy on                     # device → this machine's LAN IP, port 8080
proxy off                    # remove the proxy
proxy burp 192.168.1.10:8080 C:\burp-ca.pem   # use your own Burp + install its CA
```

### frida

Set up the matching `frida-server` on the connected device — detects the ABI,
picks the build that matches your installed Frida version, pushes it, and starts
it.

```
frida setup
```

### scripts

List the bundled Frida scripts (SSL-pinning bypass, root-detection bypass,
common hooks) and print the exact command to run one.

```
scripts
```

### install

Fetch an on-demand tool (or everything) at its current latest version.

```
install mobsf
install drozer
install all        # install every tool for your platform
install targets    # shorthand for grabbing all practice apps
```

### update

Update installed tools, or CyberHost itself. Updates re-resolve the latest
release from each tool's official source, verify checksums where the source
publishes them, and swap atomically so a failed update can't leave you with a
half-broken tool.

```
update             # update everything you've installed
update jadx        # just one tool
update --self      # update CyberHost and refresh resolver metadata
```

### targets

Legal, intentionally-vulnerable practice apps.

```
targets                     # list them with what each one teaches
targets --install diva      # download one
targets --deploy diva       # install it onto a connected device/emulator
```

### root

Honest device-root helper.

```
root check     # report root/trust status of the connected device
root guide     # a device-aware Magisk walkthrough (emulator or physical)
```

### doctor

Diagnose the environment — bundled runtimes, adb, core tools, PATH. Run this
first whenever something behaves oddly.

```
doctor
```

### bootstrap

Rebuild the Python tool environments after you've moved or copied the folder to
a new path. No-op if nothing moved. See section 12.

```
bootstrap
```

### version / exit

```
version
exit        # or quit
```

---

## 4. The core toolkit (bundled)

These ship inside the ZIP and work offline. Drive each one either with
`use <tool>` → `run`, or directly with `run <tool> [args]`. Each tool accepts
its own normal command-line arguments — the homepage in `info <tool>` is the
upstream reference if you need a flag that isn't shown here.

### platform-tools — adb, fastboot

The bundled `adb` is first-class; CyberHost uses it for everything. Common uses:

```
run adb devices                          # list attached devices
run adb install app.apk                  # sideload an APK
run adb shell pm list packages           # list installed packages
run adb shell pm path com.target.app     # find an installed app's APK path
run adb pull /data/app/.../base.apk .    # pull an APK off the device
run adb logcat                           # live device log
```

`fastboot` is there for bootloader work (used in the root guide).

### scrcpy — screen mirror and control *(Windows)*

```
run scrcpy
```

Mirrors the device to your desktop and lets you control it with mouse and
keyboard. Good for driving an app while you instrument it.

### apktool — decode and rebuild APKs

```
run apktool d app.apk -o app_decoded    # decode resources + smali
# ...edit AndroidManifest.xml, smali, resources...
run apktool b app_decoded -o patched.apk # rebuild
```

After rebuilding you must re-sign (see uber-apk-signer / apksigner) before a
device will install it.

### jadx / jadx-gui — Dex to Java decompiler

```
use jadx
target app.apk
run                         # CLI decompile; output goes to a jadx-out folder
run jadx -d out app.apk     # or be explicit about the output dir
```

The graphical decompiler (`jadx-gui`) ships in the same package under the tool's
folder in `tools/jadx/` — launch it when you want to click through classes
instead of reading files.

### dex2jar — convert dex/apk to a jar

```
run dex2jar app.apk         # produces app-dex2jar.jar
```

Pair it with a Java decompiler (jd-gui) when jadx struggles with something.

### smali / baksmali — the dex assembler/disassembler

This one takes a sub-tool as the first argument:

```
run smali baksmali disassemble classes.dex -o out_smali
# ...edit the .smali...
run smali smali assemble out_smali -o classes.dex
```

### jd-gui — Java decompiler GUI *(Windows)*

```
run jd-gui app-dex2jar.jar
```

Open a `.jar` (e.g. the one dex2jar produced) and browse the decompiled source.

### apkleaks — secret and endpoint scanner

```
run apkleaks -f app.apk
```

Scans the APK for URLs, API endpoints, keys, and other secrets. The `-f` flag is
how apkleaks takes its input file; it prints where it wrote the results.

### build-tools — apksigner, zipalign, aapt2

The official Android build-tools. `keytool` and `jarsigner` come from the
bundled JDK.

```
run aapt2 dump badging app.apk                       # package name, perms, SDK
run zipalign -p -f 4 patched.apk aligned.apk         # align before signing
run apksigner sign --ks my.keystore aligned.apk      # sign with your keystore
run apksigner verify --print-certs aligned.apk       # inspect the signature
```

### uber-apk-signer — one-command (re)signing

The fast path after `apktool b`. With no key it signs with a debug key, which is
all you need to install on a test device:

```
run uber-apk-signer -a patched.apk
```

### bundletool — .aab and split-APK handling

```
run bundletool build-apks --bundle=app.aab --output=app.apks
run bundletool install-apks --apks=app.apks           # install the right split
```

### Frida + frida-tools — instrumentation

`frida`, `frida-ps`, `frida-trace`, and `frida-ls-devices`. First get the server
running with `frida setup` (section 8), then:

```
run frida-ps -U                                        # processes on USB device
run frida -U -f com.target.app -l hook.js --no-pause   # spawn with a script
run frida-trace -U -i "open*" com.target.app           # trace native calls
```

### objection — runtime mobile exploration

Built on Frida; gives you an interactive runtime shell into an app — dump the
heap, bypass pinning, inspect keystores, etc.

```
run objection -g com.target.app explore
```

Inside objection, `android sslpinning disable` and `android keystore list` are
the two you'll reach for first.

### mitmproxy — HTTPS intercepting proxy *(Windows)*

Three front-ends ship: the terminal UI, the web UI, and the scriptable dumper.

```
run mitmproxy            # terminal UI
run mitmweb              # browser UI at http://127.0.0.1:8081
run mitmdump -w flows    # headless capture to a file
```

Pair with `proxy on` and `cert install` (section 7).

### Bundled Frida scripts

Three ready-to-load scripts live inside the `cyberhost/scripts/` package folder
and are listed by `scripts`:

- `ssl-pinning-bypass.js` — defeat common certificate pinning.
- `root-detection-bypass.js` — get past basic root/emulator checks.
- `common-hooks.js` — a grab-bag of useful hooks to build on.

Load one like:

```
run frida -U -f com.target.app -l "<path printed by `scripts`>" --no-pause
```

---

## 5. On-demand tools and how to install them

To keep the download small, heavier or less-frequently-used tools aren't in the
ZIP. `install <name>` fetches the current latest build from the official source,
verifies it, and drops it under `tools/`. After that it behaves exactly like a
core tool — `use`, `run`, `info`, `update` all work.

```
install mobsf          # then: run mobsf
list installed         # confirm what you have
```

What's available and what each is for:

| Tool | Install | What you use it for |
|---|---|---|
| **mobsf** | `install mobsf` | All-in-one automated static+dynamic analysis with a web UI. Heaviest tool here; runs as a local server (`run mobsf`). |
| **drozer** | `install drozer` | Probe an app's exported components, IPC, and attack surface. |
| **ghidra** | `install ghidra` | Reverse-engineer native `.so` libraries. Launch with `run ghidra` (ghidraRun). |
| **zap** | `install zap` | OWASP ZAP — scan the backend web services an app talks to. |
| **nmap** | `install nmap` | Port-scan and fingerprint hosts/APIs the app reaches. |
| **tcpdump** | `install tcpdump` | Push a capture binary to the device for raw packet capture. |
| **quark** | `install quark` | Behavior-based APK risk scoring (`run quark -a app.apk`). |
| **apkid** | `install apkid` | Identify packers, obfuscators, and compilers (`run apkid app.apk`). |
| **enjarify** | `install enjarify` | dex→jar translator that handles dex which trips up dex2jar. |
| **apkeep** | `install apkeep` | Download APKs from Play / APKPure / F-Droid. |
| **apkurlgrep** | `install apkurlgrep` | Pull endpoints and URLs straight out of an APK. |
| **trufflehog** | `install trufflehog` | Deep secret scanning for keys, tokens, and credentials. |
| **apk-mitm** | `install apk-mitm` | Auto-patch an APK to trust user CAs and drop pinning — the no-root interception shortcut. |
| **rms** | `install rms` | Runtime Mobile Security — a Frida-driven analysis web UI. |
| **house** | `install house` | NCC Group's Frida-based runtime analysis framework. |
| **medusa** | `install medusa` | Modular Frida instrumentation framework. |
| **fridump** | `install fridump` | Dump a process's memory through Frida. |
| **nuclei** | `install nuclei` | Template-based scanning for exposed backend endpoints. |

> **Burp Suite is not bundled** — licensing. If you use Burp, run your own copy
> and point the device at it with `proxy burp <host:port> [ca.pem]`.

---

## 6. Devices and emulators

CyberHost treats anything reachable over adb as a target — it isn't tied to one
emulator vendor.

**Android Studio AVDs.** If you have the SDK installed, `emulator list` finds it
and shows your AVDs. Launch one with:

```
emulator launch Pixel_6
devices                  # once it finishes booting it shows up here
```

**Genymotion.** In Genymotion's settings, set the ADB path to the bundled adb
(`tools/platform-tools/platform-tools/adb.exe`) so both tools share one adb
server. Then it appears in `devices` automatically.

**BlueStacks / Nox / MEmu / LDPlayer and friends.** These expose adb on a local
port. The common defaults are built in, so you can connect by name:

```
emulator connect nox          # 127.0.0.1:62001
emulator connect bluestacks   # 127.0.0.1:5555
emulator connect 127.0.0.1:21503   # or give the port yourself
```

**Waydroid** and other local-transport emulators don't need `connect` — start
them and they show up in `devices` on their own.

The quickest fully-controllable setup for cert and root work is an AVD launched
with `emulator launch` (it's writable-system), using a **Google APIs** image
rather than a **Google Play** image.

---

## 7. Intercepting HTTPS (proxy + certificates)

The goal is to read an app's TLS traffic. Two pieces: route the traffic through
a proxy, and make the device trust the proxy's CA.

### Route the traffic

```
proxy on
```

This sets the device's global HTTP proxy to your machine's LAN IP on port 8080
(mitmproxy's default). Start the proxy:

```
run mitmproxy
```

`proxy off` clears it when you're done. For your own Burp instead of mitmproxy:

```
proxy burp 192.168.1.10:8080 C:\burp-ca.pem
```

### Trust the CA

```
cert install C:\Users\you\.mitmproxy\mitmproxy-ca-cert.pem
```

Here's the part that trips everyone up. Since Android 7, the trust store is
split into **user** and **system**, and apps targeting API 24+ ignore user CAs
unless the developer explicitly opted in. So for most real apps, the certificate
has to go into the **system** store — and that needs either a rooted device or
an emulator booted writable-system.

`cert install` handles this for you: it computes Android's hashed certificate
name, checks whether it can remount `/system` read-write, and if it can, installs
to the system store. If it can't, it falls back to the user store and tells you
plainly that many apps will ignore it — no pretending.

When an app still won't trust your CA (certificate pinning), you have two
no-root-required options:

- `install apk-mitm` and run it on the APK to patch out pinning and trust user
  CAs, then reinstall the patched build; or
- a Frida pinning-bypass script (section 8).

---

## 8. Going dynamic with Frida

Static analysis tells you what the code *could* do; Frida shows you what it
*does* at runtime.

First get the server onto the device:

```
frida setup
```

This finds the device's ABI, downloads the `frida-server` build that matches the
Frida version CyberHost has installed (version mismatches are the #1 cause of
Frida errors, so this matters), pushes it, makes it executable, and starts it in
the background.

Confirm it's talking:

```
run frida-ps -U        # should list the device's running processes
```

From there:

```
scripts                                                    # see bundled scripts
run frida -U -f com.target.app -l "<script path>" --no-pause
run objection -g com.target.app explore                    # interactive runtime shell
```

Objection is the friendliest entry point — once you're in its shell,
`android sslpinning disable` kills most pinning without writing a line of
JavaScript.

---

## 9. Rooting, honestly

CyberHost does not ship a magic one-click root, because one doesn't exist for
real phones. What it gives you is an accurate status check and a careful guide.

```
root check     # is this device rooted? shows adb-root, su, Magisk, build tags
root guide     # a walkthrough tailored to what's connected
```

For **emulators**, the easy path is a Google APIs / AOSP image, where `adb root`
just works (`root check` tries this for you). For a realistic Magisk root on a
Play image, `root guide` points you through the rootAVD flow on a writable-system
AVD.

For **physical devices**, `root guide` lays out the general Magisk workflow —
unlock bootloader, patch boot.img, flash — with the warnings that matter:
unlocking **erases all data**, can void the warranty, may trip Knox/SafetyNet
permanently, and a wrong boot.img can brick the phone. Follow a guide specific to
your exact model and firmware; the built-in one is the shape, not the specifics.

---

## 10. Practice targets

Legal, intentionally-vulnerable apps so you have something to learn on without
touching a real system.

```
targets                     # list them and what each teaches
targets --install diva      # download one into ./targets/diva/
targets --deploy diva       # install it on the connected device
```

What's available:

- **diva** — Damn Insecure and Vulnerable App. The classic: insecure logging and
  storage, hardcoded secrets, SQL injection, input-validation bugs.
- **insecurebankv2** — a bank app with a broad surface: auth flaws, insecure
  storage, broken crypto, exported components, a backend API to poke at.
- **androgoat** — Kotlin app mapped to OWASP MASVS: storage, crypto, network,
  platform, code-quality categories.
- **pivaa** — a modern successor to DIVA with broad MASTG-style issues.
- **mastg-crackmes** — OWASP reversing and anti-tamper challenges, including
  root/tamper detection bypass and native code.

Each lands in `targets/<name>/` with a README describing the learning
objectives. They are deliberately broken — **keep them on an emulator or an
isolated device, never on a shared network.**

---

## 11. Keeping everything current

There are no hardcoded versions or download URLs anywhere in CyberHost. Every
version is resolved live from the tool's official source (GitHub Releases, the
Google Android repository, PyPI, npm) when you build, install, or update. That's
why updating is simply:

```
update             # everything installed, each to its current latest
update jadx        # one tool
update --self      # CyberHost's own code + refreshed resolver metadata
```

Each update downloads, verifies the checksum when the source publishes one, and
swaps the tool into place atomically. If an update fails partway, the existing
install is left intact.

---

## 12. Moving the folder / offline rebuild

The whole point is portability — you can zip the folder, move it to another path
or another machine, or run it off a USB stick. The bundled JDK and most tools
don't care where they live.

The exception is the Python-based tools (apkleaks, Frida, objection, and the
on-demand pip tools), which use virtual environments that record absolute paths.
After moving the folder to a new location, run:

```
bootstrap
```

It rebuilds those environments in place using the wheels cached inside the
folder, so it works with no network. If you didn't move anything, it's a no-op.
CyberHost also runs this automatically on startup if it notices the folder has
moved.

---

## 13. Troubleshooting

**Start here:** `doctor`. It checks the bundled runtimes, adb, the core tools,
and PATH wiring, and tells you what's wrong in plain terms.

A few specific ones:

- **A tool says "not installed" even though it's core.** You probably moved the
  folder — run `bootstrap`.
- **`devices` shows nothing.** USB debugging off, no emulator running, or the
  emulator uses its own adb server. Try `emulator list`, start/launch something,
  or `emulator connect <host:port>`.
- **Frida throws a version/handshake error.** The server and client versions
  don't match. Re-run `frida setup` — it always fetches the server build that
  matches your installed Frida.
- **The proxy is on but you see no traffic.** The device must be able to reach
  your machine's LAN IP (same network, firewall not blocking 8080), and most
  apps need the CA in the *system* store — see section 7.
- **An install or update fails.** It's almost always the network or a source
  being briefly unavailable. The atomic swap means nothing was half-installed;
  just run it again.
- **Unicode looks wrong in an old terminal.** Launch through `CyberHost.bat`,
  which sets up a UTF-8 console.

---

## 14. Where files live

Everything stays inside the CyberHost folder — delete the folder and it's all
gone, nothing left behind on your system.

- `tools/` — installed tools and their versions (`installed.lock.json` records
  what's installed and from where).
- `targets/` — downloaded practice apps, each with its own README.
- `runtime/` — the bundled JDK and Python.
- `cyberhost/scripts/` — the bundled Frida scripts.
- `.cyberhost_history` — your command history.

---

*CyberHost APE · by TCH · authorized / educational use only.*
*Inspired by Appie (Dinesh Shetty). Every bundled tool is the work of its own
authors.*
