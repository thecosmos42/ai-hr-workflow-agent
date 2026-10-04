# HR Onboarding Agent — Implementation Plan

> **Audience:** This document is written for an implementing agent (or developer) who has NO prior
> context about this project. Follow it exactly. Where a decision is marked **FIXED**, do not
> deviate. Where marked **FLEXIBLE**, use judgment but document the choice in the README.
>
> **Project codename:** `onboard-pilot`

---

## 0. One-paragraph summary

Build a single LLM agent (LangGraph) that automates HR new-hire onboarding: it takes a structured
intake form, produces a complete onboarding plan (employee record, role-based account/access
requests, equipment order within budget, day-1 schedule, mandatory trainings), validates the plan
against **deterministic, coded policy rules** (not LLM judgment), self-corrects on validation
failure (max 3 retries), escalates to a human approval queue when hard rules trigger or retries are
exhausted, and logs every step (tokens, cost, latency, validation results) to an audit trail
rendered in a 3-page Streamlit dashboard. Includes an evaluation harness with 25 seeded scenarios
and 4 metrics, and a business-case README.

---

## 1. Hard constraints (FIXED)

| Constraint | Value |
|---|---|
| Language | Python 3.11+ |
| Agent framework | LangGraph (`langgraph` pip package) |
| Validation | Pydantic v2 schemas + pure-Python validator functions. **Validators MUST NOT call an LLM.** |
| LLM | Anthropic Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) via `langchain-anthropic` (`ChatAnthropic`), `temperature=0`. Model name in config, never hardcoded. |
| Storage | SQLite only (one file: `data/onboard.db`). No Postgres, no external DBs. |
| Vector store | ChromaDB, persisted to `data/chroma/`. |
| Dashboard | Streamlit. Exactly 3 pages. No auth. |
| Checkpointing | LangGraph `SqliteSaver` on `data/checkpoints.db`. |
| Email/calendar | MOCK ONLY. Writes to `outbox` and `calendar_events` tables. Never call real SMTP/Google/MS APIs. |
| DB writes | Business tables are written ONLY in the `finalize` node. All prior nodes operate on an in-memory proposed plan. (Audit/log tables may be written at any time.) |
| Determinism | All randomness seeded (`random.seed(42)` for mock tool failures). `temperature=0`. |
| Secrets | `ANTHROPIC_API_KEY` from environment / `.env` (python-dotenv). `.env` is gitignored. Commit a `.env.example`. |
| Package management | `uv` preferred; plain `pip` + `requirements.txt` acceptable. Pin top-level deps. |

**Out of scope — do NOT build:** PDF/OCR parsing, real email/calendar APIs, multi-agent crews,
dashboard auth/user management, offboarding workflow, Next.js, Docker (optional stretch only),
LLM-as-judge evaluation.

---

## 2. Repository structure (FIXED)

Create exactly this layout. Empty `__init__.py` files where needed to make packages importable.

```
onboard-pilot/
├── README.md                     # Business case (Section 12)
├── plan.md                       # This file (copy it in)
├── pyproject.toml                # or requirements.txt
├── .env.example                  # ANTHROPIC_API_KEY=sk-ant-...
├── .gitignore                    # .env, data/*.db, data/chroma/, __pycache__
│
├── config/
│   ├── settings.py               # pydantic-settings: model name, retry limit, paths, thresholds
│   ├── policy_tables.yaml        # machine-readable policy: budgets, access matrix, training rules
│   └── policy_handbook.md        # human-readable handbook (~8-10 pages) for RAG (Section 7)
│
├── src/onboard_pilot/
│   ├── __init__.py
│   ├── schemas.py                # ALL Pydantic models (Section 3)
│   ├── db.py                     # SQLite helpers: init_db(), connection, CRUD functions
│   ├── seed.py                   # seeds reference data: managers, catalog, access matrix
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── hr_db.py              # Tool 1 (Section 5.1)
│   │   ├── it_provisioner.py     # Tool 2 (Section 5.2)
│   │   ├── equipment_catalog.py  # Tool 3 (Section 5.3)
│   │   ├── policy_rag.py         # Tool 4 (Section 5.4)
│   │   └── scheduler.py          # Tool 5 (Section 5.5)
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── violations.py         # PolicyViolation model + violation codes enum
│   │   └── validators.py         # run_all_validators(plan, form) -> list[PolicyViolation]
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py              # OnboardingState TypedDict/Pydantic (Section 4)
│   │   ├── nodes.py              # intake, plan, execute_tools, validate, revise, escalate, finalize
│   │   ├── routing.py            # route_after_validation() — THE policy engine (Section 6.3)
│   │   └── build.py              # build_graph(checkpointer) -> compiled graph
│   │
│   ├── audit/
│   │   ├── __init__.py
│   │   └── logger.py             # AuditEvent writer; token/cost/latency capture (Section 8)
│   │
│   └── llm.py                    # single get_llm() factory; cost table for token pricing
│
├── dashboard/
│   ├── app.py                    # Streamlit entry; builds graph once via st.cache_resource
│   └── pages/
│       ├── 1_Cases.py            # case list + summary metrics
│       ├── 2_Case_Trace.py       # per-case step trace
│       └── 3_Approval_Queue.py   # HITL approve/reject, resumes graph
│
├── evals/
│   ├── scenarios/                # 25 JSON files: scenario_01.json ... scenario_25.json
│   ├── run_evals.py              # runs all scenarios, writes evals/results.csv + report.md
│   └── expected.yaml             # expected outcome per scenario (Section 10)
│
├── scripts/
│   ├── init_all.py               # init_db + seed + build RAG index; idempotent
│   └── run_case.py               # CLI: python scripts/run_case.py evals/scenarios/scenario_01.json
│
└── tests/
    ├── test_validators.py        # unit tests, no LLM needed
    ├── test_routing.py           # unit tests, no LLM needed
    └── test_tools.py             # mock-tool behavior incl. seeded failures
```

---

## 3. Data schemas (`schemas.py`) — FIXED field names

All models are Pydantic v2 (`BaseModel`, `model_config = ConfigDict(extra="forbid")`).

### 3.1 IntakeForm (input)

```python
class IntakeForm(BaseModel):
    case_id: str                    # unique, e.g. "case-0007"
    full_name: str
    email: EmailStr                 # personal email
    role: Literal["software_engineer", "data_analyst", "finance_officer",
                  "hr_coordinator", "sales_rep", "engineering_manager"]
    level: Literal["junior", "medior", "senior", "lead"]
    department: Literal["engineering", "data", "finance", "hr", "sales"]
    start_date: date                # ISO format in JSON
    manager_email: EmailStr         # must exist in employees table (seeded managers)
    location: Literal["eindhoven_office", "amsterdam_office", "remote_nl"]
    contract_type: Literal["permanent", "fixed_term", "contractor"]
    visa_required: bool
    accessibility_needs: str | None = None
    requested_extras: list[str] = []   # free-text equipment/software wishes, may be invalid
```

### 3.2 OnboardingPlan (agent output — the thing validated)

```python
class AccessRequest(BaseModel):
    system: str                     # must match a key in access matrix, e.g. "gitlab"
    justification: str

class EquipmentItem(BaseModel):
    catalog_id: str                 # must exist in equipment_catalog table
    name: str
    price_eur: float
    quantity: int = 1

class ScheduledEvent(BaseModel):
    title: str
    event_type: Literal["it_setup", "manager_1on1", "buddy_lunch",
                        "compliance_training", "security_training", "hr_intro"]
    date: date
    duration_minutes: int

class OnboardingTask(BaseModel):
    title: str
    owner: Literal["hr", "it", "manager", "employee"]
    due_date: date

class OnboardingPlan(BaseModel):
    case_id: str
    employee_summary: str                    # 1-2 sentence human-readable summary
    access_requests: list[AccessRequest]
    equipment: list[EquipmentItem]
    schedule: list[ScheduledEvent]
    tasks: list[OnboardingTask]
    policy_citations: list[str]              # handbook section ids used, e.g. ["§3.2", "§5.1"]
```

The `plan` node must produce this via structured output
(`llm.with_structured_output(OnboardingPlan)`). If structured output fails to parse, retry once,
then treat as a validation failure with code `PLAN_PARSE_ERROR`.

### 3.3 PolicyViolation

```python
class PolicyViolation(BaseModel):
    code: str            # from ViolationCode enum (Section 6.2)
    severity: Literal["hard", "soft"]
    message: str         # human-readable, includes the offending value and the limit
    field_path: str      # e.g. "equipment[1].price_eur"
    policy_ref: str      # e.g. "§3.2" or "policy_tables.yaml:budgets"
```

### 3.4 ToolResult (uniform wrapper for all tool calls)

```python
class ToolResult(BaseModel):
    tool: str
    ok: bool
    data: dict | list | None = None
    error_code: str | None = None     # e.g. "LICENSE_POOL_EXHAUSTED"
    error_message: str | None = None
```

Tools NEVER raise on business failures — they return `ok=False` with an error code. Only raise
on programmer errors (bad arguments).

---

## 4. Graph state (`graph/state.py`) — FIXED

Use a Pydantic model as LangGraph state (or TypedDict mirroring it exactly):

```python
class OnboardingState(BaseModel):
    case_id: str
    form: IntakeForm
    plan: OnboardingPlan | None = None
    tool_results: list[ToolResult] = []
    violations: list[PolicyViolation] = []
    retry_count: int = 0                      # incremented by revise node
    status: Literal["running", "auto_approved", "escalated",
                    "approved_by_human", "rejected_by_human", "finalized"] = "running"
    escalation_reason: str | None = None
    human_decision: Literal["approve", "reject"] | None = None
    human_comment: str | None = None
    rag_min_score: float | None = None        # lowest retrieval score used in planning
    audit_events: list[dict] = []             # appended per node (also mirrored to DB)
```

---

## 5. Tools — exact behavior specs

Every tool is exposed to the LLM (where applicable) as a LangChain `@tool` with a docstring, and
also callable as a plain function for nodes/tests. All return `ToolResult`.

### 5.1 `hr_db.py`
Functions (deterministic, no LLM):
- `lookup_manager(email) -> ToolResult` — ok if email exists in `employees` with `is_manager=1`;
  else `error_code="MANAGER_NOT_FOUND"`.
- `check_duplicate(full_name, email) -> ToolResult` — `ok=False, error_code="DUPLICATE_EMPLOYEE"`
  if an employee with same email already exists.
- `create_employee(form) -> ToolResult` — INSERT into `employees`. **Called only from `finalize`.**

### 5.2 `it_provisioner.py` (mock API)
- `request_account(system: str, role: str, case_id: str) -> ToolResult`
- Behavior (FIXED):
  1. If `system` not in the access matrix at all → `error_code="UNKNOWN_SYSTEM"`.
  2. If `system` not allowed for `role` per `policy_tables.yaml` → `error_code="ROLE_NOT_PERMITTED"`.
  3. Seeded failure: the system `"adobe_cc"` ALWAYS returns `error_code="LICENSE_POOL_EXHAUSTED"`
     (this powers demo scenario D5; deterministic, not random).
  4. Otherwise ok; INSERT a row into `access_requests` with `status='proposed'`
     (status updated to `'submitted'` in finalize).
- Note: this duplicates the access-matrix check that validators also do. That is intentional —
  tool-level rejection simulates a real API; the validator is the policy backstop.

### 5.3 `equipment_catalog.py`
- `search_catalog(query: str | None, category: str | None) -> ToolResult` — returns matching
  rows (id, name, category, price_eur, in_stock).
- `get_item(catalog_id) -> ToolResult`.
- The catalog does NOT enforce budgets. Budget enforcement is validator-only (document this
  separation in the README).
- Seed ~20 items (Section 9.2) including deliberately over-budget options (MacBook Pro €3,499)
  and cheaper alternates (ThinkPad €1,249), plus one out-of-stock item.

### 5.4 `policy_rag.py`
- Build step (in `scripts/init_all.py`): split `config/policy_handbook.md` on `##`/`###`
  headings into chunks; each chunk's metadata includes its section id (e.g. `"§3.2"`).
  Embed with ChromaDB's default local embedding function (no API key needed; Anthropic offers no
  embeddings API) into Chroma collection `policy`.
- `query_policy(question: str, k: int = 4) -> ToolResult` — returns chunks with
  `{section_id, text, score}` where score is similarity in [0,1].
- The `plan` node records the minimum score among retrieved chunks it used into
  `state.rag_min_score`.

### 5.5 `scheduler.py` (mock)
- `propose_events(...)` is NOT a tool — the LLM puts events directly into `OnboardingPlan.schedule`.
- `commit_events(plan) -> ToolResult` — called only from `finalize`; inserts into
  `calendar_events` and writes one summary email into `outbox`.

---

## 6. Validation & policy engine

### 6.1 Machine-readable policy (`config/policy_tables.yaml`) — FIXED content

```yaml
equipment_budget_eur:        # total equipment budget per level
  junior: 1800
  medior: 2200
  senior: 2600
  lead: 3000
remote_monitor_allowance_eur: 350   # EXTRA allowance, remote_nl only — see planted ambiguity §A1

access_matrix:               # role -> allowed systems
  software_engineer:  [email, slack, gitlab, vpn, jira, aws_dev]
  data_analyst:       [email, slack, jira, tableau, snowflake_read, vpn]
  finance_officer:    [email, slack, erp_finance, expense_tool]
  hr_coordinator:     [email, slack, hris, ats]
  sales_rep:          [email, slack, crm, expense_tool]
  engineering_manager: [email, slack, gitlab, vpn, jira, aws_dev, hris_team_view]

privileged_systems: [aws_prod, erp_admin, hris]   # any request here from a NON-listed role => hard escalation
                                                   # hris allowed only for hr_coordinator (matrix governs)

training_deadlines_days:     # days after start_date by which training must be scheduled
  compliance_training: 14
  security_training: 30      # security required only for roles with vpn or aws access

min_notice_days: 10          # start_date must be >= today + 10 days
mandatory_day1_events: [it_setup, manager_1on1, hr_intro]
```

### 6.2 Violation codes (`validation/violations.py`) — FIXED enum

| Code | Severity | Check |
|---|---|---|
| `BUDGET_EXCEEDED` | soft | sum(equipment price×qty) > budget for level (+ remote allowance if `location=remote_nl` and the extra items are monitor-category) |
| `ACCESS_NOT_IN_MATRIX` | soft | requested system not in matrix for role (and not privileged) |
| `PRIVILEGED_ACCESS_REQUEST` | **hard** | requested system in `privileged_systems` and not permitted by matrix |
| `TRAINING_MISSING` | soft | required training absent from schedule |
| `TRAINING_TOO_LATE` | soft | training scheduled after deadline |
| `MISSING_DAY1_EVENT` | soft | any of `mandatory_day1_events` absent on start_date |
| `START_DATE_TOO_SOON` | **hard** | start_date < today + min_notice_days |
| `MANAGER_NOT_FOUND` | **hard** | manager_email not a seeded manager |
| `DUPLICATE_EMPLOYEE` | **hard** | email already in employees |
| `VISA_TASK_MISSING` | soft | `visa_required=true` but no task titled containing "right to work" owned by hr |
| `UNKNOWN_CATALOG_ITEM` | soft | equipment catalog_id not in catalog |
| `ITEM_OUT_OF_STOCK` | soft | catalog item has in_stock=0 |
| `PLAN_PARSE_ERROR` | soft | structured output failed twice |

`run_all_validators(plan, form, today) -> list[PolicyViolation]` runs every check, returns all
violations (not just the first). `today` is a parameter (injectable for tests/evals — in evals,
freeze `today = date(2026, 10, 1)`).

### 6.3 Routing (`graph/routing.py`) — FIXED logic, must be a pure function

```python
MAX_RETRIES = 3           # from config
RAG_SCORE_THRESHOLD = 0.35

def route_after_validation(state) -> Literal["finalize", "revise", "escalate"]:
    hard = [v for v in state.violations if v.severity == "hard"]
    soft = [v for v in state.violations if v.severity == "soft"]
    if hard:
        return "escalate"                      # hard violations never retry
    if soft and state.retry_count < MAX_RETRIES:
        return "revise"
    if soft:                                   # retries exhausted
        return "escalate"
    # no violations — soft escalation triggers:
    if state.rag_min_score is not None and state.rag_min_score < RAG_SCORE_THRESHOLD:
        return "escalate"                      # low policy-retrieval confidence
    if any(c in state.form.model_dump_json() for c in []):  # placeholder, keep simple
        pass
    if conflicting_policy_detected(state):     # see below
        return "escalate"
    return "finalize"
```

`conflicting_policy_detected(state)`: returns True iff the plan's `policy_citations` include BOTH
`"§3.2"` and `"§6.4"` (the planted contradiction, Section 7) AND `form.location == "remote_nl"`.
This is a simple deterministic proxy for "policy ambiguity detected" — document it honestly in
the README as a heuristic.

When routing to `escalate`, set `state.escalation_reason` to a formatted string listing the
trigger(s).

### 6.4 The revise loop — FIXED behavior
- `revise` node prompt gets: the current plan JSON, the list of violations (as JSON), and the
  instruction: *"Modify ONLY the parts of the plan needed to resolve these violations. Return the
  full corrected OnboardingPlan."*
- Increment `retry_count` by 1 per revise.
- After revise → go back to `execute_tools` → `validate` (tool calls re-run on the revised plan;
  proposed `access_requests` rows for this case are deleted and re-inserted each pass).

---

## 7. Policy handbook (`config/policy_handbook.md`) — content spec

Write ~8–10 pages, bullet-heavy, realistic corporate tone. Timebox: 3 hours. Required sections
(section ids FIXED because validators/routing reference them):

- **§1 Purpose & scope**
- **§2 Roles and responsibilities** (HR coordinator, IT, hiring manager)
- **§3 Equipment policy** — §3.1 standard kits per role; **§3.2 budget caps per level —
  MUST restate the exact numbers from policy_tables.yaml**; §3.3 ordering process
- **§4 System access policy** — §4.1 access matrix prose; §4.2 privileged systems require
  CISO approval (always human); §4.3 contractor restrictions (contractors never get aws_dev —
  NOTE: this rule exists ONLY in prose, not in validators → it is a known gap, used in eval
  scenario 21 to show a limitation; document in README "failure modes")
- **§5 Trainings** — compliance within 14 days; security within 30 days for vpn/aws holders
- **§6 Remote work** — §6.1–§6.3 generic; **§6.4 PLANTED CONTRADICTION:** "Remote employees
  receive a home-office monitor allowance of €500" (contradicts policy_tables.yaml's €350 and
  §3.2's cap). Do not resolve it — this drives escalation scenario D3.
- **§7 Visa & right-to-work** — HR must open a right-to-work verification task before start date
- **§8 Day-1 schedule requirements** — it_setup, manager_1on1, hr_intro mandatory on day 1
- **§9 Escalation & exceptions** — anything not covered goes to HR manager

---

## 8. Audit logging (`audit/logger.py`)

Table `audit_log` (one row per node execution per case):

```sql
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  run_id TEXT, case_id TEXT, ts TEXT,
  node TEXT,                    -- intake|plan|execute_tools|validate|revise|escalate|finalize
  attempt INTEGER,              -- retry_count at time of execution
  tokens_in INTEGER, tokens_out INTEGER,
  cost_eur REAL,                -- from a COST_TABLE dict {model: (in_price, out_price)} in llm.py
  latency_ms INTEGER,
  summary TEXT,                 -- short outcome, e.g. "3 violations: BUDGET_EXCEEDED, ..."
  payload_json TEXT             -- full violations / tool results / plan diff for trace page
);
```

Implementation: a `@log_node` decorator wrapping each node function — captures wall-clock latency;
token usage read from the LangChain response's `usage_metadata` (`input_tokens` / `output_tokens`)
for LLM nodes, zeros for pure-Python nodes. Also append a compact dict to `state.audit_events`.

Other business tables: `employees`, `access_requests`, `equipment_orders`, `calendar_events`,
`onboarding_tasks`, `outbox`, `cases` (case_id, status, created_at, finalized_at,
escalation_reason, human_decision, human_comment, thread_id).

---

## 9. Seed data (`seed.py`) — FIXED

### 9.1 Employees (managers)
Seed 5 managers: `anna.visser@corp.example` (engineering), `tom.bakker@corp.example` (data),
`sofia.jansen@corp.example` (finance), `mark.devries@corp.example` (hr),
`lisa.smit@corp.example` (sales). All `is_manager=1`.

### 9.2 Equipment catalog (~20 items, key ones FIXED)
| catalog_id | name | category | price_eur | in_stock |
|---|---|---|---|---|
| EQ-001 | ThinkPad T14 | laptop | 1249 | 1 |
| EQ-002 | MacBook Pro 14 | laptop | 3499 | 1 |
| EQ-003 | MacBook Air 13 | laptop | 1399 | 1 |
| EQ-004 | Dell 27" Monitor | monitor | 289 | 1 |
| EQ-005 | LG 34" Ultrawide | monitor | 549 | 1 |
| EQ-010 | Herman Miller chair | furniture | 1100 | 0 |
| ... | (headset, dock, keyboard, mouse, phone, etc.) | | 20–400 | 1 |

---

## 10. Evaluation harness (`evals/`)

### 10.1 Scenarios — 25 JSON intake forms + `expected.yaml`

`expected.yaml` maps each scenario to:
```yaml
scenario_01:
  expected_outcome: auto_approved        # auto_approved | escalated
  expected_hard_codes: []                # violation codes that must appear (hard)
  expected_min_retries: 0
  notes: "happy path junior engineer"
```

Scenario distribution (FIXED):
- **1–8:** clean happy paths across all 6 roles/levels/locations → `auto_approved`
- **9–12:** budget traps (requested_extras like "MacBook Pro", "two ultrawide monitors") →
  agent should self-correct within retries → `auto_approved`, `expected_min_retries: 1`
- **13–15:** access violations (finance asking for gitlab via requested_extras) → self-correct → auto_approved
- **16–18:** hard escalations — scenario 16: privileged access (`requested_extras: ["aws_prod access"]`);
  17: start_date 3 days out; 18: unknown manager email
- **19:** visa case, agent must add right-to-work task → auto_approved
- **20:** remote_nl hire with monitor request → hits planted §3.2/§6.4 contradiction → `escalated`
- **21:** contractor requesting aws_dev → prose-only rule, validators pass → records whatever
  happens; expected `auto_approved` but flagged in report as **known gap** (README failure mode)
- **22:** adobe_cc request → LICENSE_POOL_EXHAUSTED → agent substitutes alternative + adds
  follow-up task → auto_approved
- **23:** duplicate employee email → escalated (hard)
- **24:** out-of-stock chair → self-correct to alternative → auto_approved
- **25:** everything-wrong stress case (over budget + wrong access + missing training) →
  must resolve in ≤3 retries or escalate; expected `escalated` acceptable — record actual

### 10.2 Metrics (`run_evals.py` writes `results.csv` + `report.md`)
1. **Auto-approval precision** — of auto-approved cases, fraction whose final plan passes
   `run_all_validators` with zero violations AND expected_outcome was auto_approved.
2. **Escalation recall** — of scenarios with expected_outcome=escalated, fraction actually escalated.
3. **Mean retries per case.**
4. **Mean cost per case (EUR)** and total eval cost.

Eval runs must freeze `today = 2026-10-01` and reset the DB (fresh file) before each full run.
Escalated cases in eval mode are auto-resolved as "approve" so the run completes (flag
`--auto-approve-escalations`).

---

## 11. Dashboard (3 pages, Streamlit)

Graph is built ONCE in `app.py` via `@st.cache_resource` with `SqliteSaver`; `thread_id = case_id`.

- **`1_Cases.py`** — table of all cases (id, name, role, status, retries, cost, created) +
  4 metric tiles: total cases, % auto-approved, mean cost/case, mean retries. Button "Run scenario"
  with a file picker over `evals/scenarios/`.
- **`2_Case_Trace.py`** — select case → chronological audit_log rows rendered as expandable
  steps: node, attempt, latency, tokens, cost, summary; expanding shows payload (violations,
  plan diff, tool results). This is the money page — make the self-correction visible.
- **`3_Approval_Queue.py`** — cases with `status='escalated'`: show proposed plan (pretty),
  escalation_reason, policy citations, violations. Buttons Approve / Reject + comment box.
  On click: `graph.invoke(Command(resume={"decision": ..., "comment": ...}),
  config={"configurable": {"thread_id": case_id}})`. Approve → finalize runs; Reject →
  status `rejected_by_human`, END (no further revise — keep simple).

Escalation uses `interrupt()` inside the `escalate` node (LangGraph ≥0.2 pattern).

---

## 12. README.md — business case (write LAST, Week 4)

Required sections: Problem (HR coordinator ~45 min/hire across 4 systems, mid-size 500–2,000 FTE
company) · Solution overview + architecture diagram (mermaid) · Demo (GIF + the 5 demo scenarios
D1=scenario_01 happy, D2=scenario_09 budget self-correct, D3=scenario_20 ambiguity escalation,
D4=scenario_16 privileged access, D5=scenario_22 license failure) · Hours-saved math
(150 hires/yr × 40 min saved ≈ 100 hrs) · Eval results table · **Failure modes & mitigations**
(prose-only rules gap → move rules to tables; stale RAG; over-escalation tuning; cost table) ·
Design decisions (deterministic validators vs LLM-judge; DB writes only in finalize; cheap model
+ governance) · Setup instructions.

---

## 13. Build order & acceptance criteria

Work strictly in this order. Do not start a step until the previous step's acceptance criteria pass.

| # | Step | Acceptance criteria |
|---|---|---|
| 1 | Repo scaffold, config, schemas, db.py, seed.py, init_all.py | `python scripts/init_all.py` creates DB with seeded managers + catalog; re-running is idempotent |
| 2 | Tools (all 5) + tests | `pytest tests/test_tools.py` green; adobe_cc always fails; matrix rejections work |
| 3 | Validators + routing + tests | `pytest tests/test_validators.py tests/test_routing.py` green; every violation code has ≥1 test |
| 4 | Policy handbook + RAG index | `query_policy("monitor allowance remote")` returns §6.4 chunk with section_id |
| 5 | Linear graph (intake→plan→execute→validate→finalize), happy path | `python scripts/run_case.py evals/scenarios/scenario_01.json` → status auto_approved, rows in all business tables, audit_log populated |
| 6 | Revise loop | scenario_09 self-corrects: trace shows BUDGET_EXCEEDED then clean pass, retries ≥1 |
| 7 | Escalation + interrupt + resume via CLI flag | scenario_16 ends `escalated`; resuming with approve finalizes; checkpoint survives process restart |
| 8 | Streamlit 3 pages | approval queue resume works from UI; trace page shows scenario_09's correction |
| 9 | All 25 scenarios + run_evals.py | `python evals/run_evals.py` completes, writes results.csv + report.md; precision ≥0.85, escalation recall = 1.0 on hard cases (if not met, fix prompts/validators, not expectations) |
| 10 | README + demo GIF + cleanup | Fresh clone + `.env` + init_all + run scenario_01 works per README instructions |

**General rules for the implementer:**
- Commit after each step with message `step N: <description>`.
- If any spec here is impossible as written (library API changed, etc.), choose the closest
  equivalent, and record the deviation in a `DEVIATIONS.md` at repo root. Never silently deviate.
- Keep every LLM prompt in code as a named constant at the top of its module.
- No feature not listed in this document.
