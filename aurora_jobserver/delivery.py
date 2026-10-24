"""Offline completion tracking for the captured raster transfer profile.

The caller explicitly starts tracking its own upload. This class never opens a
socket or resends a job. Its returned host-terminate request is an action for a
future session transport, not a physical command executed by this module.
"""
import re

from .replies import ChannelMessageStream, MainReplyStream
from .wire import TERMINATE


class DeliveryTracker:
    def __init__(self):
        self.state = 'idle'
        self.errors = []
        self.job_time = None
        self.end_code = None
        self.main = MainReplyStream()
        self.channels = ChannelMessageStream()

    def begin_upload(self):
        if self.state != 'idle':
            raise ValueError('A tracker is used for exactly one delivery attempt')
        self.state = 'awaiting_end'

    def feed(self, data):
        actions = []
        for event in self.main.feed(data):
            if event.kind == 'controller_error':
                self.errors.append(event.value)
        for message in self.channels.feed(data):
            if message.channel == 5 and message.payload.startswith(b'\x06E'):
                if self.state == 'awaiting_end':
                    self.end_code = message.payload[2:3].decode('ascii', errors='replace')
                    if message.payload != b'\x06E0\x06':
                        self.state = 'delivery_unknown'
                        continue
                    self.state = 'awaiting_job_report'
                    actions.append(TERMINATE)
            elif message.channel == 80 and self.state == 'awaiting_job_report':
                match = re.fullmatch(rb'\s*JOB_TIME ([0-9]+(?:\.[0-9]+)?)\s*\x04', message.payload)
                if match is None:
                    self.state = 'delivery_unknown'
                else:
                    self.job_time = float(match[1])
                    self.state = 'completed_with_warning' if self.errors else 'completed'
        return actions

    def disconnected(self):
        if self.state in ('awaiting_end', 'awaiting_job_report'):
            self.state = 'delivery_unknown'
