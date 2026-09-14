#!/usr/bin/env python3
"""Run the full LLM evaluation battery against a model.

Usage:
    python run_tests.py                     # uses default model & URL
    LLM_MODEL=qwen3.8-27b python run_tests.py
    LLM_BASE_URL=http://other:1234/v1 python run_tests.py --suite code_generation
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import all test modules
from tests.test_code_generation import run_tests as run_codegen
from tests.test_refactoring import run_tests as run_refactor
from tests.test_debugging import run_tests as run_debug
from tests.test_api_knowledge import run_tests as run_api
from tests.test_documentation import run_tests as run_docs
from tests.test_error_handling import run_tests as run_errors
from tests.test_system_design import run_tests as run_design

from tests.conftest import get_client, format_result


SUITE_MAP = {
    "code_generation": ("Code Generation", run_codegen),
    "refactoring": ("Refactoring", run_refactor),
    "debugging": ("Debugging", run_debug),
    "api_knowledge": ("API Knowledge", run_api),
    "documentation": ("Documentation", run_docs),
    "error_handling": ("Error Handling", run_errors),
    "system_design": ("System Design", run_design),
}


def main():
    client, model_name = get_client()

    # Parse args
    suites = sys.argv[1:]
    if not suites:
        suites = list(SUITE_MAP.keys())

    all_results = {}  # suite_key -> list[TestResult]
    summary = []

    for key in suites:
        if key not in SUITE_MAP:
            print(f"Unknown suite: {key}. Available: {', '.join(SUITE_MAP)}")
            sys.exit(1)
        label, runner_fn = SUITE_MAP[key]
        results = runner_fn(client, model_name)
        all_results[key] = results

    # Print full report
    print("=" * 70)
    print(f"LLM Evaluation Report — {model_name}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    grand_total = 0
    grand_passed = 0

    for key in suites:
        label, _ = SUITE_MAP[key]
        results = all_results[key]
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        avg_score = sum(r.score for r in results) / total if total else 0

        grand_total += total
        grand_passed += passed

        print(f"\n--- {label} ({passed}/{total} passed, avg={avg_score:.2%}) ---")
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.name} (score={r.score:.2%})")
            for d in r.details[:3]:  # top 3 details per test
                print(f"       {d}")

    # Overall summary
    overall_pct = grand_passed / grand_total if grand_total else 0
    print("\n" + "=" * 70)
    print(f"OVERALL: {grand_passed}/{grand_total} tests passed ({overall_pct:.2%})")
    print("=" * 70)

    # Save JSON report to results/
    report_dir = Path("results")
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_path = report_dir / f"report-{timestamp}.json"

    report_data = {
        "model": model_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": {"passed": grand_passed, "total": grand_total, "pct": overall_pct},
        "suites": {},
    }
    for key in suites:
        label, _ = SUITE_MAP[key]
        results = all_results[key]
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        avg_score = sum(r.score for r in results) / total if total else 0
        report_data["suites"][key] = {
            "name": label,
            "passed": passed,
            "total": total,
            "avg_score": round(avg_score, 4),
            "tests": [
                {"name": r.name, "passed": r.passed, "score": round(r.score, 4)}
                for r in results
            ],
        }

    report_path.write_text(json.dumps(report_data, indent=2))
    print(f"\nJSON report saved to: {report_path}")


if __name__ == "__main__":
    main()
