"""Tests for deadman_switch.duress -- duress code generation."""

from __future__ import annotations

import pytest

from deadman_switch.duress import (
    DuressError, WORDLIST, classify, generate_codes,
)


def test_generate_codes_shape():
    codes = generate_codes("mission-seed")
    assert set(codes) == {"genuine", "duress"}
    assert len(codes["genuine"].split()) == 3
    assert len(codes["duress"].split()) == 3


def test_generate_codes_distinct():
    codes = generate_codes("mission-seed")
    assert codes["genuine"] != codes["duress"]


def test_generate_codes_deterministic():
    assert generate_codes("s") == generate_codes("s")


def test_generate_codes_seed_dependent():
    assert generate_codes("a") != generate_codes("b")


def test_generate_codes_validation():
    with pytest.raises(DuressError):
        generate_codes("  ")
    with pytest.raises(DuressError):
        generate_codes("s", words=1)


def test_generate_codes_custom_length():
    codes = generate_codes("s", words=5)
    assert len(codes["genuine"].split()) == 5


def test_words_from_wordlist():
    codes = generate_codes("s")
    for word in codes["genuine"].split():
        assert word in WORDLIST


def test_classify_genuine():
    codes = generate_codes("s")
    assert classify(codes["genuine"], "s") == "genuine"


def test_classify_duress():
    codes = generate_codes("s")
    assert classify(codes["duress"], "s") == "duress"


def test_classify_invalid():
    assert classify("totally wrong words", "s") == "invalid"


def test_classify_normalizes_whitespace_and_case():
    codes = generate_codes("s")
    messy = "  " + codes["genuine"].upper().replace(" ", "   ") + "  "
    assert classify(messy, "s") == "genuine"


def test_classify_wrong_seed():
    codes = generate_codes("s")
    assert classify(codes["genuine"], "other-seed") == "invalid"
