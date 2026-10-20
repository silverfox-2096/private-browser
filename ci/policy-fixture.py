#!/usr/bin/env python3
"""Credential-free HTTP/UDP operations for disposable policy namespaces only."""
import http.server
import json
import os
import socket
import sys
import threading
import time


def emit(**record):
    print(json.dumps(record), flush=True)


def response(sock):
    data = b''
    while b'\r\n\r\n' not in data:
        part = sock.recv(4096)
        if not part:
            raise ConnectionResetError('EOF before response')
        data += part
    header, body = data.split(b'\r\n\r\n', 1)
    length = next(int(x.split(b':', 1)[1]) for x in header.split(b'\r\n') if x.lower().startswith(b'content-length:'))
    while len(body) < length:
        body += sock.recv(length - len(body))
    return int(header.split()[1])


def request(sock, marker):
    emit(attempt=True, marker=marker)
    sock.sendall(('GET /' + marker + ' HTTP/1.1\r\nHost: fixture\r\n\r\n').encode())
    return response(sock)


def serve(port):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def do_GET(self):
            emit(observed=True, marker=self.path.lstrip('/'))
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'ok')
        def log_message(self, *args):
            pass
    class V6(http.server.ThreadingHTTPServer):
        address_family = socket.AF_INET6
    class ExternalV6(V6):
        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            super().server_bind()
    v6 = ExternalV6(('::', port), Handler)
    threading.Thread(target=v6.serve_forever, daemon=True).start()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(('0.0.0.0', 51820))
    def udp_server():
        while True:
            data, peer = udp.recvfrom(1024)
            emit(observed=True, marker=data.decode())
            udp.sendto(data, peer)
    threading.Thread(target=udp_server, daemon=True).start()
    emit(ready=True)
    http.server.ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()


def client(mode, host, port, marker):
    try:
        if mode == 'udp':
            emit(attempt=True, marker=marker)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(3)
            sock.sendto(marker.encode(), (host, port))
            assert sock.recv(1024) == marker.encode()
            emit(status=200, marker=marker); return 0
        emit(connect_attempt=True, marker=marker)
        sock = socket.create_connection((host, port), 3); sock.settimeout(3)
        if mode == 'existing':
            assert request(sock, 'existing-before') == 200
            emit(ready=True)
            deadline = time.monotonic() + 20
            while not os.path.exists('/signals/go'):
                if time.monotonic() > deadline:
                    raise RuntimeError('release signal missing')
                time.sleep(.05)
        status = request(sock, marker)
        emit(status=status, marker=marker)
        return 0 if status == 200 else 3
    except OSError as exc:
        emit(network_error=type(exc).__name__, errno=exc.errno, marker=marker)
        return 1
    except Exception as exc:
        emit(fixture_error=type(exc).__name__, marker=marker)
        return 3


if __name__ == '__main__':
    if sys.argv[1] == 'server':
        serve(int(sys.argv[2]))
    else:
        sys.exit(client(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]))
