import json
import os
import socket
import sqlite3
import threading
import urllib.request as request
import const

from peer import Peer

class App():
    def __init__(
            self,
            db_path=const.DEFAULT_DB_PATH,
            ident_endpoint=const.DEFAULT_IDENT_ENDPOINT,
            ipc_client_path=const.DEFAULT_IPC_CLIENT_PATH,
            ipc_server_path=const.DEFAULT_IPC_SERVER_PATH
        ):

        self.db_conn = sqlite3.connect(db_path)
        self.db_cursor = self.db_conn.cursor()
        self.ipc_client_path = ipc_client_path
        self.ipc_server_path = ipc_server_path
        self.public_ip = request.urlopen(ident_endpoint).read().decode('utf8')

        self.peers = {}

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.server.bind(ipc_server_path)

        self.init_db()
        self.init_peers()

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

    def init_peers(self):
        sql = 'SELECT * FROM peers'

        for alias, local_port, remote_ip, remote_port in self.db_cursor.execute(sql):
            peer = Peer(self, alias, local_port, remote_ip, remote_port)
            peer.bind_socket()
            self.peers[alias] = peer

    def run(self):
        done = False

        while not done:
            dgram = self.server.recv(4096)

            try:
                done = self.handle_dgram(dgram)
            except Exception as e:
                print(e)

        for peer in self.peers.values():
            peer.close()

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
            if msg_type == 'reserve_local_port':
                alias = msg_data['alias']
                data['local_port'] = self.reserve_local_port(alias)
                data['public_ip'] = self.public_ip

            elif msg_type == 'add_peer':
                alias = msg_data['alias']
                remote_ip = msg_data['remote_ip']
                remote_port = msg_data['remote_port']
                self.add_peer(alias, remote_ip, remote_port)

            elif msg_type == 'remove_peer':
                alias = msg_data['alias']
                self.remove_peer(alias)

            elif msg_type == 'show_peer':
                alias = msg_data['alias']
                peer = self.get_peer(alias)
                data['local_port'] = peer.local_port
                data['remote_ip'] = peer.remote_ip
                data['remote_port'] = peer.remote_port

            elif msg_type == 'connect_peer':
                alias = msg_data['alias']
                self.connect_peer(alias)

            elif msg_type == 'send_text':
                alias = msg_data['alias']
                content = msg_data['content']
                self.send_text(alias, content)

            elif msg_type == 'is_peer_connected':
                alias = msg_data['alias']
                peer = self.get_peer(alias)

                if not peer.is_connected():
                    raise Exception(f'Peer "{alias}" isn\'t connected')

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

    def add_peer(self, alias, remote_ip, remote_port):
        peer = self.get_peer(alias)
        peer.add_remote(remote_ip, remote_port)

    def get_peer(self, alias):
        try:
            return self.peers[alias]

        except KeyError:
            raise Exception(f'Peer "{alias}" not found')

    def connect_peer(self, alias):
        peer = self.get_peer(alias)

        if peer.is_connected():
            raise Exception(f'Already connected to peer "{alias}"')

        t = threading.Thread(target=peer.connect, daemon=True)
        t.start()

    def send_text(self, alias, content):
        peer = self.get_peer(alias)

        msg = {
            'type': 'text',
            'data': {'content': content}
        }

        peer.send_msg(msg)

    def send_to_client(self, msg):
        payload = json.dumps(msg).encode()

        return self.server.sendto(payload, self.ipc_client_path)

    def remove_peer(self, alias):
        peer = self.get_peer(alias)
        peer.delete()
        del self.peers[alias]

    def reserve_local_port(self, alias):
        sql = f'SELECT 1 FROM peers WHERE alias="{alias}" LIMIT 1'

        if self.db_cursor.execute(sql).fetchone():
            raise Exception(f'Peer "{alias}" already exists')

        for _ in range(1, 10):
            peer = Peer(self, alias)

            try:
                peer.create()
                peer.bind_socket()
                self.peers[alias] = peer

                return peer.local_port
            except Exception as e:
                print(e)

        raise Exception('Failed to find available TCP port')

def main():
    app = App()
    app.run()

main()
