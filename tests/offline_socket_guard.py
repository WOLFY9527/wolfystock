"""Socket primitives shared by pytest and its Python child processes."""

from __future__ import annotations

import ipaddress
import socket
import sys
from typing import Any


class OutboundNetworkBlocked(RuntimeError):
    """Raised before a standard test can open a non-loopback socket."""


def _host_from_address(address: object) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return address if isinstance(address, str) else None


def is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized in {"localhost", "localhost.localdomain", "0.0.0.0", "::"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _assert_local_address(address: object, *, family: int | None = None) -> None:
    if family == getattr(socket, "AF_UNIX", object()):
        return
    host = _host_from_address(address)
    if not is_loopback_host(host):
        raise OutboundNetworkBlocked(
            f"pytest outbound network is disabled; refused address {host or '<unknown>'!r}. "
            "Use an audited @pytest.mark.network opt-in and the explicit network command."
        )


class SocketGuard:
    def __init__(self) -> None:
        self._originals: dict[str, Any] = {}
        self._audit_active = False
        self._audit_installed = False

    def _audit_event(self, event: str, args: tuple[object, ...]) -> None:
        if not self._audit_active:
            return
        if event in {"socket.connect", "socket.sendto"} and len(args) >= 2:
            sock = args[0]
            _assert_local_address(args[1], family=getattr(sock, "family", None))
        elif event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"} and args:
            host = args[0]
            if host is not None:
                _assert_local_address(str(host))

    def install(self) -> None:
        if self._originals:
            return
        self._audit_active = True
        if not self._audit_installed:
            sys.addaudithook(self._audit_event)
            self._audit_installed = True
        self._originals = {
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
            "sendto": socket.socket.sendto,
            "create_connection": socket.create_connection,
            "getaddrinfo": socket.getaddrinfo,
        }
        originals = self._originals

        def guarded_connect(sock: socket.socket, address: object) -> Any:
            _assert_local_address(address, family=sock.family)
            return originals["connect"](sock, address)

        def guarded_connect_ex(sock: socket.socket, address: object) -> Any:
            _assert_local_address(address, family=sock.family)
            return originals["connect_ex"](sock, address)

        def guarded_sendto(sock: socket.socket, data: bytes, *args: object) -> Any:
            if not args:
                raise OutboundNetworkBlocked("pytest outbound UDP send requires an explicit destination")
            _assert_local_address(args[-1], family=sock.family)
            return originals["sendto"](sock, data, *args)

        def guarded_create_connection(address: object, *args: object, **kwargs: object) -> Any:
            _assert_local_address(address)
            return originals["create_connection"](address, *args, **kwargs)

        def guarded_getaddrinfo(host: object, *args: object, **kwargs: object) -> Any:
            if host is not None:
                _assert_local_address(str(host))
            return originals["getaddrinfo"](host, *args, **kwargs)

        socket.socket.connect = guarded_connect
        socket.socket.connect_ex = guarded_connect_ex
        socket.socket.sendto = guarded_sendto
        socket.create_connection = guarded_create_connection
        socket.getaddrinfo = guarded_getaddrinfo

    def restore(self) -> None:
        self._audit_active = False
        if not self._originals:
            return
        socket.socket.connect = self._originals["connect"]
        socket.socket.connect_ex = self._originals["connect_ex"]
        socket.socket.sendto = self._originals["sendto"]
        socket.create_connection = self._originals["create_connection"]
        socket.getaddrinfo = self._originals["getaddrinfo"]
        self._originals.clear()
