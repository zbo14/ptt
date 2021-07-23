import argparse
import json
import os
import socket
import stat
import subprocess
import sys
import const

def main():
    parser = argparse.ArgumentParser(prog='ptt')
    subparsers = parser.add_subparsers(help='sub-command-help')

    parser_start = subparsers.add_parser('start', help='start the daemon')
    parser_stop = subparsers.add_parser('stop', help='stop the daemon')

    parser_add_peer = subparsers.add_parser('add-peer', help='add a peer')
    parser_add_peer.add_argument('alias', type=str, help='alias of peer to add')

    parser_get_peer = subparsers.add_parser('get-peer', help='get a peer\'s info')
    parser_get_peer.add_argument('alias', type=str, help='alias of peer to get info for')

    parser_remove_peer = subparsers.add_parser('remove-peer', help='remove a peer')
    parser_remove_peer.add_argument('alias', type=str, help='alias of peer to remove')

    parser_connect = subparsers.add_parser('connect-peer', help='connect to a peer')
    parser_connect.add_argument('alias', type=str, help='alias of peer to connect to')

    try:
        cmd = sys.argv[1]
    except IndexError:
        sys.argv.append('-h')

    args = vars(parser.parse_args())

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(const.DEFAULT_IPC_CLIENT_PATH)

    def close_sock():
        sock.close()
        os.remove(const.DEFAULT_IPC_CLIENT_PATH)

    def sys_exit(msg):
        close_sock()
        sys.exit(msg)

    def send_to_server(msg):
        payload = json.dumps(msg).encode()

        try:
            sock.sendto(payload, const.DEFAULT_IPC_SERVER_PATH)
        except FileNotFoundError:
            sys_exit('Daemon not running')

    def recv_from_server():
        try:
            dgram = sock.recv(4096)
        except FileNotFoundError:
            sys_exit('Daemon not running')

        res = json.loads(dgram.decode())

        if res['error']:
            sys_exit(res['error'])

        return res

    if cmd == 'start':
        try:
            mode = os.stat(const.DEFAULT_IPC_SERVER_PATH).st_mode

            if stat.S_ISSOCK(mode):
                sys_exit('Daemon already running')

        except Exception:
            pass

        subprocess.Popen(['python3', const.APP_PATH])
        print('Started daemon')

    elif cmd == 'stop':
        msg = {'type': 'stop', 'data': {}}

        send_to_server(msg)
        recv_from_server()

        print('Stopped daemon')

    elif cmd == 'add-peer':
        alias = args['alias']

        msg = {
            'type': 'reserve_local_port',
            'data': {'alias': alias}
        }

        send_to_server(msg)

        res = recv_from_server()
        data = res['data']
        public_ip = data['public_ip']
        local_port = data['local_port']

        print(f'Share with {alias}: public_ip={public_ip}, local port={local_port}')

        remote_ip = None
        remote_port = None

        while not remote_ip:
            remote_ip = input(f'Enter {alias}\'s IP address: ')

        while not remote_port:
            remote_port = int(input(f'Enter {alias}\'s port: '))

        msg = {
            'type': 'add_peer',

            'data': {
                'alias': alias,
                'remote_ip': remote_ip,
                'remote_port': remote_port
            }
        }

        send_to_server(msg)
        recv_from_server()

        print(f'Added peer: {alias}')

    elif cmd == 'get-peer':
        alias = args['alias']

        msg = {
            'type': 'get_peer',
            'data': {'alias': alias}
        }

        send_to_server(msg)

        res = recv_from_server()
        data = res['data']
        local_port = data['local_port']
        remote_ip = data['remote_ip']
        remote_port = data['remote_port']

        print(f'Peer {alias}: local_port={local_port}, remote_ip={remote_ip}, remote_port={remote_port}')

    elif cmd == 'remove-peer':
        alias = args['alias']

        msg = {
            'type': 'remove_peer',
            'data': {'alias': alias}
        }

        send_to_server(msg)
        recv_from_server()

        print(f'Removed peer: {alias}')

    elif cmd == 'connect-peer':
        alias = args['alias']

        msg = {
            'type': 'connect_peer',
            'data': {'alias': alias}
        }

        send_to_server(msg)
        recv_from_server()

        print(f'Connected to peer: {alias}')

    close_sock()

main()
