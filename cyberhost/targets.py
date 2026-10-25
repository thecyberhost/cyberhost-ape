"""Legal, intentionally-vulnerable practice apps for students.

These are well-known teaching targets published by their authors specifically
for security practice. CyberHost does not bundle the binaries (keeping the repo
small); `cyberhost targets --install <name>` fetches them on demand and drops
them under ./targets/ with a README describing the learning objectives.
"""

from __future__ import annotations

from dataclasses import dataclass

from .banner import console, err, info, ok, step
from .device import install_apk, list_devices
from .platform_utils import targets_dir
from .resolver import _get_json  # reuse JSON helper
from .updater import download


@dataclass
class Target:
    name: str
    description: str
    source: dict           # {"type": "github"|"url", ...}
    learn: str             # what the student practices on it


TARGETS: list[Target] = [
    Target("diva", "Damn Insecure and Vulnerable App — classic Android vuln playground",
           {"type": "github", "repo": "payatu/diva-android",
            "asset_pattern": r"diva-beta\.apk$", "fallback_build": True},
           "insecure logging/storage, hardcoded secrets, SQLi, input validation"),
    Target("insecurebankv2", "InsecureBankv2 — bank app with a broad vuln surface",
           {"type": "github", "repo": "dineshshetty/Android-InsecureBankv2",
            "asset_pattern": r"InsecureBankv2\.apk$"},
           "auth flaws, insecure storage, broken crypto, exported components, backend API"),
    Target("androgoat", "AndroGoat — Kotlin OWASP-mapped vulnerable app",
           {"type": "github", "repo": "satishpatnayak/AndroGoat",
            "asset_pattern": r"AndroGoat\.apk$"},
           "OWASP MASVS categories: storage, crypto, network, platform, code quality"),
    Target("pivaa", "PIVAA — Purposefully Insecure and Vulnerable Android App",
           {"type": "github", "repo": "HTBridge/pivaa",
            "asset_pattern": r"pivaa\.apk$"},
           "modern successor to DIVA; broad MASTG-style issues"),
    Target("mastg-crackmes", "OWASP MASTG Crackmes — reversing & anti-tamper challenges",
           {"type": "url",
            "url": "https://github.com/OWASP/mastg-test-apps/archive/refs/heads/master.zip"},
           "reverse engineering, root/tamper detection bypass, native code"),
]

_BY_NAME = {t.name: t for t in TARGETS}


def list_targets() -> None:
    console.rule("[bold cyan]Practice targets (legal, intentionally vulnerable)")
    for t in TARGETS:
        console.print(f"  [bold]{t.name}[/bold] — {t.description}")
        console.print(f"      [dim]practice:[/dim] {t.learn}")
    step("install one:  cyberhost targets --install diva")
    step("then push to a device:  cyberhost targets --deploy diva")
    info(f"downloads land in {targets_dir()}")


def _resolve_url(t: Target) -> tuple[str, str]:
    if t.source["type"] == "url":
        return t.name, t.source["url"]
    repo = t.source["repo"]
    import re
    data = _get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    rx = re.compile(t.source["asset_pattern"])
    for a in data.get("assets", []):
        if rx.search(a["name"]):
            return data.get("tag_name", "latest"), a["browser_download_url"]
    # No release asset: fall back to the repo's default-branch archive.
    return "source", f"https://github.com/{repo}/archive/refs/heads/master.zip"


def install(name: str) -> bool:
    t = _BY_NAME.get(name)
    if not t:
        err(f"unknown target {name!r}; see `cyberhost targets`")
        return False
    out = targets_dir() / name
    out.mkdir(parents=True, exist_ok=True)
    try:
        version, url = _resolve_url(t)
    except Exception as e:
        err(f"could not resolve {name}: {e}")
        return False
    fname = url.split("?", 1)[0].rsplit("/", 1)[-1] or f"{name}.apk"
    dest = out / fname
    try:
        download(url, dest)
    except Exception as e:
        err(f"download failed: {e}")
        return False
    _write_readme(t, out, version, url)
    ok(f"{name} downloaded to {dest}")
    step(f"deploy to a device: cyberhost targets --deploy {name}")
    return True


def deploy(name: str, serial: str | None = None) -> bool:
    out = targets_dir() / name
    apks = sorted(out.glob("*.apk")) if out.exists() else []
    if not apks:
        err(f"no APK for {name}; run `cyberhost targets --install {name}` first")
        return False
    if not list_devices():
        err("no device connected")
        return False
    ok_all = True
    for apk in apks:
        ok_all &= install_apk(str(apk), serial=serial)
    return ok_all


def _write_readme(t: Target, out, version: str, url: str) -> None:
    (out / "README.md").write_text(
        f"# {t.name}\n\n{t.description}\n\n"
        f"**What you practice:** {t.learn}\n\n"
        f"- Version/tag: `{version}`\n- Source: {url}\n\n"
        "## ⚠ Legal & safe use\n"
        "This is an *intentionally vulnerable* app published by its authors for "
        "security education. Install it ONLY on a device or emulator you own and "
        "control. Never expose it to the internet or a shared network.\n\n"
        "## Quickstart\n"
        "```\ncyberhost targets --deploy " + t.name + "\ncyberhost run jadx-gui "
        + "<path-to-apk>\n```\n",
        encoding="utf-8")
