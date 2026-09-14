"""Shared fixtures: model client, prompt helpers, scoring."""

import os
from dataclasses import dataclass, field
from typing import Any

import pytest
from openai import OpenAI


@dataclass
class TestCase:
    """A single test case with expected output for comparison."""
    name: str
    description: str
    prompt: str
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    min_length: int = 0
    requires_correct_code: bool = False


@dataclass
class TestResult:
    """Result of running a single test case."""
    name: str
    passed: bool
    score: float  # 0.0 - 1.0
    details: list[str] = field(default_factory=list)
    model_output: str = ""


def get_client() -> OpenAI:
    """Create an OpenAI-compatible client pointing at LM Studio."""
    base_url = os.environ.get(
        "LLM_BASE_URL",
        "http://192.168.1.14:1234/v1"
    )
    model = os.environ.get("LLM_MODEL", "nail-qwen3.6-35b-a3b-mtp")
    return OpenAI(base_url=base_url, api_key="not-needed"), model


def call_model(
    client: OpenAI,
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    """Call the model and return the assistant's response text."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    return resp.choices[0].message.content or ""


def score_case(result: TestResult, case: TestCase) -> None:
    """Score a test result against its expected criteria. Mutates in place."""
    output = result.model_output.lower()
    details = []

    # Keyword coverage (up to 0.6 weight)
    if case.expected_keywords:
        matched = sum(1 for kw in case.expected_keywords if kw.lower() in output)
        keyword_score = matched / len(case.expected_keywords)
        details.append(f"Keyword coverage: {matched}/{len(case.expected_keywords)} ({keyword_score:.0%})")
    else:
        keyword_score = 1.0

    # Forbidden patterns (fail if any found, up to 0.2 weight)
    forbidden_hits = [fp for fp in case.forbidden_patterns if fp.lower() in output]
    if forbidden_hits:
        details.append(f"Forbidden patterns found: {forbidden_hits}")
        forbidden_score = 0.0
    else:
        forbidden_score = 1.0

    # Minimum length check (up to 0.2 weight)
    if case.min_length and len(result.model_output) >= case.min_length:
        length_score = 1.0
        details.append(f"Length OK ({len(result.model_output)} chars)")
    elif case.min_length:
        length_score = 0.0
        details.append(
            f"Too short: {len(result.model_output)}/{case.min_length} chars"
        )
    else:
        length_score = 1.0

    result.score = keyword_score * 0.6 + forbidden_score * 0.2 + length_score * 0.2
    result.passed = result.score >= 0.5
    result.details.extend(details)


def format_result(r: TestResult) -> str:
    """Format a single test result for display."""
    status = "PASS" if r.passed else "FAIL"
    lines = [f"[{status}] {r.name} (score={r.score:.2%})"]
    for d in r.details:
        lines.append(f"  • {d}")
    return "\n".join(lines)
