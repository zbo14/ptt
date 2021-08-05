import argparse
import datetime
import os
import signal
import sys

from ptt import common

def run():
    parser = argparse.ArgumentParser(prog='ptt')
    subparsers = parser.add_subparsers()

    subparsers.add_parser('add', add_help=False)
    subparsers.add_parser('add6', add_help=False)
    subparsers.add_parser('edit', add_help=False)
    subparsers.add_parser('edit6', add_help=False)
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

    def handle_interrupt(*_):
        if cmd in ('add', 'add6'):
            alias = args['alias']
            client.remove_peer(alias)

        client.exit('Terminating')

    signal.signal(signal.SIGINT, handle_interrupt)

    try:
        if not cmd:
            client.exit('usage: ptt {add,add6,edit,edit6,remove,show,connect,disconnect,send-text,read-texts,share-file,list-files} ...')

        common.ensure_daemon_running()

        if cmd == 'add':
            alias = args['alias']
            public_ip4, _, local_port = client.init_peer(alias, new_port=True)

            print(f'Share with {alias}: public_ip4={public_ip4}, local_port={local_port}')

            remote_ip = common.prompt_remote_ip(alias, required=True)
            remote_port = common.prompt_remote_port(alias, required=True)

            client.edit_peer(alias, remote_ip, remote_port)

            print(f'Added peer: {alias}')

        elif cmd == 'add6':
            alias = args['alias']
            _, public_ip6, local_port = client.init_peer(alias, is_ipv6=True, new_port=True)

            print(f'Share with {alias}: public_ip6={public_ip6}, local_port={local_port}')

            remote_ip = common.prompt_remote_ip(alias, is_ipv6=True, required=True)
            remote_port = common.prompt_remote_port(alias, required=True)

            client.edit_peer(alias, remote_ip, remote_port)

            print(f'Added peer: {alias}')

        elif cmd == 'edit':
            alias = args['alias']

            client.ensure_peer_exists(alias)

            new_port = input('Change local port? [y/N]: ').strip().lower() == 'y'

            public_ip4, _, local_port = client.init_peer(
                alias, new_port=new_port, should_exist=True
            )

            print(f'Share with {alias}: public_ip4={public_ip4}, local_port={local_port}')

            remote_ip = common.prompt_remote_ip(alias)
            remote_port = common.prompt_remote_port(alias)

            client.edit_peer(alias, remote_ip, remote_port)

            print(f'Edited peer: {alias}')

        elif cmd == 'edit6':
            alias = args['alias']

            client.ensure_peer_exists(alias)

            new_port = input('Change local port? [y/N]: ').strip().lower() == 'y'

            _, public_ip6, local_port = client.init_peer(
                alias, is_ipv6=True, new_port=new_port, should_exist=True
            )

            print(f'Share with {alias}: public_ip6={public_ip6}, local_port={local_port}')

            remote_ip = common.prompt_remote_ip(alias, is_ipv6=True)
            remote_port = common.prompt_remote_port(alias)

            client.edit_peer(alias, remote_ip, remote_port)

            print(f'Edited peer: {alias}')

        elif cmd == 'remove':
            alias = args['alias']
            client.remove_peer(alias)

            print(f'Removed peer: {alias}')

        elif cmd == 'show':
            alias = args['alias']
            _, _, local_port, remote_ip, remote_port, state = client.show_peer(alias)

            print(f'Peer {alias}: local_port={local_port}, remote_ip={remote_ip}, remote_port={remote_port}, state="{state}"')

        elif cmd == 'connect':
            alias = args['alias']
            client.connect_peer(alias)

            print(f'Connecting to peer: {alias}')

        elif cmd == 'disconnect':
            alias = args['alias']
            client.disconnect_peer(alias)

            print(f'Disconnected from peer: {alias}')

        elif cmd == 'send-text':
            alias = args['alias']
            client.ensure_peer_connected(alias)
            content = input(f'Write to {alias}: ')
            client.send_text(alias, content)

            print(f'Sent message to {alias}')

        elif cmd == 'read-texts':
            alias = args['alias']
            texts = client.read_texts(alias)

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

            print('\n'.join([format_text(text) for text in texts]))

        elif cmd == 'share-file':
            alias = args['alias']

            client.ensure_peer_connected(alias)

            filepath = None

            while not filepath:
                filepath = input(f'Enter path of file to share with {alias}: ')

            filepath = os.path.abspath(filepath)

            if not os.path.isfile(filepath):
                raise Exception(f'No file exists: {filepath}')

            client.share_file(alias, filepath)

            print(f'Shared file with {alias}')

        elif cmd == 'list-files':
            alias = args['alias']
            files = client.list_files(alias)

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

            print('\n'.join([format_file(file) for file in files]))

    except Exception as e:
        print(e)

    client.close()
