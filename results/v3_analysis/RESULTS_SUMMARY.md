# Study 1 v3: results summary (auto-generated)

Costlier fund = SPY (S&P 500) or QQQ (Nasdaq-100). Shares are of valid picks, templates and system prompts pooled. Runs per cell: 30 (API, Amendment v3-1) or 50 (local).

## 1. One index family per test: costlier-fund share

| Model | Family | No document | D1 valid cost | D3 brand | D5 authority | D7 performance |
|---|---|---|---|---|---|---|
| qwen2.5-7b | sp500 | 2% | 0% | 94% | 100% | 100% |
| qwen2.5-7b | ndx | 81% | 0% | 100% | 100% | 100% |
| qwen2.5-14b | sp500 | 0% | 0% | 63% | 100% | 46% |
| qwen2.5-14b | ndx | 58% | 0% | 100% | 100% | 98% |
| gpt-5.4-nano | sp500 | 0% | 0% | 0% | 22% | 10% |
| gpt-5.4-nano | ndx | 2% | 0% | 77% | 80% | 48% |
| gpt-5.4-mini | sp500 | 0% | 0% | 33% | 8% | 0% |
| gpt-5.4-mini | ndx | 0% | 0% | 61% | 21% | 8% |
| gpt-5.4 | sp500 | 0% | 0% | 0% | 0% | 0% |
| gpt-5.4 | ndx | 0% | 0% | 0% | 0% | 0% |
| claude-haiku-5.5 | sp500 | 0% | 0% | 0% | 0% | 0% |
| claude-haiku-5.5 | ndx | 0% | 0% | 0% | 0% | 0% |
| claude-sonnet-5.5 | sp500 | 0% | 0% | 0% | 0% | 0% |
| claude-sonnet-5.5 | ndx | 0% | 0% | 0% | 0% | 0% |
| claude-opus-5.5 | sp500 | 0% | 0% | 0% | 0% | 0% |
| claude-opus-5.5 | ndx | 0% | 0% | 0% | 0% | 0% |

## 2. Scaling (biased documents pooled)

| Vendor | Size | Model | S&P 500 | Nasdaq-100 |
|---|---|---|---|---|
| ollama | small | qwen2.5-7b | 98% [96%, 99%] | 100% [99%, 100%] |
| ollama | mid | qwen2.5-14b | 70% [66%, 73%] | 99% [98%, 100%] |
| openai | small | gpt-5.4-nano | 11% [8%, 14%] | 68% [63%, 73%] |
| openai | mid | gpt-5.4-mini | 14% [10%, 18%] | 30% [26%, 35%] |
| openai | large | gpt-5.4 | 0% [0%, 1%] | 0% [0%, 1%] |
| anthropic | small | claude-haiku-5.5 | 0% [0%, 1%] | 0% [0%, 1%] |
| anthropic | mid | claude-sonnet-5.5 | 0% [0%, 1%] | 0% [0%, 1%] |
| anthropic | large | claude-opus-5.5 | 0% [0%, 1%] | 0% [0%, 1%] |

Figures: `figures/scaling_sp500.png`, `figures/scaling_ndx.png`.

## 3. Robustness: fiduciary prompt and templates

| Model | Family | Fiduciary - standard (biased docs) | 95% CI | Holm p | Template sign agreement (D3/D5/D7) |
|---|---|---|---|---|---|
| qwen2.5-7b | sp500 | -0.01 | [-0.04, +0.02] | 0.288 | 3/3 |
| qwen2.5-7b | ndx | +0.00 | [-0.01, +0.01] | 1 | 3/3 |
| qwen2.5-14b | sp500 | -0.41 | [-0.47, -0.34] | 1.24e-28 | 3/3 |
| qwen2.5-14b | ndx | -0.01 | [-0.03, +0.00] | 0.0619 | 3/3 |
| gpt-5.4-nano | sp500 | -0.19 | [-0.25, -0.13] | 2.35e-09 | 3/3 |
| gpt-5.4-nano | ndx | -0.45 | [-0.53, -0.36] | 1.05e-20 | 3/3 |
| gpt-5.4-mini | sp500 | -0.18 | [-0.25, -0.11] | 7.05e-07 | 3/3 |
| gpt-5.4-mini | ndx | -0.44 | [-0.52, -0.36] | 7.57e-21 | 2/3 |
| gpt-5.4 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-5.4 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-haiku-5.5 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-haiku-5.5 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-sonnet-5.5 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-sonnet-5.5 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-opus-5.5 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-opus-5.5 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |

## 4. Literature positioning

See `docs/literature_v3.md`.

## Caveats

- Post-freeze amendments: v3-1 (30 runs per cell for API models); see `docs/design_v3.md`.
- Name-vs-ID flags were cleared only by recorded manual review (`data/gate_reviews_v3.csv`).
- Returns as of 2026-09-30 (S&P 500) vs 2026-06-30 (Nasdaq-100); QQQ's 5-yr history spans its UIT years.
