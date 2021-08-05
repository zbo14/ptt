import ipaddress
import json
import os
import socket
import subprocess
import sys

from ptt import const

def format_filesize(filesize):
    units = 'B'

    if filesize > 1e9:
        filesize = round(filesize / 1e9, 1)
        units = 'GB'
    elif filesize > 1e6:
        filesize = round(filesize / 1e6, 1)
        units = 'MB'
    elif filesize > 1e3:
        filesize = round(filesize / 1e3, 1)
        units = 'KB'

    return f'{filesize}{units}'

def ensure_daemon_running():
    if not kill_daemon(0):
        raise Exception('Daemon not running')

def start_daemon():
    with open(const.LOG_PATH, 'w+') as logfile:
        with open(const.PID_PATH, 'w+') as pidfile:
            proc = subprocess.Popen(
                ['python3', const.DAEMON_PATH],
                stdout=logfile,
                stderr=logfile
            )

            pidfile.write(str(proc.pid))

def kill_daemon(code):
    try:
        with open(const.PID_PATH, 'r') as file:
            pid = int(file.readlines().pop(0).strip())
            os.kill(pid, code)

        return True

    except (FileNotFoundError, OSError):
        return False

def prompt(prompt, *, required=True):
    val = input(prompt).strip()

    if required and not val:
        val = input(prompt).strip()

    return val

def prompt_remote_ip(alias, *, is_ipv6=False, required=False):
    ipv = 6 if is_ipv6 else 4
    remote_ip = prompt(f'Enter {alias}\'s IPv{ipv} address: ', required=required)

    if not remote_ip:
        return None

    try:
        if ipaddress.ip_address(remote_ip).version != ipv:
            raise Exception
    except Exception:
        raise Exception(f'Invalid IPv{ipv} address')

    return remote_ip

def prompt_remote_port(alias, *, required=False):
    remote_port = prompt(f'Enter {alias}\'s port: ', required=required)

    try:
        remote_port = int(remote_port)

        if not 0 < remote_port < 65536:
            raise Exception

        return remote_port
    except Exception:
        raise Exception('Invalid port number')


def remove_pidfile():
    try:
        os.remove(const.PID_PATH)
    except FileNotFoundError:
        pass

def remove_server_sock():
    try:
        os.remove(const.DEFAULT_IPC_SERVER_PATH)
    except FileNotFoundError:
        pass

def remove_client_sock():
    try:
        os.remove(const.DEFAULT_IPC_SERVER_PATH)
    except FileNotFoundError:
        pass

class Client:
    def __init__(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(const.DEFAULT_IPC_CLIENT_PATH)

    def close(self):
        self.sock.close()
        os.remove(const.DEFAULT_IPC_CLIENT_PATH)

    def exit(self, msg):
        self.close()
        sys.exit(msg)

    def ensure_peer_connected(self, alias):
        if not list(self.show_peer(alias)).pop() == 'connected':
            raise Exception(f'Peer {alias} isn\'t connected')

    def ensure_peer_exists(self, alias):
        res = self.request('peer_exists', {'alias': alias})

        if not res['data']['exists']:
            raise Exception(f'Peer {alias} doesn\'t exist')

    def request(self, msg_type, msg_data):
        payload = json.dumps({'type': msg_type, 'data': msg_data}).encode()

        self.sock.sendto(payload, const.DEFAULT_IPC_SERVER_PATH)

        dgram = self.sock.recv(4096)
        res = json.loads(dgram.decode())

        if 'error' in res and res['error']:
            self.exit(res['error'])

        return res

    def init_peer(self, alias, *, is_ipv6=False, new_port=False, should_exist=False):
        res = self.request('init_peer', {
            'alias': alias,
            'is_ipv6': is_ipv6,
            'new_port': new_port,
            'should_exist': should_exist
        })

        data = res['data']
        public_ip4 = data['public_ip4']
        public_ip6 = data['public_ip6']
        local_port = data['local_port']

        return public_ip4, public_ip6, local_port

    def edit_peer(self, alias, remote_ip, remote_port):
        return self.request('edit_peer', {
            'alias': alias,
            'remote_ip': remote_ip,
            'remote_port': remote_port
        })

    def remove_peer(self, alias):
        return self.request('remove_peer', {'alias': alias})

    def show_peer(self, alias):
        res = self.request('show_peer', {'alias': alias})

        data = res['data']
        local_port = data['local_port']
        public_ip4 = data['public_ip4']
        public_ip6 = data['public_ip6']
        remote_ip = data['remote_ip']
        remote_port = data['remote_port']
        state = data['state']

        return public_ip4, public_ip6, local_port, remote_ip, remote_port, state

    def connect_peer(self, alias):
        return self.request('connect_peer', {'alias': alias})

    def disconnect_peer(self, alias):
        return self.request('disconnect_peer', {'alias': alias})

    def send_text(self, alias, content):
        return self.request('send_text', {
            'alias': alias,
            'content': content
        })

    def read_texts(self, alias):
        res = self.request('read_texts', {'alias': alias})

        return res['data']['texts']

    def share_file(self, alias, filepath):
        return self.request('share_file', {
            'alias': alias,
            'filepath': filepath
        })

    def list_files(self, alias):
        res = self.request('list_files', {'alias': alias})

        return res['data']['files']

    def stop_daemon(self):
        return self.request('stop', {})
