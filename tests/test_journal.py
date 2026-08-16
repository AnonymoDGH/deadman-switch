"""Tests for deadman_switch.journal -- operator journal."""

from __future__ import annotations

import pytest

from deadman_switch.journal import Entry, Journal, JournalError


def _journal():
    j = Journal()
    j.add(100.0, "left home", ["travel"])
    j.add(200.0, "boarded flight", ["travel", "flight"])
    j.add(300.0, "landed safe", ["travel"])
    j.add(400.0, "checked into hotel")
    return j


def test_entry_validation():
    with pytest.raises(JournalError):
        Entry(1.0, "  ")


def test_add_and_len():
    j = _journal()
    assert len(j) == 4


def test_add_out_of_order_rejected():
    j = Journal()
    j.add(100.0, "first")
    with pytest.raises(JournalError):
        j.add(50.0, "backwards")


def test_by_tag():
    j = _journal()
    travel = j.by_tag("travel")
    assert len(travel) == 3
    flight = j.by_tag("flight")
    assert len(flight) == 1
    assert flight[0].text == "boarded flight"


def test_by_tag_case_insensitive():
    j = Journal()
    j.add(1.0, "x", ["TRAVEL"])
    assert len(j.by_tag("travel")) == 1


def test_window():
    j = _journal()
    window = j.window(150.0, 350.0)
    assert [e.text for e in window] == ["boarded flight", "landed safe"]


def test_window_invalid():
    j = _journal()
    with pytest.raises(JournalError):
        j.window(300.0, 100.0)


def test_last():
    j = _journal()
    last_two = j.last(2)
    assert [e.text for e in last_two] == ["landed safe", "checked into hotel"]


def test_last_invalid():
    with pytest.raises(JournalError):
        _journal().last(0)


def test_all_tags():
    j = _journal()
    assert j.all_tags() == ["flight", "travel"]


def test_text_roundtrip():
    j = _journal()
    restored = Journal.from_text(j.to_text())
    assert len(restored) == 4
    assert restored.entries[0].text == "left home"
    assert restored.entries[1].tags == ["travel", "flight"]


def test_from_text_corrupt():
    with pytest.raises(JournalError):
        Journal.from_text("{not json")


def test_from_text_out_of_order():
    text = ('{"ts": 200, "text": "b", "tags": []}\n'
            '{"ts": 100, "text": "a", "tags": []}')
    with pytest.raises(JournalError):
        Journal.from_text(text)


def test_entry_from_dict_missing():
    with pytest.raises(JournalError):
        Entry.from_dict({"ts": 1.0})
