import ipaddress
import json
import os
import socket
import struct
import threading
import time

from ptt import conn

class Peer:
    def __init__(
            self, daemon, alias,
            local_port=0, remote_ip=None, remote_port=0
    ):
        self.daemon = daemon

        self.alias = alias
        self.conn = None
        self.is_ipv6 = remote_ip and ipaddress.ip_address(remote_ip).version == 6
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.sock = None
        self.state = ''
        self.state_lock = threading.Lock()

    def init(self, is_ipv6=False, new_port=False):
        is_ipv6 = is_ipv6 or self.is_ipv6

        for _ in range(1, 10):
            family = socket.AF_INET6 if is_ipv6 else socket.AF_INET
            sock = socket.socket(family, socket.SOCK_STREAM)

            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

            try:
                sock.bind(('', 0 if new_port else self.local_port))
                local_port = sock.getsockname()[1]

                if not self.local_port:
                    self.daemon.db_write(f'INSERT INTO peers VALUES ("{self.alias}", {local_port}, "", 0)')
                    self.local_port = local_port
                else:
                    self.edit(local_port=local_port)

                self.is_ipv6 = is_ipv6
                self.sock = sock

                return local_port
            except Exception:
                sock.close()
                pass

        raise Exception(f'Peer {self.alias}: failed to find available TCP port')

    def setstate(self, state=''):
        self.state_lock.acquire()
        self.state = state
        self.state_lock.release()

    def getstate(self):
        self.state_lock.acquire()
        state = self.state
        self.state_lock.release()

        return state or 'not connected'

    def run(self):
        try:
            self.conn = conn.Conn(self)
            self.conn.connect()
        except Exception as e:
            if self.conn:
                self.conn.close()

            self.conn = None

            print(e)

            return

        self.daemon.recvd.put({
            'type': 'connect',
            'peer': self.alias,
            'data': {}
        })

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

                    if msg['type'] == 'file':
                        data = self.handle_file(data, msg['data'])

                    self.daemon.recvd.put(msg)
                except Exception as e:
                    print(e)

                handle_chunk()

        while self.is_connected():
            try:
                chunk = self.recv()

            except TimeoutError:
                continue

            except Exception as e:
                print(e)
                break

            if not chunk:
                break

            handle_chunk(chunk)

        self.disconnect()

        self.daemon.recvd.put({
            'type': 'disconnect',
            'peer': self.alias,
            'data': {}
        })

    def remote_addr(self):
        return (self.remote_ip, self.remote_port)

    def server_side(self):
        if self.remote_port > self.local_port:
            return True

        elif self.remote_port < self.local_port:
            return False

        return self.remote_ip > (self.daemon.public_ip6 if self.is_ipv6 else self.daemon.public_ip4)

    def is_connected(self):
        return self.getstate() == 'connected'

    def is_connecting(self):
        return self.getstate() == 'connecting'

    def handle_file(self, data, msg_data):
        filename = msg_data['filename']
        filesize = msg_data['filesize']

        peer_files_path = os.path.join(self.daemon.files_path, self.alias)

        if not os.path.isdir(peer_files_path):
            os.mkdir(peer_files_path)

        msg_data['filepath'] = os.path.join(peer_files_path, filename)

        with open(msg_data['filepath'], 'wb') as file:
            nread = min(len(data), filesize)

            if nread:
                file.write(data[:nread])
                data = data[nread:]

            while nread < filesize:
                chunk = self.recv()

                if not chunk:
                    raise Exception(f'Peer {self.alias}: connection closed while reading file data')

                file.write(chunk)
                nread += len(chunk)

        return data

    def edit(self, **kwargs):
        sql = ' '.join([
            'UPDATE peers SET',

            ', '.join([
                f'{key} = "{val}"' if isinstance(val, str) else f'{key} = {val}'
                for key, val in kwargs.items() if val
            ]),

            f'WHERE alias = "{self.alias}"'
        ])

        self.daemon.db_write(sql)

        if 'local_port' in kwargs and kwargs['local_port']:
            self.local_port = kwargs['local_port']

        if 'remote_ip' in kwargs and kwargs['remote_ip']:
            self.remote_ip = kwargs['remote_ip']

        if 'remote_port' in kwargs and kwargs['remote_port']:
            self.remote_port = kwargs['remote_port']

    def close(self):
        self.disconnect()

        if self.sock:
            self.sock.close()

    def disconnect(self):
        if self.is_connected():
            self.conn.close()

    def delete(self):
        self.daemon.db_write(f'DELETE FROM peers WHERE alias="{self.alias}"')
        self.close()

    def recv(self, bufsize=4096):
        return self.conn.recv(bufsize)

    def send(self, data):
        return self.conn.send(data)

    def sendmessage(self, msg_type, msg_data):
        payload = json.dumps({'type': msg_type, 'data': msg_data}).encode()
        header = struct.pack('!I', len(payload))

        return self.send(header + payload)

    def sendfile(self, file):
        return self.conn.sendfile(file)

    def send_text(self, content):
        sent_at = time.time()

        self.daemon.db_write(
            f'INSERT INTO texts VALUES ("{self.alias}", "{content}", {sent_at}, {False})'
        )

        self.sendmessage('text', {
            'content': content,
            'sent_at': sent_at
        })

    def read_texts(self):
        sql = f'SELECT * FROM texts WHERE peer="{self.alias}" ORDER BY sent_at'
        rows = self.daemon.db_read(sql).fetchall()

        return [{
            'peer': row[0],
            'content': row[1],
            'sent_at': row[2],
            'from_peer': bool(row[3])
        } for row in rows]

    def share_file(self, filepath):
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        shared_at = time.time()

        self.sendmessage('file', {
            'filename': filename,
            'filesize': filesize,
            'shared_at': shared_at
        })

        with open(filepath, 'rb') as file:
            self.sendfile(file)

        sql = f'''INSERT INTO files VALUES
            ("{self.alias}", "{filename}", "{filepath}", {filesize}, {shared_at}, {False})'''

        self.daemon.db_write(sql)

    def list_files(self):
        sql = f'SELECT * FROM files WHERE peer="{self.alias}" ORDER BY shared_at'
        rows = self.daemon.db_read(sql).fetchall()

        return [{
            'peer': row[0],
            'filename': row[1],
            'filepath': row[2],
            'filesize': row[3],
            'shared_at': row[4],
            'from_peer': bool(row[5])
        } for row in rows]
