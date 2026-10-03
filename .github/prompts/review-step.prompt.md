---
description: "Audit the current/last step against plan.md before moving on"
agent: agent
---
Audit the work for the step marked as current/just finished in [PROGRESS.md](../../PROGRESS.md) against [plan.md](../../plan.md), [DEVIATIONS.md](../../DEVIATIONS.md) and `.github/copilot-instructions.md`. **Do not add features.**

Check and report as a short table (✅ / ⚠️ / ❌ + file:line evidence):
1. Every FIXED item for this step's spec sections (field names, enum codes, file layout, check order, thresholds).
2. Hard constraints: no LLM in validators/routing; model name only from settings; business-table writes only in `finalize` (except P3); mock email/calendar only; prompts as top-level constants.
3. Acceptance criteria in PROGRESS.md — re-run the commands now and paste the output.
4. Undocumented deviations → add them to DEVIATIONS.md.
5. Scope creep (files, pages, deps not in plan.md).

Then fix every ❌ (code, not tests/thresholds/expectations) and re-run the acceptance commands. If everything passes, say so and stop.
