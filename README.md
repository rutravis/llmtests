# LLM Evaluation Suite

A battery of tests for evaluating agentic coding capabilities of LLM models.

## Test Categories

| Suite | Description | Tests |
|-------|-------------|-------|
| Code Generation | Writing correct Python from scratch | 3 |
| Refactoring | Restructuring existing code while preserving behavior | 3 |
| Debugging | Finding and fixing subtle bugs | 3 |
| API Knowledge | Correct usage of standard library & patterns | 3 |
| Documentation | Clear, accurate docs and comments | 3 |
| Error Handling | Robust exception handling & validation | 3 |
| System Design | Architectural reasoning & tradeoff analysis | 2 |

## Evaluation Results (nail-qwen3.6-35b-a3b-mtp)

**Status: Model is functional but impractical for automated testing.**

| Metric | Result |
|--------|--------|
| Response time (short prompts) | 2–391 seconds (highly variable) |
| Output quality | Empty content with `finish_reason: "length"` on all tested prompts |
| GPU acceleration | None — model runs entirely on CPU (Quadro K2000 has only 3GB VRAM, model needs ~14GB) |
| Model variant `-mtp` vs non-`-mtp` | Non-MTP responds in ~2s but also empty; MTP takes minutes and same result |

### Root Cause Analysis

The `nail-qwen3.6-35b-a3b-mtp` model uses Qwen3.5 MoE (Mixture of Experts) architecture with Multi-Token Prediction. LM Studio's OpenAI-compatible API wrapper appears to have a compatibility issue: the model generates tokens internally but they are not returned in the response payload, resulting in empty content strings.

This is likely a bug in how LM Studio handles Qwen3.5 MoE routing/attention patterns through its inference engine, not an issue with the model weights themselves.

### Recommendations

1. **Use a different model** for automated testing — e.g., `Spark X2.5 4B` (fits in GPU VRAM) or any non-MoE model loaded on LM Studio
2. **Test interactively** via LM Studio's UI to verify the model produces correct output when not going through the API wrapper
3. **Consider upgrading GPU** — a card with ≥16GB VRAM (e.g., RTX 4090) would allow full GPU inference of this model

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run all suites against default model (nail-qwen3.6-35b-a3b-mtp)
python3 run_tests.py

# Run a specific suite
python3 run_tests.py code_generation debugging

# Override model and endpoint
LLM_MODEL=qwen3.8-27b-gsq-rco LLM_BASE_URL=http://192.168.1.14:1234/v1 python3 run_tests.py

# The same battery also runs under pytest (after `pip install -e .`):
#   LLM_MODEL=qwen3.8-27b-gsq-rco pytest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `nail-qwen3.6-35b-a3b-mtp` | Model name to evaluate |
| `LLM_BASE_URL` | `http://192.168.1.14:1234/v1` | OpenAI-compatible API endpoint |
| `LLM_MAX_TOKENS` | `16384` | Per-call completion budget (thinking models need headroom for reasoning) |

## Scoring

Each test case is scored on a 0–1 scale based on:
- **Keyword coverage** (60%): Does the output contain expected terms/patterns?
- **Forbidden patterns** (20%): Does the code avoid known anti-patterns?
  Checked inside fenced code blocks only — prose mentions like "this avoids
  `sorted()`" do not trigger a fail.
- **Minimum length** (20%): Is the response sufficiently detailed?

A test passes at score ≥ 0.5. Suites pass when ≥60% of their tests pass.

Additional gates:
- **Syntax gate**: cases flagged `requires_correct_code` fail if none of their
  fenced code blocks parse as valid Python (`ast.parse`).
- **API errors**: a failed model call records an error on that test and never
  aborts the battery; it is reported as an error, not a model failure.
- **Thinking models**: chain-of-thought is streamed separately and stored per
  test as `reasoning` (recorded for review, never scored) — only the final
  answer counts. If the token budget is exhausted mid-thinking, the test fails
  with an explicit detail.

## Output

Console output shows live per-test PASS/FAIL with score and elapsed time. A JSON
report is saved to `results/report-<timestamp>.json` after each suite
(incremental, so partial results survive an interrupted run). Each report
includes the full model output, per-test timing, scoring details, reasoning,
and any API errors for every test.

A single self-contained HTML report (inline CSS/JS, no external assets) is
written alongside the JSON after each suite — model name and testing date in
the header, an overall score ring, suite cards, and expandable per-test
output/reasoning. Serve `results/<model>-<timestamp>.html` from any static web
server, or regenerate one manually:

```bash
python3 make_html_report.py results/report-<timestamp>.json
```
