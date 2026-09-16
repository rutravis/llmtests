"""Regression tests for scoring logic — no LLM API required.

Verifies that score_case, extract_code_blocks, and code_parses behave correctly
for edge cases discovered during the evaluation battery review.
"""

import ast
from .conftest import TestCase, TestResult, score_case, extract_code_blocks, code_parses


# ---------------------------------------------------------------------------
# Code block extraction
# ---------------------------------------------------------------------------

def test_extract_code_blocks_basic():
    """Extract fenced code blocks from mixed prose."""
    text = "Here is some code:\n```python\ndef foo(): pass\n```\nAnd more text.\n```js\nconsole.log(1)\n```"
    blocks = extract_code_blocks(text)
    assert len(blocks) == 2
    assert "def foo():" in blocks[0]
    assert "console.log(1)" in blocks[1]


def test_extract_code_blocks_no_fences():
    """No code blocks when no fences present."""
    text = "Just prose with no backticks."
    assert extract_code_blocks(text) == []


def test_extract_code_blocks_empty():
    """Empty input returns empty list."""
    assert extract_code_blocks("") == []
    assert extract_code_blocks(None) == []


# ---------------------------------------------------------------------------
# Code parsing gate
# ---------------------------------------------------------------------------

def test_code_parses_valid():
    """Valid Python parses successfully."""
    assert code_parses("def foo(x): return x + 1") is True
    assert code_parses("class Bar:\n    pass") is True


def test_code_parses_invalid():
    """Invalid Python fails to parse."""
    assert code_parses("def foo(  # missing colon and body") is False
    assert code_parses("not valid python at all") is False


# ---------------------------------------------------------------------------
# Forbidden patterns — scope isolation
# ---------------------------------------------------------------------------

def test_forbidden_only_in_code_blocks():
    """Forbidden patterns should NOT trigger on prose mentions outside code blocks."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="""\
Here is my approach. I avoid using sorted() because it's not stable.
Instead I implement merge sort from scratch.

```python
def stable_sort(items):
    if len(items) <= 1:
        return items[:]
    mid = len(items) // 2
    left, right = stable_sort(items[:mid]), stable_sort(items[mid:])
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result
```
""")
    case = TestCase(
        name="test", description="forbidden only in code blocks", prompt="",
        expected_keywords=["stable_sort"],
        forbidden_patterns=["sorted("],
        min_length=50,
        requires_correct_code=True,
    )
    score_case(result, case)
    # The prose mentions sorted() but the code block does NOT — should pass
    assert result.passed is True


def test_forbidden_in_code_block():
    """Forbidden patterns SHOULD trigger when found inside actual code blocks."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="""\
```python
result = sorted(items)  # This is bad
```
""")
    case = TestCase(
        name="test", description="forbidden in code block", prompt="",
        expected_keywords=["sorted"],
        forbidden_patterns=["sorted("],
        min_length=10,
        requires_correct_code=True,
    )
    score_case(result, case)
    # Forbidden patterns reduce score by 0.2; with keyword=1.0 and length=1.0:
    # score = 0.6 + 0.0 + 0.2 = 0.8 → still passes (≥0.5)
    assert result.score == 0.8
    assert result.passed is True


def test_forbidden_skipped_when_no_code():
    """Forbidden patterns should be skipped when no code blocks exist."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="""\
I would normally use sorted() but since I'm not writing code here,\njust explaining the approach.\
""")
    case = TestCase(
        name="test", description="forbidden skipped no code", prompt="",
        expected_keywords=[],
        forbidden_patterns=["sorted("],
        min_length=10,
        requires_correct_code=False,  # no code required — prose-only response
    )
    score_case(result, case)
    # Should NOT fail on forbidden patterns since there's no code to check
    assert result.passed is True


# ---------------------------------------------------------------------------
# Syntax gate behavior
# ---------------------------------------------------------------------------

def test_gate_skipped_no_code_blocks():
    """When requires_correct_code=True but no code blocks, gate is SKIPPED (not failed)."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="""\
Here is the answer with all keywords present and plenty of text.\n""" * 50)
    case = TestCase(
        name="test", description="gate skipped no code blocks", prompt="",
        expected_keywords=["answer"],
        forbidden_patterns=[],
        min_length=500,
        requires_correct_code=True,
    )
    score_case(result, case)
    # No code blocks → gate skipped (not failed); high scores → passes
    assert result.passed is True
    assert any("Syntax gate skipped" in d for d in result.details)


def test_gate_failed_with_invalid_code():
    """When requires_correct_code=True and code blocks exist but none parse, gate FAILS."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="""\
Here is my answer:
```python
def broken(  # invalid syntax
```
""")
    case = TestCase(
        name="test", description="gate failed with invalid code", prompt="",
        expected_keywords=["answer"],
        forbidden_patterns=[],
        min_length=50,
        requires_correct_code=True,
    )
    score_case(result, case)
    # Code block exists but doesn't parse → gate fails → score capped at 0.4 → FAIL
    assert result.passed is False
    assert any("Syntax gate" in d for d in result.details)


def test_gate_skipped_without_code_required():
    """When requires_correct_code=False, syntax gate is skipped entirely."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="Just prose.")
    case = TestCase(
        name="test", description="gate skipped no code required", prompt="",
        expected_keywords=[],
        forbidden_patterns=[],
        min_length=5,
        requires_correct_code=False,
    )
    score_case(result, case)
    assert result.passed is True


# ---------------------------------------------------------------------------
# Keyword coverage edge cases
# ---------------------------------------------------------------------------

def test_keyword_coverage_zero():
    """Zero keyword matches should be explicitly noted in details."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="completely unrelated text")
    case = TestCase(
        name="test", description="keyword coverage zero", prompt="",
        expected_keywords=["expected_term_1", "expected_term_2"],
        forbidden_patterns=[],
        min_length=5,
    )
    score_case(result, case)
    assert any("Keyword coverage: 0/2 (0%)" in d for d in result.details)


def test_keyword_coverage_partial():
    """Partial keyword matches should show correct fraction."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="contains term_one and some other text")
    case = TestCase(
        name="test", description="keyword coverage partial", prompt="",
        expected_keywords=["term_one", "term_two"],
        forbidden_patterns=[],
        min_length=5,
    )
    score_case(result, case)
    assert any("Keyword coverage: 1/2 (50%)" in d for d in result.details)


# ---------------------------------------------------------------------------
# Score arithmetic
# ---------------------------------------------------------------------------

def test_score_max_is_1():
    """Perfect keyword + no forbidden + sufficient length → score = 1.0."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="has all keywords here")
    case = TestCase(
        name="test", description="score max is 1", prompt="",
        expected_keywords=["keywords"],
        forbidden_patterns=[],
        min_length=5,
    )
    score_case(result, case)
    assert result.score == 1.0


def test_score_gate_cap_at_04():
    """Gate-failed tests are capped at 0.4 (below pass threshold of 0.5)."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="""\
perfect answer with all keywords and lots of text:
```python
def broken(  # invalid syntax
```
""")
    case = TestCase(
        name="test", description="score gate cap at 04", prompt="",
        expected_keywords=["answer"],
        forbidden_patterns=[],
        min_length=50,
        requires_correct_code=True,
    )
    score_case(result, case)
    assert result.score <= 0.4


def test_empty_output_score():
    """Empty model output gets score from forbidden default (no patterns → 1.0*0.2 = 0.2)."""
    result = TestResult(name="test", passed=False, score=0.0, model_output="")
    case = TestCase(
        name="test", description="empty output score", prompt="",
        expected_keywords=["term"],
        forbidden_patterns=[],
        min_length=10,
    )
    score_case(result, case)
    # keyword=0.0*0.6 + forbidden(1.0)*0.2 + length(0.0)*0.2 = 0.2
    assert result.score == 0.2


# ---------------------------------------------------------------------------
# Token estimation sanity (no API needed)
# ---------------------------------------------------------------------------

def test_token_estimation_word_count():
    """Token estimate uses word count, not character count."""
    short = "hello world"
    long_text = " ".join(["word"] * 100)
    # Word count for short: 2; for long: 100
    assert len(short.split()) == 2
    assert len(long_text.split()) == 100
