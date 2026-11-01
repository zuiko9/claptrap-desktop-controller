"""Send microphone audio to the robot while the user holds Talk."""

import socket
import struct
import threading

AUDIO_PORT = 8081
SAMPLE_RATE = 11025
SAMPLES_PER_PACKET = 640
PACKET_BYTES = SAMPLES_PER_PACKET * 2


def scale_pcm16le(data, percent):
    """Lower the volume of signed 16-bit audio samples."""
    if len(data) % 2 or not 0 <= percent <= 100:
        raise ValueError('Invalid PCM data or microphone level')
    samples = struct.unpack(f'<{len(data) // 2}h', data)
    scaled = (int(sample * percent / 100) for sample in samples)
    return struct.pack(f'<{len(samples)}h', *scaled)


class TalkSender:
    def __init__(self, host, status_is_fresh, level):
        self.host = host
        self.status_is_fresh = status_is_fresh
        self.level = level
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.restart_requested = False
        self.message = 'Talk idle'

    @property
    def active(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        with self.lock:
            if self.thread is not None:
                if self.stop_event.is_set():
                    self.restart_requested = True
                return
            self._start_locked()

    def _start_locked(self):
        self.stop_event = threading.Event()
        self.message = 'Starting microphone…'
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        with self.lock:
            self.restart_requested = False
            self.stop_event.set()

    def _run(self):
        try:
            self._capture()
        finally:
            with self.lock:
                if self.thread is threading.current_thread():
                    self.thread = None
                    if self.restart_requested:
                        self.restart_requested = False
                        self._start_locked()

    def _capture(self):
        try:
            import sounddevice as sd
        except ImportError:
            self.message = 'Talk needs sounddevice (python -m pip install sounddevice)'
            return
        except OSError as exc:
            self.message = f'Microphone library unavailable: {exc}'
            return
        try:
            if self.stop_event.is_set() or not self.status_is_fresh():
                self.message = 'Talk idle'
                return
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('', AUDIO_PORT))
                with sd.RawInputStream(samplerate=SAMPLE_RATE,
                                       blocksize=SAMPLES_PER_PACKET,
                                       channels=1, dtype='int16') as stream:
                    self.message = 'Talking · release to stop'
                    while not self.stop_event.is_set() and self.status_is_fresh():
                        data, overflowed = stream.read(SAMPLES_PER_PACKET)
                        if self.stop_event.is_set() or not self.status_is_fresh():
                            break
                        packet = bytes(data)
                        if len(packet) != PACKET_BYTES:
                            raise ValueError('Microphone returned an incomplete packet')
                        sock.sendto(scale_pcm16le(packet, self.level()),
                                    (self.host, AUDIO_PORT))
                        if overflowed:
                            self.message = 'Talking · microphone input overflow'
            self.message = 'Talk idle'
        except Exception as exc:
            self.message = f'Microphone: {exc}'
