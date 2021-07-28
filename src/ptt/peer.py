import json
import socket
import struct

from conn import Conn

class Peer():
    def __init__(self, app, alias, local_port=0, remote_ip='', remote_port=0):
        self.app = app
        self.alias = alias
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port

        self.conn = None
        self.sock = None

    def bind_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        self.sock.bind(('', self.local_port))
        _, self.local_port = self.sock.getsockname()

    def connect(self):
        try:
            self.conn = Conn((self.app.public_ip, self.local_port), (self.remote_ip, self.remote_port))
            self.conn.connect()
        except Exception as e:
            self.conn = None
            raise e

    def run(self):
        data = bytes()
        size = 0

        def handle_chunk(chunk=bytes()):
            nonlocal data
            nonlocal size

            if chunk:
                data += chunk

            if size == 0 and len(data) >= 4:
                size = struct.unpack_from('!I', data)[0]

            if len(data) - 4 >= size > 0:
                payload = data[4: 4 + size]
                data = data[4 + size:]
                size = 0

                try:
                    msg = json.loads(payload.decode())
                    msg['peer'] = self.alias
                    self.app.recvd.put(msg)
                except Exception as e:
                    print(e)

                handle_chunk()

        while self.is_connected():
            chunk = self.conn.read()

            if not chunk:
                self.conn.close()
                break

            handle_chunk(chunk)

        self.conn = None

    def is_connected(self):
        return self.conn and self.conn.is_connected()

    def add_remote(self, remote_ip, remote_port):
        if self.remote_ip and self.remote_port:
            raise Exception(f'Peer {self.alias} already has remote info')

        sql = f'''UPDATE peers
            SET remote_ip = "{remote_ip}",
                remote_port = "{remote_port}"
            WHERE
                alias = "{self.alias}"'''

        self.app.db_cursor.execute(sql)
        self.app.db_conn.commit()

        self.remote_ip = remote_ip
        self.remote_port = remote_port

    def close(self):
        if self.conn:
            self.conn.close()

        if self.sock:
            self.sock.close()

    def create(self):
        sql = f'SELECT 1 FROM peers WHERE local_port="{self.local_port}" LIMIT 1'

        if self.app.db_cursor.execute(sql).fetchone():
            raise Exception(f'Peer "{self.alias}" already created')

        sql = f'INSERT INTO peers VALUES ("{self.alias}", {self.local_port}, "", 0)'

        self.app.db_cursor.execute(sql)
        self.app.db_conn.commit()

    def delete(self):
        sql = f'DELETE FROM peers WHERE alias="{self.alias}"'

        self.app.db_cursor.execute(sql)
        self.app.db_conn.commit()

        self.close()

    def read(self, bufsize=4096):
        return self.conn.read(bufsize)

    def write(self, data):
        return self.conn.write(data)

    def send_message(self, msg):
        payload = json.dumps(msg).encode()
        header = struct.pack('!I', len(payload))

        return self.write(header + payload)
