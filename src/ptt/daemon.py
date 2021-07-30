import json
import os
import queue
import select
import socket
import sqlite3
import threading
import time
import urllib.request as request
import const

from peer import Peer
from pollqueue import PollQueue

class Daemon:
    def __init__(
            self,
            db_path=const.DEFAULT_DB_PATH,
            files_path=const.DEFAULT_FILES_PATH,
            ident_endpoint=const.DEFAULT_IDENT_ENDPOINT,
            ipc_client_path=const.DEFAULT_IPC_CLIENT_PATH,
            ipc_server_path=const.DEFAULT_IPC_SERVER_PATH
        ):

        self.db_conn = sqlite3.connect(db_path)
        self.db_cursor = self.db_conn.cursor()
        self.db_path = db_path

        self.files_path = files_path

        self.ipc_client_path = ipc_client_path
        self.ipc_server_path = ipc_server_path

        self.ident_endpoint = ident_endpoint
        self.public_ip = request.urlopen(ident_endpoint).read().decode('utf8')

        self.peers = {}
        self.recvd = PollQueue()

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

        sql = '''CREATE TABLE IF NOT EXISTS texts
            (peer text, content text, sent_at numeric, from_peer bool)'''

        self.db_cursor.execute(sql)

        sql = '''CREATE TABLE IF NOT EXISTS files
            (peer text, filename text, filepath text, filesize int, shared_at numeric, from_peer bool)'''

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
        rlist = [self.server, self.recvd]

        while not done:
            try:
                can_read, _, _ = select.select(rlist, [], [])

                if self.server in can_read:
                    req = self.server.recv(4096)
                    done = self.handle_request(req)

                if self.recvd in can_read:
                    msg = self.recvd.get(block=False)
                    self.handle_message(msg)

            except Exception as e:
                print(e)

        for peer in self.peers.values():
            peer.close()

        self.server.close()
        os.remove(self.ipc_server_path)

        done = self.recvd.empty()

        while not done:
            try:
                msg = self.recvd.get(False)
                self.handle_message(msg)

            except queue.Empty:
                done = True

        self.db_conn.close()
        self.recvd.close()

    def handle_message(self, msg):
        alias = msg['peer']
        msg_type = msg['type']
        msg_data = msg['data']

        if msg_type == 'text':
            self.handle_text(alias, msg_data)

        elif msg_type == 'file':
            self.handle_file(alias, msg_data)

        else:
            raise Exception(f'Unexpected message type "{msg_type}" from {alias}')

    def handle_text(self, alias, data):
        content = data['content']
        sent_at = data['sent_at']

        sql = f'INSERT INTO texts VALUES ("{alias}", "{content}", {sent_at}, {True})'

        self.db_cursor.execute(sql)
        self.db_conn.commit()

    def handle_file(self, alias, data):
        filename = data['filename']
        filepath = data['filepath']
        filesize = data['filesize']
        shared_at = data['shared_at']

        sql = f'''INSERT INTO files VALUES
            ("{alias}", "{filename}", "{filepath}", {filesize}, {shared_at}, {True})'''

        self.db_cursor.execute(sql)
        self.db_conn.commit()

    def handle_request(self, req):
        if not req:
            return True

        req = json.loads(req.decode())
        req_type = req['type']
        req_data = req['data']

        data = {}

        try:
            if req_type == 'reserve_local_port':
                alias = req_data['alias']
                data['local_port'] = self.reserve_local_port(alias)
                data['public_ip'] = self.public_ip

            elif req_type == 'add_peer':
                alias = req_data['alias']
                remote_ip = req_data['remote_ip']
                remote_port = req_data['remote_port']
                self.add_peer(alias, remote_ip, remote_port)

            elif req_type == 'remove_peer':
                alias = req_data['alias']
                self.remove_peer(alias)

            elif req_type == 'show_peer':
                alias = req_data['alias']
                peer = self.get_peer(alias)
                data['is_connected'] = peer.is_connected()
                data['local_port'] = peer.local_port
                data['remote_ip'] = peer.remote_ip
                data['remote_port'] = peer.remote_port

            elif req_type == 'connect_peer':
                alias = req_data['alias']
                self.connect_peer(alias)

            elif req_type == 'interrupt_connect':
                alias = req_data['alias']
                self.interrupt_connect(alias)

            elif req_type == 'disconnect_peer':
                alias = req_data['alias']
                self.disconnect_peer(alias)

            elif req_type == 'is_peer_connected':
                alias = req_data['alias']
                peer = self.get_peer(alias)

                if not peer.is_connected():
                    raise Exception(f'Peer {alias} isn\'t connected')

            elif req_type == 'send_text':
                alias = req_data['alias']
                content = req_data['content']
                self.send_text(alias, content)

            elif req_type == 'read_texts':
                alias = req_data['alias']
                data['texts'] = self.read_texts(alias)

            elif req_type == 'share_file':
                alias = req_data['alias']
                filepath = req_data['filepath']
                self.share_file(alias, filepath)

            elif req_type == 'list_files':
                alias = req_data['alias']
                data['files'] = self.list_files(alias)

            elif req_type != 'stop':
                raise Exception(f'Unrecognized message type: "{req_type}"')

            self.send_to_client({
                'error': None,
                'data': data
            })

        except Exception as e:
            self.send_to_client({
                'data': None,
                'error': str(e)
            })

        return req_type == 'stop'

    def add_peer(self, alias, remote_ip, remote_port):
        peer = self.get_peer(alias)
        peer.add_remote(remote_ip, remote_port)

    def get_peer(self, alias):
        try:
            return self.peers[alias]

        except KeyError:
            raise Exception(f'Peer {alias} not found')

    def connect_peer(self, alias):
        peer = self.get_peer(alias)

        if peer.is_connected():
            raise Exception(f'Peer {alias} is already connected')

        peer.connect()
        threading.Thread(target=peer.run, daemon=True).start()

    def interrupt_connect(self, alias):
        peer = self.get_peer(alias)

        if not peer.is_connecting():
            raise Exception(f'Peer is not connecting')

        peer.stop_connecting()

    def disconnect_peer(self, alias):
        peer = self.get_peer(alias)

        if not peer.is_connected():
            raise Exception(f'Peer {alias} is not connected')

        peer.disconnect()

    def send_text(self, alias, content):
        peer = self.get_peer(alias)
        sent_at = time.time()

        msg = {
            'type': 'text',

            'data': {
                'content': content,
                'sent_at': sent_at
            }
        }

        peer.sendmessage(msg)

        sql = f'INSERT INTO texts VALUES ("{alias}", "{content}", {sent_at}, {False})'

        self.db_cursor.execute(sql)
        self.db_conn.commit()

    def read_texts(self, alias):
        self.get_peer(alias)

        sql = f'SELECT * FROM texts WHERE peer="{alias}" ORDER BY sent_at'
        rows = self.db_cursor.execute(sql).fetchall()

        return [{
            'peer': row[0],
            'content': row[1],
            'sent_at': row[2],
            'from_peer': bool(row[3])
        } for row in rows]

    def share_file(self, alias, filepath):
        peer = self.get_peer(alias)
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        shared_at = time.time()

        msg = {
            'type': 'file',

            'data': {
                'filename': filename,
                'filesize': filesize,
                'shared_at': shared_at
            }
        }

        peer.sendmessage(msg)

        with open(filepath, 'rb') as file:
            peer.sendfile(file)

        sql = f'''INSERT INTO files VALUES
            ("{alias}", "{filename}", "{filepath}", {filesize}, {shared_at}, {False})'''

        self.db_cursor.execute(sql)
        self.db_conn.commit()

    def list_files(self, alias):
        self.get_peer(alias)

        sql = f'SELECT * FROM files WHERE peer="{alias}" ORDER BY shared_at'
        rows = self.db_cursor.execute(sql).fetchall()

        return [{
            'peer': row[0],
            'filename': row[1],
            'filepath': row[2],
            'filesize': row[3],
            'shared_at': row[4],
            'from_peer': bool(row[5])
        } for row in rows]

    def send_to_client(self, msg):
        payload = json.dumps(msg).encode()

        try:
            return self.server.sendto(payload, self.ipc_client_path)
        except FileNotFoundError:
            pass

    def remove_peer(self, alias):
        peer = self.get_peer(alias)
        peer.delete()
        del self.peers[alias]

    def reserve_local_port(self, alias):
        try:
            peer = self.get_peer(alias)
        except Exception:
            peer = None

        if peer:
            raise Exception(f'Peer {alias} already exists')

        for _ in range(1, 10):
            peer = Peer(self, alias)

            try:
                peer.bind_socket()
                peer.create()
                self.peers[alias] = peer

                return peer.local_port
            except Exception as e:
                peer.close()
                print(e)

        raise Exception('Failed to find available TCP port')

def main():
    daemon = Daemon()

    try:
        daemon.run()

    except Exception as e:
        print(e)

main()
