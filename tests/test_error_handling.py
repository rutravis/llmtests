"""Test 6 — Error Handling

Evaluate the model's ability to write code that handles errors gracefully.
Tests cover: custom exceptions, retry logic, input validation, and cleanup."""

import textwrap
from .conftest import TestCase, TestResult, call_model, score_case


TEST_CASES: list[TestCase] = [
    TestCase(
        name="err_custom_exceptions",
        description="Design a hierarchy of custom exceptions with proper chaining.",
        prompt=textwrap.dedent("""\
            Write a Python module `errors.py` that defines an exception hierarchy for
            a file processing pipeline:

            Base: `PipelineError(Exception)` — base class with `step` and `message` attrs
            ├── `ValidationError(PipelineError)` — bad input data
            ├── `ProcessingError(PipelineError)` — runtime failure during processing
            └── `OutputError(PipelineError)` — failed to write output

            Requirements:
            - All exceptions accept `message`, `step`, and optional `cause` (Exception)
            - Use exception chaining (`raise ... from cause`) in the docstring example
            - Include a `__str__` that formats as `[<step>] <message>`
        """),
        expected_keywords=[
            "PipelineError", "ValidationError", "ProcessingError", "OutputError",
            "__init__", "cause", "raise ... from", "exception chain",
            "__str__", "type hint",
        ],
        min_length=400,
    ),
    TestCase(
        name="err_retry_with_backoff",
        description="Implement a robust retry decorator with exponential backoff.",
        prompt=textwrap.dedent("""\
            Write a Python decorator `@retry(max_retries=3, exceptions=(ConnectionError,),
            backoff_factor=0.5)` that:
            - Retries the decorated function on specified exception types
            - Uses exponential backoff: sleep(backoff_factor * 2^attempt)
            - Logs each retry attempt (use print for simplicity)
            - Re-raises the last exception after all retries exhausted
            - Works with async and sync functions

            Include type hints and a usage example.
        """),
        expected_keywords=[
            "retry", "decorator", "functools.wraps", "exponential",
            "backoff", "ConnectionError", "max_retries", "attempt",
            "sleep", "raise", "type hint",
        ],
        min_length=400,
    ),
    TestCase(
        name="err_input_validation",
        description="Write comprehensive input validation for a config parser.",
        prompt=textwrap.dedent("""\
            Write a Python function `validate_config(config: dict) -> list[str]` that
            validates a configuration dict and returns a list of error messages.

            Schema requirements:
            - 'host': required, must be non-empty string
            - 'port': required, must be int between 1-65535
            - 'timeout': optional, defaults to 30, must be positive number
            - 'retries': optional, defaults to 3, must be non-negative int
            - 'tags': optional, if present must be list of strings

            Requirements:
            - Return empty list for valid config
            - One error message per validation failure
            - Use descriptive error messages (e.g., "port must be between 1 and 65535")
        """),
        expected_keywords=[
            "validate_config", "host", "port", "timeout", "retries",
            "tags", "list[str]", "error message", "required",
            "type check", "isinstance", "range",
        ],
        min_length=300,
    ),
]


def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all error handling test cases."""
    results = []
    for case in TEST_CASES:
        output = call_model(
            client, model_name,
            prompt=case.prompt,
            system_prompt="You are an expert Python developer. Write robust, defensive code.",
            temperature=0.1,
        )
        result = TestResult(name=case.name, passed=False, score=0.0, model_output=output)
        score_case(result, case)
        results.append(result)
    return results


def test_error_handling(client, model_name: str):
    """Run the full error handling battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== Error Handling Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} error handling tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")
