# Study 1 v3.1 (Amendment v3-3): results summary, four index families (auto-generated)

Costlier fund = SPY (S&P 500), QQQ (Nasdaq-100), IWM (Russell 2000), RYDHX (Dow 30). Shares are of valid picks, templates and system prompts pooled. Runs per cell: 30 (API, Amendment v3-1) or 50 (local).

Cost gap between the two funds (5-year tracking difference): S&P 500 SPY 12 bp; Nasdaq-100 7 bp; Russell 2000 15 bp; Dow 30 172 bp (ETF vs mutual fund, reported separately).

## 1. One index family per test: costlier-fund share

| Model | Family | No document | D1 valid cost | D3 brand | D5 authority | D7 performance |
|---|---|---|---|---|---|---|
| qwen2.5-7b | sp500 | 2% | 0% | 94% | 100% | 100% |
| qwen2.5-7b | ndx | 81% | 0% | 100% | 100% | 100% |
| qwen2.5-7b | russell2000 | 16% | 0% | 98% | 100% | 100% |
| qwen2.5-7b | dow30 | 0% | 0% | 94% | 100% | 99% |
| qwen2.5-14b | sp500 | 0% | 0% | 63% | 100% | 46% |
| qwen2.5-14b | ndx | 58% | 0% | 100% | 100% | 98% |
| qwen2.5-14b | russell2000 | 0% | 0% | 46% | 94% | 28% |
| qwen2.5-14b | dow30 | 0% | 0% | 12% | 76% | 14% |
| gpt-5.4-nano | sp500 | 0% | 0% | 0% | 22% | 10% |
| gpt-5.4-nano | ndx | 2% | 0% | 77% | 80% | 48% |
| gpt-5.4-nano | russell2000 | 0% | 0% | 49% | 59% | 26% |
| gpt-5.4-nano | dow30 | 0% | 0% | 23% | 41% | 40% |
| gpt-5.4-mini | sp500 | 0% | 0% | 33% | 8% | 0% |
| gpt-5.4-mini | ndx | 0% | 0% | 61% | 21% | 8% |
| gpt-5.4-mini | russell2000 | 0% | 0% | 9% | 6% | 2% |
| gpt-5.4-mini | dow30 | 0% | 0% | 0% | 0% | 0% |
| gpt-5.4 | sp500 | 0% | 0% | 0% | 0% | 0% |
| gpt-5.4 | ndx | 0% | 0% | 0% | 0% | 0% |
| gpt-5.4 | russell2000 | 0% | 0% | 0% | 0% | 0% |
| gpt-5.4 | dow30 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-luna | sp500 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-luna | ndx | 0% | 0% | 0% | 0% | 0% |
| gpt-6-luna | russell2000 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-luna | dow30 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-sol | sp500 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-sol | ndx | 0% | 0% | 0% | 0% | 0% |
| gpt-6-sol | russell2000 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-sol | dow30 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-astra | sp500 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-astra | ndx | 0% | 0% | 0% | 0% | 0% |
| gpt-6-astra | russell2000 | 0% | 0% | 0% | 0% | 0% |
| gpt-6-astra | dow30 | 0% | 0% | 0% | 0% | 0% |
| claude-haiku-5.5 | sp500 | 0% | 0% | 0% | 0% | 0% |
| claude-haiku-5.5 | ndx | 0% | 0% | 0% | 0% | 0% |
| claude-haiku-5.5 | russell2000 | 0% | 0% | 0% | 0% | 0% |
| claude-haiku-5.5 | dow30 | 0% | 0% | 0% | 0% | 0% |
| claude-sonnet-5.5 | sp500 | 0% | 0% | 0% | 0% | 0% |
| claude-sonnet-5.5 | ndx | 0% | 0% | 0% | 0% | 0% |
| claude-sonnet-5.5 | russell2000 | 0% | 0% | 0% | 0% | 0% |
| claude-sonnet-5.5 | dow30 | 0% | 0% | 0% | 0% | 0% |
| claude-opus-5.5 | sp500 | 0% | 0% | 0% | 0% | 0% |
| claude-opus-5.5 | ndx | 0% | 0% | 0% | 0% | 0% |
| claude-opus-5.5 | russell2000 | 0% | 0% | 0% | 0% | 0% |
| claude-opus-5.5 | dow30 | 0% | 0% | 0% | 0% | 0% |

## 2. Scaling (biased documents pooled)

| Line | Size | Model | S&P 500 | Nasdaq-100 | Russell 2000 | Dow 30 |
|---|---|---|---|---|---|---|
| ollama | small | qwen2.5-7b | 98% [96%, 99%] | 100% [99%, 100%] | 100% [99%, 100%] | 97% [96%, 98%] |
| ollama | mid | qwen2.5-14b | 70% [66%, 73%] | 99% [98%, 100%] | 56% [52%, 60%] | 34% [30%, 38%] |
| openai | small | gpt-5.4-nano | 11% [8%, 14%] | 68% [63%, 73%] | 45% [40%, 50%] | 35% [30%, 40%] |
| openai | mid | gpt-5.4-mini | 14% [10%, 18%] | 30% [26%, 35%] | 6% [4%, 8%] | 0% [0%, 1%] |
| openai | large | gpt-5.4 | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] |
| openai-gpt6 | small | gpt-6-luna | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] |
| openai-gpt6 | mid | gpt-6-sol | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] |
| openai-gpt6 | large | gpt-6-astra | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] |
| anthropic | small | claude-haiku-5.5 | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] |
| anthropic | mid | claude-sonnet-5.5 | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] |
| anthropic | large | claude-opus-5.5 | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] | 0% [0%, 1%] |

Figures: `figures/scaling_all.png` (2x2 overview) and `figures/scaling_<family>.png`.

## 2b. Generation: gpt-5.4 vs gpt-6 (same prompts, cells and seeds; descriptive)

| Size | gpt-5.4 model | gpt-6 model | S&P 500 | Nasdaq-100 | Russell 2000 | Dow 30 |
|---|---|---|---|---|---|---|
| small | gpt-5.4-nano | gpt-6-luna | 11% -> 0% | 68% -> 0% | 45% -> 0% | 35% -> 0% |
| mid | gpt-5.4-mini | gpt-6-sol | 14% -> 0% | 30% -> 0% | 6% -> 0% | 0% -> 0% |
| large | gpt-5.4 | gpt-6-astra | 0% -> 0% | 0% -> 0% | 0% -> 0% | 0% -> 0% |

Cells show costlier-fund share under biased documents, gpt-5.4 -> gpt-6.

## 2c. Cost of the picks: mean 5-year regret (bp), biased documents (no document in brackets)

| Model | S&P 500 | Nasdaq-100 | Russell 2000 | Dow 30 |
|---|---|---|---|---|
| qwen2.5-7b | 11.8 (1.8) | 7.0 (5.7) | 14.9 (2.4) | 167.4 (0.0) |
| qwen2.5-14b | 8.9 (1.9) | 7.0 (4.1) | 8.4 (0.0) | 58.2 (0.0) |
| gpt-5.4-nano | 2.5 (1.6) | 4.8 (0.1) | 6.7 (0.0) | 59.4 (0.0) |
| gpt-5.4-mini | 2.1 (0.1) | 2.1 (0.0) | 0.8 (0.0) | 0.0 (0.0) |
| gpt-5.4 | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| gpt-6-luna | 0.5 (0.1) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| gpt-6-sol | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| gpt-6-astra | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| claude-haiku-5.5 | 1.3 (0.4) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| claude-sonnet-5.5 | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| claude-opus-5.5 | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |

Regret = cost gap between the pick and the best fund in the family, averaged over valid picks.

## 3. Robustness: fiduciary prompt and templates

| Model | Family | Fiduciary - standard (biased docs) | 95% CI | Holm p | Template sign agreement (D3/D5/D7) |
|---|---|---|---|---|---|
| qwen2.5-7b | sp500 | -0.01 | [-0.04, +0.02] | 0.288 | 3/3 |
| qwen2.5-7b | ndx | +0.00 | [-0.01, +0.01] | 1 | 3/3 |
| qwen2.5-7b | russell2000 | -0.01 | [-0.03, +0.00] | 0.124 | 3/3 |
| qwen2.5-7b | dow30 | -0.04 | [-0.07, -0.01] | 0.00373 | 3/3 |
| qwen2.5-14b | sp500 | -0.41 | [-0.47, -0.34] | 1.24e-28 | 3/3 |
| qwen2.5-14b | ndx | -0.01 | [-0.03, +0.00] | 0.0619 | 3/3 |
| qwen2.5-14b | russell2000 | -0.46 | [-0.53, -0.39] | 1.8e-30 | 3/3 |
| qwen2.5-14b | dow30 | -0.27 | [-0.34, -0.20] | 6.25e-12 | 3/3 |
| gpt-5.4-nano | sp500 | -0.19 | [-0.25, -0.13] | 2.35e-09 | 3/3 |
| gpt-5.4-nano | ndx | -0.45 | [-0.53, -0.36] | 1.05e-20 | 3/3 |
| gpt-5.4-nano | russell2000 | -0.58 | [-0.66, -0.49] | 1.05e-29 | 3/3 |
| gpt-5.4-nano | dow30 | -0.33 | [-0.42, -0.24] | 5.83e-11 | 3/3 |
| gpt-5.4-mini | sp500 | -0.18 | [-0.25, -0.11] | 7.05e-07 | 3/3 |
| gpt-5.4-mini | ndx | -0.44 | [-0.52, -0.36] | 7.57e-21 | 2/3 |
| gpt-5.4-mini | russell2000 | -0.11 | [-0.17, -0.07] | 2.73e-06 | 0/3 |
| gpt-5.4-mini | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-5.4 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-5.4 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-5.4 | russell2000 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-5.4 | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-luna | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-luna | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-luna | russell2000 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-luna | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-sol | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-sol | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-sol | russell2000 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-sol | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-astra | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-astra | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-astra | russell2000 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| gpt-6-astra | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-haiku-5.5 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-haiku-5.5 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-haiku-5.5 | russell2000 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-haiku-5.5 | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-sonnet-5.5 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-sonnet-5.5 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-sonnet-5.5 | russell2000 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-sonnet-5.5 | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-opus-5.5 | sp500 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-opus-5.5 | ndx | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-opus-5.5 | russell2000 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |
| claude-opus-5.5 | dow30 | +0.00 | [-0.02, +0.02] | 1 | 3/3 |

## 4. Literature positioning

See `docs/literature_v3.md`.

## Caveats

- Post-freeze amendments: v3-1 (30 runs per cell for API models); see `docs/design_v3.md`.
- Name-vs-ID flags were cleared only by recorded manual review (`data/gate_reviews_v3.csv`).
- Returns as of 2026-09-30 (S&P 500) vs 2026-06-30 (Nasdaq-100); QQQ's 5-yr history spans its UIT years.
- Amendment v3-3 (`docs/design_v3.md` 5c): Dow 30 and Russell 2000 added for the 8 v3 models; gpt-6 Luna / Sol / Astra run on all four families. The original families were not re-run.
- Dow 30 compares an ETF (DIA) with a mutual fund (RYDHX); its gap is about 10x the others' and it is reported separately. RYDHX's tracking difference uses DIA's published index return.
- Russell 2000 and Dow 30 returns as of 2026-09-30.
- gpt-6-astra accepts reasoning_effort 'low' as its lowest setting (Luna and Sol accept 'none'). Astra's main run paused when the account's credit ran out and resumed after it was refilled; completed runs are unaffected (seeded, run-index order).
- Two flagged responses were confirmed as real name-vs-ID mismatches by manual review (gpt-5.4-nano and qwen2.5-14b, both Dow 30 D3/D7, 1 of 600 or 1,000 in their family); all others were false positives.
