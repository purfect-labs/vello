"""The std_minutes vs. std_dev_minutes bug — make sure the routine_variance check fires."""

def test_routine_variance_uses_std_dev_minutes(registered_user_id):
    """
    Pre-fix: gaps.py read p['std_minutes'] which doesn't exist; the
    routine_variance check silently never fired. This regression-tests
    the rename to std_dev_minutes.
    """
    from vello.database import upsert_context, upsert_temporal_pattern
    from vello.gaps import detect_gaps

    # User says they want a routine
    upsert_context(registered_user_id, "schedule", "preference",
                   "I want a consistent regular routine", source="manual")
    # But their wake_time pattern has std_dev > 60 minutes (very noisy)
    upsert_temporal_pattern(
        registered_user_id, "wake_time", "Wake time",
        mean_minutes=420, std_dev_minutes=75, sample_count=20, typical_days=[0, 1, 2, 3, 4],
    )

    gaps = detect_gaps(registered_user_id)
    # At least one routine_variance gap should fire now
    assert any(g["type"] == "routine_variance" for g in gaps), \
        f"routine_variance gap did not fire; got: {gaps}"
