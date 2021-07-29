import argparse
import datetime
import json
import pathlib
import os
import signal
import socket
import stat
import subprocess
import sys
from ptt import const

def run():
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
    peer_subparsers.add_parser('remove', add_help=False)
    peer_subparsers.add_parser('show', add_help=False)
    peer_subparsers.add_parser('connect', add_help=False)
    peer_subparsers.add_parser('disconnect', add_help=False)
    peer_subparsers.add_parser('is-connected', add_help=False)
    peer_subparsers.add_parser('send-text', add_help=False)
    peer_subparsers.add_parser('read-texts', add_help=False)
    peer_subparsers.add_parser('share-file', add_help=False)
    peer_subparsers.add_parser('list-files', add_help=False)

    peer_parser.add_argument('alias', type=str, help='alias of peer')

    try:
        cmd = sys.argv[1]
    except IndexError:
        cmd = None

    try:
        subcmd = sys.argv[2]
    except IndexError:
        subcmd = None

    if not cmd and not subcmd:
        sys.argv.append('-h')

    args = vars(root_parser.parse_args())

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(const.DEFAULT_IPC_CLIENT_PATH)

    def close_sock():
        sock.close()
        os.remove(const.DEFAULT_IPC_CLIENT_PATH)

    def sys_exit(msg):
        close_sock()
        sys.exit(msg)

    signal.signal(signal.SIGINT, lambda x, y: sys_exit("Terminating"))

    def request(req):
        payload = json.dumps(req).encode()

        try:
            sock.sendto(payload, const.DEFAULT_IPC_SERVER_PATH)
            dgram = sock.recv(4096)
        except FileNotFoundError:
            sys_exit('Daemon not running')

        res = json.loads(dgram.decode())

        if 'error' in res and res['error']:
            sys_exit(res['error'])

        return res

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

                subprocess.Popen(['python3', const.DAEMON_PATH])
                print('Started daemon')

            elif subcmd == 'restart':
                request({'type': 'stop', 'data': {}})

                subprocess.Popen(['python3', const.DAEMON_PATH])
                print('Restarted daemon')

            elif subcmd == 'stop':
                request({'type': 'stop', 'data': {}})

                print('Stopped daemon')

        elif cmd == 'peer':
            if not subcmd:
                sys_exit('usage: ptt peer {add,remove,show,connect,is-connected,text} ...')

            elif subcmd == 'add':
                alias = args['alias']

                res = request({
                    'type': 'reserve_local_port',
                    'data': {'alias': alias}
                })

                data = res['data']
                public_ip = data['public_ip']
                local_port = data['local_port']

                print(f'Share with {alias}: public_ip={public_ip}, local_port={local_port}')

                remote_ip = None
                remote_port = None

                while not remote_ip:
                    remote_ip = input(f'Enter {alias}\'s IP address: ')

                while not remote_port:
                    remote_port = int(input(f'Enter {alias}\'s port: '))

                request({
                    'type': 'add_peer',

                    'data': {
                        'alias': alias,
                        'remote_ip': remote_ip,
                        'remote_port': remote_port
                    }
                })

                print(f'Added peer: {alias}')

            elif subcmd == 'remove':
                alias = args['alias']

                request({
                    'type': 'remove_peer',
                    'data': {'alias': alias}
                })

                print(f'Removed peer: {alias}')

            elif subcmd == 'show':
                alias = args['alias']

                res = request({
                    'type': 'show_peer',
                    'data': {'alias': alias}
                })

                data = res['data']
                local_port = data['local_port']
                remote_ip = data['remote_ip']
                remote_port = data['remote_port']

                print(f'Peer {alias}: local_port={local_port}, remote_ip={remote_ip}, remote_port={remote_port}')

            elif subcmd == 'connect':
                alias = args['alias']

                request({
                    'type': 'connect_peer',
                    'data': {'alias': alias}
                })

                print(f'Connected to peer: {alias}')

            elif subcmd == 'disconnect':
                alias = args['alias']

                request({
                    'type': 'disconnect_peer',
                    'data': {'alias': alias}
                })

                print(f'Disconnected from peer: {alias}')

            elif subcmd == 'is-connected':
                alias = args['alias']

                request({
                    'type': 'is_peer_connected',
                    'data': {'alias': alias}
                })

                print(f'Peer {alias} is connected')

            elif subcmd == 'send-text':
                alias = args['alias']

                request({
                    'type': 'is_peer_connected',
                    'data': {'alias': alias}
                })

                content = input(f'Write to {alias}: ')

                request({
                    'type': 'send_text',
                    'data': {'alias': alias, 'content': content}
                })

                print(f'Sent message to {alias}')

            elif subcmd == 'read-texts':
                alias = args['alias']

                res = request({
                    'type': 'read_texts',
                    'data': {'alias': alias}
                })

                texts = res['data']['texts']

                def format_text(text):
                    timestamp = round(text['sent_at'])
                    date_str = str(datetime.datetime.fromtimestamp(timestamp))
                    preface = f'[{date_str}] '

                    if text['from_peer']:
                        alias = text['peer']
                        preface += f'{alias}: '
                    else:
                        preface += 'me: '

                    return preface + text['content']

                fmt_texts = [format_text(text) for text in texts]

                print('\n'.join(fmt_texts))

            elif subcmd == 'share-file':
                alias = args['alias']

                request({
                    'type': 'is_peer_connected',
                    'data': {'alias': alias}
                })

                filepath = None

                while not filepath:
                    filepath = input(f'Enter path of file to share with {alias}: ')

                filepath = os.path.abspath(filepath)

                if not pathlib.Path(filepath).is_file():
                    raise Exception(f'No file exists: {filepath}')

                request({
                    'type': 'share_file',

                    'data': {
                        'alias': alias,
                        'filepath': filepath
                    }
                })

                print(f'Shared file with {alias}')

            elif subcmd == 'list-files':
                alias = args['alias']

                res = request({
                    'type': 'list_files',
                    'data': {'alias': alias}
                })

                files = res['data']['files']

                def format_file(file):
                    timestamp = round(file['shared_at'])
                    date_str = str(datetime.datetime.fromtimestamp(timestamp))
                    preface = f'[{date_str}] '

                    filepath = file['filepath']
                    filesize = file['filesize']
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

                    if file['from_peer']:
                        preface += f'Recv: '
                    else:
                        preface += 'Sent: '

                    return preface + f'{filepath} ({filesize}{units})'

                fmt_files = [format_file(file) for file in files]

                print('\n'.join(fmt_files))

    except Exception as e:
        print(e)

    close_sock()
