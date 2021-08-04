import os
import socket
import ssl
import time

class Conn:
    def __init__(self, peer):
        self.peer = peer
        self.sock = None

        self.create_context()

    def close(self):
        if not self.sock:
            return

        try:
            self.sock.shutdown(socket.SHUT_WR)
        except Exception:
            pass

        try:
            self.sock.close()
        except Exception:
            pass

        self.peer.setstate()
        self.sock = None

    def send(self, data):
        return self.sock.sendall(data)

    def recv(self, bufsize):
        return self.sock.recv(bufsize)

    def sendfile(self, file):
        return self.sock.sendfile(file)

    def bind_socket(self):
        family = socket.AF_INET6 if self.peer.is_ipv6 else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        sock.settimeout(10)

        sock.bind(('', self.peer.local_port))

        return sock

    def create_context(self):
        server_side = self.peer.server_side()
        proto = ssl.PROTOCOL_TLS_SERVER if server_side else ssl.PROTOCOL_TLS_CLIENT
        context = ssl.SSLContext(proto)

        if server_side:
            private_dir = os.path.normpath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'private')
            )

            context.load_cert_chain(
                os.path.join(private_dir, 'cert.pem'),
                os.path.join(private_dir, 'key.pem')
            )

        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        self.context = context

    def connect(self):
        server_side = self.peer.server_side()
        sock = None

        self.peer.setstate('connecting')

        while self.peer.is_connecting():
            try:
                sock = self.bind_socket()
                print(self.peer.is_ipv6, self.peer.remote_addr())
                sock.connect(self.peer.remote_addr())

                self.sock = self.context.wrap_socket(sock=sock, server_side=server_side)

                self.sock.setblocking(True)
                self.peer.setstate('connected')

                return

            except ConnectionRefusedError:
                time.sleep(1)

            except (socket.timeout, TimeoutError):
                pass

            if sock:
                sock.close()
                sock = None

        self.peer.setstate()

        raise Exception('Failed to connect to peer')
