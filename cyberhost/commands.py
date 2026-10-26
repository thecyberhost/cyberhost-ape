"""The command layer — every console command in one place.

Each handler has the signature ``handler(session, args) -> int`` and returns a
process-style exit code (0 == ok). Both the interactive REPL (`shell.py`) and
the one-off argv mode (`__main__.py`) dispatch through :func:`dispatch`, so the
two UXs can never drift apart.
"""

from __future__ import annotations

from . import __version__, frida_helper, proxy, root, runner, updater
from . import cert as cert_mod
from . import doctor as doctor_mod
from . import emulator as emu
from . import targets as targets_mod
from .banner import console, err, info, ok, step, warn
from .context import Session
from .device import list_devices
from .registry import Tool
from .resolver import ResolutionError

# Category display order / labels for `list`.
_CATEGORY_LABELS = {
    "runtime": "Bundled runtimes",
    "device": "Device & runtime",
    "static": "Reverse engineering / static",
    "signing": "APK build / signing",
    "dynamic": "Dynamic / instrumentation",
    "interception": "Interception / proxy",
    "network": "Network / scanning",
    "acquisition": "APK acquisition",
    "allinone": "All-in-one",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_tool(session: Session, name: str) -> Tool | None:
    t = session.manifest.get(name)
    if not t:
        err(f"unknown tool {name!r}. Try `search {name}` or `list`.")
    return t


def _ver_cell(session: Session, t: Tool) -> str:
    inst = session.lock.installed_version(t.name)
    if inst:
        return f"[green]{inst}[/green]"
    return "[dim]core (ships in ZIP)[/dim]" if t.core else "[dim]on-demand[/dim]"


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_help(session: Session, args: list[str]) -> int:
    if args and args[0] in COMMANDS:
        name = args[0]
        console.print(f"[bold]{name}[/bold] — {COMMANDS[name][1]}")
        usage = COMMANDS[name][2]
        if usage:
            console.print(f"  usage: [cyan]{usage}[/cyan]")
        return 0
    console.rule("[bold cyan]Commands")
    for name, (_fn, desc, _usage) in COMMANDS.items():
        console.print(f"  [bold cyan]{name:12}[/bold cyan] {desc}")
    console.print("")
    step("try:  list   ·   use jadx   ·   target app.apk   ·   run   ·   devices")
    return 0


def cmd_list(session: Session, args: list[str]) -> int:
    flt = args[0] if args else "all"
    cats = session.manifest.categories()
    console.rule("[bold cyan]Tools")
    for cat, label in _CATEGORY_LABELS.items():
        tools = [t for t in cats.get(cat, [])]
        if flt == "core":
            tools = [t for t in tools if t.core]
        elif flt in ("optional", "on-demand"):
            tools = [t for t in tools if not t.core]
        elif flt == "installed":
            tools = [t for t in tools if session.lock.is_installed(t.name)]
        if not tools:
            continue
        console.print(f"\n[bold]{label}[/bold]")
        for t in tools:
            tag = "[cyan]core[/cyan]" if t.core else "[yellow]on-demand[/yellow]"
            console.print(f"  {t.name:16} {tag:20} {_ver_cell(session, t)}")
            console.print(f"      [dim]{t.description}[/dim]")
    step("install an on-demand tool:  install mobsf   ·   details:  info <tool>")
    return 0


def cmd_search(session: Session, args: list[str]) -> int:
    if not args:
        err("usage: search <term>")
        return 2
    term = " ".join(args).lower()
    hits = [t for t in session.manifest.tools
            if term in t.name.lower() or term in t.description.lower()
            or term in t.category.lower()]
    if not hits:
        warn(f"no tools match {term!r}")
        return 0
    for t in hits:
        tag = "core" if t.core else "on-demand"
        console.print(f"  [bold]{t.name}[/bold] [{tag}] — {t.description}")
    return 0


def cmd_use(session: Session, args: list[str]) -> int:
    if not args:
        err("usage: use <tool>")
        return 2
    t = _resolve_tool(session, args[0])
    if not t:
        return 1
    session.current_tool = t
    ok(f"using {t.name} — {t.description}")
    if not session.lock.is_installed(t.name) and not t.core:
        warn(f"{t.name} is on-demand and not installed yet → `install {t.name}`")
    step("set a target:  target <apk-or-package>   then:  run")
    return 0


def cmd_target(session: Session, args: list[str]) -> int:
    if not args:
        if session.target:
            info(f"current target: {session.target}")
        else:
            err("usage: target <apk-path-or-package-name>")
        return 0
    session.target = args[0]
    ok(f"target set: {session.target}")
    if session.current_tool:
        step("run it:  run")
    else:
        step("pick a tool:  use jadx   (then `run`)")
    return 0


def cmd_run(session: Session, args: list[str]) -> int:
    # `run <tool> [args]` selects on the fly; otherwise use the current tool.
    tool = session.current_tool
    if args and session.manifest.get(args[0]):
        tool = session.manifest.get(args[0])
        args = args[1:]
    if not tool:
        err("no tool selected — `use <tool>` first, or `run <tool> [args]`")
        return 2
    # Append the target automatically if the user gave no positional args.
    run_args = list(args)
    if not run_args and session.target:
        run_args = [session.target]
        info(f"using target: {session.target}")
    try:
        return runner.run(tool, run_args, lock=session.lock)
    except runner.RunError as e:
        err(str(e))
        return 1


def cmd_info(session: Session, args: list[str]) -> int:
    name = args[0] if args else (session.current_tool.name if session.current_tool else None)
    if not name:
        err("usage: info <tool>")
        return 2
    t = _resolve_tool(session, name)
    if not t:
        return 1
    console.rule(f"[bold cyan]{t.name}")
    console.print(f"  {t.description}\n")
    console.print(f"  category     {t.category}")
    console.print(f"  bundled      {'yes (core, offline)' if t.core else 'no (on-demand)'}")
    console.print(f"  platforms    {', '.join(t.platforms)}")
    console.print(f"  install      {t.install}  (source: {t.source.get('type','?')})")
    console.print(f"  homepage     {t.homepage or '—'}")
    inst = session.lock.installed_version(t.name)
    console.print(f"  installed    {inst or '[dim]not installed[/dim]'}")
    if t.bin:
        console.print(f"  provides     {', '.join(t.bin)}")
    return 0


def cmd_devices(session: Session, args: list[str]) -> int:
    devs = list_devices()
    if not devs:
        warn("no devices connected")
        step("start an emulator (`emulator list`) or connect one "
             "(`emulator connect <host:port>`)")
        return 0
    ok(f"{len(devs)} device(s):")
    for d in devs:
        info("  " + d.label)
    return 0


def cmd_emulator(session: Session, args: list[str]) -> int:
    sub = args[0] if args else "list"
    rest = args[1:]
    if sub == "list":
        emu.print_detection()
    elif sub == "connect":
        if not rest:
            err("usage: emulator connect <host:port | genymotion|bluestacks|nox|...>")
            return 2
        emu.connect(rest[0])
    elif sub == "launch":
        if not rest:
            err("usage: emulator launch <avd-name>   (see `emulator list`)")
            return 2
        emu.launch_avd(rest[0], writable_system=True)
    else:
        err(f"unknown emulator subcommand {sub!r} (list|connect|launch)")
        return 2
    return 0


def cmd_cert(session: Session, args: list[str]) -> int:
    if not args or args[0] != "install":
        err("usage: cert install <path-to-ca.pem>")
        return 2
    if len(args) < 2:
        err("provide the CA PEM path, e.g. cert install ~/.mitmproxy/mitmproxy-ca-cert.pem")
        return 2
    return 0 if cert_mod.install(args[1]) else 1


def cmd_frida(session: Session, args: list[str]) -> int:
    if args and args[0] == "setup":
        return 0 if frida_helper.setup() else 1
    err("usage: frida setup")
    return 2


def cmd_scripts(session: Session, args: list[str]) -> int:
    frida_helper.print_scripts()
    return 0


def cmd_install(session: Session, args: list[str]) -> int:
    if not args:
        err("usage: install <tool|all>")
        return 2
    if args[0] == "targets":
        return cmd_targets(session, ["--install", "all"])
    names = [t.name for t in session.manifest.for_platform()] if args[0] == "all" else [args[0]]
    rc = 0
    for name in names:
        t = session.manifest.get(name)
        if not t:
            err(f"unknown tool {name!r}")
            rc = 1
            continue
        try:
            updater.install_tool(t, lock=session.lock)
        except (updater.InstallError, ResolutionError) as e:
            err(f"{name}: {e}")
            rc = 1
    session.reload()
    return rc


def cmd_update(session: Session, args: list[str]) -> int:
    if args and args[0] in ("--self", "self"):
        return 0 if updater.self_update() else 1
    if not args or args[0] in ("--all", "all"):
        targets = [t for t in session.manifest.tools if session.lock.is_installed(t.name)]
        if not targets:
            warn("nothing installed yet")
            return 0
    else:
        t = session.manifest.get(args[0])
        if not t:
            err(f"unknown tool {args[0]!r}")
            return 1
        targets = [t]
    rc = 0
    for t in targets:
        try:
            updater.update_tool(t, lock=session.lock)
        except (updater.InstallError, ResolutionError) as e:
            err(f"{t.name}: {e}")
            rc = 1
    session.reload()
    return rc


def cmd_targets(session: Session, args: list[str]) -> int:
    if not args:
        targets_mod.list_targets()
        return 0
    if args[0] == "--install":
        which = args[1] if len(args) > 1 else "all"
        names = [t.name for t in targets_mod.TARGETS] if which == "all" else [which]
        return 0 if all(targets_mod.install(n) for n in names) else 1
    if args[0] == "--deploy":
        if len(args) < 2:
            err("usage: targets --deploy <name>")
            return 2
        return 0 if targets_mod.deploy(args[1]) else 1
    err("usage: targets [--install <name|all>] [--deploy <name>]")
    return 2


def cmd_root(session: Session, args: list[str]) -> int:
    sub = args[0] if args else "check"
    if sub == "check":
        root.check()
    elif sub == "guide":
        root.guide()
    else:
        err("usage: root <check|guide>")
        return 2
    return 0


def cmd_proxy(session: Session, args: list[str]) -> int:
    if not args:
        err("usage: proxy <on|off|burp> [host:port]")
        return 2
    sub = args[0]
    if sub == "on":
        return 0 if proxy.on(args[1] if len(args) > 1 else None) else 1
    if sub == "off":
        return 0 if proxy.off() else 1
    if sub == "burp":
        if len(args) < 2:
            err("usage: proxy burp <host:port> [ca.pem]")
            return 2
        return 0 if proxy.burp(args[1], args[2] if len(args) > 2 else None) else 1
    err("usage: proxy <on|off|burp> [host:port]")
    return 2


def cmd_doctor(session: Session, args: list[str]) -> int:
    return 0 if doctor_mod.run() else 1


def cmd_bootstrap(session: Session, args: list[str]) -> int:
    """Rebuild relocated Python tool environments offline (no-op if unchanged)."""
    ok("bootstrap complete") if updater.bootstrap(session.lock) else warn("bootstrap had issues")
    return 0


def cmd_version(session: Session, args: list[str]) -> int:
    console.print(f"CyberHost APE v{__version__}")
    return 0


def cmd_exit(session: Session, args: list[str]) -> int:
    return -1  # sentinel: shell loop treats negative as "quit"


# ---------------------------------------------------------------------------
# registry + dispatch
# ---------------------------------------------------------------------------
# name -> (handler, description, usage)
COMMANDS: dict[str, tuple] = {
    "help":     (cmd_help, "show commands or help for one", "help [command]"),
    "list":     (cmd_list, "list tools (core vs on-demand, installed version)", "list [core|on-demand|installed]"),
    "search":   (cmd_search, "search tools by name/description", "search <term>"),
    "use":      (cmd_use, "select a tool to work with", "use <tool>"),
    "target":   (cmd_target, "set the APK path or package to operate on", "target <apk|package>"),
    "run":      (cmd_run, "run the selected tool (or `run <tool> [args]`)", "run [tool] [args...]"),
    "info":     (cmd_info, "show details about a tool", "info <tool>"),
    "devices":  (cmd_devices, "list connected devices/emulators", "devices"),
    "emulator": (cmd_emulator, "detect/connect/launch emulators", "emulator <list|connect|launch> [arg]"),
    "cert":     (cmd_cert, "install a proxy CA to the device", "cert install <ca.pem>"),
    "frida":    (cmd_frida, "set up frida-server on the device", "frida setup"),
    "scripts":  (cmd_scripts, "list the bundled Frida scripts", "scripts"),
    "install":  (cmd_install, "install an on-demand tool (or all)", "install <tool|all>"),
    "update":   (cmd_update, "update tools / CyberHost itself", "update [<tool>|--all|--self]"),
    "targets":  (cmd_targets, "legal vulnerable practice apps", "targets [--install <name|all>|--deploy <name>]"),
    "root":     (cmd_root, "check or guide device rooting", "root <check|guide>"),
    "proxy":    (cmd_proxy, "set/clear device proxy to the interceptor", "proxy <on|off|burp> [host:port]"),
    "doctor":   (cmd_doctor, "diagnose the environment", "doctor"),
    "bootstrap":(cmd_bootstrap, "rebuild tool envs after moving the folder", "bootstrap"),
    "version":  (cmd_version, "show the CyberHost APE version", "version"),
    "exit":     (cmd_exit, "leave the console", "exit"),
}
# aliases
COMMANDS["quit"] = COMMANDS["exit"]
COMMANDS["?"] = COMMANDS["help"]
COMMANDS["ls"] = COMMANDS["list"]


def dispatch(session: Session, line: str) -> int:
    parts = line.strip().split()
    if not parts:
        return 0
    name, args = parts[0].lower(), parts[1:]
    entry = COMMANDS.get(name)
    if not entry:
        err(f"unknown command {name!r} — type `help`")
        return 127
    return entry[0](session, args)


def command_names() -> list[str]:
    return sorted(COMMANDS.keys())
