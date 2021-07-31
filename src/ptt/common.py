import json
import os
import signal
import socket
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

class Client:
    def __init__(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(const.DEFAULT_IPC_CLIENT_PATH)

        signal.signal(signal.SIGINT, self.handle_interrupt)

    def close(self):
        self.sock.close()
        os.remove(const.DEFAULT_IPC_CLIENT_PATH)

    def exit(self, msg):
        self.close()
        sys.exit(msg)

    def ensure_daemon_running(self):
        if not os.path.isfile(const.PID_PATH):
            self.exit('Daemon not running')

    def ensure_peer_connected(self, alias):
        self.request({
            'type': 'is_peer_connected',
            'data': {'alias': alias}
        })

    def handle_interrupt(self, *_):
        self.exit('Terminating')

    def request(self, req):
        payload = json.dumps(req).encode()

        self.sock.sendto(payload, const.DEFAULT_IPC_SERVER_PATH)

        dgram = self.sock.recv(4096)
        res = json.loads(dgram.decode())

        if 'error' in res and res['error']:
            self.exit(res['error'])

        return res
