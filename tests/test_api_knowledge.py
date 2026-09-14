"""Test 4 — API Knowledge

Evaluate the model's knowledge of Python standard library, common packages,
and correct API usage patterns. Tests cover: asyncio, pathlib, typing,
logging, and dataclasses."""

import textwrap
from .conftest import TestCase, TestResult, call_model, score_case


TEST_CASES: list[TestCase] = [
    TestCase(
        name="api_asyncio_patterns",
        description="Use asyncio primitives correctly (Event, Queue, gather).",
        prompt=textwrap.dedent("""\
            Write a Python async function `run_pipeline(tasks)` that:
            - Accepts an iterable of async callables
            - Runs them concurrently with a max concurrency of 5 using asyncio.Semaphore
            - Collects results in original order
            - Returns (results, errors) where errors maps task index to exception

            Use proper type hints and include the function signature.
        """),
        expected_keywords=[
            "asyncio", "Semaphore", "gather", "concurrent",
            "max_concurrency", "type hint", "coroutine", "await",
            "results", "errors",
        ],
        forbidden_patterns=["ThreadPoolExecutor", "ProcessPoolExecutor"],
        min_length=300,
    ),
    TestCase(
        name="api_pathlib_usage",
        description="Use pathlib correctly for file operations.",
        prompt=textwrap.dedent("""\
            Write a Python function `find_duplicates(directory)` that:
            - Uses `pathlib.Path` (not os.walk) to traverse the directory
            - Computes SHA-256 hashes of all files
            - Returns a dict mapping hash -> list of paths for duplicate files
            - Skips non-regular files and broken symlinks gracefully

            Include type hints.
        """),
        expected_keywords=[
            "pathlib", "Path", "sha256", "hashlib", "is_file",
            "iterdir", "rglob", "symlink", "duplicate", "type hint",
        ],
        forbidden_patterns=["os.walk", "glob.glob"],
        min_length=300,
    ),
    TestCase(
        name="api_typing_generics",
        description="Use typing module correctly for generic types.",
        prompt=textwrap.dedent("""\
            Write a Python class `Result[T]` that implements a simple Either-like type:
            - Generic over T (the success type)
            - Class methods `ok(value)` and `error(message)` as constructors
            - Properties `.is_ok()` and `.unwrap_or(default)`
            - Proper use of typing.Generic, TypeVar

            Include full type hints on all methods.
        """),
        expected_keywords=[
            "Generic", "TypeVar", "Result", "ok", "error",
            "is_ok", "unwrap_or", "typing", "type hint",
            "__class_getitem__", "Optional",
        ],
        min_length=300,
    ),
]


def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all API knowledge test cases."""
    results = []
    for case in TEST_CASES:
        output = call_model(
            client, model_name,
            prompt=case.prompt,
            system_prompt="You are an expert Python developer. Use the correct standard library APIs.",
            temperature=0.1,
        )
        result = TestResult(name=case.name, passed=False, score=0.0, model_output=output)
        score_case(result, case)
        results.append(result)
    return results


def test_api_knowledge(client, model_name: str):
    """Run the full API knowledge battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== API Knowledge Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} API knowledge tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")
