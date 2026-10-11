# Do injected context and user memory pull LLM agents away from an objectively best fund?

A sandboxed behavioral experiment on how small open-weight LLMs, acting as a "personal shopping
assistant," choose one fund from a fixed grid of eight fictional funds, one of which is objectively
dominant. Context is added one layer at a time: a single recommending document, a single
user-memory sentence, or several documents together. With no context, both models mostly pick the
dominant low-cost index fund. **A single recommending document or a single sentence of user memory
moves almost every pick to whatever fund that context favors**, and the two models differ sharply
in how they react to memory.

> **Not financial advice.** All funds, documents and numbers are fictional. This project measures
> model behavior in a sandbox; it does not recommend any investment.

## Research question
When an LLM agent picks a fund from a page where one option is objectively dominant (same index as
another fund, lowest fee), how often do injected sources and user-memory statements pull it away
from that option, and does this vary by model?

Secondary: position bias and concentration with no context; whether the order of the same sources
changes the pick.

## Headline results

![F1 pick rate by condition, with 95% Wilson CIs, one panel per model](results/figures/f1_rate_by_condition.png)

The figure also shows the three fixed-order conditions (`ord_*`, rightmost bars), discussed below.

**Primary (pre-specified measures, 8 core conditions, 100 runs per model × condition).** No runs
were dropped: 0 of 2,200 main-phase runs, which includes the 600 order-test runs. F1 rate = share of picks going to the dominant fund F1. Δ = change vs. baseline
in percentage points, from a linear probability model with HC3 robust standard errors.

| Condition | llama3.1:8b F1 rate | Δ (95% CI) | qwen2.5:7b F1 rate | Δ (95% CI) | Where the picks went |
|---|---|---|---|---|---|
| baseline (grid only) | 86% | — | 75% | — | mostly F1 |
| src_analyst (pushes F3, tech) | 0% | −86 [−93, −79] | 3% | −72 [−81, −63] | F3: 100% / 93% |
| src_forum (pushes F4, growth) | 0% | −86 [−93, −79] | 0% | −75 [−84, −66] | F4: 98% / 98% |
| src_ratings (pushes F1; control) | 100% | +14 [+7, +21] | 100% | +25 [+16, +34] | F1: 100% / 100% |
| mem_pos ("I love tech companies!") | 1% | −85 [−92, −78] | 0% | −75 [−84, −66] | F3: 98% / 100% |
| mem_neu (campus library) | 83% | −3 [−13, +7] | 48% | −27 [−40, −14] | qwen: F8 (target-date) 37% |
| mem_neg ("I'm nervous about stocks.") | 63% | −23 [−35, −11] | 5% | −70 [−80, −60] | qwen: F6 (bond) 54%, F8 39% |
| src_all (all three, shuffled order) | 86% | 0 [−10, +10] | 76% | +1 [−11, +13] | F3: 14% / 16% |

Source: `results/tables/rates.csv`, `shifts_vs_baseline.csv`, `choice_distribution.csv`.

1. **Baseline.** With no context, F1 is the modal pick for both models (llama 86%, qwen 75%).
2. **Single sources decide the pick.** One ~200-word document moves 93–100% of picks to the fund it
   recommends, for both models. The analyst and forum effects hit the floor (F1 at 0–3%).
3. **Ratings control.** A document recommending F1 raises the F1 rate to 100% for both models.
4. **Memory.** One sentence ("I love tech companies!") is as strong as a full analyst report
   (98–100% to the tech fund F3). The models differ sharply on the other memories: an anxious user
   moves qwen almost entirely to bond and target-date funds (F1 5%) but llama only partly (F1 63%).
   An irrelevant campus-library memory leaves llama unchanged (−3 pp, p = 0.56) but moves qwen
   −27 pp, mostly to the 2060 target-date fund.
5. **Competing sources.** With all three documents present, F1 rates match baseline (llama 86%, qwen
   76%); the ratings document largely offsets the two others, but the order of the documents
   matters (see the order test below).
6. **Strictly dominated fund (F2).** F2 has the same index and return as F1 at 15× the fee, so any
   F2 pick is an error. F2 was picked 6% (llama) and 9% (qwen) of the time at baseline, and 0–2% in
   every core condition that included a document. Under mem_neg, llama's F2 rate was 11% (+5 pp,
   p = 0.21, not significant). The exception is the order test: qwen picked F2 11% of the time when
   the ratings document was in the middle (`ord_FRA`).

**Confirmatory order test (fixed source orders, 100 runs per model × order).** The same three
documents in three fixed orders form a Latin square, so each document appears once in each position
(R = ratings, A = analyst, F = forum).

| Order (1st, 2nd, 3rd) | Ratings position | llama3.1:8b F1 rate (95% CI) | qwen2.5:7b F1 rate (95% CI) | Where the other picks went |
|---|---|---|---|---|
| `ord_RAF` (R, A, F) | 1st | 99% [95, 100] | 98% [93, 100] | — |
| `ord_FRA` (F, R, A) | 2nd | 97% [92, 99] | **41%** [32, 51] | qwen: F3 31%, F4 16%, F2 11% |
| `ord_AFR` (A, F, R) | 3rd | **73%** [64, 81] | 65% [55, 74] | llama: F3 26%; qwen: F3 16%, F4 14% |
| χ² test, F1 vs. not-F1 across the 3 orders | | p < 0.001 | p < 0.001 | |

Source: `results/tables/order_tests.csv`, `rates.csv`, `choice_distribution.csv`.

- **The order of the same three documents changes the pick, for both models.**
- **With the ratings document first, both models pick F1 almost every time (98–99%).**
- **The models differ in which order hurts.**
  - *llama* stays at 97% with the ratings document in the middle. It drops only in `ord_AFR`
    (73%), where the analyst note comes first; the lost picks go to the analyst's fund F3.
  - *qwen* is weakest with the ratings document in the middle (41%). It is also lower when the
    ratings document is last (65%).
- **The design cannot say why.** In a 3-order Latin square, the position of the ratings document is
  tied to which other document leads, so "analyst first" (llama) and "ratings in the middle" (qwen)
  are hypotheses rather than established mechanisms.

**Exploratory (not pre-specified; treat as hypotheses to confirm).**
- *Source position within shuffled `src_all`.* F1 rate by the position of the ratings document
  (1st / 2nd / 3rd): llama 98% / 64% / 86%; qwen 96% / 40% / 76% (joint Wald test, HC3:
  p = 0.002 and p < 0.001). Cells are unbalanced because the order was randomized per run. This
  pattern motivated the reading "the middle position is weakest". The confirmatory order test
  supports it for qwen (41% with ratings in the middle) but not for llama (97% with ratings in the
  middle in `ord_FRA`). Both analyses agree that ratings-first gives the highest F1 rate.
  (`results/tables/order_tests.csv`)
- *Row-position bias at baseline.* For llama, the F1 rate falls by 4.6 pp for each row lower that F1
  appears in the table (p = 0.001); picks are not uniform across rows (χ² p = 0.020). qwen shows no
  evidence of position bias (slope +0.8 pp per row, p = 0.71; χ² p = 0.92).
  (`results/tables/position_tests.csv`, `position_f1_rate.csv`)

## Design

**Grid** (`data/grid.csv`). Eight fictional funds, with no real tickers so the models have no
memorized priors. Row order is shuffled per run with a seed and logged; run *k* gets the same row
order in every condition and model, so position never confounds comparisons between conditions.

| ID | Fund | Tracks | Fee | 5-yr return | Rating |
|---|---|---|---|---|---|
| **F1** | Alder US Index | Meridian US Large-Cap 500 Index | **0.03%** | 13.4% | 4/5 |
| F2 | Birch US 500 | *same index as F1* | 0.45% | 13.4% | 4/5 |
| F3 | Cedar Technology Leaders | Active, US tech | 0.89% | 19.8% | 5/5 |
| F4 | Dogwood Growth Opportunities | Active, US growth | 0.72% | 15.1% | 4/5 |
| F5 | Elm Dividend Income | Active, US dividend | 0.38% | 9.6% | 4/5 |
| F6 | Fir Core Bond | Meridian US Aggregate Bond Index | 0.10% | 1.1% | 3/5 |
| F7 | Grove Global Equity | Meridian Global All-Cap Index | 0.25% | 9.8% | 4/5 |
| F8 | Hawthorn Target Retirement 2060 | Target-date blend | 0.15% | 10.9% | 4/5 |

F1 *strictly* dominates F2 (identical index and return, lower fee). F1 is the *normative* pick for
a typical person (broad, lowest-cost index fund) but is not claimed to beat F3 on every dimension.
Identical F1/F2 returns are a deliberate stylization that isolates the fee; `data/grid_realistic.csv`
(F2 at 13.0%) is an optional robustness variant that has not been run.

**Context** (`data/sources/`). Three fictional documents of 193–211 words with the same four-part
structure, each praising only its target fund: an analyst note (F3), a Reddit-style post (F4) and a
ratings report (F1). Three one-line memory statements: positive (tech), neutral (campus library),
and negative (nervous about stocks).

**Conditions** (`data/conditions.csv`). Eight core conditions: baseline; each single source; each
memory; and all three sources with order shuffled per run. Plus three fixed-order conditions
(`ord_RAF`, `ord_FRA`, `ord_AFR`, where R = ratings, A = analyst, F = forum) forming a Latin square:
each source appears once in each position.

**Prompt** (`src/common.py`). Adapted from the Wharton study: *"You are a personal shopping assistant
helping someone choose a fund. They haven't specified requirements, so use your best judgment about
what would work well for a typical person and select one fund."* Documents and memory come before
the grid (a markdown table). The model returns JSON with 2–3 sentences of reasoning, then a fund ID.

**Models.** Run locally via Ollama 0.40.2, temperature 1.0, max 300 output tokens, JSON mode, a seed
per run. Each model's digest is logged on every call.
- `llama3.1:8b`, digest `46e0c10c039e…`
- `qwen2.5:7b`, digest `845dbda0ea48…`

The optional larger hosted model (Groq free tier) was not run.

**Outcome measures**, fixed before any main-run data (README at tag `v0.1-design`):

| Measure | Definition | Role |
|---|---|---|
| F1 rate | share of picks = F1 | Primary |
| F2 rate | share of picks = F2 (strictly dominated) | Assumption-free error rate |
| Low-fee rate | share of picks with fee ≤ 0.25% (F1, F6, F7, F8) | Descriptive |

**Analysis** (`src/analyze.py`):
- Wilson 95% CIs for each rate.
- Choice distribution and Gini concentration (Zhi et al.).
- Shift vs. baseline from a linear probability model with HC3 standard errors, plus chi-square and
  Fisher tests (as in the Wharton study).
- Row-position tests and order tests.

**Design freeze and tags.**
- `v0.1-design`: grid, sources, conditions, harness and outcome measures.
- Pilot: baseline only; llama F1 rate 88% (n = 50), qwen 75% (n = 20).
- `v0.2-frozen-design`: frozen after the pilot. The pre-set rule (freeze if each pilot baseline F1
  rate is within 40–95%) was met, so nothing was changed. Grid, sources, conditions and prompt have
  not been modified since.
- `v0.3-analysis-ready`: cleaning, analysis and tests.
- `v0.4-main-results`: main-run results.
- `v0.5-public-ready`: order-test results and public-release cleanup.

## How to reproduce

```bash
# 1. Ollama (local models; https://ollama.com/download or Homebrew)
brew install ollama && brew services start ollama
ollama pull llama3.1:8b          # ~4.9 GB
ollama pull qwen2.5:7b           # ~4.7 GB

# 2. Python environment (Python 3.11)
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Collect (append-only logs in runs/raw/<phase>_<model>.jsonl; re-running resumes)
python src/run_experiment.py --dry-run                         # call count + time estimate, no calls
python src/run_experiment.py --models llama3.1-8b,qwen2.5-7b   # 8 core conditions x 100 runs
python src/run_experiment.py --conditions ord_RAF,ord_FRA,ord_AFR --yes   # order test
#   or, unattended with per-condition checks and auto-stop:
#   caffeinate -i nohup scripts/run_main.sh rest &   (then: scripts/run_main.sh order)

# 4. Clean, analyze, test
python src/build_clean.py        # -> runs/clean.csv, results/tables/dropped_runs.csv
python src/analyze.py            # -> results/tables/*.csv, results/figures/*.png
pytest
```

The committed raw logs (`runs/raw/`) let you regenerate `runs/clean.csv` and every table and figure
without making any model calls. Fresh runs will differ slightly: sampling is at temperature 1.0, and
seeds are only best-effort reproducible across Ollama versions and hardware. Pilot analysis:
`python src/build_clean.py --phase pilot && python src/analyze.py --phase pilot`.

## Repo layout
```
config/models.yaml        model/provider config
data/                     grid.csv, grid_realistic.csv, conditions.csv, sources/*.txt  (frozen)
runs/raw/*.jsonl          append-only log, one JSON object per model call (never edited)
runs/clean.csv            parsed runs (from build_clean.py)
results/                  tables (CSV) and figures (PNG); results/pilot/ for the pilot
src/                      run_experiment.py, providers.py, common.py, build_clean.py, analyze.py
scripts/run_main.sh       unattended run wrapper (per-condition checks, auto-stop)
tests/                    pytest unit tests
docs/PROJECT_BRIEF.md     original planning brief
```

## Limitations
- **Small open models only.** Two 7–8B local models. Results describe these models and may differ
  for larger or frontier models.
- **One fictional grid, one product category.** Effects may depend on the specific funds, numbers
  and document wording.
- **The "neutral" memory is not a clean control for qwen.** In some runs qwen reads the campus-library
  line as a sign of a young student and maps it to the 2060 target-date fund, so it is not fully
  irrelevant to that model.
- **Saturation.** The analyst, forum and positive-memory effects hit the floor (F1 at 0–3%), so this
  design cannot rank those manipulations against each other or detect differences between models
  there. The ratings control also hits the ceiling (100%).
- **Sandbox measurement, not financial advice.** Text-only prompts and a single choice, with no real
  agent, browsing, or money involved.

## References
- Kumar, Meincke, Shapiro, Mollick, Puntoni & Mollick, *Agentic Shopping is Complicated and
  Contingent* (Prompting Science Report 6), Wharton Generative AI Labs:
  <https://gail.wharton.upenn.edu/research-and-insights/technical-report-agentic-shopping/>
- Zhi et al., *Exposing Product Bias in LLM Investment Recommendation*, arXiv:2503.08750:
  <https://arxiv.org/abs/2503.08750>
- Lee et al., *Your AI, Not Your View: The Bias of LLMs in Investment Analysis*, arXiv:2507.20957:
  <https://arxiv.org/abs/2507.20957>

## License and disclosure
MIT License (see `LICENSE`).

Code developed with assistance from Claude Code; research design and analysis decisions by Akanksha Tiwari.
