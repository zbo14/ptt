import ipaddress
import json
import os
import socket
import struct
import threading

from ptt import conn

class Peer:
    def __init__(
            self, daemon, alias,
            local_port=0, remote_ip=None, remote_port=0
    ):
        self.daemon = daemon

        self.alias = alias
        self.conn = None
        self.is_ipv6 = False
        self.local_port = local_port
        self.server_side = False
        self.sock = None
        self.state = ''
        self.state_lock = threading.Lock()

        self.remote_addr = ('', 0)
        self.remote_ip = remote_ip
        self.remote_port = remote_port

    def bind_socket(self):
        family = socket.AF_INET6 if self.is_ipv6 else socket.AF_INET
        self.sock = socket.socket(family, socket.SOCK_STREAM)

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
            self.conn = conn.Conn(self)
            self.conn.connect()
        except Exception:
            if self.conn:
                self.conn.close()

            self.conn = None

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

    @property
    def remote_port(self):
        return self._remote_port

    @remote_port.setter
    def remote_port(self, remote_port=''):
        if not remote_port:
            return

        sql = f'UPDATE peers SET remote_port = "{remote_port}" WHERE alias = "{self.alias}"'

        self.daemon.db_cursor.execute(sql)
        self.daemon.db_conn.commit()

        self._remote_port = remote_port
        self.remote_addr = (self.remote_addr[0], remote_port)
        self.server_side = remote_port > self.local_port

    @property
    def remote_ip(self):
        return self._remote_ip

    @remote_ip.setter
    def remote_ip(self, remote_ip):
        if not remote_ip:
            return

        ipaddr = ipaddress.ip_address(remote_ip)
        sql = f'UPDATE peers SET remote_ip = "{remote_ip}" WHERE alias = "{self.alias}"'

        self.daemon.db_cursor.execute(sql)
        self.daemon.db_conn.commit()

        self._remote_ip = remote_ip
        self.is_ipv6 = ipaddr.version == 6
        self.remote_addr = (remote_ip, self.remote_addr[1])

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
