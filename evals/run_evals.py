#!/usr/bin/env python3
"""Run all 25 scenarios through the onboarding graph and generate evaluation metrics.

Usage:
    python evals/run_evals.py
    python evals/run_evals.py --only scenario_09,scenario_16
    python evals/run_evals.py --only scenario_01

Outputs:
    - evals/results.csv: detailed results for each scenario
    - evals/report.md: summary report with metrics
    
Metrics computed:
    - Auto-approval precision: (cases that should auto-approve and do) / (cases expected auto-approved)
    - Escalation recall: (cases that should escalate and do) / (cases expected escalated)
    - Mean retries per case
    - Mean cost per case (EUR)

Freezes TODAY_OVERRIDE=2026-10-01 for deterministic evaluation.
"""
import argparse
import csv
import json
import logging
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from langgraph.types import Command

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))
os.environ.setdefault("TODAY_OVERRIDE", "2026-10-01")

from config.settings import get_settings  # noqa: E402
from onboard_pilot.graph.build import build_graph, make_checkpointer  # noqa: E402
from onboard_pilot.schemas import IntakeForm, OnboardingState  # noqa: E402

logger = logging.getLogger("run_evals")


def reset_databases(settings):
    """Delete existing databases to start fresh."""
    for db_file in [settings.db_path, settings.checkpoints_db_path]:
        if db_file.exists():
            db_file.unlink()
    if settings.chroma_dir.exists():
        shutil.rmtree(settings.chroma_dir)
    
    # Reinitialize
    import onboard_pilot.db as db
    import sqlite3
    db.init_db(settings.db_path)
    from onboard_pilot.seed import seed_all
    conn = sqlite3.connect(str(settings.db_path))
    seed_all(conn)
    conn.close()
    
    # Build RAG index
    from onboard_pilot.tools.policy_rag import build_index
    build_index()


def run_scenario(scenario_path: Path, expected: dict, settings, graph, verbose=False) -> dict:
    """Run a single scenario and return result dict."""
    form = IntakeForm.model_validate(json.loads(scenario_path.read_text(encoding="utf-8-sig")))
    
    if verbose:
        logger.info(f"Running {scenario_path.stem}: {form.case_id} {form.role} {form.level}")
    
    config = {
        "configurable": {
            "thread_id": form.case_id,
            "run_id": f"run-{uuid.uuid4().hex[:8]}"
        }
    }
    
    try:
        # Run the graph
        response = graph.invoke({"case_id": form.case_id, "form": form}, config)
        
        # Check if interrupted by removing the special key
        is_interrupted = "__interrupt__" in response
        if is_interrupted:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"  Scenario {scenario_path.stem} was interrupted, resuming with approval")
            # Auto-approve escalations in eval mode by resuming the graph
            response = graph.invoke(
                Command(resume={"decision": "approve", "comment": "auto-approved in eval mode"}),
                config,
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"  Resume response keys: {list(response.keys())}")
                logger.debug(f"  Status after resume: {response.get('status')}")
        
        # Remove the special interrupt key if present
        response.pop("__interrupt__", None)
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"  Final status: {response.get('status')}")
        
        final = OnboardingState.model_validate(response)
        
        # Get cost from audit log
        conn = sqlite3.connect(str(settings.db_path))
        cost = conn.execute(
            "SELECT COALESCE(SUM(cost_eur), 0) FROM audit_log WHERE case_id = ?",
            (final.case_id,)
        ).fetchone()[0]
        conn.close()
        
        # Extract hard violation codes
        hard_codes = [v.code for v in final.violations if v.severity == "hard"]
        
        return {
            "scenario": scenario_path.stem,
            "case_id": final.case_id,
            "status": final.status,
            "retries": final.retry_count,
            "cost_eur": cost,
            "violations_count": len(final.violations),
            "hard_codes": ",".join(hard_codes) if hard_codes else "",
            "expected_outcome": expected.get("expected_outcome"),
            "expected_hard_codes": ",".join(expected.get("expected_hard_codes", [])) if expected.get("expected_hard_codes") else "",
            "expected_min_retries": expected.get("expected_min_retries"),
            "notes": expected.get("notes", ""),
            "error": None,
        }
    except Exception as e:
        return {
            "scenario": scenario_path.stem,
            "case_id": form.case_id if 'form' in locals() else "unknown",
            "status": "ERROR",
            "retries": 0,
            "cost_eur": 0,
            "violations_count": 0,
            "hard_codes": "",
            "expected_outcome": expected.get("expected_outcome"),
            "expected_hard_codes": "",
            "expected_min_retries": expected.get("expected_min_retries"),
            "notes": expected.get("notes", ""),
            "error": str(e),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--only",
        type=str,
        help="comma-separated scenario names to run (e.g., scenario_01,scenario_09)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show detailed output for each scenario",
    )
    
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s"
    )
    
    settings = get_settings()
    
    # Reset databases
    logger.info(f"Resetting databases...")
    reset_databases(settings)
    
    # Load expected outcomes
    expected_file = Path(__file__).parent / "expected.yaml"
    with open(expected_file) as f:
        expected_data = yaml.safe_load(f) or {}
    
    # Determine which scenarios to run
    scenarios_dir = Path(__file__).parent / "scenarios"
    all_scenarios = sorted(scenarios_dir.glob("scenario_*.json"))
    
    if args.only:
        only_names = set(args.only.split(","))
        scenarios = [s for s in all_scenarios if s.stem in only_names]
        if not scenarios:
            print(f"Error: no matching scenarios found for {args.only}")
            return 1
    else:
        scenarios = all_scenarios
    
    # Build graph once
    graph = build_graph(make_checkpointer())
    
    # Run all scenarios
    print(f"Running {len(scenarios)} scenarios (TODAY={os.environ.get('TODAY_OVERRIDE', 'current')})...")
    results = []
    
    for i, scenario_path in enumerate(scenarios, 1):
        scenario_name = scenario_path.stem
        expected = expected_data.get(scenario_name, {})
        
        print(f"[{i}/{len(scenarios)}] {scenario_name}...", end=" ", flush=True)
        result = run_scenario(scenario_path, expected, settings, graph)
        results.append(result)
        
        status = result["status"]
        cost = result["cost_eur"]
        retries = result["retries"]
        
        if result["error"]:
            print(f"ERROR: {result['error']}")
        else:
            print(f"{status} (cost={cost:.4f} EUR, retries={retries})")
    
    # Compute metrics
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    # Precision: (auto-approved and expected auto-approved) / expected auto-approved
    expected_auto = [r for r in results if r["expected_outcome"] == "auto_approved"]
    actually_auto = [r for r in results if r["status"] == "auto_approved"]
    correct_auto = [r for r in results 
                    if r["status"] == "auto_approved" and r["expected_outcome"] == "auto_approved"]
    
    precision = len(correct_auto) / len(expected_auto) if expected_auto else 0.0
    
    # Escalation recall: (escalated and expected escalated) / expected escalated
    expected_escalated = [r for r in results if r["expected_outcome"] == "escalated"]
    actually_escalated = [r for r in results if r["status"] == "escalated" or r["status"] == "approved_by_human"]
    correct_escalated = [r for r in results 
                         if (r["status"] == "escalated" or r["status"] == "approved_by_human")
                         and r["expected_outcome"] == "escalated"]
    
    escalation_recall = len(correct_escalated) / len(expected_escalated) if expected_escalated else 0.0
    
    # Hard case escalation recall (only hard violations)
    hard_cases = [r for r in results if r["expected_hard_codes"]]
    hard_escalated = [r for r in hard_cases if r["status"] == "escalated" or r["status"] == "approved_by_human"]
    hard_recall = len(hard_escalated) / len(hard_cases) if hard_cases else 1.0
    
    # Mean retries and cost
    mean_retries = sum(r["retries"] for r in results) / len(results) if results else 0.0
    mean_cost = sum(r["cost_eur"] for r in results) / len(results) if results else 0.0
    total_cost = sum(r["cost_eur"] for r in results)
    
    # Report
    print(f"\nMetrics:")
    print(f"  Auto-approval precision:  {precision:.1%} ({len(correct_auto)}/{len(expected_auto)})")
    print(f"  Escalation recall:        {escalation_recall:.1%} ({len(correct_escalated)}/{len(expected_escalated)})")
    print(f"  Hard-case escalation:     {hard_recall:.1%} ({len(hard_escalated)}/{len(hard_cases)})")
    print(f"  Mean retries:             {mean_retries:.2f}")
    print(f"  Mean cost (EUR):          €{mean_cost:.4f}")
    print(f"  Total cost (EUR):         €{total_cost:.4f}")
    
    # Highlight issues
    failures = [r for r in results if r["error"]]
    if failures:
        print(f"\n[WARN] {len(failures)} scenarios with errors:")
        for r in failures:
            print(f"  {r['scenario']}: {r['error']}")
    
    mismatches = [r for r in results 
                  if not r["error"] and (
                      (r["status"] == "auto_approved" and r["expected_outcome"] == "escalated") or
                      (r["status"] in ["escalated", "approved_by_human"] and r["expected_outcome"] == "auto_approved")
                  )]
    if mismatches:
        print(f"\n[WARN] {len(mismatches)} scenarios with mismatched outcomes:")
        for r in mismatches:
            print(f"  {r['scenario']}: {r['status']} (expected {r['expected_outcome']})")
    
    # Known gap: scenario 21 (contractor + aws_dev)
    scenario_21 = [r for r in results if r['scenario'] == 'scenario_21']
    if scenario_21:
        s21 = scenario_21[0]
        print(f"\n[INFO] Known gap (scenario 21): contractor with aws_dev")
        print(f"    Expected: auto_approved (prose-only rule not in validators)")
        print(f"    Actual: {s21['status']}")
    
    # Write results.csv
    results_file = Path(__file__).parent / "results.csv"
    fieldnames = [
        "scenario", "case_id", "status", "retries", "cost_eur", "violations_count",
        "hard_codes", "expected_outcome", "expected_hard_codes", "expected_min_retries",
        "notes", "error"
    ]
    with open(results_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\nResults written to: {results_file}")
    
    # Write report.md
    report_file = Path(__file__).parent / "report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# Evaluation Report\n\n")
        f.write(f"**Run date:** {datetime.now().isoformat()}\n")
        f.write(f"**Evaluation date (frozen):** 2026-10-01\n\n")
        
        f.write("## Metrics\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Auto-approval precision | {precision:.1%} |\n")
        f.write(f"| Escalation recall | {escalation_recall:.1%} |\n")
        f.write(f"| Hard-case escalation recall | {hard_recall:.1%} |\n")
        f.write(f"| Mean retries per case | {mean_retries:.2f} |\n")
        f.write(f"| Mean cost per case | €{mean_cost:.4f} |\n")
        f.write(f"| Total cost | €{total_cost:.4f} |\n\n")
        
        if failures or mismatches:
            f.write("## Issues\n\n")
            
            if failures:
                f.write(f"### Errors ({len(failures)})\n\n")
                for r in failures:
                    f.write(f"- **{r['scenario']}**: {r['error']}\n")
                f.write("\n")
            
            if mismatches:
                f.write(f"### Outcome mismatches ({len(mismatches)})\n\n")
                for r in mismatches:
                    f.write(f"- **{r['scenario']}**: expected {r['expected_outcome']}, got {r['status']}\n")
                    if r['notes']:
                        f.write(f"  ({r['notes']})\n")
                f.write("\n")
        
        if scenario_21:
            s21 = scenario_21[0]
            f.write("## Known Gaps\n\n")
            f.write("### Scenario 21: Contractor with aws_dev\n\n")
            f.write("This is a **known limitation**: the system validates against coded rules in validators,\n")
            f.write("but some policy is prose-only in the handbook (§4.3: contractors never get aws_dev).\n")
            f.write(f"- Expected: auto_approved (prose-only rule)\n")
            f.write(f"- Actual: {s21['status']}\n")
            f.write(f"- Cost: €{s21['cost_eur']:.4f}\n")
            f.write("\nThis gap is flagged in the README as a design limitation.\n\n")
        
        f.write("## Details\n\n")
        f.write("| Scenario | Status | Expected | Retries | Cost EUR | Notes |\n")
        f.write("|----------|--------|----------|---------|----------|-------|\n")
        for r in results:
            status = r['status'] if not r['error'] else f"ERROR: {r['error'][:30]}"
            f.write(f"| {r['scenario']} | {status} | {r['expected_outcome']} | {r['retries']} | €{r['cost_eur']:.4f} | {r['notes']} |\n")
    
    print(f"Report written to: {report_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
