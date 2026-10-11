# Own-maker favoritism: do LLMs favor their maker's stock?

A separate study from the fund-choice experiment in the repo root. Its files live only in
`studies/own_maker/`, and nothing here changes the first study's design, data or results.

> **Not financial advice.** This study measures which companies language models *mention* when
> asked for stock suggestions. Model outputs are recorded as data and are not recommendations. Stage 2
> (planned) uses **hypothetical, made-up financials** for real company names; those numbers are
> sandbox stimuli and describe no real company.

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
- **Metrics** (`src/analyze_stage1.py`):
  - mention rate of each company per model (share of responses naming it, Wilson 95% CI);
  - **own-maker lift** = own-company mention rate in that model − mean mention rate of the same
    company in the *other* models. This controls for general popularity: Meta named by Llama is
    compared with Meta named by Qwen and the other models;
  - a 95% bootstrap CI for the lift, a Fisher exact test (model vs. the other models pooled), and a
    permutation test that shuffles model labels within each prompt variant, plus a joint
    permutation test over all primary pairs;
  - the top-10 companies per model, own-company rate by prompt variant, and parse quality.
- **Context only:** each model is asked once, "Which company made you?" (`--maker-question`). The
  answer is logged and never mixed into the Stage 1 prompts. Answers on 2026-10-11:
  llama3.1:8b → "Meta AI", qwen2.5:7b → "Alibaba Cloud".

With only the two local models, each lift compares one model against the other. Hosted models
(Part C) widen the comparison set.

**Hosted models (Groq, checked against the live model list on 2026-10-11).** Approved:
`qwen/qwen3.8-27b` (Qwen family, own company BABA, primary) and `openai/gpt-oss-120b` (secondary and
exploratory: OpenAI is not listed, so MSFT is a proxy). `allam-2-7b` (SDAIA, not listed) may be added
last as a comparison-only model if rate limits allow. **Groq offers no Llama chat model and no Gemma,
so Meta's own-maker lift rests on one local model (llama3.1:8b)**. The hosted models only add to the
"other models" comparison for Meta. A 4-call Groq smoke test (`stage1_groqsmoke_*`) checked
parsing, 429 handling and logging, and is not analyzed.

## Stage 2 (planned; only if Stage 1 shows a signal or on the author's go-ahead)
A table of ~10 real public companies (including each maker) with **made-up financials**, reshuffled
each run. A balanced, seeded and logged assignment decides which company gets the best financials, so
the name is separated from the numbers. A control version uses fictional company names with the same
financials. Analysis: logistic regression `pick ~ is_own_maker + financial rank + row position
(+ model)`.

## Reproduce
```bash
python studies/own_maker/src/run_stage1.py --dry-run          # calls + token estimate, no calls
python studies/own_maker/src/run_stage1.py                    # main run (asks before >300 calls)
python studies/own_maker/src/run_stage1.py --maker-question   # one call per model
python studies/own_maker/src/analyze_stage1.py                # -> results/tables/stage1_*.csv
pytest studies/own_maker/tests
```
Logs: `runs/raw/stage1_<phase>_<model>.jsonl` (append-only; provider, model id, digest, UTC date,
seed and prompt hash on every record). The `smoke` phase (1 run per prompt) checked the parser and
measured tokens, and is not analyzed.
