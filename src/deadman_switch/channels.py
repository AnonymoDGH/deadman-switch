"""Delivery channels for switch alerts.

When the switch fires, the alert has to reach someone. A single webhook is
fragile: one network blip and the alert is lost. This module models
delivery as channels with a retry queue.

Two concrete channels are provided, both safe for testing:

* FileChannel   -- appends the alert to a local file. Always available.
* UdpChannel    -- sends the alert as a datagram to a loopback port. The
  receiver is included so tests can verify delivery end to end without
  touching the real network.

On top of them, DeliveryQueue buffers alerts and retries failed sends with
a bounded attempt count, so a transient failure does not drop the alert.
Every send attempt is recorded so the event log can show exactly what was
tried.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "ChannelError",
    "SendResult",
    "Channel",
    "FileChannel",
    "UdpChannel",
    "DeliveryQueue",
]


class ChannelError(RuntimeError):
    """Raised when a channel is misconfigured."""


@dataclass(frozen=True)
class SendResult:
    """The outcome of one send attempt."""

    ok: bool
    channel: str
    detail: str


class Channel:
    """Base class for delivery channels."""

    name = "base"

    def send(self, message: str) -> SendResult:
        raise NotImplementedError


class FileChannel(Channel):
    """Append alerts to a local file, one JSON line each."""

    name = "file"

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def send(self, message: str) -> SendResult:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"alert": message}) + "\n")
            return SendResult(True, self.name, f"appended to {self.path}")
        except OSError as exc:
            return SendResult(False, self.name, f"write failed: {exc}")


class UdpChannel(Channel):
    """Send alerts as datagrams to a (loopback) UDP port."""

    name = "udp"

    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 timeout: float = 1.0) -> None:
        if not host:
            raise ChannelError("host must not be empty")
        if not 0 < port <= 65535:
            raise ChannelError("port must be in 1..65535")
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, message: str) -> SendResult:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(self.timeout)
                sock.sendto(message.encode("utf-8"), (self.host, self.port))
            return SendResult(True, self.name,
                              f"sent to {self.host}:{self.port}")
        except OSError as exc:
            return SendResult(False, self.name, f"send failed: {exc}")


class UdpReceiver:
    """A tiny loopback UDP receiver for tests and local tooling."""

    def __init__(self, host: str = "127.0.0.1") -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((host, 0))
        self._sock.settimeout(2.0)

    @property
    def port(self) -> int:
        return self._sock.getsockname()[1]

    def recv(self) -> Optional[str]:
        """Wait for one datagram; returns None on timeout."""
        try:
            data, _ = self._sock.recvfrom(65535)
            return data.decode("utf-8")
        except socket.timeout:
            return None

    def close(self) -> None:
        self._sock.close()


class DeliveryQueue:
    """Buffers alerts and retries failed sends with a bounded attempt count.

    Alerts are queued with deliver(). The queue tries each channel in order
    for each alert; a success removes the alert, a failure schedules a
    retry until max_attempts is reached. The full attempt history is kept
    for the event log.
    """

    def __init__(self, channels: List[Channel], max_attempts: int = 3) -> None:
        if not channels:
            raise ChannelError("at least one channel is required")
        if max_attempts < 1:
            raise ChannelError("max_attempts must be >= 1")
        self._channels = list(channels)
        self._max_attempts = max_attempts
        self._pending: List[Dict] = []
        self._delivered: List[str] = []
        self._dropped: List[str] = []
        self._attempts: List[SendResult] = []

    def deliver(self, message: str) -> None:
        """Queue one alert for delivery."""
        self._pending.append({"message": message, "attempts": 0})

    def flush(self) -> Dict:
        """Work the queue once: try every pending alert against the channels.

        Returns a summary with delivered/dropped/still-pending counts.
        """
        still_pending: List[Dict] = []
        for item in self._pending:
            sent = False
            for channel in self._channels:
                result = channel.send(item["message"])
                self._attempts.append(result)
                if result.ok:
                    self._delivered.append(item["message"])
                    sent = True
                    break
            if not sent:
                item["attempts"] += 1
                if item["attempts"] >= self._max_attempts:
                    self._dropped.append(item["message"])
                else:
                    still_pending.append(item)
        self._pending = still_pending
        return {
            "delivered": len(self._delivered),
            "dropped": len(self._dropped),
            "pending": len(self._pending),
        }

    @property
    def delivered(self) -> List[str]:
        return list(self._delivered)

    @property
    def dropped(self) -> List[str]:
        return list(self._dropped)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def attempts(self) -> List[SendResult]:
        return list(self._attempts)
