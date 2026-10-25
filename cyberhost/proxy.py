"""Device proxy control — point device traffic at the bundled interceptor.

`proxy on`  sets the device's global HTTP proxy to this host's LAN IP + the
interceptor port (mitmproxy's default 8080). `proxy off` clears it. For a user's
own Burp, pass an explicit host:port.
"""

from __future__ import annotations

import socket

from .banner import err, info, ok, step
from .device import clear_proxy, list_devices, set_proxy

DEFAULT_PORT = 8080


def host_lan_ip() -> str:
    """Best-effort LAN IP that a device on the same network can reach."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packets sent; just picks the route
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def on(host_port: str | None = None, serial: str | None = None) -> bool:
    if not list_devices():
        err("no device connected")
        return False
    target = host_port or f"{host_lan_ip()}:{DEFAULT_PORT}"
    info(f"routing device traffic through {target}")
    if not set_proxy(target, serial=serial):
        return False
    step(f"start the interceptor:  run mitmproxy --listen-port {target.split(':')[-1]}")
    step("then install its CA:  cert install <path-to-ca.pem>")
    return True


def off(serial: str | None = None) -> bool:
    if not list_devices():
        err("no device connected")
        return False
    clear_proxy(serial=serial)
    return True


def burp(host_port: str, pem: str | None = None, serial: str | None = None) -> bool:
    """Point the device at a user's own Burp and (optionally) install its CA."""
    ok(f"configuring device for Burp at {host_port}")
    if not on(host_port, serial=serial):
        return False
    if pem:
        from . import cert
        cert.install(pem, serial=serial)
    else:
        step("export Burp's CA (Proxy → Options → Import/Export CA) then "
             "`cert install <burp-ca.pem>`")
    return True
