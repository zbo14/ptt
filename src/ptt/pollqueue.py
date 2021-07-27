import queue
import os
import socket

class PollQueue(queue.SimpleQueue):
    def __init__(self):
        super().__init__()

        self.rsock, self.wsock = socket.socketpair()

    def fileno(self):
        return self.rsock.fileno()

    def put(self, *args, **kwargs):
        super().put(*args, **kwargs)
        self.wsock.send(b'!')

    def get(self, *args, **kwargs):
        self.rsock.recv(1)
        return super().get(*args, **kwargs)
