import os
import socket
import ssl
import time

class Conn:
    def __init__(self, public_addr, remote_addr):
        self.public_addr = public_addr
        self.remote_addr = remote_addr
        self.sock = None

        self.server_side = self.public_addr[0] > self.remote_addr[0]
        self.create_context()

    def close(self):
        if not self.sock:
            return

        self.sock.close()
        self.sock = None

    def write(self, data):
        return self.sock.sendall(data)

    def read(self):
        return self.sock.recv(4096)

    def bind_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        sock.settimeout(3)

        sock.bind(('', self.public_addr[1]))

        return sock

    def create_context(self):
        proto = ssl.PROTOCOL_TLS_SERVER if self.server_side else ssl.PROTOCOL_TLS_CLIENT
        context = ssl.SSLContext(proto)

        if self.server_side:
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
        sock = None

        for _ in range(1, 10):
            try:
                sock = self.bind_socket()
                sock.connect(self.remote_addr)

                self.sock = self.context.wrap_socket(sock=sock, server_side=self.server_side)
                self.sock.settimeout(None)

                return

            except ConnectionRefusedError:
                time.sleep(1)

            except socket.timeout:
                pass

            if sock:
                sock.close()

        raise Exception('Failed to connect to peer')
