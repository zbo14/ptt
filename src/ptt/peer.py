import json
import os
import socket
import struct
import threading

from ptt import conn

class Peer:
    def __init__(self, daemon, alias, local_port=0, remote_ip='', remote_port=0):
        self.daemon = daemon
        self.alias = alias
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.state = ''
        self.state_lock = threading.Lock()

        self.conn = None
        self.sock = None

    def bind_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        self.sock.bind(('', self.local_port))
        _, self.local_port = self.sock.getsockname()

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
            self.conn = conn.Conn(
                self,
                (self.daemon.public_ip, self.local_port),
                (self.remote_ip, self.remote_port)
            )

            self.conn.connect()
            self.daemon.notify(f'Connected: {self.alias}')
        except Exception:
            if self.conn:
                self.conn.close()

            self.conn = None

            return

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

    def add_remote(self, remote_ip, remote_port):
        if self.remote_ip and self.remote_port:
            raise Exception(f'Peer {self.alias} already has remote info')

        sql = f'''UPDATE peers
            SET remote_ip = "{remote_ip}",
                remote_port = "{remote_port}"
            WHERE
                alias = "{self.alias}"'''

        self.daemon.db_cursor.execute(sql)
        self.daemon.db_conn.commit()

        self.remote_ip = remote_ip
        self.remote_port = remote_port

    def close(self):
        self.disconnect()

        if self.sock:
            self.sock.close()

    def disconnect(self):
        if self.is_connected():
            self.conn.close()

    def create(self):
        sql = f'SELECT 1 FROM peers WHERE local_port="{self.local_port}" LIMIT 1'

        if self.daemon.db_cursor.execute(sql).fetchone():
            raise Exception(f'Peer "{self.alias}" already created')

        sql = f'INSERT INTO peers VALUES ("{self.alias}", {self.local_port}, "", 0)'

        self.daemon.db_cursor.execute(sql)
        self.daemon.db_conn.commit()

    def delete(self):
        sql = f'DELETE FROM peers WHERE alias="{self.alias}"'

        self.daemon.db_cursor.execute(sql)
        self.daemon.db_conn.commit()

        self.close()

    def recv(self, bufsize=4096):
        return self.conn.recv(bufsize)

    def send(self, data):
        return self.conn.send(data)

    def sendmessage(self, msg):
        payload = json.dumps(msg).encode()
        header = struct.pack('!I', len(payload))

        return self.send(header + payload)

    def sendfile(self, file):
        return self.conn.sendfile(file)
