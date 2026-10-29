"""Encode movement commands and restore frames from the camera stream."""


PACKET_SIZE = 22
CHECKSUM_ADD = (1, 2, 4, 7, 11, 16)
CHECKSUM_SUBTRACT = (3, 5, 6, 8, 9, 10, 12, 13, 14, 15, 17, 18, 19)


def packet_checksum(packet):
    """Calculate the checksum byte stored at position 20 in a control packet."""
    if len(packet) != PACKET_SIZE:
        raise ValueError('Expected a 22-byte control packet')
    checksum_value = 0x7c + sum(packet[index] for index in CHECKSUM_ADD)
    checksum_value -= sum(packet[index] for index in CHECKSUM_SUBTRACT)
    return (~checksum_value) & 0xff


def encode_axis(value):
    """Convert a slider value from -31 to 31 to the robot's sign-and-magnitude format."""
    if type(value) is not int or not -31 <= value <= 31:
        raise ValueError('Axis must be an integer from -31 to 31')
    return value if value >= 0 else 0x80 | -value


def build_control_packet(throttle=0, steering=0):
    """Build a movement packet, leaving unsupported flags turned off."""
    packet = bytearray(PACKET_SIZE)
    packet[0] = 0xaa
    packet[1] = 1
    packet[7] = encode_axis(steering)
    packet[9] = encode_axis(throttle)
    packet[20] = packet_checksum(packet)
    packet[21] = 0xbb
    return bytes(packet)


def restore_camera_buffer(payload):
    """Restore the image bytes in a camera frame.

    The returned buffer includes four trailing bytes; the image itself is the
    first N-4 bytes. Raise an error if the frame is too short or malformed.
    """
    length = len(payload)
    if length < 263:
        raise ValueError('Frame is too short for trailer and sample offsets')
    image_length = int.from_bytes(payload[-6:-2], 'big')
    if image_length != length - 4:
        raise ValueError('Frame length trailer does not match payload length')
    frame = bytearray(payload)
    frame[-6] = frame[-2]
    frame[-5] = frame[-1]
    frame[-4] = 0
    sample_total = frame[length - 149] + frame[length - 263]
    correction_offset = image_length // 2 + sample_total % 10
    frame[correction_offset] ^= 0xff
    return bytes(frame)
