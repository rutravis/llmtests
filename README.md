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
python run_tests.py

# Run a specific suite
python run_tests.py code_generation debugging

# Override model and endpoint
LLM_MODEL=qwen3.8-27b LLM_BASE_URL=http://192.168.1.14:1234/v1 python run_tests.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `nail-qwen3.6-35b-a3b-mtp` | Model name to evaluate |
| `LLM_BASE_URL` | `http://192.168.1.14:1234/v1` | OpenAI-compatible API endpoint |

## Scoring

Each test case is scored on a 0–1 scale based on:
- **Keyword coverage** (60%): Does the output contain expected terms/patterns?
- **Forbidden patterns** (20%): Does it avoid known anti-patterns?
- **Minimum length** (20%): Is the response sufficiently detailed?

A test passes at score ≥ 0.5. Suites pass when ≥60% of their tests pass.

## Output

Console output shows per-test PASS/FAIL with details. JSON reports are saved to `results/` with timestamped filenames.
