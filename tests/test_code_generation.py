"""Test 1 — Code Generation

Evaluate the model's ability to produce correct, idiomatic Python code
from natural-language specifications. Tests cover: basic algorithms,
data structures, standard library usage, and type hints."""

import ast
import textwrap
from typing import Any

from .conftest import TestCase, TestResult, call_model, score_case


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

TEST_CASES: list[TestCase] = [
    TestCase(
        name="generate_sort_function",
        description="Write a stable sort implementation from scratch (no built-in sorted).",
        prompt=textwrap.dedent("""\
            Write a Python function `stable_sort(items, key=None)` that implements
            a stable sorting algorithm from scratch. Do NOT use Python's built-in
            `sorted()` or `list.sort()`. Include type hints and docstring.

            Requirements:
            - Must be stable (equal elements preserve original order)
            - O(n log n) time complexity preferred
            - Handle None values gracefully
        """),
        expected_keywords=[
            "def stable_sort", "key", "lambda", "stable", "sort",
            "merge", "insertion", "bubble", "selection", "quicksort",
            "type hint", "docstring", "None",
        ],
        forbidden_patterns=["sorted(", "list.sort()"],
        min_length=200,
    ),
    TestCase(
        name="generate_context_manager",
        description="Write a context manager for file handling with proper cleanup.",
        prompt=textwrap.dedent("""\
            Write a Python context manager class `AtomicFile` that:
            - Takes a filepath and mode in __init__
            - On enter, creates the file; on exit, atomically replaces the target
              (write to temp, then os.replace)
            - Handles exceptions by cleaning up the temp file
            - Supports `with AtomicFile('out.txt', 'w') as f:` syntax

            Include type hints and a usage example in the docstring.
        """),
        expected_keywords=[
            "__enter__", "__exit__", "tempfile", "os.replace",
            "AtomicFile", "context manager", "shutil", "cleanup",
            "type hint", "docstring",
        ],
        min_length=300,
    ),
    TestCase(
        name="generate_async_http_client",
        description="Write an async HTTP client with retry logic.",
        prompt=textwrap.dedent("""\
            Write an async Python class `RetryClient` that wraps `aiohttp.ClientSession`:
            - Constructor accepts base_url, max_retries (default 3), and backoff_factor
            - A `get(path)` method that returns response text with exponential backoff
            - Retries on ConnectionError, TimeoutError, and 5xx responses
            - Uses asyncio.sleep for backoff delay
            - Properly closes the session via async context manager protocol

            Include type hints throughout.
        """),
        expected_keywords=[
            "aiohttp", "async def", "__aenter__", "__aexit__",
            "max_retries", "backoff", "exponential", "ConnectionError",
            "TimeoutError", "5xx", "retry", "type hint",
        ],
        min_length=400,
    ),
]


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all code-generation test cases and return results."""
    results = []
    for case in TEST_CASES:
        output = call_model(
            client, model_name,
            prompt=case.prompt,
            system_prompt="You are an expert Python developer. Write clean, correct, idiomatic code.",
            temperature=0.1,
        )
        result = TestResult(name=case.name, passed=False, score=0.0, model_output=output)
        score_case(result, case)
        results.append(result)

    return results


def test_code_generation(client, model_name: str):
    """Run the full code generation battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== Code Generation Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} code generation tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(format_result(r))
