import argparse
import os
import signal
import subprocess
import sys

from ptt import common, const

def run():
    parser = argparse.ArgumentParser(prog='pttd')
    subparsers = parser.add_subparsers()

    subparsers.add_parser('start', add_help=False)
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
            client.exit('usage: ptt daemon {start,stop,restart,clean} ...')

        elif cmd == 'start':
            if os.path.isfile(const.PID_PATH):
                client.exit('Daemon already running')

            proc = subprocess.Popen(['python3', const.DAEMON_PATH])

            with open(const.PID_PATH, 'w+') as file:
                file.write(str(proc.pid))

            print('Started daemon')

        elif cmd == 'restart':
            client.ensure_daemon_running()
            client.request({'type': 'stop', 'data': {}})

            subprocess.Popen(['python3', const.DAEMON_PATH])
            print('Restarted daemon')

        elif cmd == 'stop':
            client.ensure_daemon_running()
            client.request({'type': 'stop', 'data': {}})

            try:
                os.remove(const.PID_PATH)
            except FileNotFoundError:
                pass

            print('Stopped daemon')

        elif cmd == 'clean':
            try:
                with open(const.PID_PATH, 'r') as file:
                    pid = int(file.readlines().pop(0).strip())
                    os.kill(pid, signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass

            try:
                os.remove(const.PID_PATH)
            except FileNotFoundError:
                pass

            try:
                os.remove('/tmp/ptt_server')
            except FileNotFoundError:
                pass

    except Exception as e:
        print(e)

    client.close()
