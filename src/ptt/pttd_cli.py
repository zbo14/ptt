import argparse
import signal
import sys

from ptt import common

def run():
    parser = argparse.ArgumentParser(prog='pttd')
    subparsers = parser.add_subparsers()

    start_parser = subparsers.add_parser('start')
    start_parser.add_argument('-c', '--connect', default=False, action=argparse.BooleanOptionalAction)

    subparsers.add_parser('status')
    subparsers.add_parser('stop')

    restart_parser = subparsers.add_parser('restart')
    restart_parser.add_argument('-c', '--connect', default=False, action=argparse.BooleanOptionalAction)

    subparsers.add_parser('clean')

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
            client.exit('usage: ptt daemon {start,status,stop,restart,clean} ...')

        elif cmd == 'start':
            try:
                common.ensure_daemon_running()
                running = True
            except Exception:
                running = False

            if running:
                raise Exception('Daemon already running')

            common.start_daemon(args['connect'])

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
            common.start_daemon(args['connect'])

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
