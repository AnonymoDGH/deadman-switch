"""Tests for deadman_switch.channels -- delivery channels with retry."""

from __future__ import annotations

import json

import pytest

from deadman_switch.channels import (
    ChannelError, DeliveryQueue, FileChannel, SendResult, UdpChannel,
    UdpReceiver,
)


def test_file_channel_appends(tmp_path):
    path = tmp_path / "alerts.jsonl"
    channel = FileChannel(path)
    result = channel.send("switch fired")
    assert result.ok
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[0])["alert"] == "switch fired"


def test_file_channel_appends_multiple(tmp_path):
    path = tmp_path / "alerts.jsonl"
    channel = FileChannel(path)
    channel.send("one")
    channel.send("two")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_udp_channel_validation():
    with pytest.raises(ChannelError):
        UdpChannel(host="", port=1000)
    with pytest.raises(ChannelError):
        UdpChannel(host="127.0.0.1", port=0)
    with pytest.raises(ChannelError):
        UdpChannel(host="127.0.0.1", port=70000)


def test_udp_roundtrip_loopback():
    receiver = UdpReceiver()
    try:
        channel = UdpChannel(host="127.0.0.1", port=receiver.port)
        result = channel.send("hello over udp")
        assert result.ok
        assert receiver.recv() == "hello over udp"
    finally:
        receiver.close()


def test_delivery_queue_delivers(tmp_path):
    channel = FileChannel(tmp_path / "a.jsonl")
    queue = DeliveryQueue([channel])
    queue.deliver("alert-1")
    summary = queue.flush()
    assert summary["delivered"] == 1
    assert summary["pending"] == 0
    assert queue.delivered == ["alert-1"]


class _FailingChannel(FileChannel):
    """A channel that always fails, for retry testing."""

    name = "failing"

    def send(self, message):
        return SendResult(False, self.name, "always fails")


def test_delivery_queue_retries_then_drops(tmp_path):
    queue = DeliveryQueue([_FailingChannel(tmp_path / "x")], max_attempts=2)
    queue.deliver("doomed")
    queue.flush()
    assert queue.pending_count == 1
    assert queue.dropped == []
    queue.flush()
    assert queue.pending_count == 0
    assert queue.dropped == ["doomed"]


def test_delivery_queue_falls_back_to_second_channel(tmp_path):
    failing = _FailingChannel(tmp_path / "x")
    good = FileChannel(tmp_path / "good.jsonl")
    queue = DeliveryQueue([failing, good])
    queue.deliver("fallback")
    summary = queue.flush()
    assert summary["delivered"] == 1
    assert (tmp_path / "good.jsonl").exists()


def test_delivery_queue_validation(tmp_path):
    with pytest.raises(ChannelError):
        DeliveryQueue([])
    with pytest.raises(ChannelError):
        DeliveryQueue([FileChannel(tmp_path / "x")], max_attempts=0)


def test_delivery_queue_records_attempts(tmp_path):
    queue = DeliveryQueue([_FailingChannel(tmp_path / "x")], max_attempts=1)
    queue.deliver("m")
    queue.flush()
    assert len(queue.attempts) == 1
    assert queue.attempts[0].ok is False
