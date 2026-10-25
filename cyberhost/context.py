"""Shared session state for the interactive console.

Holds the currently-selected tool (`use <tool>`) and target (`target <path>`),
plus lazily-loaded singletons for the manifest and lockfile so every command
sees the same state within a session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .registry import Lockfile, Manifest, Tool


@dataclass
class Session:
    manifest: Manifest = field(default_factory=Manifest.load)
    lock: Lockfile = field(default_factory=Lockfile)
    current_tool: Tool | None = None
    target: str | None = None  # an APK path or a package name

    def prompt(self) -> str:
        if self.current_tool:
            return f"cyberhost ({self.current_tool.name})> "
        return "cyberhost> "

    def reload(self) -> None:
        self.manifest = Manifest.load()
        self.lock = Lockfile()
