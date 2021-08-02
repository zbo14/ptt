import argparse
import datetime
import ipaddress
import os
import sys

from ptt import common

def run():
    parser = argparse.ArgumentParser(prog='ptt')
    subparsers = parser.add_subparsers()

    subparsers.add_parser('add', add_help=False)
    subparsers.add_parser('remove', add_help=False)
    subparsers.add_parser('show', add_help=False)
    subparsers.add_parser('connect', add_help=False)
    subparsers.add_parser('disconnect', add_help=False)
    subparsers.add_parser('send-text', add_help=False)
    subparsers.add_parser('read-texts', add_help=False)
    subparsers.add_parser('share-file', add_help=False)
    subparsers.add_parser('list-files', add_help=False)

    parser.add_argument('alias', type=str, help='alias of peer')

    try:
        cmd = sys.argv[1]
    except IndexError:
        cmd = None

    if not cmd:
        sys.argv.append('-h')

    args = vars(parser.parse_args())
    client = common.Client()

    try:
        if not cmd:
            client.exit('usage: ptt {add,remove,show,connect,disconnect,send-text,read-texts,share-file,list-files} ...')

        client.ensure_daemon_running()

        if cmd == 'add':
            alias = args['alias']

            res = client.request({
                'type': 'reserve_local_port',
                'data': {'alias': alias}
            })

            data = res['data']
            public_ip4 = data['public_ip4']
            public_ip6 = data['public_ip6']
            local_port = data['local_port']

            print(f'Share with {alias}: public_ip4={public_ip4}, public_ip6={public_ip6}, local_port={local_port}')

            remote_ip = None
            remote_port = None

            while not remote_ip:
                remote_ip = input(f'Enter {alias}\'s IP address: ')

            try:
                ipaddress.ip_address(remote_ip)
            except ValueError:
                raise Exception('Invalid IP address')

            while not remote_port:
                remote_port = int(input(f'Enter {alias}\'s port: '))

            client.request({
                'type': 'add_peer',

                'data': {
                    'alias': alias,
                    'remote_ip': remote_ip,
                    'remote_port': remote_port
                }
            })

            print(f'Added peer: {alias}')

        elif cmd == 'remove':
            alias = args['alias']

            client.request({
                'type': 'remove_peer',
                'data': {'alias': alias}
            })

            print(f'Removed peer: {alias}')

        elif cmd == 'show':
            alias = args['alias']

            res = client.request({
                'type': 'show_peer',
                'data': {'alias': alias}
            })

            data = res['data']
            local_port = data['local_port']
            remote_ip = data['remote_ip']
            remote_port = data['remote_port']
            state = data['state']

            print(f'Peer {alias}: local_port={local_port}, remote_ip={remote_ip}, remote_port={remote_port}, state="{state}"')

        elif cmd == 'connect':
            alias = args['alias']

            client.request({
                'type': 'connect_peer',
                'data': {'alias': alias}
            })

            print(f'Connecting to peer: {alias}')

        elif cmd == 'disconnect':
            alias = args['alias']

            client.request({
                'type': 'disconnect_peer',
                'data': {'alias': alias}
            })

            print(f'Disconnected from peer: {alias}')

        elif cmd == 'send-text':
            alias = args['alias']

            client.ensure_peer_connected(alias)

            content = input(f'Write to {alias}: ')

            client.request({
                'type': 'send_text',
                'data': {'alias': alias, 'content': content}
            })

            print(f'Sent message to {alias}')

        elif cmd == 'read-texts':
            alias = args['alias']

            res = client.request({
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

        elif cmd == 'share-file':
            alias = args['alias']

            client.ensure_peer_connected(alias)

            filepath = None

            while not filepath:
                filepath = input(f'Enter path of file to share with {alias}: ')

            filepath = os.path.abspath(filepath)

            if not os.path.isfile(filepath):
                raise Exception(f'No file exists: {filepath}')

            client.request({
                'type': 'share_file',

                'data': {
                    'alias': alias,
                    'filepath': filepath
                }
            })

            print(f'Shared file with {alias}')

        elif cmd == 'list-files':
            alias = args['alias']

            res = client.request({
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
                fmtsize = common.format_filesize(filesize)

                if file['from_peer']:
                    preface += 'Recv: '
                else:
                    preface += 'Sent: '

                return preface + f'{filepath} ({fmtsize})'

            fmt_files = [format_file(file) for file in files]

            print('\n'.join(fmt_files))

    except Exception as e:
        print(e)

    client.close()
