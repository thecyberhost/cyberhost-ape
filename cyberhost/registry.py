"""The tool registry: the data-driven manifest + the installed lockfile.

`tools.yaml` is the single source of truth for *what* can be installed. The
lockfile (`tools/installed.lock.json`) records what *is* installed and from
where, so updates are diffable and reversible per tool.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .platform_utils import current_os, data_file, tool_home, tools_dir


@dataclass
class Tool:
    """One entry from the manifest."""

    name: str
    category: str = "misc"
    description: str = ""
    core: bool = True
    optional: bool = False
    platforms: list[str] = field(default_factory=lambda: ["windows", "macos", "linux"])
    install: str = "github_release"  # archive|github_release|pip|jar|docker|script
    source: dict[str, Any] = field(default_factory=dict)
    bin: list[str] = field(default_factory=list)
    entry: str = ""  # jar filename, python module/script, or console-script name
    launch: dict[str, Any] = field(default_factory=dict)  # e.g. {bin: main-class} for maven
    version: str = ""  # manifest's build-time snapshot; updater re-resolves latest
    notes: str = ""
    homepage: str = ""

    # -- helpers ----------------------------------------------------------
    def supports(self, os_token: str | None = None) -> bool:
        return (os_token or current_os()) in self.platforms

    @property
    def home(self) -> Path:
        return tool_home(self.name)

    @property
    def installed_marker(self) -> Path:
        return self.home / ".cyberhost_installed.json"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Tool:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


class Manifest:
    """Loaded view of tools.yaml."""

    def __init__(self, tools: list[Tool], meta: dict[str, Any]):
        self.tools = tools
        self.meta = meta
        self._by_name = {t.name: t for t in tools}

    # -- construction -----------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> Manifest:
        p = path or data_file("tools.yaml")
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        tools = [Tool.from_dict(t) for t in data.get("tools", [])]
        meta = {k: v for k, v in data.items() if k != "tools"}
        return cls(tools, meta)

    # -- queries ----------------------------------------------------------
    def get(self, name: str) -> Tool | None:
        return self._by_name.get(name)

    def for_platform(self, os_token: str | None = None) -> list[Tool]:
        return [t for t in self.tools if t.supports(os_token)]

    def core(self, os_token: str | None = None) -> list[Tool]:
        return [t for t in self.for_platform(os_token) if t.core and not t.optional]

    def optional(self, os_token: str | None = None) -> list[Tool]:
        return [t for t in self.for_platform(os_token) if t.optional]

    def categories(self) -> dict[str, list[Tool]]:
        out: dict[str, list[Tool]] = {}
        for t in self.tools:
            out.setdefault(t.category, []).append(t)
        return out


# ---------------------------------------------------------------------------
# Lockfile — what is actually installed
# ---------------------------------------------------------------------------

class Lockfile:
    """Tracks installed tool versions, source URLs, and checksums."""

    def __init__(self, path: Path | None = None):
        self.path = path or (tools_dir() / "installed.lock.json")
        self.data: dict[str, Any] = {"schema": 1, "tools": {}}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        self.data.setdefault("tools", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")

    # -- record / query ---------------------------------------------------
    def record(self, name: str, *, version: str, url: str = "",
               sha256: str = "", install: str = "") -> None:
        self.data["tools"][name] = {
            "version": version,
            "url": url,
            "sha256": sha256,
            "install": install,
        }

    def remove(self, name: str) -> None:
        self.data["tools"].pop(name, None)

    def installed_version(self, name: str) -> str | None:
        rec = self.data["tools"].get(name)
        return rec["version"] if rec else None

    def is_installed(self, name: str) -> bool:
        return name in self.data["tools"]
