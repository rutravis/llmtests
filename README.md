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
