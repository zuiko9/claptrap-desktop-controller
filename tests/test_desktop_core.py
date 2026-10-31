"""Small tests for safe input handling and split network messages."""

from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
import struct
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from claptrap_controller.camera import FrameParser
from claptrap_controller.audio import PACKET_BYTES, TalkSender, scale_pcm16le
from claptrap_controller.control import BatteryEstimate, Movement, StatusParser
from claptrap_controller.transport import ControlClient


class MovementTests(unittest.TestCase):
    def test_opposing_directions_and_release(self):
        movement = Movement()
        movement.held.update(('up', 'down', 'left'))
        self.assertEqual(movement.axes(6), (0, -6))
        movement.held.remove('down')
        self.assertEqual(movement.axes(6), (6, -6))
        movement.clear()
        self.assertEqual(movement.axes(6), (0, 0))


class BatteryEstimateTests(unittest.TestCase):
    def test_rejects_spikes_and_follows_sustained_change(self):
        estimate = BatteryEstimate()
        for raw in (50, 50, 90, 50, 50):
            displayed = estimate.update(raw)
        self.assertEqual(displayed, 50)
        for _ in range(30):
            displayed = estimate.update(80)
        self.assertEqual(displayed, 80)
        self.assertEqual(estimate.update(255), 80)


class TalkSenderTests(unittest.TestCase):
    def test_signed_pcm_is_attenuated_without_clipping(self):
        data = struct.pack('<3h', -32000, 0, 32000)
        self.assertEqual(struct.unpack('<3h', scale_pcm16le(data, 40)),
                         (-12800, 0, 12800))

    def test_sends_1280_byte_pcm_from_local_port_8081(self):
        sender = TalkSender('192.168.10.123', lambda: True, lambda: 40)
        sent = []

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def bind(self, address):
                sent.append(('bind', address))

            def sendto(self, data, address):
                sent.append(('send', data, address))
                sender.stop()

        class FakeStream:
            def __init__(self, **kwargs):
                self.options = kwargs

            def __enter__(self):
                sent.append(('stream', self.options))
                return self

            def __exit__(self, *args):
                pass

            def read(self, frames):
                self_test.assertEqual(frames, 640)
                return struct.pack('<640h', *([-1000] * 640)), False

        self_test = self
        fake_sd = types.SimpleNamespace(RawInputStream=FakeStream)
        with patch.dict(sys.modules, {'sounddevice': fake_sd}), \
                patch('claptrap_controller.audio.socket.socket', return_value=FakeSocket()):
            sender._run()
        self.assertEqual(sent[0], ('bind', ('', 8081)))
        self.assertEqual(sent[1][1], {'samplerate': 11025, 'blocksize': 640,
                                      'channels': 1, 'dtype': 'int16'})
        self.assertEqual(sent[2][2], ('192.168.10.123', 8081))
        self.assertEqual(len(sent[2][1]), PACKET_BYTES)
        self.assertEqual(struct.unpack_from('<h', sent[2][1]), (-400,))

    def test_release_during_capture_does_not_send_audio(self):
        sender = TalkSender('192.168.10.123', lambda: True, lambda: 40)
        sent = []

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def bind(self, address):
                pass

            def sendto(self, data, address):
                sent.append(data)

        class FakeStream:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, frames):
                sender.stop()
                return bytes(PACKET_BYTES), False

        fake_sd = types.SimpleNamespace(RawInputStream=FakeStream)
        with patch.dict(sys.modules, {'sounddevice': fake_sd}), \
                patch('claptrap_controller.audio.socket.socket', return_value=FakeSocket()):
            sender._run()
        self.assertEqual(sent, [])


class StatusParserTests(unittest.TestCase):
    def test_fragmentation_and_resynchronization(self):
        frame = bytes.fromhex('ee010203' + '00' * 17 + 'dd')
        parser = StatusParser()
        self.assertEqual(parser.feed(b'noise' + frame[:9]), [])
        self.assertEqual(parser.feed(frame[9:] + frame), [frame, frame])
        self.assertEqual(parser.feed(frame[:-1] + b'\x00' + frame), [frame])


class ControlClientTests(unittest.TestCase):
    def test_requires_fresh_status_and_explicit_arm(self):
        client = ControlClient('example.invalid')
        client.update(6, -6)
        self.assertEqual(client.axes, (0, 0))
        client.connected = True
        client.status_time = time.monotonic()
        client.update(6, -6)
        self.assertEqual(client.axes, (0, 0))
        client.arm()
        client.update(6, -6)
        self.assertEqual(client.axes, (6, -6))
        client.neutral()
        self.assertEqual(client.axes, (0, 0))


class FrameParserTests(unittest.TestCase):
    def test_content_length_and_fragmented_frame(self):
        payload = b'\xff\xd8abcdefg'
        header = b'--frame\r\nContent-Length: 9\r\n\r\n'
        parser = FrameParser()
        self.assertEqual(parser.feed(header + payload[:4]), [])
        self.assertEqual(parser.feed(payload[4:] + header + payload), [payload, payload])

    def test_rejects_oversized_frame(self):
        with self.assertRaises(ValueError):
            FrameParser().feed(b'Content-Length: 2097153\r\n\r\n\xff\xd8')


if __name__ == '__main__':
    unittest.main()
