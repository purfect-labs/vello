"""Temporal pattern engine — wake-window guard, bimodal split, timezone."""

def test_wake_window_constants():
    from vello.temporal import WAKE_WINDOW
    wake_min, wake_max = WAKE_WINDOW
    # Sanity check the configured window: 4am to 11:30am local
    assert wake_min == 4 * 60
    assert wake_max == 11 * 60 + 30


def test_user_local_now_falls_back_to_utc_for_unknown_user():
    """Calling with a non-existent user_id must not raise; just returns UTC-ish."""
    from vello.temporal import user_local_now
    result = user_local_now("nonexistent-user")
    assert result is not None
    # The exact tz isn't important — just that it returned something


def test_log_observation_uses_local_minutes(registered_user_id):
    from vello.temporal import log_observation
    result = log_observation(registered_user_id, "wake_time", "Wake time", minutes=420)  # 7am
    assert result["pattern_key"] == "wake_time"
    assert result["sample_count"] == 1


def test_bimodal_split_detection(registered_user_id):
    """Distribution with two distinct clusters should split into :early and :late."""
    from vello.database import get_temporal_patterns
    from vello.temporal import log_observation

    # Cluster A: 7-8am workouts (5 obs)
    for _ in range(6):
        log_observation(registered_user_id, "gym_arrive", "Gym arrival", minutes=420)
    # Cluster B: 6-7pm workouts (5 obs), gap >> 45 min from cluster A
    for _ in range(6):
        log_observation(registered_user_id, "gym_arrive", "Gym arrival", minutes=1140)

    patterns = {p["pattern_key"]: dict(p) for p in get_temporal_patterns(registered_user_id)}
    assert "gym_arrive:early" in patterns
    assert "gym_arrive:late"  in patterns
