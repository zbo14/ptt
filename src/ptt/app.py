import json
import os
import socket
import sqlite3
import struct
import sys
import threading
import urllib.request as request
from conn import Conn
import const

class App():
    def __init__(
            self,
            db_path=const.DEFAULT_DB_PATH,
            ident_endpoint=const.DEFAULT_IDENT_ENDPOINT,
            ipc_client_path=const.DEFAULT_IPC_CLIENT_PATH,
            ipc_server_path=const.DEFAULT_IPC_SERVER_PATH
        ):

        self.conns = {}
        self.db_conn = sqlite3.connect(db_path)
        self.db_cursor = self.db_conn.cursor()
        self.ipc_client_path = ipc_client_path
        self.ipc_server_path = ipc_server_path
        self.public_ip = request.urlopen(ident_endpoint).read().decode('utf8')
        self.socks = {}
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.server.bind(ipc_server_path)

        self.init_db()
        self.bind_sockets()

    def init_db(self):
        sql = '''CREATE TABLE IF NOT EXISTS peers
            (alias text, local_port int, remote_ip text, remote_port int)'''

        self.db_cursor.execute(sql)

        sql = '''CREATE UNIQUE INDEX IF NOT EXISTS index_local_port
            ON peers(local_port)'''

        self.db_cursor.execute(sql)

        sql = '''CREATE UNIQUE INDEX IF NOT EXISTS index_alias
            ON peers(alias)'''

        self.db_cursor.execute(sql)
        self.db_conn.commit()

    def run(self):
        done = False

        while not done:
            dgram = self.server.recv(4096)

            try:
                done = self.handle_dgram(dgram)
            except Exception as e:
                print(e)

        for conn in self.conns.values():
            conn.close()

        for sock in self.socks.values():
            sock.close()

        self.server.close()
        os.remove(self.ipc_server_path)

        self.db_conn.close()

    def handle_dgram(self, dgram):

        if not dgram:
            return True

        msg = json.loads(dgram.decode())
        msg_type = msg['type']
        msg_data = msg['data']

        data = {}

        try:
            if msg_type == 'add_peer':
                alias = msg_data['alias']
                remote_ip = msg_data['remote_ip']
                remote_port = msg_data['remote_port']
                self.add_peer(alias, remote_ip, remote_port)

            elif msg_type == 'get_peer':
                alias = msg_data['alias']
                data = self.get_peer(alias)

            elif msg_type == 'connect_peer':
                alias = msg_data['alias']
                self.connect_to(alias)

            elif msg_type == 'connected_peers':
                data['aliases'] = list(self.conns)
                data['aliases'].sort()

            elif msg_type == 'remove_peer':
                alias = msg_data['alias']
                self.remove_peer(alias)

            elif msg_type == 'reserve_local_port':
                alias = msg_data['alias']
                data['local_port'] = self.reserve_local_port(alias)
                data['public_ip'] = self.public_ip

            elif msg_type != 'stop':
                raise Exception(f'Unrecognized message type: "{msg_type}"')

            self.send_to_client({
                'error': None,
                'data': data
            })

        except Exception as e:
            self.send_to_client({
                'data': None,
                'error': str(e)
            })

        return msg_type == 'stop'

    def remove_sock(self, alias):
        if alias in self.socks:
            self.socks[alias].close()
            del self.socks[alias]

    def remove_conn(self, alias):
        if alias in self.conns:
            self.conns[alias].close()
            del self.conns[alias]

    def bind_socket(local_port=0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        sock.bind(('', local_port))

        _, local_port = sock.getsockname()

        return sock, local_port

    def add_peer(self, alias, remote_ip, remote_port):
        sql = f'SELECT * FROM peers WHERE alias="{alias}" LIMIT 1'
        row = self.db_cursor.execute(sql).fetchone()

        if row is None:
            raise Exception(f'No local port reserved for "{alias}"')

        if row[2] != '' or row[3] != 0:
            raise Exception('Contact already added')

        sql = f'''UPDATE peers
            SET remote_ip = "{remote_ip}",
                remote_port = "{remote_port}"
            WHERE
                alias = "{alias}"'''

        self.db_cursor.execute(sql)
        self.db_conn.commit()

    def get_peer(self, alias):
        sql = f'SELECT * FROM peers WHERE alias="{alias}" LIMIT 1'
        row = self.db_cursor.execute(sql).fetchone()

        if row is None:
            raise Exception(f'Peer "{alias}" not found')

        return {
            'local_port': row[1],
            'remote_ip': row[2],
            'remote_port': row[3]
        }

    def bind_sockets(self):
        sql = 'SELECT alias, local_port FROM peers'

        for alias, local_port in self.db_cursor.execute(sql):
            sock, _ = App.bind_socket(local_port)
            self.socks[alias] = sock

    def connect_to(self, alias):
        if alias in self.conns:
            raise Exception(f'Already connected to "{alias}"')

        sql = f'''SELECT local_port, remote_ip, remote_port
            FROM peers WHERE alias="{alias}" LIMIT 1'''

        row = self.db_cursor.execute(sql).fetchone()

        if row is None:
            raise Exception(f'Peer "{alias}" not found')

        if row[1] == '' or row[2] == 0:
            raise Exception('Contact not yet added')

        conn = Conn((self.public_ip, row[0]), (row[1], row[2]))
        conn.connect()

        threading.Thread(target=self.handle_conn, args=(alias, conn,), daemon=True)

        self.conns[alias] = conn

    def handle_conn(self, alias, conn):
        data = bytes()
        size = 0

        def handle_chunk(chunk=bytes()):
            if chunk:
                data += chunk

            if size == 0 and len(data) >= 4:
                size = struct.unpack_from('!I', data)

            if size > 0 and len(data) - 4 >= size:
                payload = data[4: 4 + size]
                data = data[4 + size:]
                size = 0

                try:
                    self.handle_payload(alias, conn, payload)
                except Exception as e:
                    print(e)

                handle_chunk()

        while conn.is_connected():
            chunk = conn.read()

            if not chunk:
                break

            handle_chunk(chunk)

        self.remove_conn(alias)

    def send_to_client(self, msg):
        payload = json.dumps(msg).encode()

        return self.server.sendto(payload, self.ipc_client_path)

    def handle_payload(self, alias, conn, payload):
        msg = json.loads(payload.decode())

        msg_type = msg['type']
        msg_data = msg['data']

        msg['from'] = alias

        if msg_type == 'text':
            content = msg_data['content']
            print(f'Received text (content_length={len(content)})')
            self.send_to_client(msg)

        elif msg_type == 'file':
            print('TODO')

        else:
            raise Exception(f'Unexpected message type: "{msg_type}"')

    def remove_peer(self, alias):
        self.get_peer(alias)

        sql = f'DELETE FROM peers WHERE alias="{alias}"'

        self.db_cursor.execute(sql)
        self.db_conn.commit()

        self.remove_conn(alias)
        self.remove_sock(alias)

    def reserve_local_port(self, alias):
        sql = f'SELECT 1 FROM peers WHERE alias="{alias}" LIMIT 1'

        if self.db_cursor.execute(sql).fetchone():
            raise Exception(f'Peer "{alias}" already exists')

        for _ in range(1, 10):
            sock, local_port = App.bind_socket()
            sql = f'SELECT 1 FROM peers WHERE local_port="{local_port}" LIMIT 1'

            if self.db_cursor.execute(sql).fetchone():
                sock.close()
                continue

            sql = f'INSERT INTO peers VALUES ("{alias}", {local_port}, "", 0)'
            self.db_cursor.execute(sql)
            self.db_conn.commit()

            self.socks[alias] = sock

            return local_port

        raise Exception('Failed to find available TCP port')

def main():
    app = App()
    app.run()

main()
