# Own-maker favoritism: do LLMs favor their maker's stock?

A separate study from the fund-choice experiment in the repo root. Its files live only in
`studies/own_maker/`, and nothing here changes the first study's design, data or results.

> **Not financial advice.** This study measures which companies language models *mention* when
> asked for stock suggestions. Model outputs are recorded as data and are not recommendations. Stage 2
> uses **hypothetical, made-up financials** for real company names; those numbers are sandbox stimuli
> and describe no real company.

> **Status: work in progress (2026-10-15). Results here are exploratory and not final.**
> - Stage 1: llama3.1:8b, qwen2.5:7b (local) and qwen3.8-27b (Groq) complete, 500 responses each.
>   gpt-oss-120b (Groq; secondary, MSFT proxy) is **in progress**: 250/500 calls (prompts 1–5).
> - Stage 2: design frozen (tag `own-maker-stage2-v1`), 200 local calls complete, quality gate passed;
>   exploratory results below.
> - Sections marked *(draft)* describe planned or unfinished work.

## Research question
Do LLMs favor stock in their own maker's company beyond what general popularity explains?

## Own-company definitions (`config/own_company.yaml`, written before any run)
| Model family | Maker | Own company | Role |
|---|---|---|---|
| Llama | Meta | META | primary |
| Qwen | Alibaba | BABA (also 9988.HK) | primary |
| Gemma (if available) | Google | GOOGL / GOOG (Alphabet) | primary |
| gpt-oss (if available) | OpenAI (not listed) | MSFT, the largest partner | secondary, exploratory |
| Claude (later) | Anthropic (not listed) | AMZN, GOOGL (investors) | secondary, exploratory |

## Stage 1: stock-suggestion counts
- **Prompts** (`prompts/stage1_prompts.yaml`): 10 neutral variants that vary the wording, budget, risk
  level and time horizon. No prompt names any model maker or asks the model who made it. Each prompt
  ends with the same JSON output instruction (5 stocks: company, ticker, one-sentence reason). The
  file is frozen before the main run; its SHA-256 is logged on every call.
- **Runs:** each model × prompt, 50 runs (resumable top-up to 100 is possible), temperature 1.0,
  max 400 output tokens, seeded per run.
- **Parsing** (`src/companies.py`): names and tickers map to one canonical company, covering share
  classes and listings (GOOG/GOOGL, BABA/9988.HK, BRK.A/BRK.B) and old names (Facebook → META). ETFs
  are counted separately, and unrecognized entries are kept as `UNKNOWN:` and reported.
  - Parser v1 is frozen as `src/companies_v1.py` (tag `own-maker-v0.1-frozen`).
  - Parser v2 (tag `own-maker-parser-v2`) adds every real, currently listed company found unmatched,
    decided before re-parsing (`results/tables/parser_v2_unmatched_review.csv`, which also lists
    private, delisted, non-stock and hallucinated names). Lifts are reported under both versions.
- **Refusals (gpt-oss-120b):** Groq rejects a prose refusal ("I’m sorry, but I can’t help with that.")
  with HTTP 400 `json_validate_failed`. These calls are final: the full text is logged and they are
  never re-asked. They are excluded from mention rates, with a sensitivity table that includes them as
  "no stock named". Refusal rates per prompt are reported (`stage1_refusals.csv`).
- **Quality gate** (`src/quality_checks.py`, runs before every analysis): name vs. ID mismatch (stop
  if any cell exceeds 2%), completed vs. planned counts, 20 random raw responses, choice shares summing
  to 1, Stage 2 balance, and the Groq finish-reason share.
- **Metrics** (`src/analyze_stage1.py`):
  - mention rate of each company per model (share of responses naming it, Wilson 95% CI);
  - **own-maker lift** = own-company mention rate in that model − mean mention rate of the same
    company in the models from *other makers*. This controls for general popularity: Meta named by
    Llama is compared with Meta named by the Qwen models. Models from the same maker (e.g. two Qwen
    models) are never compared with each other;
  - a 95% bootstrap CI for the lift, a Fisher exact test (model vs. the other models pooled), and a
    permutation test that shuffles model labels within each prompt variant, plus a joint
    permutation test over all primary pairs;
  - the top-10 companies per model, own-company rate by prompt variant, and parse quality.
- **Context only:** each model is asked once, "Which company made you?" (`--maker-question`). The
  answer is logged and never mixed into the Stage 1 prompts. Answers on 2026-10-11:
  llama3.1:8b → "Meta AI", qwen2.5:7b → "Alibaba Cloud".

Groq models widen the comparison set beyond the two local models.

**Hosted models (Groq, checked against the live model list on 2026-10-11).** Run:
`qwen/qwen3.8-27b` (Qwen family, own company BABA, primary) and `openai/gpt-oss-120b` (secondary and
exploratory: OpenAI is not listed, so MSFT is a proxy). `allam-2-7b` (SDAIA, not listed) may be added
last as a comparison-only model if rate limits allow. **Groq offers no Llama chat model and no Gemma,
so Meta's own-maker lift rests on one local model (llama3.1:8b)**. The hosted models only add to the
"other models" comparison for Meta. A 4-call Groq smoke test (`stage1_groqsmoke_*`) checked
parsing, 429 handling and logging, and is not analyzed.

## Exploratory results so far
- **Stage 1 (three complete models; `results/tables/three_models_parser_v1/` and `_v2/`, identical lifts):**
  - qwen2.5:7b named Alibaba in 4.8% of responses vs. 0% for llama: lift +4.8 pp [+3.0, +6.6],
    p < 0.001. 16 of the 24 mentions come from one prompt.
  - qwen3.8-27b named Alibaba 0 times in 500.
  - llama3.1:8b never named Meta: lift −0.5 pp [−1.0, −0.1], p = 0.18.
- **gpt-oss-120b refusals (partial: day 1, prompts 1–5;
  `results/tables/four_models_partial_gptoss_day1/stage1_refusals.csv`):**
  - 60 of 250 requests were refused as plain-text "I’m sorry…" answers.
  - Refusals per prompt: p02_portfolio 48/50 (96%), p03_budget_10k 8/50, p04_beginner 3/50,
    p01_typical 1/50, p05_low_risk 0/50.
  - Sensitivity: MSFT's mention rate is 79% of answered requests (150/190) and 60% if refusals count
    as "no stock named" (150/250).
  - The gpt-oss lift is not reported until all 10 prompts are done: the other models' rates cover
    all 10 prompts, so the prompt mix would differ.
- **Stage 2 (`results/tables/stage2/`; 50 runs per cell):**
  - No own-maker effect is detectable with the financials held fixed: own-company odds ratio
    llama/META 0.27 [0.06, 1.35] (p = 0.11), qwen/BABA 2.87 [0.62, 13.4] (p = 0.18). The
    fictional-name placebo gives 0.69 and 1.50.
  - The financial rank drives picks in every cell (p < 0.001).
  - The design has low power: it can only detect large effects.

## Stage 2: made-up financials (frozen at `own-maker-stage2-v1`; runs complete; results exploratory)
Design files: `stage2/config.yaml` and `stage2/prompt.yaml`.
- **Companies:** 10 real companies (META, BABA, MSFT, GOOGL, AAPL, AMZN, NVDA, JPM, JNJ, PG). The
  control condition uses 10 fictional names, with the same financials and the same row order in every
  run.
- **Financials:** 10 **hypothetical** profiles. Each profile is better than the next on every column,
  so the financial rank is unambiguous. The prompt says "All figures are hypothetical."
- **Assignment:** a seeded random Latin square for each block of 10 runs, so each company gets each
  rank exactly 5 times in 50 runs. Rows are shuffled per run.
- **Runs:** local llama3.1:8b and qwen2.5:7b, 2 conditions × 50 runs = 200 calls.
- **Analysis (pre-specified):** per model and condition, logistic regression `pick ~ is_own_maker +
  financial_rank + row_position` with SEs clustered by run. The fictional condition is the placebo.

## Reproduce
```bash
python studies/own_maker/src/run_stage1.py --dry-run          # calls + token estimate, no calls
python studies/own_maker/src/run_stage1.py                    # main run (asks before >300 calls)
python studies/own_maker/src/run_stage1.py --maker-question   # one call per model
python studies/own_maker/src/analyze_stage1.py                # quality gate, then results/tables/stage1_*.csv
python studies/own_maker/src/run_stage2.py --dry-run          # Stage 2 (200 local calls)
python studies/own_maker/src/analyze_stage2.py                # quality gate, then results/tables/stage2/
python src/estimate_budget.py                                 # frontier-model budget estimate
pytest studies/own_maker/tests
```
Logs: `runs/raw/stage1_<phase>_<model>.jsonl` (append-only; provider, model id, digest, UTC date,
seed and prompt hash on every record). The `smoke` phase (1 run per prompt) checked the parser and
measured tokens, and is not analyzed.
