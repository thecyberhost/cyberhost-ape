# Contributing to CyberHost APE

Thanks for helping make Android security education more accessible! This project
thrives on community-contributed tools and improvements.

## Ground rules

- CyberHost APE is a **legitimate, authorized-testing / educational** toolkit.
  Contributions must fit that purpose. We don't accept features whose primary
  use is unauthorized access, evasion for malicious ends, or targeting people.
- Be respectful — see the [Code of Conduct](CODE_OF_CONDUCT.md).

## Adding a tool (the common case)

Most tools need **only a manifest entry**. Edit
[`cyberhost/data/tools.yaml`](cyberhost/data/tools.yaml) and add:

```yaml
  - name: mytool
    category: static          # device|static|signing|dynamic|interception|network|acquisition|allinone|runtime
    description: "One clear line shown in `list` / `info`"
    core: false               # true only if it should ship bundled & offline
    optional: true
    platforms: [windows, macos, linux]
    install: github_release   # archive|github_release|jar|pip|npm|binary|script|docker|google
    source:
      type: github            # github|google|pypi|npm|url
      repo: owner/repo
      asset_pattern: "mytool-.*-windows-x86_64\\.zip$"
    bin: [mytool]             # executables it provides
    entry: ""                 # jar filename / python script / console-script, if needed
    homepage: https://example.com
```

**Never hardcode a version or a download URL.** The resolver fetches the current
latest from `source` at install/update time. Use `{version}`, `{os}`, `{arch}`
tokens in an `asset_pattern`/`url_template` where helpful.

Verify it resolves:

```bash
python -c "from cyberhost.registry import Manifest; from cyberhost.resolver import resolve; print(resolve(Manifest.load().get('mytool')))"
```

## Running tests & lint

```bash
pip install -r requirements.txt pytest ruff
python -m pytest -q
ruff check cyberhost
```

All tests are offline (network is mocked), so they must pass without internet.
Add a test when you change resolver/updater/device logic.

## Code layout

| Module | Responsibility |
|---|---|
| `shell.py` | interactive REPL |
| `commands.py` | command layer (shared by REPL + one-off mode) |
| `registry.py` | manifest + lockfile |
| `resolver.py` | latest-version/URL resolution |
| `updater.py` | download / verify / atomic-swap install engine |
| `runner.py` | launch a tool with the bundled runtimes |
| `device.py` · `emulator.py` | adb + universal emulator support |
| `cert.py` · `root.py` · `frida_helper.py` · `proxy.py` · `targets.py` | helpers |

## Pull requests

1. Branch from `main`.
2. Keep changes focused; update docs/tests as needed.
3. Describe what you tested (and on which OS / device).
