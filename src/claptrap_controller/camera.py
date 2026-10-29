"""Read the robot's HTTP camera stream and keep its latest decoded frame."""

import http.client
import io
import re
import threading
import time

from .protocol import restore_camera_buffer

MAX_FRAME = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 4096 * 2160
CAMERA_PORT = 8080
FRAME_INTERVAL = 0.1
RECONNECT_DELAY = 2


class FrameParser:
    """Collect complete JPEG frames, even when HTTP splits them across reads."""

    def __init__(self):
        self.pending = bytearray()

    def feed(self, chunk):
        self.pending.extend(chunk)
        frames = []
        while True:
            jpeg_start = self.pending.find(b'\xff\xd8')
            if jpeg_start < 0:
                if len(self.pending) > 8192:
                    del self.pending[:-8192]
                return frames
            headers = bytes(self.pending[:jpeg_start])
            content_lengths = re.findall(
                br'(?im)^content-length:\s*(\d+)\s*\r?$', headers)
            if content_lengths:
                frame_size = int(content_lengths[-1])
                if frame_size < 4 or frame_size > MAX_FRAME:
                    raise ValueError('Camera frame size is invalid')
                frame_end = jpeg_start + frame_size
                if len(self.pending) < frame_end:
                    return frames
            else:
                jpeg_end = self.pending.find(b'\xff\xd9', jpeg_start + 2)
                if jpeg_end < 0:
                    if len(self.pending) - jpeg_start > MAX_FRAME:
                        raise ValueError('Camera frame exceeds size limit')
                    return frames
                frame_end = jpeg_end + 2
            frames.append(bytes(self.pending[jpeg_start:frame_end]))
            del self.pending[:frame_end]


class Camera:
    def __init__(self, host):
        self.host = host
        self.stop_event = threading.Event()
        self.thread = None
        self.frame = None
        self.frame_time = 0
        self.message = 'Camera connecting…'

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()

    def _run(self):
        try:
            from PIL import Image
        except ImportError:
            self.message = 'Camera needs Pillow (python3-pil)'
            return
        while not self.stop_event.is_set():
            try:
                self._read_stream(Image)
            except (OSError, ValueError, http.client.HTTPException) as exc:
                self.message = f'Camera: {exc}'
            self.stop_event.wait(RECONNECT_DELAY)

    def _read_stream(self, image_module):
        connection = http.client.HTTPConnection(self.host, CAMERA_PORT, timeout=2)
        try:
            connection.request('GET', '/')
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f'Camera HTTP {response.status}')
            parser = FrameParser()
            last_decode = 0
            while not self.stop_event.is_set():
                chunk = response.read1(8192)
                if not chunk:
                    raise ConnectionError('Camera stream ended')
                frames = parser.feed(chunk)
                if not frames or time.monotonic() - last_decode < FRAME_INTERVAL:
                    continue
                try:
                    self._decode_frame(image_module, frames[-1])
                    last_decode = self.frame_time = time.monotonic()
                    self.message = 'Camera live'
                except (OSError, ValueError) as exc:
                    self.message = f'Camera decode: {exc}'
        finally:
            connection.close()

    def _decode_frame(self, image_module, payload):
        if len(payload) >= 263 and int.from_bytes(payload[-6:-2], 'big') == len(payload) - 4:
            payload = restore_camera_buffer(payload)[:-4]
        with image_module.open(io.BytesIO(payload)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError('Camera image dimensions exceed limit')
            self.frame = image.convert('RGB')
