"""DB-backed rate limiter — replaces the previous in-memory dict."""

def test_under_limit_does_not_raise():
    from vello.database import record_rate_limit_attempt, count_recent_rate_limit_attempts
    record_rate_limit_attempt("login", "1.2.3.4")
    assert count_recent_rate_limit_attempts("login", "1.2.3.4", window_seconds=300) == 1


def test_counts_only_within_window():
    from vello.database import record_rate_limit_attempt, count_recent_rate_limit_attempts, get_connection
    record_rate_limit_attempt("login", "1.2.3.4")
    # Backdate the row to 10 minutes ago
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE rate_limit_attempts SET attempt_at=datetime('now', '-15 minutes') WHERE key=?",
            ("1.2.3.4",),
        )
    conn.close()
    # 5-minute window should NOT see it
    assert count_recent_rate_limit_attempts("login", "1.2.3.4", window_seconds=300) == 0


def test_buckets_are_isolated():
    from vello.database import record_rate_limit_attempt, count_recent_rate_limit_attempts
    record_rate_limit_attempt("login", "1.2.3.4")
    record_rate_limit_attempt("reg",   "1.2.3.4")
    assert count_recent_rate_limit_attempts("login", "1.2.3.4", 300) == 1
    assert count_recent_rate_limit_attempts("reg",   "1.2.3.4", 300) == 1
    assert count_recent_rate_limit_attempts("export", "1.2.3.4", 300) == 0
