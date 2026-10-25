"""The interactive framework console (the primary UX).

Launches a branded msfconsole-style REPL at a `cyberhost>` prompt with
tab-completion, persistent history, and colored output. Degrades gracefully to a
plain `input()` loop if prompt_toolkit is unavailable, so the shell always runs.
"""

from __future__ import annotations

from .banner import console, info, ok, print_banner
from .commands import command_names, dispatch
from .context import Session
from .device import list_devices
from .platform_utils import toolkit_root

# Subcommand suggestions for nested completion.
_SUBCOMMANDS = {
    "emulator": ["list", "connect", "launch"],
    "root": ["check", "guide"],
    "proxy": ["on", "off", "burp"],
    "cert": ["install"],
    "frida": ["setup"],
    "update": ["--all", "--self"],
    "targets": ["--install", "--deploy"],
    "list": ["core", "on-demand", "installed"],
}

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    _HAVE_PTK = True
except Exception:  # pragma: no cover
    _HAVE_PTK = False


def _status_line(session: Session) -> None:
    n_core = len(session.manifest.core())
    try:
        n_dev = len(list_devices())
    except Exception:
        n_dev = 0
    console.print(
        f"[bold green]{n_core}[/bold green] core tools loaded · "
        f"[bold green]{n_dev}[/bold green] device(s) connected")
    info("type `help` for commands, `list` for tools, `exit` to quit")


if _HAVE_PTK:
    class _CyberCompleter(Completer):
        def __init__(self, session: Session):
            self.session = session

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            words = text.split()
            tool_names = [t.name for t in self.session.manifest.tools]
            # first word → command
            if len(words) <= 1 and not text.endswith(" "):
                frag = words[0] if words else ""
                for name in command_names():
                    if name.startswith(frag):
                        yield Completion(name, start_position=-len(frag))
                return
            cmd = words[0]
            frag = "" if text.endswith(" ") else words[-1]
            pool: list[str] = []
            if cmd in ("use", "info", "install", "update", "run", "search"):
                pool = tool_names
            elif cmd in _SUBCOMMANDS:
                pool = _SUBCOMMANDS[cmd]
            for name in pool:
                if name.startswith(frag):
                    yield Completion(name, start_position=-len(frag))


def run_shell() -> int:
    session = Session()
    print_banner()
    # Self-heal relocated Python tool venvs offline before the status line.
    try:
        from . import updater
        if updater.check_relocated():
            updater.bootstrap(session.lock)
            session.reload()
    except Exception:
        pass
    _status_line(session)

    read = None
    if _HAVE_PTK:
        try:
            hist = toolkit_root() / ".cyberhost_history"
            ptk = PromptSession(history=FileHistory(str(hist)),
                                completer=_CyberCompleter(session))

            def read() -> str:
                return ptk.prompt(session.prompt())
        except Exception:
            # No interactive console (piped stdin, redirected output, etc.)
            read = None
    if read is None:
        def read() -> str:
            return input(session.prompt())

    while True:
        try:
            line = read()
        except (EOFError, KeyboardInterrupt):
            console.print("")
            break
        if not line.strip():
            continue
        rc = dispatch(session, line)
        if rc == -1:  # exit sentinel
            break
    ok("goodbye — stay authorized.")
    return 0
