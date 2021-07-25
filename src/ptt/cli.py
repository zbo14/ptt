import argparse
import json
import os
# import signal
import socket
import stat
import subprocess
import sys
import const

def main():
    root_parser = argparse.ArgumentParser(prog='ptt')
    root_subparsers = root_parser.add_subparsers()

    daemon_parser = root_subparsers.add_parser('daemon')
    daemon_subparsers = daemon_parser.add_subparsers()

    peer_parser = root_subparsers.add_parser('peer')
    peer_subparsers = peer_parser.add_subparsers()

    daemon_subparsers.add_parser('start', add_help=False)
    daemon_subparsers.add_parser('stop', add_help=False)
    daemon_subparsers.add_parser('restart', add_help=False)

    peer_subparsers.add_parser('add', add_help=False)
    peer_subparsers.add_parser('show', add_help=False)
    peer_subparsers.add_parser('remove', add_help=False)
    peer_subparsers.add_parser('connect', add_help=False)
    peer_subparsers.add_parser('is-connected', add_help=False)
    peer_subparsers.add_parser('text', add_help=False)

    peer_parser.add_argument('alias', type=str, help='alias of peer')

    try:
        cmd = sys.argv[1]
    except IndexError:
        cmd = None

    try:
        subcmd = sys.argv[2]
    except IndexError:
        subcmd = None

    args = vars(root_parser.parse_args())

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

        if 'error' in res and res['error']:
            sys_exit(res['error'])

        return res

    def request(msg):
        send_to_server(msg)

        return recv_from_server()

    try:
        if cmd == 'daemon':
            if not subcmd:
                sys_exit('usage: ptt daemon {start,stop,restart} ...')

            elif subcmd == 'start':
                try:
                    mode = os.stat(const.DEFAULT_IPC_SERVER_PATH).st_mode

                    if stat.S_ISSOCK(mode):
                        sys_exit('Daemon already running')

                except Exception:
                    pass

                subprocess.Popen(['python3', const.APP_PATH])
                print('Started daemon')

            elif subcmd == 'restart':
                msg = {'type': 'stop', 'data': {}}

                request(msg)

                subprocess.Popen(['python3', const.APP_PATH])
                print('Restarted daemon')

            elif subcmd == 'stop':
                msg = {'type': 'stop', 'data': {}}

                request(msg)

                print('Stopped daemon')

        elif cmd == 'peer':
            if not subcmd:
                sys_exit('usage: ptt peer {add,remove,show,connect,chat} ...')

            elif subcmd == 'add':
                alias = args['alias']

                msg = {
                    'type': 'reserve_local_port',
                    'data': {'alias': alias}
                }

                res = request(msg)

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

                request(msg)

                print(f'Added peer: {alias}')

            elif subcmd == 'remove':
                alias = args['alias']

                msg = {
                    'type': 'remove_peer',
                    'data': {'alias': alias}
                }

                request(msg)

                print(f'Removed peer: {alias}')

            elif subcmd == 'show':
                alias = args['alias']

                msg = {
                    'type': 'show_peer',
                    'data': {'alias': alias}
                }

                res = request(msg)

                data = res['data']
                local_port = data['local_port']
                remote_ip = data['remote_ip']
                remote_port = data['remote_port']

                print(f'Peer "{alias}": local_port={local_port}, remote_ip={remote_ip}, remote_port={remote_port}')

            elif subcmd == 'connect':
                alias = args['alias']

                msg = {
                    'type': 'connect_peer',
                    'data': {'alias': alias}
                }

                request(msg)

                print(f'Connected to peer: {alias}')

            elif subcmd == 'is-connected':
                alias = args['alias']

                msg = {
                    'type': 'is_peer_connected',
                    'data': {'alias': alias}
                }

                request(msg)
                print(f'Peer "{alias}" is connected')

            elif subcmd == 'text':
                alias = args['alias']

                msg = {
                    'type': 'is_peer_connected',
                    'data': {'alias': alias}
                }

                request(msg)

                alias = args['alias']
                content = input(f'Write to "{alias}": ')

                msg = {
                    'type': 'send_text',
                    'data': {'alias': alias, 'content': content}
                }

                request(msg)

                print(f'Sent message to "{alias}"')

    finally:
        close_sock()

main()
