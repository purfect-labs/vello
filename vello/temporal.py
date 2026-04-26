"""
Temporal pattern engine for Vello.

Learns recurring time-of-day behaviors from observation logs, detects when
the user is running late, and automatically splits bimodal distributions
into sub-patterns (e.g. "gym days leave at 7:30, other days at 9:00").
"""
import math
import json
from datetime import datetime, timezone
from typing import Optional

from vello.database import (
    log_temporal_observation,
    get_temporal_observations,
    upsert_temporal_pattern,
    get_temporal_patterns,
    get_temporal_pattern,
)


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance)


def _minutes_now() -> int:
    t = datetime.now(timezone.utc)
    return t.hour * 60 + t.minute


def _day_of_week_now() -> int:
    return datetime.now(timezone.utc).weekday()  # 0=Mon


def minutes_to_hhmm(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    period = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d}{period}"


# ── Bimodal detection ──────────────────────────────────────────────────────────

def _find_bimodal_split(sorted_values: list[int]) -> Optional[int]:
    """
    Scan for the largest gap in sorted observations.
    Returns the split index if:
      - gap > 45 minutes (large enough to be two distinct behaviors)
      - at least 5 observations on each side (statistical stability)
    Returns None if distribution is unimodal.
    """
    n = len(sorted_values)
    if n < 10:
        return None

    max_gap = 0
    split_at = -1
    for i in range(1, n):
        gap = sorted_values[i] - sorted_values[i - 1]
        if gap > max_gap:
            max_gap = gap
            split_at = i

    if max_gap < 45 or split_at < 5 or split_at > n - 5:
        return None
    return split_at


def _typical_days_for(observations: list, indices: set[int]) -> list[int]:
    """Compute typical days for a subset of observations identified by index."""
    day_counts: dict[int, int] = {}
    count = 0
    for i, r in enumerate(observations):
        if i in indices:
            d = r["day_of_week"]
            day_counts[d] = day_counts.get(d, 0) + 1
            count += 1
    if count == 0:
        return []
    total_weeks = max(count / 7, 1)
    return [d for d, c in day_counts.items() if c / total_weeks >= 0.3]


def _build_and_persist_pattern(user_id: str, pattern_key: str, label: str,
                                values: list[float], observations: list,
                                indices: set[int]) -> dict:
    """Compute stats for a set of observations and upsert the pattern."""
    mean, std = _mean_std(values)
    typical_days = _typical_days_for(observations, indices)
    upsert_temporal_pattern(
        user_id, pattern_key, label,
        mean_minutes=mean,
        std_dev_minutes=std,
        sample_count=len(values),
        typical_days=typical_days,
    )
    return {
        "pattern_key":     pattern_key,
        "label":           label,
        "mean_minutes":    mean,
        "std_dev_minutes": std,
        "sample_count":    len(values),
        "typical_days":    sorted(set(typical_days)),
        "mean_time":       minutes_to_hhmm(mean),
    }


def update_pattern_stats(user_id: str, pattern_key: str, label: str) -> dict:
    """
    Recompute mean/std from stored observations and persist.
    If the distribution is bimodal, automatically creates two sub-patterns
    ({pattern_key}:A and {pattern_key}:B) and marks the parent as bimodal.
    Uses the 90 most recent observations.
    """
    rows = get_temporal_observations(user_id, pattern_key, limit=90)
    if not rows:
        return {}

    all_minutes = [r["minutes"] for r in rows]
    sorted_minutes = sorted(all_minutes)
    split = _find_bimodal_split(sorted_minutes)

    if split is not None:
        # Build index sets for each cluster
        threshold = sorted_minutes[split - 1] + (sorted_minutes[split] - sorted_minutes[split - 1]) / 2
        cluster_a_idx = {i for i, r in enumerate(rows) if r["minutes"] < threshold}
        cluster_b_idx = {i for i, r in enumerate(rows) if r["minutes"] >= threshold}
        vals_a = [rows[i]["minutes"] for i in cluster_a_idx]
        vals_b = [rows[i]["minutes"] for i in cluster_b_idx]

        # Persist sub-patterns
        result_a = _build_and_persist_pattern(
            user_id, f"{pattern_key}:early", f"{label} (early)", vals_a, rows, cluster_a_idx)
        result_b = _build_and_persist_pattern(
            user_id, f"{pattern_key}:late",  f"{label} (late)",  vals_b, rows, cluster_b_idx)

        # Parent pattern: persist with bimodal stats for reference
        mean, std = _mean_std(all_minutes)
        typical_days = list({d for r in rows for d in [r["day_of_week"]]})
        upsert_temporal_pattern(user_id, pattern_key, label,
                                mean_minutes=mean, std_dev_minutes=std,
                                sample_count=len(rows), typical_days=typical_days)
        return {"pattern_key": pattern_key, "bimodal": True,
                "clusters": [result_a, result_b]}

    # Unimodal path
    mean, std = _mean_std(all_minutes)
    typical_days_map: dict[int, int] = {}
    for r in rows:
        d = r["day_of_week"]
        typical_days_map[d] = typical_days_map.get(d, 0) + 1
    total_weeks = max(len(rows) / 7, 1)
    typical_days = [d for d, c in typical_days_map.items() if c / total_weeks >= 0.3]

    upsert_temporal_pattern(user_id, pattern_key, label,
                            mean_minutes=mean, std_dev_minutes=std,
                            sample_count=len(rows), typical_days=typical_days)
    return {
        "pattern_key":     pattern_key,
        "label":           label,
        "mean_minutes":    mean,
        "std_dev_minutes": std,
        "sample_count":    len(rows),
        "typical_days":    sorted(set(typical_days)),
        "mean_time":       minutes_to_hhmm(mean),
    }


def log_observation(user_id: str, pattern_key: str,
                    label: str, minutes: Optional[int] = None) -> dict:
    """Record one observation and return updated pattern stats."""
    if minutes is None:
        minutes = _minutes_now()
    dow = _day_of_week_now()
    log_temporal_observation(user_id, pattern_key, minutes, dow)
    return update_pattern_stats(user_id, pattern_key, label)


def predict_pattern(user_id: str, pattern_key: str) -> Optional[dict]:
    """
    Return the predicted next occurrence for a pattern.
    If the pattern is bimodal, returns prediction for the sub-pattern
    that applies today (by day-of-week), falling back to the earlier cluster.
    """
    current_dow = _day_of_week_now()

    # Try sub-patterns first
    for suffix in (":early", ":late"):
        sub = get_temporal_pattern(user_id, pattern_key + suffix)
        if sub and sub["sample_count"] >= 3:
            typical_days = json.loads(sub["typical_days"])
            if current_dow in typical_days:
                return {
                    "pattern_key":     sub["pattern_key"],
                    "label":           sub["label"],
                    "predicted_time":  minutes_to_hhmm(sub["mean_minutes"]),
                    "mean_minutes":    sub["mean_minutes"],
                    "std_dev_minutes": sub["std_dev_minutes"],
                    "typical_days":    typical_days,
                    "sample_count":    sub["sample_count"],
                }

    row = get_temporal_pattern(user_id, pattern_key)
    if not row or row["sample_count"] < 3:
        return None
    typical_days = json.loads(row["typical_days"])
    return {
        "pattern_key":     pattern_key,
        "label":           row["label"],
        "predicted_time":  minutes_to_hhmm(row["mean_minutes"]),
        "mean_minutes":    row["mean_minutes"],
        "std_dev_minutes": row["std_dev_minutes"],
        "typical_days":    typical_days,
        "sample_count":    row["sample_count"],
    }


def detect_deviations(user_id: str, threshold_std: float = 1.5) -> list[dict]:
    """
    Compare current time against all learned patterns for today.
    Skips parent keys when bimodal sub-patterns exist (uses the sub-pattern instead).
    Only fires for patterns that typically occur today.
    """
    current_minutes = _minutes_now()
    current_dow = _day_of_week_now()
    patterns = get_temporal_patterns(user_id)
    deviations = []

    # Collect all pattern keys so we can skip parents with active sub-patterns
    all_keys = {r["pattern_key"] for r in patterns}

    for row in patterns:
        key = row["pattern_key"]

        # Skip parent if bimodal sub-patterns exist
        if f"{key}:early" in all_keys or f"{key}:late" in all_keys:
            continue

        if row["mean_minutes"] is None or row["sample_count"] < 5:
            continue

        typical_days = json.loads(row["typical_days"])
        if current_dow not in typical_days:
            continue

        mean = row["mean_minutes"]
        std  = row["std_dev_minutes"] or 15.0
        late_by = current_minutes - mean

        if late_by > threshold_std * std:
            deviations.append({
                "pattern_key":      key,
                "label":            row["label"],
                "expected_time":    minutes_to_hhmm(mean),
                "current_time":     minutes_to_hhmm(current_minutes),
                "late_by_minutes":  int(late_by),
                "message": (
                    f"You haven't {row['label'].lower()} yet — "
                    f"you usually do around {minutes_to_hhmm(mean)}."
                ),
            })

    return deviations


def refresh_all_patterns() -> None:
    """Recompute pattern stats for every user that has observations."""
    from vello.database import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT user_id, pattern_key, label FROM temporal_patterns"
    ).fetchall()
    conn.close()
    for row in rows:
        try:
            update_pattern_stats(row["user_id"], row["pattern_key"], row["label"])
        except Exception:
            pass
