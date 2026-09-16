#!/usr/bin/env python3
"""Run the full LLM evaluation battery against a model.

Usage:
    python run_tests.py                     # interactive menu for suites + model
    python run_tests.py mcp_tools debugging # skip menu, run specified suites (env vars for model)
    LLM_MODEL=nail-qwen3.6-35b-a3b-mtp python run_tests.py  # env model, no menu
"""

import json
import os
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
from tests.test_mcp_tools import run_tests as run_mcp

from tests.conftest import get_client
from make_html_report import write_html


SUITE_MAP = {
    "code_generation": ("Code Generation", run_codegen),
    "refactoring": ("Refactoring", run_refactor),
    "debugging": ("Debugging", run_debug),
    "api_knowledge": ("API Knowledge", run_api),
    "documentation": ("Documentation", run_docs),
    "error_handling": ("Error Handling", run_errors),
    "mcp_tools": ("MCP Tools", run_mcp),
}
def discover_models(base_url: str) -> list[str]:
    """Query /v1/models to discover available models on the server."""
    import urllib.request, urllib.error
    url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [m["id"] for m in data.get("data", [])]
    except Exception:
        return []

def pick_model(base_url: str, env_model: str | None) -> tuple[str, list[str]]:
    """Interactive model picker. Returns (chosen_model, available_models)."""
    models = discover_models(base_url)
    if not models and not env_model:
        print("No models discovered from server; using default.")
        return "nail-qwen3.6-35b-a3b-mtp", []

    # Prepend env model if it's not already in the list
    if env_model and env_model not in models:
        models.insert(0, env_model)

    print(f"\nAvailable models on {base_url} (default: {models[0]}):")
    for i, m in enumerate(models, 1):
        marker = " ← default" if i == 1 else (" (env)" if m == env_model else "")
        print(f"  {i}. {m}{marker}")

    while True:
        choice = input(f"\nSelect model [1-{len(models)}], type name to search (Enter=default): ").strip()
        if not choice:
            chosen = models[0]
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                chosen = models[idx]
            else:
                print(f"Invalid. Choose 1-{len(models)}.")
                continue
        else:
            # Try matching by name (prefix match)
            matches = [m for m in models if m.lower().startswith(choice.lower())]
            if len(matches) == 1:
                chosen = matches[0]
            elif len(matches) > 1:
                print(f"Ambiguous — matched: {', '.join(matches)}")
                continue
            else:
                print(f"Not found. Try again.")
                continue
        break
    return chosen, models

def pick_suites() -> list[str]:
    """Interactive suite picker. Returns selected suite keys."""
    keys = list(SUITE_MAP.keys())
    print(f"\nAvailable test suites:")
    for i, k in enumerate(keys, 1):
        label, runner_fn = SUITE_MAP[k]
        mod = sys.modules.get(runner_fn.__module__, None)
        n_tests = len(getattr(mod, "TEST_CASES", [])) if mod else "?"
        print(f"  {i}. {k} — {label} ({n_tests} tests)")

    while True:
        choice = input(f"\nSelect suite(s) [1-{len(keys)}, A for all, or comma-separated e.g. '1,3,7']: ").strip()
        if not choice:
            print("Defaulting to all suites.")
            return keys
        upper = choice.upper()
        if upper == "A":
            return keys
        # Parse comma-separated numbers or names
        parts = [p.strip() for p in choice.split(",") if p.strip()]
        selected: list[str] = []
        valid = True
        for part in parts:
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(keys):
                    selected.append(keys[idx])
                else:
                    print(f"Invalid index {part}.")
                    valid = False
                    break
            elif part in SUITE_MAP:
                selected.append(part)
            else:
                print(f"Unknown suite '{part}'.")
                valid = False
                break
        if not valid:
            continue
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for s in selected:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique


def main():
    base_url = os.environ.get("LLM_BASE_URL", "http://192.168.1.14:1234/v1")
    env_model = os.environ.get("LLM_MODEL") or None

    # Parse args — if any CLI flags present, skip interactive menu
    cli_args = sys.argv[1:]
    use_menu = not cli_args  # no args → interactive; args → direct mode

    if use_menu:
        model_name, _ = pick_model(base_url, env_model)
        suites = pick_suites()
    else:
        model_name = env_model or "nail-qwen3.6-35b-a3b-mtp"
        suites = cli_args  # treat positional args as suite keys
    # Create client (base_url from env; model_name passed separately to each call)
    client, _ = get_client()

    all_results = {}  # suite_key -> list[TestResult]
    summary = []
    # Save JSON reports incrementally so partial results survive mid-run crashes
    report_dir = Path("results")
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_path = report_dir / f"report-{timestamp}.json"
    html_path = ""

    def save_report(completed: list[str]) -> None:
        nonlocal html_path
        passed_total = sum(1 for k in completed for r in all_results[k] if r.passed)
        total_tests = sum(len(all_results[k]) for k in completed)
        data = {
            "model": model_name,
            "base_url": os.environ.get("LLM_BASE_URL", "http://192.168.1.14:1234/v1"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall": {
                "passed": passed_total,
                "total": total_tests,
                "pct": (passed_total / total_tests if total_tests else 0),
                "total_elapsed_s": round(
                    sum(r.elapsed_s for k in completed for r in all_results[k]), 1
                ),
            },
            "suites": {},
        }
        # Infer session details from model name + env vars
        mf = os.environ.get("LLM_SESSION_MODEL_FINGERPRINT", "")
        data["session"] = {
            "model": model_name,
            "base_url": data["base_url"],
            "ctx_window": int(os.environ.get("LLM_SESSION_CTX", "0") or "0"),
            "gpu_offload_layers": int(os.environ.get("LLM_SESSION_GPU_OFFLOAD", "0") or "0"),
            "reasoning_budget_tokens": int(os.environ.get("LLM_SESSION_REASONING_BUDGET", "0") or "0"),
            "moe_experts": int(os.environ.get("LLM_SESSION_EXPERTS", "0") or "0"),
            "speculative_decoding": bool(
                os.environ.get("LLM_SESSION_SPEC_DEC", "").lower() in ("true", "1", "yes")
            ) if os.environ.get("LLM_SESSION_SPEC_DEC") else "mtp" in model_name.lower(),
            "draft_tokens_per_step": int(os.environ.get("LLM_SESSION_DRAFT_TOKENS", "0") or "0"),
            "cache_quantization": os.environ.get("LLM_SESSION_CACHE_QUANT", ""),
            "system_fingerprint": mf,
        }
        # Aggregate draft/rejected stats across tests for spec-dec insight
        total_draft = sum(r.draft_tokens for k in completed for r in all_results[k])
        total_accepted = sum(r.accepted_draft_tokens for k in completed for r in all_results[k])
        total_rejected = sum(r.rejected_draft_tokens for k in completed for r in all_results[k])
        if total_draft > 0:
            data["session"]["spec_acceptance_rate"] = round(total_accepted / total_draft, 3)
            data["session"]["spec_efficiency"] = round(1 - total_rejected / max(total_draft, 1), 3)

        for key in completed:
            label, _ = SUITE_MAP[key]
            results = all_results[key]
            passed = sum(1 for r in results if r.passed)
            total = len(results)
            avg_score = sum(r.score for r in results) / total if total else 0
            data["suites"][key] = {
                "name": label,
                "passed": passed,
                "total": total,
                "avg_score": round(avg_score, 4),
                "tests": [
                    {
                        "name": r.name,
                        "passed": r.passed,
                        "score": round(r.score, 4),
                        "elapsed_s": r.elapsed_s,
                        "prefill_ms": r.prefill_ms,
                        "gen_speed": r.gen_speed,
                        "prompt_tokens": r.prompt_tokens,
                        "completion_tokens": r.completion_tokens,
                        "reasoning_tokens": r.reasoning_tokens,
                        "draft_tokens": r.draft_tokens,
                        "accepted_draft_tokens": r.accepted_draft_tokens,
                        "rejected_draft_tokens": r.rejected_draft_tokens,
                        "error": r.error,
                        "details": r.details,
                        "model_output": r.model_output,
                        "reasoning": r.reasoning,
                        "finish_reason": r.finish_reason,
                    }
                    for r in results
                ],
            }
        report_path.write_text(json.dumps(data, indent=2))
        html_path = write_html(report_path)

    for key in suites:
        if key not in SUITE_MAP:
            print(f"Unknown suite: {key}. Available: {', '.join(SUITE_MAP)}")
            sys.exit(1)
        label, runner_fn = SUITE_MAP[key]
        print(f"\n=== {label} ===", flush=True)
        results = runner_fn(client, model_name)
        all_results[key] = results
        save_report([k for k in suites if k in all_results])

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
        # Suite-level verdict (passes when ≥60% of tests pass)
        suite_pass = passed >= total * 0.6 if total else False
        print(f"  [{('PASS' if suite_pass else 'FAIL')} — SUITE]")

    # Overall summary
    overall_pct = grand_passed / grand_total if grand_total else 0
    print("\n" + "=" * 70)
    print(f"OVERALL: {grand_passed}/{grand_total} tests passed ({overall_pct:.2%})")
    print("=" * 70)

    # Save final JSON report (incremental saves already written per suite)
    save_report(suites)
    print(f"\nJSON report saved to: {report_path}")
    print(f"HTML report saved to: {html_path}")


if __name__ == "__main__":
    main()
