"""Test 3 — Debugging

Evaluate the model's ability to identify subtle bugs, explain root causes,
and produce correct fixes. Tests cover: off-by-one errors, race conditions,
type mismatches, and logic errors."""

import textwrap
from .conftest import TestCase, TestResult, call_model, score_case


TEST_CASES: list[TestCase] = [
    TestCase(
        name="debug_off_by_one",
        description="Find the off-by-one error in a binary search implementation.",
        prompt=textwrap.dedent("""\
            Find and fix the bug(s) in this binary search implementation. Explain
            each bug you find, then provide the corrected code.

            ```python
            def binary_search(arr, target):
                left, right = 0, len(arr) - 1
                while left < right:
                    mid = (left + right) // 2
                    if arr[mid] == target:
                        return mid
                    elif arr[mid] < target:
                        left = mid
                    else:
                        right = mid
                return -1
            ```

            Requirements:
            - Identify ALL bugs, not just the first one
            - Explain why each bug causes incorrect behavior with a concrete example
            - Provide corrected code that handles all edge cases
        """),
        expected_keywords=[
            "left =", "right =", "mid", "while", "return",
            "off-by-one", "infinite loop", "edge case", "boundary",
            "corrected", "fix",
        ],
        min_length=400,
    ),
    TestCase(
        name="debug_race_condition",
        description="Identify and fix a race condition in concurrent code.",
        prompt=textwrap.dedent("""\
            Find the concurrency bug(s) in this counter implementation. Explain
            the root cause and provide a thread-safe version.

            ```python
            import threading

            class Counter:
                def __init__(self):
                    self.count = 0

                def increment(self, n=1):
                    current = self.count
                    # Simulate some async work
                    import time; time.sleep(0.01)
                    self.count = current + n

                def get_count(self):
                    return self.count
            ```

            Requirements:
            - Explain the race condition clearly with a scenario
            - Use threading.Lock or equivalent to fix it
            - Keep the same public API
        """),
        expected_keywords=[
            "race condition", "thread-safe", "Lock", "threading",
            "increment", "count", "atomic", "critical section",
            "fix", "corrected",
        ],
        min_length=400,
    ),
    TestCase(
        name="debug_type_error",
        description="Fix a subtle type error involving None and string operations.",
        prompt=textwrap.dedent("""\
            Find the bug(s) in this data processing function. It crashes on certain inputs.

            ```python
            def format_records(records):
                results = []
                for record in records:
                    name = record.get('name')
                    email = record.get('email', '')
                    formatted = f"{name} <{email}>"
                    if len(formatted) > 100:
                        formatted = formatted[:97] + "..."
                    results.append(formatted)
                return results
            ```

            Requirements:
            - Identify the crash scenario (what input causes it?)
            - Explain why it crashes
            - Provide a fixed version that handles all inputs gracefully
        """),
        expected_keywords=[
            "None", "TypeError", "format_records", "record.get",
            "f-string", "fix", "handle None", "graceful",
            "corrected", "edge case",
        ],
        min_length=300,
    ),
]


def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all debugging test cases."""
    results = []
    for case in TEST_CASES:
        output = call_model(
            client, model_name,
            prompt=case.prompt,
            system_prompt="You are an expert Python debugger. Be thorough and precise.",
            temperature=0.1,
        )
        result = TestResult(name=case.name, passed=False, score=0.0, model_output=output)
        score_case(result, case)
        results.append(result)
    return results


def test_debugging(client, model_name: str):
    """Run the full debugging battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== Debugging Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} debugging tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")
