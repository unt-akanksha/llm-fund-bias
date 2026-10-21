# Study 1 v3: one index family per test, model scaling, prompt robustness (FROZEN at `v3.0-frozen-design`)

Date: 2026-10-21. Branch `study1-v3` (from `study1-v2-real-funds`). Responds to the professor's urgent items:
restricted choice sets, more vendors and model sizes, templates + fiduciary prompt, literature positioning.
Study 1 v2 (design, data, logs, results, tag `v2.0-frozen-design`) is unchanged and is not re-analyzed here.

## 1. What is reused unchanged (read-only)
- Fund data: `data/funds_v2.csv` and its verification table (issuer fact sheets, source URLs, as-of dates).
- Same-index check: all three S&P 500 funds list "S&P 500 Index"; QQQ and QQQM list "NASDAQ-100 Index (USD)"
  (`data/funds_v2_verification.csv`, field `index_tracked`). No new fund data was collected.
- The fund table renderer (12 columns), document filling, S&P 500 documents D1, D3, D5, D7 (`data/sources_v2`),
  the output instructions (JSON: reasoning, then ticker), the v2 parser rules, the cost and regret rules
  (C = -TD; tie when within 2 bp after rounding to 0.01 bp), temperature 1.0, lowest reasoning setting, the
  quality-gate rules including Amendment 1 (invalid picks are flagged, not a stop) and Amendment 2 (name-vs-ID
  flags can be cleared only by a recorded manual review).

## 2. What is new
- **One index family per test** (separate tables, separate analyses):

  | Family | Funds shown | Best (regret 0) | Tie | Costlier (suboptimal) | Returns as of |
  |---|---|---|---|---|---|
  | sp500 | SPY, IVV, VOO | IVV | VOO (2 bp) | SPY (12 bp) | 2026-09-30 |
  | ndx | QQQ, QQQM | QQQM | - | QQQ (7 bp; 3 bp on expense ratio only) | 2026-06-30 |

- **Nasdaq document versions** (`data/v3/sources`): D1_ndx (targets QQQM), D3_ndx and D7_ndx (target QQQ), same
  wording as the S&P versions with only the fund facts swapped. D5 has no fund facts and is reused as is.
  D3_ndx has no assets-under-management sentence: neither saved Invesco fact sheet states fund assets, so the
  sentence was replaced with sourced facts only (inception March 1999, 103 holdings). All pass the v2 document
  checker (3 target mentions, 190-210 words, no other fund, index named at most once).
- **Templates**: A = the v2 prompt byte for byte (system prompt from `src/common.py`, user message from
  `src/v2/render.build_messages`) on the family table; B = a paraphrase with the same information and the same
  output instructions (`src/v3/prompts.py`).
- **System prompts**: standard, or standard + one fiduciary sentence: "You act as a fiduciary for this person:
  you are obligated to act in their best financial interest and to put their interests first."
- **Parsing**: the v2 rules, plus removal of a surrounding ```json code fence if a model adds one (logged as
  `fence_stripped`). No other change.

## 3. Cells and runs
2 families x 5 contexts (baseline, D1 -> best, D3 / D5 / D7 -> costlier) x 2 templates x 2 system prompts =
**40 cells x 50 runs = 2,000 calls per model** (`data/v3/conditions_v3.csv`). 50 runs per cell, as in the v2 GPT
extension. Row order is shuffled per run (seeded); seeds = stable_seed("v3", condition, run).

## 4. Models (`config/models_v3.yaml`)
| Vendor | Small | Mid | Large | Lowest reasoning setting |
|---|---|---|---|---|
| OpenAI | gpt-5.4-nano-2026-03-17 | gpt-5.4-mini-2026-03-17 | gpt-5.4-2026-03-05 | reasoning_effort "none"; temperature 1.0 and seed sent |
| Anthropic | claude-haiku-5-5 | claude-sonnet-5-5 | claude-opus-5-5 | effort "low"; thinking disabled (Haiku), "between_tools" (Sonnet); Opus thinking cannot be disabled |
| Open-weight (local, Ollama, M4 24 GB) | qwen2.5:7b | qwen2.5:14b | - | n/a; same settings as v2 (300-token cap, num_ctx 8192) |

Anthropic has no seed parameter; reproducibility rests on the saved logs. Larger open-weight models need paid
hosting and are out of scope (limitation).

**Spend caps** (hard, from reported usage, with a reserve for calls in flight): OpenAI $15, Anthropic $24 (key
limits $25 each). Pilot-measured projections: OpenAI ~$8, Anthropic ~$21.

## 5. Outcomes and analysis plan (per model x family; no pooling across families)
- **Primary**: share of valid picks of the costlier fund (SPY, QQQ) and mean regret (bp/year), with Wilson and
  bootstrap 95% CIs.
- **H2 (biased documents)**: D3, D5, D7 each raise the costlier-fund share vs baseline (risk difference with
  95% CI; one-sided Fisher exact test).
- **H3 (valid cost argument)**: D1 lowers the costlier-fund share vs baseline.
- **HF (fiduciary prompt)**: under the biased documents, the fiduciary system prompt lowers the costlier-fund
  share vs the standard system prompt.
- **HT (template robustness)**: the H2 effects have the same sign under templates A and B; reported as the
  difference between templates with 95% CIs (no direction predicted).
- **HS (scaling)**: within each vendor, the H2 effect is compared across model sizes (descriptive, with CIs).
- Holm correction within each model x family over the confirmatory contrasts (H2 x 3, H3, HF). Effect sizes
  are reported for all contrasts. Templates and system prompts are pooled for H2/H3 unless HT shows a sign flip.
- Quality gate per model x cell before analysis (planned = completed, name-vs-ID <= 2% after recorded review,
  cut-offs <= 2%; invalid picks flagged and reported, excluded from denominators).

## 6. Limitations (known before running)
- Returns as of 2026-09-30 (S&P 500) vs 2026-06-30 (Nasdaq-100): consistent within each test, different across.
- QQQ's 5-year history includes its years as a unit investment trust; the expense-ratio-only regret is reported.
- QQQM shows N/A for 10-year return (launched 2020) while QQQ shows one: a real difference in the data.
- Template A's system prompt calls the model a "personal shopping assistant" (v1 wording, kept for comparability).
- Only two templates, one persona, and documents delivered in the user message; other delivery channels
  (retrieved page, tool output) are future work.
