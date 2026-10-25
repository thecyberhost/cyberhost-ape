"""The shared command layer dispatches correctly (no network needed)."""

from cyberhost.commands import COMMANDS, command_names, dispatch
from cyberhost.context import Session


def test_all_commands_registered():
    for required in ("help", "list", "search", "use", "target", "run", "info",
                     "devices", "emulator", "cert", "frida", "scripts", "install",
                     "update", "targets", "root", "proxy", "doctor", "version", "exit"):
        assert required in COMMANDS, f"{required} command missing"


def test_version_and_help(tmp_home):
    s = Session()
    assert dispatch(s, "version") == 0
    assert dispatch(s, "help") == 0
    assert dispatch(s, "help list") == 0


def test_list_and_search(tmp_home):
    s = Session()
    assert dispatch(s, "list") == 0
    assert dispatch(s, "list core") == 0
    assert dispatch(s, "search frida") == 0


def test_use_sets_current_tool(tmp_home):
    s = Session()
    assert dispatch(s, "use jadx") == 0
    assert s.current_tool is not None and s.current_tool.name == "jadx"
    assert s.prompt() == "cyberhost (jadx)> "


def test_target_sets_target(tmp_home):
    s = Session()
    dispatch(s, "target com.example.app")
    assert s.target == "com.example.app"


def test_unknown_command(tmp_home):
    s = Session()
    assert dispatch(s, "flibbertigibbet") == 127


def test_exit_sentinel(tmp_home):
    s = Session()
    assert dispatch(s, "exit") == -1
    assert dispatch(s, "quit") == -1


def test_use_unknown_tool(tmp_home):
    s = Session()
    assert dispatch(s, "use not-a-real-tool") == 1


def test_command_names_sorted():
    names = command_names()
    assert names == sorted(names)
