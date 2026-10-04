#!/usr/bin/env python
"""Run one scenario JSON through the onboarding graph.

Usage:
    python scripts/run_case.py evals/scenarios/scenario_01.json
    python scripts/run_case.py <scenario.json> --auto-approve-escalations
    python scripts/run_case.py --resume case-0016 --decision approve [--comment "looks good"]

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

from langgraph.types import Command

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
    
    # Either run a new scenario or resume an escalated case
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("scenario", nargs="?", type=Path, help="path to a scenario JSON (an IntakeForm)")
    group.add_argument("--resume", type=str, help="case_id of an escalated case to resume")
    
    parser.add_argument(
        "--auto-approve-escalations",
        action="store_true",
        help="approve escalated cases automatically so the run completes (eval mode)",
    )
    parser.add_argument(
        "--decision",
        type=str,
        choices=["approve", "reject"],
        help="human decision when resuming: approve or reject",
    )
    parser.add_argument(
        "--comment",
        type=str,
        default=None,
        help="optional human comment when resuming",
    )
    
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    graph = build_graph(make_checkpointer())
    
    # Resume mode: apply human decision and resume the graph
    if args.resume:
        if not args.decision:
            parser.error("--decision is required when using --resume")
        
        case_id = args.resume
        config = {"configurable": {"thread_id": case_id}}
        
        # Resume by passing the human decision through the state
        # This allows the escalate node to see the decision and apply it
        final = OnboardingState.model_validate(
            graph.invoke(
                {
                    "human_decision": args.decision,
                    "human_comment": args.comment,
                },
                config,
            )
        )
    else:
        # Normal mode: run a new scenario
        form = IntakeForm.model_validate(json.loads(args.scenario.read_text(encoding="utf-8-sig")))
        config = {
            "configurable": {"thread_id": form.case_id, "run_id": f"run-{uuid.uuid4().hex[:8]}"}
        }
        
        response = graph.invoke({"case_id": form.case_id, "form": form}, config)
        
        # Check if the graph was interrupted (e.g., at escalate node)
        if "__interrupt__" in response:
            if args.auto_approve_escalations:
                # Resume with auto-approval by passing decision through state
                response = graph.invoke(
                    {
                        "human_decision": "approve",
                        "human_comment": "auto-approved in eval mode",
                    },
                    config,
                )
                final = OnboardingState.model_validate(response)
            else:
                # For now, just print that it was interrupted
                print(f"case:     {form.case_id}")
                print(f"status:   escalated")
                print(f"retries:  0")
                print(f"rag_min:  None")
                print(f"cost EUR: 0.0000")
                print(f"interrupted: awaiting human decision")
                return 0
        else:
            final = OnboardingState.model_validate(response)

    violations = final.violations
    conn = sqlite3.connect(str(settings.db_path))
    cost = conn.execute(
        "SELECT COALESCE(SUM(cost_eur), 0) FROM audit_log WHERE case_id = ?", (final.case_id,)
    ).fetchone()[0]
    conn.close()

    print(f"case:     {final.case_id}")
    print(f"status:   {final.status}")
    print(f"retries:  {final.retry_count}")
    print(f"rag_min:  {final.rag_min_score}")
    print(f"cost EUR: {cost:.4f}")
    print(f"violations ({len(violations)}):")
    for v in violations:
        print(f"  [{v.severity}] {v.code}: {v.message}")
    if final.escalation_reason:
        print(f"escalation: {final.escalation_reason}")
    if final.human_decision:
        print(f"human_decision: {final.human_decision}")
    if final.human_comment:
        print(f"human_comment: {final.human_comment}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
