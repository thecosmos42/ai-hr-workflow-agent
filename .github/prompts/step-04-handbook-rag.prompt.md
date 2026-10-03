---
description: "Build step 4 — policy handbook + Chroma RAG index"
agent: agent
---
Execute **build step 4** of [plan.md](../../plan.md) §13. Read first: plan.md §5.4, §7, §6.1 and `.github/instructions/tools.instructions.md`. Step 3 must be ticked in [PROGRESS.md](../../PROGRESS.md). Embeddings are local (DEVIATIONS P14): no API key needed, but the first run downloads the model, so network access is required.

1. Write `config/policy_handbook.md` (~3,500–4,500 words, bullet-heavy, realistic corporate tone) with the **exact** section ids from §7. Use headings like `## §3 Equipment policy` and `### §3.2 Budget caps per level` so ids are parseable by regex.
   - §3.2 restates the exact budgets from `policy_tables.yaml` (1800 / 2200 / 2600 / 3000).
   - §4.3 says contractors never receive `aws_dev` (prose only — do NOT add a validator; known gap for scenario 21).
   - §6.4 says remote employees receive a home-office monitor allowance of **€500** — the planted contradiction. Do not resolve or flag it anywhere in the handbook.
   - §5: compliance within 14 days, security within 30 days for vpn/aws holders. §7: right-to-work task before start date. §8: day-1 events. §9: escalation to HR manager.
2. Implement `policy_rag.build_index()`: split on `##`/`###`, metadata `section_id` (e.g. `"§3.2"`), embed with Chroma's default local embedding function (P14) into Chroma collection `policy` at `data/chroma/` (cosine space). Idempotent: drop and recreate the collection. Wire it into `scripts/init_all.py` (already guarded).
3. Implement `query_policy(question, k=4)` returning `{section_id, text, score}` with score in [0,1] (`1 - cosine distance`, clipped).
4. Add one `@pytest.mark.integration` test (skipped if the embedding model can't be loaded) asserting `query_policy("monitor allowance remote")` returns a chunk with `section_id == "§6.4"` in the top results. Register the marker in `pyproject.toml`.

Calibration note: print the similarity scores for ~5 clearly relevant and ~5 irrelevant queries and report them to the user. `RAG_SCORE_THRESHOLD = 0.35` is FIXED in plan §6.3 — do not change it yourself.

Acceptance (run, show output):
- `python scripts/init_all.py`
- `python -c "from onboard_pilot.tools.policy_rag import query_policy; print(query_policy('monitor allowance remote'))"` → includes `§6.4`.

Finish: tick step 4, set current step to 5, commit `step 4: policy handbook and RAG`.
