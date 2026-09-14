"""Test 2 — Refactoring

Evaluate the model's ability to restructure existing code while preserving
behavior. Tests cover: extracting methods, renaming, simplifying conditionals,
and converting patterns."""

import textwrap
from .conftest import TestCase, TestResult, call_model, score_case


TEST_CASES: list[TestCase] = [
    TestCase(
        name="refactor_extract_method",
        description="Extract a repeated logic block into a reusable method.",
        prompt=textwrap.dedent("""\
            Refactor the following Python code by extracting the repeated validation
            logic into a separate method called `validate_field`. The original function
            must still work identically.

            ```python
            def process_record(record):
                errors = []
                if not record.get('name'):
                    errors.append("Name is required")
                if len(str(record.get('name', ''))) > 100:
                    errors.append("Name too long")
                if not record.get('email'):
                    errors.append("Email is required")
                if '@' not in str(record.get('email', '')):
                    errors.append("Invalid email format")
                return errors
            ```

            Requirements:
            - Extract validation into `validate_field(field_name, value, max_length=None)`
            - The refactored function should call the extracted method twice
            - Preserve all original behavior and error messages
        """),
        expected_keywords=[
            "def validate_field", "extracted", "refactor", "errors.append",
            "Name is required", "Email is required", "Invalid email format",
        ],
        min_length=300,
    ),
    TestCase(
        name="refactor_simplify_conditionals",
        description="Simplify nested if/else into guard clauses.",
        prompt=textwrap.dedent("""\
            Refactor the following function to use early-return (guard clause) pattern
            instead of deep nesting. Preserve all behavior.

            ```python
            def calculate_discount(price, user_type, is_member):
                if price > 0:
                    if user_type == 'premium':
                        if is_member:
                            return price * 0.7
                        else:
                            return price * 0.85
                    elif user_type == 'regular':
                        if is_member:
                            return price * 0.9
                        else:
                            return price
                    else:
                        return price
                else:
                    return 0
            ```

            Requirements:
            - Use early returns / guard clauses to flatten nesting
            - Keep the same discount logic and return values
        """),
        expected_keywords=[
            "early", "guard", "return", "premium", "regular",
            "is_member", "price * 0.7", "price * 0.85", "price * 0.9",
        ],
        min_length=200,
    ),
    TestCase(
        name="refactor_convert_to_dataclass",
        description="Convert a plain class with __init__ to a dataclass.",
        prompt=textwrap.dedent("""\
            Convert the following Python class into a `@dataclass` while preserving
            all behavior. Add any necessary imports and keep custom methods intact.

            ```python
            from datetime import datetime

            class UserProfile:
                def __init__(self, username, email, created_at=None):
                    self.username = username
                    self.email = email
                    self.created_at = created_at or datetime.now()
                    self._profile_complete = False

                @property
                def is_complete(self):
                    return self._profile_complete and bool(self.email)

                def mark_complete(self):
                    self._profile_complete = True
            ```

            Requirements:
            - Use `@dataclass` decorator from dataclasses module
            - Keep the property and custom method
            - Add type hints as appropriate
        """),
        expected_keywords=[
            "@dataclass", "from dataclasses import", "UserProfile",
            "username", "email", "created_at", "is_complete",
            "mark_complete", "_profile_complete",
        ],
        min_length=200,
    ),
]


def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all refactoring test cases."""
    results = []
    for case in TEST_CASES:
        output = call_model(
            client, model_name,
            prompt=case.prompt,
            system_prompt="You are an expert Python developer specializing in code refactoring. Preserve all original behavior.",
            temperature=0.1,
        )
        result = TestResult(name=case.name, passed=False, score=0.0, model_output=output)
        score_case(result, case)
        results.append(result)
    return results


def test_refactoring(client, model_name: str):
    """Run the full refactoring battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== Refactoring Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} refactoring tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")
