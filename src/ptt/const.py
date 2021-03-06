import os

ROOT_PATH = os.path.abspath(
    os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..')
    )
)

PRIVATE_PATH = os.path.join(ROOT_PATH, 'private')
LOG_PATH = os.path.join(PRIVATE_PATH, 'daemon.log')
PID_PATH = os.path.join(PRIVATE_PATH, 'daemon.pid')
SRC_PATH = os.path.join(ROOT_PATH, 'src', 'ptt')
DAEMON_PATH = os.path.join(SRC_PATH, 'daemon.py')

DEFAULT_DB_PATH = os.path.join(PRIVATE_PATH, 'ptt.db')
DEFAULT_FILES_PATH = os.path.join(PRIVATE_PATH, 'files')
DEFAULT_IDENT4_ENDPOINT = 'https://v4.ident.me'
DEFAULT_IDENT6_ENDPOINT = 'https://v6.ident.me'
DEFAULT_IPC_CLIENT_PATH = '/tmp/ptt_client'
DEFAULT_IPC_SERVER_PATH = '/tmp/ptt_server'
