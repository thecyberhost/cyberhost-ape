"""Branded banner + shared rich console helpers.

Renders assets/banner.txt or assets/logo.png when present, otherwise an ASCII
"CyberHost" wordmark. All colorful output in the toolkit goes through the
`console` object defined here so theming stays consistent.
"""

from __future__ import annotations

import sys

from . import __appname__, __tagline__, __version__
from .platform_utils import toolkit_root

# Windows legacy consoles default to a non-UTF-8 code page (cp1252), which
# raises UnicodeEncodeError on the box-drawing / dash glyphs used throughout.
# Reconfigure to UTF-8 with replacement so output never crashes the program.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

try:  # rich is a hard dependency, but degrade gracefully if missing
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    _HAVE_RICH = True
except Exception:  # pragma: no cover - fallback path
    _HAVE_RICH = False

    class _Plain:
        def print(self, *a, **k):
            msg = " ".join(str(x) for x in a)
            # strip the most common rich markup tokens for readability
            for tok in ("[bold]", "[/bold]", "[dim]", "[/dim]", "[red]",
                        "[/red]", "[green]", "[/green]", "[cyan]", "[/cyan]",
                        "[yellow]", "[/yellow]", "[bold red]", "[bold green]",
                        "[bold cyan]"):
                msg = msg.replace(tok, "")
            print(msg)

        def rule(self, *a, **k):
            print("-" * 60)

    console = _Plain()  # type: ignore


_ASCII = r"""
  ____      _               _   _           _
 / ___|   _| |__   ___ _ __| | | | ___  ___| |_
| |  | | | | '_ \ / _ \ '__| |_| |/ _ \/ __| __|
| |__| |_| | |_) |  __/ |  |  _  | (_) \__ \ |_
 \____\__, |_.__/ \___|_|  |_| |_|\___/|___/\__|
      |___/   A P E  ·  Android Pentesting Environment
"""


def banner() -> str:
    """Return the banner text (custom asset if present, else ASCII)."""
    asset = toolkit_root() / "assets" / "banner.txt"
    if asset.exists():
        try:
            return asset.read_text(encoding="utf-8")
        except Exception:
            pass
    return _ASCII


def print_banner() -> None:
    if _HAVE_RICH:
        body = Text(banner(), style="bold cyan")
        sub = Text(
            f"{__appname__} v{__version__} — {__tagline__}\n"
            "Authorized / educational use only.",
            style="dim",
        )
        console.print(body)
        console.print(Panel.fit(sub, border_style="cyan"))
    else:
        console.print(banner())
        console.print(f"{__appname__} v{__version__} — {__tagline__}")
        console.print("Authorized / educational use only.")


def ok(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]![/yellow] {msg}")


def err(msg: str) -> None:
    console.print(f"[bold red]✗[/bold red] {msg}")


def info(msg: str) -> None:
    console.print(f"[cyan]·[/cyan] {msg}")


def step(msg: str) -> None:
    """Beginner-friendly 'what to do next' hint."""
    console.print(f"[dim]→ {msg}[/dim]")
