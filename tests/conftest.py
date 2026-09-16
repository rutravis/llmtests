"""Shared fixtures, model client, prompt helpers, and scoring."""

import ast
import json
import os
import re
import time
from dataclasses import dataclass, field

import pytest
from openai import APIError, OpenAI


@dataclass
class TestCase:
    """A single test case with expected output for comparison."""
    __test__ = False  # not a pytest test class
    name: str
    description: str
    prompt: str
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    min_length: int = 0
    requires_correct_code: bool = False  # gate: at least one fenced block must parse as Python


@dataclass
class TestResult:
    """Result of running a single test case.

    completion_tokens is estimated from character count (~1 char/token) when the API
    does not report usage in streaming mode; draft/rejected counts come from LM Studio's
    `stats` field on the final chunk."""
    name: str
    passed: bool
    score: float  # 0.0 - 1.0
    details: list[str] = field(default_factory=list)
    model_output: str = ""
    error: str = ""  # non-empty => API/transport failure, not a model-quality fail
    elapsed_s: float = 0.0
    reasoning: str = ""  # thinking-model chain-of-thought (recorded for review, not scored)
    finish_reason: str = ""
    prefill_ms: float = 0.0  # time from request start to first token
    gen_speed: float = 0.0  # tokens/sec during generation phase
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    draft_tokens: int = 0
    accepted_draft_tokens: int = 0
    rejected_draft_tokens: int = 0

_CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)?\s*\n(.*?)```", re.DOTALL)


def get_client() -> OpenAI:
    """Create an OpenAI-compatible client pointing at LM Studio."""
    base_url = os.environ.get(
        "LLM_BASE_URL",
        "http://192.168.1.14:1234/v1"
    )
    model = os.environ.get("LLM_MODEL", "nail-qwen3.6-35b-a3b-mtp")
    # Chunk-wise streaming keeps requests alive however slow the server;
    # one retry for transient failures (each retry is expensive).
    return OpenAI(base_url=base_url, api_key="not-needed", timeout=300.0, max_retries=1), model


def call_model(
    client: OpenAI,
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
    max_tokens: int = 0,  # 0 => LLM_MAX_TOKENS env or 16384
) -> tuple[str, str, str, str, float, float, dict]:
    """Stream the model; return (content, reasoning, finish_reason, tools_json,
       prefill_ms, gen_speed_tokens_per_sec, usage_dict).

    Streaming avoids total-request timeouts on slow servers and captures the
    reasoning_content field emitted by thinking models separately from the
    answer. Raises openai.APIError on transport/server failures; the caller
    (run_suite) records them.

    Timing: prefill_ms = wall time to first token; gen_speed = completion_tokens
    / generation-wall-time (tokens/sec). Usage dict carries prompt/completion/
    reasoning/draft/rejected counts from the final chunk's usage field.
    """
    if max_tokens <= 0:
        max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "16384"))
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    t_start = time.monotonic()
    first_token_t = None  # when we see the first token (reasoning or content)
    gen_start_t = None     # same as first_token_t for this model
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[str] = []
    finish_reason = ""
    usage_dict: dict = {}
    stream = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if choice.finish_reason:
            finish_reason = choice.finish_reason
        delta = choice.delta
        has_token = bool(delta.content) or bool((delta.model_extra or {}).get("reasoning_content"))
        if has_token and first_token_t is None:
            first_token_t = time.monotonic()
        if delta.content:
            content_parts.append(delta.content)
        rc = (delta.model_extra or {}).get("reasoning_content")
        if rc:
            reasoning_parts.append(rc)
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index or 0
                while len(tool_calls) <= idx:
                    tool_calls.append("")
                if tc.function:
                    tool_calls[idx] += tc.function.arguments or ""
        # Usage/timing stats come from the final chunk's model_extra (LM Studio
        # sends draft/rejected counts via `stats`, not via `usage` in streaming).
        if choice.finish_reason and hasattr(chunk, "model_extra"):
            me = chunk.model_extra or {}
            st = me.get("stats", {})
            usage_dict["draft_tokens"] = st.get("total_draft_tokens_count", 0)
            usage_dict["accepted_draft_tokens"] = st.get("accepted_draft_tokens_count", 0)
            usage_dict["rejected_draft_tokens"] = st.get("rejected_draft_tokens_count", 0)
    tools_json = json.dumps(tool_calls) if any(t for t in tool_calls) else ""
    # Compute timing
    prefill_ms = round((first_token_t - t_start) * 1000, 1) if first_token_t is not None else 0.0
    gen_s = (time.monotonic() - first_token_t) if first_token_t is not None else 0.0
    # Estimate completion_tokens from output length (LM Studio doesn't send usage in streaming).
    # BPE tokens average ~4 chars for English text; use word count as a rougher proxy.
    full_text = "".join(content_parts) + "".join(reasoning_parts)
    ct_est = max(len(full_text.split()), 1) if full_text else 0
    # If stream ended without finish_reason but tokens were produced, mark incomplete
    if first_token_t and not finish_reason and full_text:
        finish_reason = "incomplete"
    gen_speed = round(ct_est / gen_s, 2) if gen_s > 0 else 0.0
    usage_dict["completion_tokens"] = ct_est
    return "".join(content_parts), "".join(reasoning_parts), finish_reason, tools_json, prefill_ms, gen_speed, usage_dict


def extract_code_blocks(text: str) -> list[str]:
    """Return the contents of all fenced (```) code blocks."""
    return [m for m in _CODE_FENCE_RE.findall(text or "")]


def code_parses(code: str) -> bool:
    """True if the snippet is syntactically valid Python."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def score_case(result: TestResult, case: TestCase) -> None:
    """Score a test result against its expected criteria. Mutates in place."""
    output = result.model_output.lower()
    details = []

    if not result.model_output:
        details.append("Empty model output")

    # Keyword coverage (up to 0.6 weight) — matched over the full response
    if case.expected_keywords:
        matched = sum(1 for kw in case.expected_keywords if kw.lower() in output)
        keyword_score = matched / len(case.expected_keywords)
        details.append(f"Keyword coverage: {matched}/{len(case.expected_keywords)} ({keyword_score:.0%})")
    else:
        keyword_score = 1.0

    # Forbidden patterns (up to 0.2 weight) — checked only inside code blocks
    # (actual usage) when code is fenced, so prose mentions like
    # "this avoids sorted()" do not trigger a false fail.
    blocks = extract_code_blocks(result.model_output)
    if blocks and case.forbidden_patterns:
        forbidden_scope = "\n".join(blocks).lower()
        forbidden_hits = [fp for fp in case.forbidden_patterns if fp.lower() in forbidden_scope]
        if forbidden_hits:
            details.append(f"Forbidden patterns found in code: {forbidden_hits}")
            forbidden_score = 0.0
        else:
            forbidden_score = 1.0
    elif case.forbidden_patterns:
        # No code blocks to check — skip forbidden-pattern gate (prose-only responses
        # can't be evaluated for actual anti-pattern usage)
        forbidden_score = 1.0
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

    # Syntax gate: for code-producing cases, at least one fenced block must
    # parse as valid Python. Unfenced responses skip the gate (indeterminate).
    gate_failed = False
    if case.requires_correct_code:
        if blocks:
            if not any(code_parses(b) for b in blocks):
                gate_failed = True
                details.append("Syntax gate: no fenced code block parses as valid Python")
        else:
            details.append("Syntax gate skipped: no fenced code blocks in response")

    result.score = keyword_score * 0.6 + forbidden_score * 0.2 + length_score * 0.2
    if gate_failed:
        result.score = min(result.score, 0.4)
    result.passed = result.score >= 0.5 and not gate_failed and not result.error
    result.details.extend(details)


def run_suite(
    client: OpenAI,
    model_name: str,
    test_cases: list[TestCase],
    system_prompt: str = "",
    temperature: float = 0.1,
) -> list[TestResult]:
    """Execute a suite of test cases with live progress, timing, and error capture.

    A failed API call records an error on that result and never aborts the battery.
    """
    results = []
    for case in test_cases:
        print(f"  -> {case.name} ...", end="", flush=True)
        t0 = time.monotonic()
        try:
            output, reasoning, finish, tools, prefill_ms, gen_speed, usage_dict = call_model(
                client, model_name,
                prompt=case.prompt,
                system_prompt=system_prompt,
                temperature=temperature,
            )
            error = ""
        except APIError as e:
            output, reasoning, finish, tools = "", "", "", ""
            prefill_ms, gen_speed, usage_dict = 0.0, 0.0, {}
            error = f"{e.__class__.__name__}: {e}"
        except Exception as e:  # keep the battery alive on unexpected failures
            output, reasoning, finish, tools = "", "", "", ""
            prefill_ms, gen_speed, usage_dict = 0.0, 0.0, {}
            error = f"{e.__class__.__name__}: {e}"
        elapsed = time.monotonic() - t0

        result = TestResult(
            name=case.name, passed=False, score=0.0,
            model_output=output, error=error, elapsed_s=round(elapsed, 1),
            reasoning=reasoning, finish_reason=finish,
            prefill_ms=prefill_ms, gen_speed=gen_speed,
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            reasoning_tokens=usage_dict.get("reasoning_tokens", 0),
            draft_tokens=usage_dict.get("draft_tokens", 0),
            accepted_draft_tokens=usage_dict.get("accepted_draft_tokens", 0),
            rejected_draft_tokens=usage_dict.get("rejected_draft_tokens", 0),
        )
        score_case(result, case)
        print(f" {'PASS' if result.passed else 'FAIL'} (score={result.score:.0%}, {elapsed:.0f}s)", flush=True)
        results.append(result)
    return results


def format_result(r: TestResult) -> str:
    """Format a single test result for display."""
    status = "PASS" if r.passed else "FAIL"
    lines = [f"[{status}] {r.name} (score={r.score:.2%})"]
    for d in r.details:
        lines.append(f"  • {d}")
    return "\n".join(lines)


# --- pytest integration -----------------------------------------------------
# Makes the whole battery runnable under plain `pytest` (one fixture session).

@pytest.fixture(scope="session")
def client() -> OpenAI:
    return get_client()[0]


@pytest.fixture(scope="session")
def model_name() -> str:
    return get_client()[1]
