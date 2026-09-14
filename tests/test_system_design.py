"""Test 7 — System Design

Evaluate the model's ability to reason about architecture, make tradeoffs,
and produce well-structured design documents."""

import textwrap
from .conftest import TestCase, TestResult, call_model, score_case


TEST_CASES: list[TestCase] = [
    TestCase(
        name="design_event_system",
        description="Design a pub/sub event system with filtering and ordering.",
        prompt=textwrap.dedent("""\
            Design a Python pub/sub event system. Describe the architecture and provide
            code for the core components:

            Requirements:
            - Multiple topics, each with ordered message delivery per subscriber
            - Subscribers can filter events by metadata (e.g., only events from 'service:A')
            - Supports sync and async subscribers
            - Dead-letter queue for failed messages
            - At-least-once delivery guarantee

            Provide: class diagrams as comments, core interfaces, and a usage example.
        """),
        expected_keywords=[
            "pub/sub", "topic", "subscriber", "filter", "event",
            "async", "sync", "dead-letter", "delivery", "queue",
            "interface", "class", "example",
        ],
        min_length=800,
    ),
    TestCase(
        name="design_cache_layer",
        description="Design a multi-tier caching layer with TTL and eviction.",
        prompt=textwrap.dedent("""\
            Design a Python caching layer that sits between an application and a database.

            Requirements:
            - Two tiers: in-memory LRU (fast, limited size) + file-based (slower, larger)
            - Per-key TTL with configurable default
            - Cache-aside pattern: miss triggers DB lookup, result cached on write
            - Write-through for critical data, write-back for non-critical
            - Graceful degradation when disk is full

            Provide the class design, key methods, and a usage example.
        """),
        expected_keywords=[
            "cache", "LRU", "TTL", "eviction", "tier",
            "write-through", "write-back", "cache-aside",
            "in-memory", "disk", "class design", "example",
        ],
        min_length=600,
    ),
]


def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all system design test cases."""
    results = []
    for case in TEST_CASES:
        output = call_model(
            client, model_name,
            prompt=case.prompt,
            system_prompt="You are a senior software architect. Provide clear designs with code.",
            temperature=0.3,  # Higher temp for creative design thinking
        )
        result = TestResult(name=case.name, passed=False, score=0.0, model_output=output)
        score_case(result, case)
        results.append(result)
    return results


def test_system_design(client, model_name: str):
    """Run the full system design battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== System Design Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} system design tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")
