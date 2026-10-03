# DEVIATIONS & CLARIFICATIONS

Rule: never deviate from plan.md silently. Log every deviation or ambiguity decision below
(ID, what, why). The `P` entries are **pre-approved** — they fill gaps or contradictions in plan.md
and apply from step 1.

## Pre-approved clarifications

**P1 — `TOOL_FAILURE` soft violation code (sanctioned addition to the §6.2 enum).**
Scenario 22 (adobe_cc → `LICENSE_POOL_EXHAUSTED`) can only self-correct if a tool failure reaches the
revise loop, but routing only looks at violations. Add `TOOL_FAILURE` (soft). The `validate` node
appends violations built by `violations_from_tool_results(tool_results)` (in `validators.py`) for every
failed tool result **except** `UNKNOWN_SYSTEM` and `ROLE_NOT_PERMITTED` (those are already covered by
`ACCESS_NOT_IN_MATRIX` / `PRIVILEGED_ACCESS_REQUEST`). `run_all_validators` itself stays unchanged.

**P2 — Injected "today".** `config/settings.py` exposes `TODAY_OVERRIDE` (ISO date or unset) and
`get_today()`. Nodes call `get_today()`; validators/routing receive `today` as a parameter. Evals set
`TODAY_OVERRIDE=2026-10-01`.

**P3 — Which tables `finalize` owns.** Business tables = employees, equipment_orders,
onboarding_tasks, calendar_events, outbox, and the final `submitted` status of access_requests —
written only in `finalize`. Exceptions explicitly allowed: `it_provisioner` inserts
`access_requests(status='proposed')` during `execute_tools` (plan §5.2); `cases` is a control table
writable at any time (the approval queue needs it before finalize). `cases.status` stores the
**outcome** (`auto_approved | escalated | approved_by_human | rejected_by_human`); `finalize` sets
`finalized_at` and must not overwrite the outcome.

**P4 — Validators read reference data.** "No LLM" is the rule; read-only SQLite lookups (managers,
employees, catalog) are allowed, via `db.py` helpers with an optional `conn` parameter.

**P5 — Authoritative prices.** Budget totals use the catalog price when `catalog_id` exists (LLM-supplied
`price_eur` is only a fallback for unknown items, which already raise `UNKNOWN_CATALOG_ITEM`).

**P6 — Remote allowance.** For `location == remote_nl`: effective budget = level budget +
`min(remote_monitor_allowance_eur, total price of monitor-category items)`.

**P7 — Security training requirement.** Required iff the role's access-matrix entry contains `vpn` or
any system starting with `aws_`. Deadline = `start_date + 30 days`; compliance = `+14 days`.
Day-1 events must have `date == start_date`.

**P8 — Routing purity.** Omit the no-op placeholder block in plan §6.3. Add pure helper
`build_escalation_reason(state) -> str` in `routing.py`; the `escalate` node calls it.

**P9 — Literal-first plan prompt.** The plan prompt honours `requested_extras` literally and cites every
handbook section used; it does not pre-filter policy-violating requests. Validators + revise are the
policy layer. Document this in the README design decisions.

**P10 — Small dev conveniences.** `scripts/run_case.py` flags: `--auto-approve-escalations`,
`--resume <case_id> --decision approve|reject [--comment ...]`. `evals/run_evals.py` flag:
`--only scenario_09,scenario_16`.

**P11 — `dashboard/app.py` is a bootstrap, not a 4th page.** It defines `get_graph()`
(`@st.cache_resource`) and switches to `pages/1_Cases.py` under `if __name__ == "__main__":`.

**P12 — Cost table.** `COST_TABLE` in `llm.py` stores EUR per 1M tokens `(in, out)`. Look up current
`claude-haiku-4-5-20251001` pricing (believed ~$1 in / ~$5 out per 1M tokens — verify), note the date and the assumed USD→EUR rate in a comment and in the README.

**P13 — LLM is Claude Haiku 4.5 (overrides plan §1 "LLM" row and every mention of gpt-4o-mini,
`langchain-openai`, `OPENAI_API_KEY`, `get_openai_callback`).** Use `langchain-anthropic`:
`ChatAnthropic(model=settings.llm_model, temperature=0, max_tokens=settings.llm_max_tokens)` with
`llm_model = "claude-haiku-4-5-20251001"` and `llm_max_tokens = 4096` in `config/settings.py`. Key:
`ANTHROPIC_API_KEY`. Structured output: `llm.with_structured_output(OnboardingPlan, include_raw=True)`
(tool-use under the hood); read token counts from the raw message's `usage_metadata`
(`input_tokens` / `output_tokens`) and sum them across the parse-retry. The "retry once, then
`PLAN_PARSE_ERROR`" behaviour is unchanged.

**P14 — Embeddings are local (overrides plan §5.4 `text-embedding-3-small`).** Anthropic has no
embeddings API. Use Chroma's default local embedding function (ONNX all-MiniLM-L6-v2): no second API
key; the first run downloads the model (~80 MB, needs network). `RAG_SCORE_THRESHOLD` stays 0.35 per
plan §6.3, but it was not calibrated for this model — report observed scores (see step 4), do not
change the threshold silently. (If the user prefers OpenAI embeddings, that is a one-line change in
`policy_rag.py` plus `OPENAI_API_KEY`.)

## Logged during the build
(agent: append new entries as `D1`, `D2`, … with date, step, what, why)

**D1 — Step 1, 2026-10-04: Python 3.10 instead of 3.11+.** Target system has Python 3.10.11; spec requires 3.11+. Downgraded pyproject.toml `requires-python` to ">=3.10" to proceed. All Pydantic v2 schemas and Python 3.10-compatible syntax in use; no impact on functionality.
