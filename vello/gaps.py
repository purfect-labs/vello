"""
Behavioral gap detection for Vello.

Compares stated preferences/goals from life_context against observed temporal
patterns. Gaps surface when the user says one thing and does another — useful
as conversation starters or nudge candidates.
"""
from vello.database import get_context, get_temporal_patterns


# Heuristic checks: (domain, key_fragment, pattern_key_fragment, description)
_GAP_CHECKS = [
    ("health",    "exercise",   "gym",        "states exercise goal but no gym pattern observed"),
    ("health",    "sleep",      "sleep",      "stated sleep goal differs from observed sleep time"),
    ("wellness",  "meditation", "meditation", "mentions meditation practice but no recurring pattern"),
    ("work",      "focus",      "work_start", "describes deep-work preference but work start is irregular"),
    ("health",    "diet",       None,         None),  # text-only, handled separately
]


def _context_map(user_id: str) -> dict[str, dict[str, str]]:
    """Return life_context as {domain: {key: value}}."""
    rows = get_context(user_id)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        result.setdefault(row["domain"], {})[row["key"]] = str(row["value"])
    return result


def _pattern_keys(user_id: str) -> set[str]:
    rows = get_temporal_patterns(user_id)
    return {r["pattern_key"] for r in rows}


def _pattern_map(user_id: str) -> dict[str, dict]:
    rows = get_temporal_patterns(user_id)
    return {r["pattern_key"]: dict(r) for r in rows}


def detect_gaps(user_id: str) -> list[dict]:
    ctx = _context_map(user_id)
    patterns = _pattern_map(user_id)
    pattern_keys = set(patterns.keys())
    gaps = []

    # ── Stated goal with no supporting pattern ──────────────────────────────
    for domain, key_frag, pat_frag, description in _GAP_CHECKS:
        if description is None:
            continue
        domain_ctx = ctx.get(domain, {})
        # Check if user has stated something containing the key fragment
        stated = any(key_frag in k.lower() or key_frag in v.lower()
                     for k, v in domain_ctx.items())
        if not stated:
            continue
        # Check for any matching temporal pattern
        has_pattern = pat_frag and any(pat_frag in pk for pk in pattern_keys)
        if not has_pattern:
            gaps.append({
                "type":        "missing_pattern",
                "domain":      domain,
                "description": description,
                "stated_key":  key_frag,
            })

    # ── Irregular schedule despite stated preference for routine ────────────
    schedule_ctx = ctx.get("schedule", {})
    routine_stated = any("routine" in v.lower() or "consistent" in v.lower() or "regular" in v.lower()
                         for v in schedule_ctx.values())
    if routine_stated:
        high_variance = [pk for pk, p in patterns.items()
                         if p.get("std_minutes", 0) and float(p["std_minutes"]) > 60]
        for pk in high_variance:
            gaps.append({
                "type":        "routine_variance",
                "domain":      "schedule",
                "description": f"stated preference for routine but '{pk}' has high time variance (std > 60 min)",
                "pattern_key": pk,
            })

    # ── Sleep: stated goal vs. observed mean ───────────────────────────────
    health_ctx = ctx.get("health", {})
    sleep_goal_entry = next(
        ((k, v) for k, v in health_ctx.items() if "sleep" in k.lower() and any(c.isdigit() for c in v)),
        None
    )
    sleep_pattern = patterns.get("sleep_time") or patterns.get("bedtime")
    if sleep_goal_entry and sleep_pattern:
        import re
        nums = re.findall(r'\d+', sleep_goal_entry[1])
        if nums:
            stated_hour = int(nums[0])
            obs_mean = sleep_pattern.get("mean_minutes")
            if obs_mean is not None:
                obs_hour = int(float(obs_mean)) // 60 % 24
                if abs(obs_hour - stated_hour) >= 2:
                    gaps.append({
                        "type":         "sleep_mismatch",
                        "domain":       "health",
                        "description":  f"stated sleep target ~{stated_hour}:00 but observed average is ~{obs_hour:02d}:{int(float(obs_mean))%60:02d}",
                        "stated":       sleep_goal_entry[1],
                        "observed_mean": obs_mean,
                    })

    return gaps


def gaps_as_context(user_id: str) -> str:
    gaps = detect_gaps(user_id)
    if not gaps:
        return ""
    lines = ["[BEHAVIORAL GAPS — stated vs. observed]"]
    for g in gaps:
        lines.append(f"- {g['description']}")
    return "\n".join(lines)
