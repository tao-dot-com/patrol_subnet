from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
import pytest

def test_scoring_for_invalid_payload():
    scoring = HotkeyOwnershipScoring()
    score = scoring.score(False, 0.5)
    assert score.overall == 0
    assert score.response_time == 0
    assert score.validity == 0

def test_scoring_for_zero_response_time():
    scoring = HotkeyOwnershipScoring()
    score = scoring.score(True, 0.0)
    assert score.overall == 1
    assert score.response_time == 1
    assert score.validity == 1

def test_scoring_for_2_second_response_time():
    scoring = HotkeyOwnershipScoring()
    score = scoring.score(True, 2)
    assert score.overall == 0.75
    assert score.response_time == 0.5
    assert score.validity == 1

def test_scoring_for_5_second_response_time():
    scoring = HotkeyOwnershipScoring()
    score = scoring.score(True, 5)
    assert score.overall == pytest.approx(0.64, 0.05)
    assert score.response_time == pytest.approx(0.29, 0.05)
    assert score.validity == 1

def test_scoring_for_60_second_response_time():
    scoring = HotkeyOwnershipScoring()
    score = scoring.score(True, 60)
    assert score.overall == pytest.approx(0.52, 0.05)
    assert score.response_time == pytest.approx(0.032, 0.05)
    assert score.validity == 1
