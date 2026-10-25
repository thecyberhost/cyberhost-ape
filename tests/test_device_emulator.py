"""Device parsing and emulator connect/detection (adb mocked)."""

from conftest import fake_cp

from cyberhost import device, emulator


def test_list_devices_parses_output(monkeypatch):
    out = (
        "List of devices attached\n"
        "emulator-5554          device product:sdk_gphone64 model:Pixel_6 device:emu64\n"
        "192.168.56.101:5555    device model:Genymotion\n"
        "RZ8N12ABCDE            unauthorized\n"
    )
    monkeypatch.setattr(device, "adb", lambda *a, **k: fake_cp(stdout=out))
    devs = device.list_devices()
    serials = {d.serial for d in devs}
    assert "emulator-5554" in serials
    assert "192.168.56.101:5555" in serials
    emu_dev = next(d for d in devs if d.serial == "emulator-5554")
    assert emu_dev.is_emulator and emu_dev.model == "Pixel_6"
    unauth = next(d for d in devs if d.serial.startswith("RZ8"))
    assert unauth.state == "unauthorized"


def test_list_devices_handles_no_adb(monkeypatch):
    def boom(*a, **k):
        raise device.AdbError("adb not found")
    monkeypatch.setattr(device, "adb", boom)
    assert device.list_devices() == []


def test_list_packages(monkeypatch):
    out = "package:com.example.app\npackage:com.foo.bar\n"
    monkeypatch.setattr(device, "adb", lambda *a, **k: fake_cp(stdout=out))
    pkgs = device.list_packages()
    assert pkgs == ["com.example.app", "com.foo.bar"]


def test_emulator_connect_known_alias(monkeypatch):
    calls = {}

    def fake_adb(*args, **kwargs):
        calls["args"] = args
        return fake_cp(stdout="connected to 127.0.0.1:62001")
    monkeypatch.setattr(emulator, "adb", fake_adb)
    assert emulator.connect("nox") is True
    assert "127.0.0.1:62001" in calls["args"]


def test_emulator_connect_bare_host_adds_port(monkeypatch):
    seen = {}

    def fake_adb(*args, **kwargs):
        seen["args"] = args
        return fake_cp(stdout="connected to 10.0.0.5:5555")
    monkeypatch.setattr(emulator, "adb", fake_adb)
    emulator.connect("10.0.0.5")
    assert "10.0.0.5:5555" in seen["args"]


def test_emulator_connect_failure(monkeypatch):
    monkeypatch.setattr(emulator, "adb",
                        lambda *a, **k: fake_cp(stdout="unable to connect", returncode=1))
    assert emulator.connect("10.0.0.9:5555") is False


def test_known_endpoints_table():
    assert "bluestacks" in emulator.KNOWN_ENDPOINTS
    assert emulator.KNOWN_ENDPOINTS["waydroid"] is None  # local transport
