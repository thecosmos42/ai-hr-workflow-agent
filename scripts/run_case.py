#!/usr/bin/env python
"""Run one scenario JSON through the onboarding graph.

Usage:
    python scripts/run_case.py evals/scenarios/scenario_01.json
    python scripts/run_case.py <scenario.json> --auto-approve-escalations

TODAY_OVERRIDE defaults to 2026-10-01 here so min-notice checks are deterministic (P2);
set the environment variable to override.
"""
import argparse
import json
import logging
import os
import sqlite3
import sys
import uuid
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))
os.environ.setdefault("TODAY_OVERRIDE", "2026-10-01")

from config.settings import get_settings  # noqa: E402
from onboard_pilot.graph.build import build_graph, make_checkpointer  # noqa: E402
from onboard_pilot.schemas import IntakeForm, OnboardingState  # noqa: E402

logger = logging.getLogger("run_case")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", type=Path, help="path to a scenario JSON (an IntakeForm)")
    parser.add_argument(
        "--auto-approve-escalations",
        action="store_true",
        help="approve escalated cases automatically so the run completes (eval mode)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    form = IntakeForm.model_validate(json.loads(args.scenario.read_text(encoding="utf-8-sig")))
    graph = build_graph(make_checkpointer())
    config = {
        "configurable": {"thread_id": form.case_id, "run_id": f"run-{uuid.uuid4().hex[:8]}"}
    }
    # invoke() returns only written channels; validating fills the defaults back in
    final = OnboardingState.model_validate(
        graph.invoke({"case_id": form.case_id, "form": form}, config)
    )

    if final.status == "escalated" and args.auto_approve_escalations:
        raise NotImplementedError("escalation resume is implemented in build step 7")

    violations = final.violations
    conn = sqlite3.connect(str(settings.db_path))
    cost = conn.execute(
        "SELECT COALESCE(SUM(cost_eur), 0) FROM audit_log WHERE case_id = ?", (form.case_id,)
    ).fetchone()[0]
    conn.close()

    print(f"case:     {form.case_id}")
    print(f"status:   {final.status}")
    print(f"retries:  {final.retry_count}")
    print(f"rag_min:  {final.rag_min_score}")
    print(f"cost EUR: {cost:.4f}")
    print(f"violations ({len(violations)}):")
    for v in violations:
        print(f"  [{v.severity}] {v.code}: {v.message}")
    if final.escalation_reason:
        print(f"escalation: {final.escalation_reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
