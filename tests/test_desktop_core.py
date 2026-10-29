"""Small tests for safe input handling and split network messages."""

from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from claptrap_controller.camera import FrameParser
from claptrap_controller.control import Movement, StatusParser
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
