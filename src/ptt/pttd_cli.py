import argparse
import signal
import sys

from ptt import common

def run():
    parser = argparse.ArgumentParser(prog='pttd')
    subparsers = parser.add_subparsers()

    subparsers.add_parser('start', add_help=False)
    subparsers.add_parser('status', add_help=False)
    subparsers.add_parser('stop', add_help=False)
    subparsers.add_parser('restart', add_help=False)
    subparsers.add_parser('clean', add_help=False)

    try:
        cmd = sys.argv[1]
    except IndexError:
        cmd = None

    if not cmd:
        sys.argv.append('-h')

    parser.parse_args()

    client = common.Client()

    try:
        if not cmd:
            client.exit('usage: ptt daemon {start,status,stop,restart,clean} ...')

        elif cmd == 'start':
            try:
                common.ensure_daemon_running()
                running = True
            except Exception:
                running = False

            if running:
                raise Exception('Daemon already running')

            common.start_daemon()

            print('Started daemon')

        elif cmd == 'status':
            try:
                common.ensure_daemon_running()
                print('Daemon is running')
            except Exception:
                print('Daemon is not running')

        elif cmd == 'restart':
            common.ensure_daemon_running()
            client.stop_daemon()
            common.start_daemon()

            print('Restarted daemon')

        elif cmd == 'stop':
            common.ensure_daemon_running()
            client.stop_daemon()
            common.remove_pidfile()

            print('Stopped daemon')

        elif cmd == 'clean':
            common.kill_daemon(signal.SIGTERM)
            common.remove_pidfile()
            common.remove_client_sock()
            common.remove_server_sock()

    except Exception as e:
        print(e)

    client.close()
