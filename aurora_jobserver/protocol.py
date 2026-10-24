"""Offline decoding of the status exchange observed on control port 29.

This module deliberately has no sockets. Frame meanings beyond the original
library's numeric state codes remain to be established from further captures.
"""
from dataclasses import dataclass


STATUS_REQUEST = bytes.fromhex("ff e0 01")
STATUS_PREFIX = bytes.fromhex("ff e1 01")


@dataclass(frozen=True)
class ControllerStatus:
    raw_hex: str
    flags_4_5: int
    byte_6: int
    legacy_state_code: int


def decode_status_reply(frame):
    if len(frame) != 8 or not frame.startswith(STATUS_PREFIX):
        raise ValueError("Expected the observed eight-byte status reply")
    flags = int.from_bytes(frame[4:6], "little")
    code = 2 if flags & 0x8000 else 3 if flags & 0x1000 else 4 if frame[6] & 8 else 1
    return ControllerStatus(frame.hex(), flags, frame[6], code)


class StatusReplyStream:
    """Handle TCP fragmentation/coalescing for this one observed reply type."""
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        replies = []
        while self.buffer:
            prefix_size = min(len(self.buffer), len(STATUS_PREFIX))
            if self.buffer[:prefix_size] != STATUS_PREFIX[:prefix_size]:
                raise ValueError("Unrecognized control reply; capture needed before interpreting it")
            if len(self.buffer) < 8:
                break
            replies.append(decode_status_reply(bytes(self.buffer[:8])))
            del self.buffer[:8]
        return replies
