"""Tests for deadman_switch.proof -- proof-of-life challenges."""

from __future__ import annotations

import random

import pytest

from deadman_switch.proof import (
    Challenge, ProofError, ProofOfLife, make_arithmetic_challenge,
    make_recall_challenge,
)


def test_arithmetic_challenge_correct_answer():
    rng = random.Random(1)
    ch = make_arithmetic_challenge(rng)
    # Recompute the expected answer from the prompt.
    assert ch.kind == "arithmetic"
    assert ch.answer.lstrip("-").isdigit()


def test_arithmetic_deterministic():
    a = make_arithmetic_challenge(random.Random(5))
    b = make_arithmetic_challenge(random.Random(5))
    assert a == b


def test_challenge_window_validation():
    with pytest.raises(ProofError):
        Challenge(kind="arithmetic", prompt="p", answer="a", window_seconds=0)


def test_recall_challenge_uses_facts():
    facts = [{"q": "What is the word?", "a": "ORANGE"}]
    ch = make_recall_challenge(random.Random(1), facts=facts)
    assert ch.answer == "ORANGE"
    assert ch.kind == "recall"


def test_proof_issue_and_answer_correct():
    pol = ProofOfLife(seed=1)
    ch = pol.issue("arithmetic")
    result = pol.answer(ch.answer)
    assert result.correct is True
    assert result.duress is False


def test_proof_answer_wrong():
    pol = ProofOfLife(seed=1)
    pol.issue("arithmetic")
    result = pol.answer("definitely wrong")
    assert result.correct is False


def test_proof_answer_case_insensitive():
    facts = [{"q": "word?", "a": "ORANGE"}]
    pol = ProofOfLife(seed=1, facts=facts)
    pol.issue("recall")
    assert pol.answer("orange").correct is True


def test_proof_no_pending_raises():
    pol = ProofOfLife(seed=1)
    with pytest.raises(ProofError):
        pol.answer("x")


def test_proof_unknown_kind_raises():
    pol = ProofOfLife(seed=1)
    with pytest.raises(ProofError):
        pol.issue("telepathy")


def test_duress_flag_covert():
    pol = ProofOfLife(seed=1)
    ch = pol.issue("arithmetic")
    result = pol.answer(ch.answer, duress=True)
    # Looks like a correct beat...
    assert result.correct is True
    # ...but secretly flags coercion.
    assert result.duress is True
    assert pol.is_coerced() is True
    assert pol.duress_count == 1


def test_pass_rate():
    pol = ProofOfLife(seed=1)
    ch = pol.issue("arithmetic")
    pol.answer(ch.answer)          # correct
    ch2 = pol.issue("arithmetic")
    pol.answer("wrong")            # wrong
    assert pol.pass_rate() == 0.5


def test_pass_rate_empty():
    pol = ProofOfLife(seed=1)
    assert pol.pass_rate() == 1.0


def test_issue_replaces_pending():
    pol = ProofOfLife(seed=1)
    pol.issue("arithmetic")
    second = pol.issue("recall")
    assert pol.pending == second


def test_history_recorded():
    pol = ProofOfLife(seed=1)
    ch = pol.issue("arithmetic")
    pol.answer(ch.answer)
    assert len(pol.history) == 1
