"""Incremental, offline decoding of observed port-23 controller replies.

EOT (04) is deliberately a control event, not a job-complete event: it appears
both in the pre-job handshake and at the end of this captured engraving.
"""
from dataclasses import dataclass
import re


CONTROL_BYTES = {0x01, 0x04, 0x05, 0x06, 0x07, 0xac}
ERROR = re.compile(rb'Error ([0-9]+): (.+)')
JOB_TIME = re.compile(rb'JOB_TIME ([0-9]+(?:\.[0-9]+)?)')
FEATURE = re.compile(rb'(?:.*\bdsp_feature 1 wchar )?#([0-9]{10})')


@dataclass(frozen=True)
class ReplyEvent:
    offset: int
    kind: str
    raw: bytes
    value: object = None
    channel: int | None = None


class MainReplyStream:
    def __init__(self, max_line=65536):
        self.max_line = max_line
        self.offset = 0
        self.line_start = 0
        self.line = bytearray()
        self.channel = None
        self.channel_marker = None

    def _flush(self):
        raw = bytes(self.line)
        self.line.clear()
        text = raw.strip(b'\r\n \t')
        if not text:
            return []
        kind, value = 'text', None
        if match := ERROR.fullmatch(text):
            kind, value = 'controller_error', {'code': int(match[1]), 'message': match[2].decode('cp1252', errors='replace')}
        elif match := JOB_TIME.fullmatch(text):
            kind, value = 'job_time', float(match[1])
        elif match := FEATURE.fullmatch(text):
            kind, value = 'feature_value', int(match[1])
        return [ReplyEvent(self.line_start, kind, raw, value, self.channel)]

    def feed(self, data):
        events = []
        for byte in data:
            if self.channel_marker is not None:
                self.channel = byte
                events.append(ReplyEvent(self.channel_marker, 'channel_select',
                                        bytes([0xad, byte]), byte, byte))
                self.channel_marker = None
            elif byte == 0xad:
                events.extend(self._flush())
                self.channel_marker = self.offset
            elif byte in CONTROL_BYTES:
                events.extend(self._flush())
                events.append(ReplyEvent(self.offset, 'control', bytes([byte]), byte, self.channel))
                if byte == 0xac:
                    self.channel = None
            else:
                if not self.line:
                    self.line_start = self.offset
                self.line.append(byte)
                if len(self.line) > self.max_line:
                    raise ValueError('Controller reply line exceeds the configured limit')
                if byte in (10, 13):
                    events.extend(self._flush())
            self.offset += 1
        return events

    def finish(self):
        """Flush a final unterminated line only when input is known to be over."""
        if self.channel_marker is not None:
            raise ValueError('Truncated controller channel selector')
        return self._flush()


@dataclass(frozen=True)
class ChannelMessage:
    offset: int
    channel: int
    payload: bytes


class ChannelMessageStream:
    """Collect AD/channel ... AC messages, retaining controls inside payloads."""
    def __init__(self, max_message=1024 * 1024):
        self.max_message = max_message
        self.offset = 0
        self.marker = None
        self.start = None
        self.channel = None
        self.payload = bytearray()

    def feed(self, data):
        messages = []
        for byte in data:
            if self.marker is not None:
                self.start = self.marker
                self.channel = byte
                self.marker = None
            elif byte == 0xad:
                if self.channel is not None:
                    raise ValueError('New channel selector before the preceding message terminator')
                self.marker = self.offset
            elif byte == 0xac:
                if self.channel is not None:
                    messages.append(ChannelMessage(self.start, self.channel, bytes(self.payload)))
                    self.channel = None
                    self.payload.clear()
            elif self.channel is not None:
                self.payload.append(byte)
                if len(self.payload) > self.max_message:
                    raise ValueError('Controller channel message exceeds the configured limit')
            self.offset += 1
        return messages

    def finish(self):
        if self.marker is not None or self.channel is not None:
            raise ValueError('Truncated controller channel message')
