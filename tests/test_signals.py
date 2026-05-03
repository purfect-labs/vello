"""Signal pipeline — pattern matching, dedup, transition chaining."""
import pytest


def test_scan_text_matches_job_change():
    from vello.signals import scan_text
    matches = scan_text("I just accepted an offer at Acme")
    assert any(m["signal_id"] == "job_change" for m in matches)


def test_scan_text_no_match_for_neutral_text():
    from vello.signals import scan_text
    assert scan_text("It's a nice day today.") == []


def test_fire_signals_dedupe(registered_user_id):
    """Same signal text fired twice should only create one trigger."""
    from vello.signals import fire_signals
    fired_first  = fire_signals(registered_user_id, "I have a flight to Tokyo next week")
    fired_second = fire_signals(registered_user_id, "I have a flight to Tokyo next week")
    assert fired_first == 1
    assert fired_second == 0


def test_signal_chaining_creates_watches(registered_user_id):
    """Firing job_change should activate watches on moving_home, schedule_disruption, financial_shift."""
    from vello.database import get_active_watch
    from vello.signals import fire_signals
    fire_signals(registered_user_id, "I'm starting at a new company next month")
    # The downstream watches should be active
    assert get_active_watch(registered_user_id, "moving_home") is not None
    assert get_active_watch(registered_user_id, "schedule_disruption") is not None
