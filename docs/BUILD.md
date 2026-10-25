# Building the CyberHost APE distributable

`build.py` assembles the shippable folder and produces the Windows ZIP. Every
runtime and tool is fetched at its **current latest** version resolved live from
the official source — the build never ships stale links.

## Prerequisites (build machine only)

- Python 3.11+ and `pip install -r requirements.txt`
- Internet access (the build downloads the runtimes + tools)
- ~3–4 GB free disk for the full build

## Commands

```bash
# Full build: bundled JDK + Python + all core tools + frida-servers, then ZIP.
python build.py

# Just stage the framework code/docs/launchers (fast, no downloads).
python build.py --stage-only

# Tools only, reuse an existing runtime.
python build.py --skip-runtime

# A subset of tools (handy for iterating).
python build.py --tools jadx,apktool,platform-tools

# Assemble but don't zip.
python build.py --no-zip
```

Output: `dist/CyberHost-APE/` (the assembled folder) and
`dist/CyberHost-APE-<version>-windows.zip`.

## What the full build does

1. **Stage** the `cyberhost` package, launchers (`CyberHost.bat`,
   `cyberhost.sh`), `assets/`, `docs/`, and top-level docs into
   `dist/CyberHost-APE/`.
2. **Runtimes** → `runtime/jdk` and `runtime/python` (portable, relocatable),
   then install CyberHost's own deps into the bundled Python.
3. **Core tools** → `tools/<name>/`. Pip tools build a venv with the bundled
   Python and cache their wheels for offline relocation.
4. **frida-server** for `arm64-v8a`, `x86_64`, `armeabi-v7a`, `x86` →
   `tools/frida-server/`.
5. Record the install path and **zip** the folder.

## Relocation / portability

venvs embed absolute paths. The build records the install path; when a user
unzips to a different location, the console runs `bootstrap` on first launch and
rebuilds pip-tool venvs **offline** from the cached wheels. Users can also run
`bootstrap` manually.

## Size budget

Target core ZIP is ~1.2–1.5 GB. Keep heavy/occasional tools **on-demand**
(`core: false` in the manifest) so the core stays small; users pull them with
`install <tool>`.
