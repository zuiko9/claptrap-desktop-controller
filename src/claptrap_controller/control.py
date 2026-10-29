"""Turn held keys into movement values and collect robot status messages."""


class Movement:
    def __init__(self):
        self.held = set()

    def clear(self):
        self.held.clear()

    def axes(self, strength):
        throttle = int('up' in self.held) - int('down' in self.held)
        steering = int('right' in self.held) - int('left' in self.held)
        return throttle * strength, steering * strength


class StatusParser:
    """Collect full 22-byte status messages, even when TCP splits them apart."""

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            start = self.buffer.find(b'\xee')
            if start < 0:
                self.buffer.clear()
                break
            del self.buffer[:start]
            if len(self.buffer) < 22:
                break
            if self.buffer[21] != 0xdd:
                del self.buffer[0]
                continue
            frames.append(bytes(self.buffer[:22]))
            del self.buffer[:22]
        return frames
