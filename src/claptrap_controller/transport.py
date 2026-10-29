"""Manage the robot connection and stop movement if the app stops responding."""

import socket
import threading
import time

from .control import StatusParser
from .protocol import build_control_packet

CONTROL_PORT = 2000
CONNECT_TIMEOUT = 3
SOCKET_TIMEOUT = 0.15
SEND_INTERVAL = 0.15
STATUS_TIMEOUT = 2
UI_HEARTBEAT_TIMEOUT = 0.75


class ControlClient:
    def __init__(self, host, port=CONTROL_PORT):
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = None
        self.connected = False
        self.locked = True
        self.status = None
        self.status_time = 0
        self.message = 'Disconnected'
        self.axes = (0, 0)
        self.heartbeat = time.monotonic()

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def has_fresh_status(self):
        return self.connected and time.monotonic() - self.status_time < STATUS_TIMEOUT

    def arm(self):
        """Allow movement after fresh status arrives and held inputs are cleared."""
        with self.lock:
            if self.has_fresh_status():
                self.locked = False

    def update(self, throttle, steering):
        with self.lock:
            self.heartbeat = time.monotonic()
            requested_axes = ((throttle, steering)
                              if self.has_fresh_status() and not self.locked else (0, 0))
            if requested_axes != self.axes:
                self.axes = requested_axes
                self.wake_event.set()

    def neutral(self):
        with self.lock:
            self.axes = (0, 0)
            self.wake_event.set()

    def close(self):
        self.neutral()
        self.stop_event.set()
        self.wake_event.set()

    def _run(self):
        sock = None
        try:
            self.message = 'Connecting…'
            sock = socket.create_connection((self.host, self.port), timeout=CONNECT_TIMEOUT)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self.lock:
                self.connected = True
                self.locked = True
                self.axes = (0, 0)
            self.message = 'Connected · waiting for status'
            self._exchange_packets(sock)
        except (OSError, ValueError) as exc:
            self.message = f'Connection: {exc}'
        finally:
            if sock is not None:
                try:
                    sock.sendall(build_control_packet())
                except OSError:
                    pass
                sock.close()
            with self.lock:
                self.connected = False
                self.locked = True
                self.axes = (0, 0)
            if self.stop_event.is_set():
                self.message = 'Disconnected'

    def _exchange_packets(self, sock):
        parser = StatusParser()
        last_send = 0
        connected_at = time.monotonic()
        while not self.stop_event.is_set():
            now = time.monotonic()
            with self.lock:
                if (now - self.heartbeat > UI_HEARTBEAT_TIMEOUT or
                        now - (self.status_time or connected_at) > STATUS_TIMEOUT):
                    self.axes = (0, 0)
                    self.locked = True
                axes = self.axes
            if now - last_send >= SEND_INTERVAL or self.wake_event.is_set():
                sock.sendall(build_control_packet(*axes))
                last_send = now
                self.wake_event.clear()
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                raise ConnectionError('Robot closed the connection')
            for frame in parser.feed(data):
                self.status = frame
                self.status_time = time.monotonic()
                self.message = 'Connected'
