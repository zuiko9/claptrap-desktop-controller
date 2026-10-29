"""Check packet encoding and camera restoration with sample data."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from claptrap_controller.protocol import build_control_packet, packet_checksum, restore_camera_buffer


class ControlPacketTests(unittest.TestCase):
    def test_idle_packet(self):
        # Starting at 0x7c and adding 1 gives 0x7d; its bytewise complement is 0x82.
        expected = bytes.fromhex('aa01' + '00' * 18 + '82bb')
        self.assertEqual(build_control_packet(), expected)

    def test_axis_checksum_vectors(self):
        cases = [
            ({'throttle': 31}, 7, 0, 9, 0x1f, 0xa1),
            ({'throttle': -31}, 7, 0, 9, 0x9f, 0x21),
            ({'steering': 31}, 7, 0x1f, 9, 0, 0x63),
            ({'steering': -31}, 7, 0x9f, 9, 0, 0xe3),
        ]
        for kwargs, a, av, b, bv, checksum in cases:
            with self.subTest(kwargs=kwargs):
                expected = bytearray.fromhex('aa01' + '00' * 18 + '00bb')
                expected[a], expected[b], expected[20] = av, bv, checksum
                self.assertEqual(build_control_packet(**kwargs), expected)

    def test_checksum_with_all_fields_populated(self):
        # Added values total 41 and subtracted values total 149: ~(124 + 41 - 149).
        self.assertEqual(packet_checksum(bytes(range(22))), 0xef)
        self.assertEqual(packet_checksum(bytes([255] * 22)), 0x7c)

    def test_checksum_excludes_markers_and_own_byte(self):
        packet = bytearray(build_control_packet())
        packet[0], packet[20], packet[21] = 0, 0xff, 0
        self.assertEqual(packet_checksum(packet), 0x82)

    def test_invalid_axis_or_packet_size(self):
        for value in (-32, 32, 1.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_control_packet(throttle=value)
        with self.assertRaises(ValueError):
            packet_checksum(bytes(21))


class CameraTransformationTests(unittest.TestCase):
    def test_known_camera_offset_calculation(self):
        frame = bytearray((i * 37 + 11) % 256 for i in range(300))
        frame[-6:-2] = bytes.fromhex('00000128')  # 296 = N - 4.
        frame[-2:] = bytes.fromhex('ffd9')
        original = bytes(frame)
        # The samples are 222 and 100, so the target byte is 296 // 2 + 2 = 150.
        # Restoration flips 0xb9 at that position to 0x46.
        expected = bytearray(original)
        expected[294:297] = bytes.fromhex('ffd900')
        expected[150] = 0x46
        self.assertEqual(restore_camera_buffer(frame), expected)
        self.assertEqual(bytes(frame), original)

    def test_odd_image_length(self):
        frame = bytearray(301)
        frame[-6:-2] = (297).to_bytes(4, 'big')
        frame[-2:] = bytes.fromhex('ffd9')
        decoded = restore_camera_buffer(frame)
        self.assertEqual(decoded[148], 0xff)  # floor(297/2), zero-valued samples.
        self.assertEqual(decoded[295:298], bytes.fromhex('ffd900'))

    def test_invalid_or_undersized_frames(self):
        with self.assertRaises(ValueError):
            restore_camera_buffer(bytes(262))
        with self.assertRaises(ValueError):
            restore_camera_buffer(bytes(300))


if __name__ == '__main__':
    unittest.main()
