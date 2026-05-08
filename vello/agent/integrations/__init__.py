"""
Integration adapters for external services. Each module exposes a single
`Client` class with a small, typed method surface consumed by tools.py.

All clients raise `ToolUnavailable` when the service key/OAuth token is
absent or the service returns an error that Vello can't recover from. The
agent loop catches `ToolUnavailable` and converts it into an `unavailable`
observation so the planner can re-route — the user never sees a raw exception.

Cost tracking: every client that incurs per-call cost calls
`db.record_integration_cost(user_id, integration_name, cost_usd)` after a
successful response. The daily budget cap in the approval engine reads from
the same ledger.
"""
