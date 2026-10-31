"""Turn held keys into movement values and collect robot status messages."""

from collections import deque
from statistics import median


class Movement:
    def __init__(self):
        self.held = set()

    def clear(self):
        self.held.clear()

    def axes(self, strength):
        throttle = int('up' in self.held) - int('down' in self.held)
        steering = int('right' in self.held) - int('left' in self.held)
        return throttle * strength, steering * strength


class BatteryEstimate:
    """Keep brief changes in the battery reading from moving the display."""

    def __init__(self):
        self.samples = deque(maxlen=9)
        self.filtered = None

    def update(self, raw):
        if not 0 <= raw <= 100:
            return None if self.filtered is None else self.display
        self.samples.append(raw)
        middle = median(self.samples)
        if self.filtered is None:
            self.filtered = float(middle)
        else:
            self.filtered += 0.12 * (middle - self.filtered)
        return self.display

    @property
    def display(self):
        return min(100, max(0, 5 * round(self.filtered / 5)))


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
