"""Test 5 — Documentation Quality

Evaluate the model's ability to produce clear, accurate, and useful documentation.
Tests cover: docstrings, API docs, README content, and inline comments."""

import textwrap
from .conftest import TestCase, TestResult, call_model, score_case


TEST_CASES: list[TestCase] = [
    TestCase(
        name="doc_generate_docstring",
        description="Generate a comprehensive docstring following Google style.",
        prompt=textwrap.dedent("""\
            Write a complete Google-style docstring for this function. Include
            Args, Returns, Raises, and Examples sections.

            ```python
            def parse_config(path: str, schema: dict = None) -> dict:
                ...
            ```

            The function reads a YAML config file, validates it against an optional
            schema (dict with 'required' and 'types' keys), and returns the parsed
            config. It raises ValueError on validation failure and FileNotFoundError
            if the path doesn't exist.
        """),
        expected_keywords=[
            "Args:", "Returns:", "Raises:", "Examples:",
            "path", "schema", "dict", "YAML", "config",
            "ValueError", "FileNotFoundError", "type",
        ],
        min_length=400,
    ),
    TestCase(
        name="doc_write_readme",
        description="Write a clear README with usage examples.",
        prompt=textwrap.dedent("""\
            Write a concise README for a Python package called `logwatch` that:
            - Monitors log files and alerts on pattern matches (regex)
            - Supports multiple backends: file, email, Slack webhook
            - Has a CLI (`logwatch watch /var/log/syslog --pattern 'ERROR'`)
            - Uses async for non-blocking I/O

            Include sections: Overview, Installation, Usage, Configuration, API.
        """),
        expected_keywords=[
            "Installation", "Usage", "Configuration", "API",
            "pip install", "logwatch", "async", "regex",
            "Slack", "email", "CLI", "example",
        ],
        min_length=600,
    ),
    TestCase(
        name="doc_inline_comments",
        description="Add meaningful inline comments to complex code.",
        prompt=textwrap.dedent("""\
            Add clear, concise inline comments explaining the purpose and logic of
            each major block. Do NOT comment obvious things like `i += 1`.

            ```python
            def compress_chunks(data: bytes, chunk_size: int = 4096) -> list[bytes]:
                chunks = []
                current = bytearray()
                for byte in data:
                    if byte == 0x00 and len(current) > 1:
                        chunks.append(bytes(current))
                        current.clear()
                    elif byte == 0xFF:
                        if current:
                            chunks.append(bytes(current))
                            current.clear()
                    else:
                        current.append(byte)
                if current:
                    chunks.append(bytes(current))
                return chunks
            ```

            Requirements:
            - Explain the purpose of each block in 1-2 sentences
            - Use `#` comments, not docstrings
        """),
        expected_keywords=[
            "chunk", "delimiter", "0x00", "0xFF", "clear",
            "append", "compress", "bytearray", "purpose",
        ],
        min_length=300,
    ),
]


def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all documentation test cases."""
    results = []
    for case in TEST_CASES:
        output = call_model(
            client, model_name,
            prompt=case.prompt,
            system_prompt="You are an expert technical writer. Write clear, accurate documentation.",
            temperature=0.3,  # Slightly higher temp for more natural prose
        )
        result = TestResult(name=case.name, passed=False, score=0.0, model_output=output)
        score_case(result, case)
        results.append(result)
    return results


def test_documentation(client, model_name: str):
    """Run the full documentation battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== Documentation Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} documentation tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")
