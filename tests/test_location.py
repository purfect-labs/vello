"""Location event ingestion — the geofence pillar that wasn't implemented before."""

def test_record_location_event(registered_user_id):
    from vello.database import create_zone, record_location_event, get_recent_location_events
    zid = create_zone(registered_user_id, "Home", "home", None, None, None, 200)
    eid = record_location_event(registered_user_id, zid, "enter")
    assert eid

    events = get_recent_location_events(registered_user_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "enter"
    assert events[0]["zone_id"] == zid


def test_get_zone_returns_none_for_other_user(registered_user_id):
    """Cross-user access guard."""
    from vello.database import create_zone, create_user, get_zone
    other = create_user("other@example.com", "secure-test-password-42")
    zid = create_zone(other, "Home", "home", None, None, None, 200)
    assert get_zone(registered_user_id, zid) is None
