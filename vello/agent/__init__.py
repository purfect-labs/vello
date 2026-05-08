"""
Vello home agent.

The agent loop is what differentiates Vello v2 from v1: instead of just
*observing* and surfacing inferences, Vello plans and acts on home logistics
within a draft-first approval framework. See the build plan in
DESIGN_BRIEF.md and the architecture sections of README.md.

Public surface (kept small on purpose):

  loop.run_agent_turn(user_id, trigger)   → AgentTurnResult
  campaigns.find_matching_open(...)
  tools.get_tools(...)                    → tool catalog filtered by user
  approval.decide_approval(...)           → "auto" | "draft" | "deny"
"""
