"""Reaching an own camera through a SOCKS5 proxy when this computer is away from the camera's network. Tailscale run
without a system VPN (tailscaled --tun=userspace-networking --socks5-server=127.0.0.1:1055) gives such a proxy, as does
`ssh -D`. A camera with one ("tunnel": "host:port") is tried directly first. When it doesn't answer within DIRECT_WAIT
s, a port on this computer is used instead, whose connections the proxy carries to the camera.

A direct connection that gives no video is skipped for SKIP_DIRECT s (mine.py): another network can have something
else at the camera's address.
"""

import ipaddress
import socket
import threading

DIRECT_WAIT = 1.5
SKIP_DIRECT = 60
_forwards = {}  # (proxy, target) -> Forward
_lock = threading.Lock()


def answers(target):
    """Whether (host, port) takes a connection directly, within DIRECT_WAIT s."""
    try:
        socket.create_connection(target, timeout=DIRECT_WAIT).close()
        return True
    except OSError:
        return False


def port_for(proxy, target):
    """A port on this computer whose connections go to `target` (host, port) through `proxy` (host, port)."""
    with _lock:
        if (proxy, target) not in _forwards:
            _forwards[proxy, target] = Forward(proxy, target)
        return _forwards[proxy, target].port


class Forward:
    def __init__(self, proxy, target):
        self.proxy, self.target = proxy, target
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            client, _ = self.server.accept()
            threading.Thread(target=self._carry, args=(client,), daemon=True).start()

    def _carry(self, client):
        try:
            far = connect(self.proxy, *self.target)
        except OSError:
            client.close()  # (the reader reports the failed stream, and tries again)
            return
        for a, b in ((client, far), (far, client)):
            threading.Thread(target=_pipe, args=(a, b), daemon=True).start()


def connect(proxy, host, port, timeout=10):
    """A socket to (host, port) through a SOCKS5 proxy that needs no login."""
    s = socket.create_connection(proxy, timeout=timeout)
    try:
        s.sendall(b"\x05\x01\x00")
        if _read(s, 2) != b"\x05\x00":
            raise OSError("the tunnel's proxy refused the connection")
        try:
            address = b"\x01" + ipaddress.IPv4Address(host).packed
        except ValueError:
            address = b"\x03" + bytes([len(host.encode())]) + host.encode()
        s.sendall(b"\x05\x01\x00" + address + port.to_bytes(2, "big"))
        reply = _read(s, 4)
        if reply[1] != 0:
            raise OSError(f"the tunnel couldn't reach {host}:{port} (SOCKS error {reply[1]})")
        _read(s, (_read(s, 1)[0] if reply[3] == 3 else {1: 4, 4: 16}.get(reply[3], 0)) + 2)  # (the address it used)
        s.settimeout(None)
        return s
    except OSError:
        s.close()
        raise


def _read(s, n):
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk:
            raise OSError("the tunnel closed the connection")
        data += chunk
    return data


def _pipe(a, b):
    try:
        while chunk := a.recv(65536):
            b.sendall(chunk)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()
