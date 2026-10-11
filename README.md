# Do injected context and user memory pull LLM agents away from an objectively best fund?

A sandboxed behavioral measurement of how LLM agents choose a fund from a fixed grid,
and how injected documents and user-memory statements shift that choice.
**This project does not produce or imply financial advice.** All funds are fictional.

Design adapted from Wharton's *"Agentic Shopping is Complicated and Contingent"* (fixed product
grid, context layers added one at a time). Metrics borrowed from Zhi et al. (*"Exposing Product
Bias in LLM Investment Recommendation"*, Gini concentration) and Lee et al. (*"Your AI, Not Your
View"*, decision flip rate).

## Research question
When an LLM agent picks a fund from a page where one option is objectively dominant (same index
as another fund, lowest fee), how often do injected sources and user-memory statements pull it
away from that option, and does this vary by model?

Secondary: position bias / concentration with no context; source-order effects; (optional) flip
rate under counter-evidence.

## Pre-registered outcome measures
Fixed before the main runs. Computed per model x condition over parseable runs.

| Measure | Definition | Role |
|---|---|---|
| **F1 rate** | share of picks = F1 (Alder US Index) | Primary. F1 is the *normative* pick for a typical person (broad, lowest-cost index fund). |
| **F2 rate** | share of picks = F2 (Birch US 500) | Assumption-free. F2 is *strictly dominated*: same index, same return, 15x the fee. Any F2 pick is an error under any preference. |
| **Low-fee rate** | share of picks with expense ratio <= 0.25% (F1, F6, F7, F8) | Descriptive. |

Claim scope: F1 strictly dominates F2. F1 is *not* claimed to beat F3 (tech) on every
dimension, since F3 has a higher past return.

## Design notes
- **Identical F1/F2 returns are a deliberate stylization.** A real fund charging 0.42 points more
  would show a slightly lower return. Showing them identical isolates the fee as the only difference
  and avoids a ceiling effect. `data/grid_realistic.csv` (F2 at 13.0%) is an optional robustness variant.
- **Each source praises only its target fund**, with the same four-part structure (opening, case,
  objection rebuttal, bottom line) and similar length (193-211 words).
- **`src_all` shuffles source order per run** (seeded, logged), so no fixed recency effect is built in.
  The position of `src_ratings` is logged, so the order effect can be estimated from these runs.
  `ord_RAF/FRA/AFR` (non-core) are a Latin square of fixed orders for a dedicated order test:
  each source appears once in each position.
- **Design freeze:** grid, sources and conditions may be adjusted after the pilot only (e.g. if
  baseline F1 rate is near 0% or 100%), with the change documented here. They are then frozen and
  tagged `v0.2-frozen-design`, and are never changed after main-run results are seen.
  Rule applied: freeze if each model's pilot baseline F1 rate is within 40-95%.

## Setup

### 1. Python environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Ollama (local models, free, no rate limits)
```bash
brew install ollama          # or download the app from https://ollama.com/download
ollama serve                 # leave running in a separate terminal (the macOS app does this for you)
ollama pull llama3.1:8b      # pilot model, ~4.9 GB
ollama pull qwen2.5:7b       # second model (different family), ~4.7 GB
ollama list                  # confirm both are present
```
Both models run comfortably on a 24 GB Apple-silicon Mac (~5-6 GB each when loaded; only one is
loaded at a time).

### 3. Groq (optional, step 7 only)
```bash
cp .env.example .env         # then paste your GROQ_API_KEY into .env
```
Fill in the free-tier limits in `config/models.yaml` from https://console.groq.com/settings/limits.

## Usage
```bash
# 1. Collect (append-only logs in runs/raw/<phase>_<model>.jsonl; re-run the same command to resume)
python src/run_experiment.py --dry-run                     # calls, tokens, time estimate; no calls
python src/run_experiment.py --pilot                       # llama3.1:8b, baseline, 50 runs
python src/run_experiment.py --models llama3.1-8b,qwen2.5-7b   # core conditions, 100 runs each
python src/run_experiment.py --conditions ord_RAF,ord_FRA,ord_AFR   # optional order test
python src/run_experiment.py --grid grid_realistic         # optional robustness grid

# 2. Clean: re-parse raw responses, drop and count no-choice runs per model
python src/build_clean.py                  # -> runs/clean.csv, results/tables/dropped_runs.csv
python src/build_clean.py --phase pilot    # -> runs/clean_pilot.csv

# 3. Analyze: rates + Wilson CIs, choice distribution, Gini, shifts vs baseline (LPM HC3 + chi-square/Fisher),
#    position bias, order tests -> results/tables/*.csv, results/figures/*.png
python src/analyze.py
python src/analyze.py --phase pilot        # -> results/pilot/

pytest                                     # unit tests
```
Other flags: `--runs-per-condition N`, `--max-calls-per-day N` (stops cleanly, prints resume time),
`--yes` (skip the >300-call confirmation).

## Repo layout
```
config/models.yaml        model/provider config (params, Groq limits)
data/grid.csv             8 fictional funds; F1 is dominant
data/sources/*.txt        injected documents (src_*) and memory statements (mem_*)
data/grid_realistic.csv   optional robustness variant (F2 net return 13.0%)
data/conditions.csv       experimental conditions (core=1 run by default; ord_* = order test)
runs/raw/*.jsonl          append-only log, one JSON per LLM call (never edited)
runs/clean.csv            parsed runs (generated by build_clean.py)
results/                  tables (CSV) and figures (PNG)
src/                      experiment, cleaning, analysis scripts
tests/                    pytest unit tests
```

## Reproducibility
- Every call is logged with model tag + digest, seed, grid row order, and source order.
- Raw logs are committed (small); `runs/clean.csv` and `results/` can be regenerated from them.

## Pilot (baseline only, before design freeze)
| Model | n | F1 rate (95% Wilson CI) | F2 rate | Low-fee rate | Unparseable |
|---|---|---|---|---|---|
| llama3.1:8b | 50 | 88% (76-94%) | 2% | 98% | 0% |
| qwen2.5:7b | 20 | 75% (53-89%) | 10% | 85% | 0% |

Both baselines fall in the pre-set 40-95% window, so the grid, sources, conditions and prompt
template (`src/common.py`) were **not** adjusted. Design frozen at tag `v0.2-frozen-design`.
Pilot logs (`runs/raw/pilot_*.jsonl`) are kept separate and are not part of the main analysis.

## Results
_TBD._

## Limitations
- Small open-weight models (run locally) and free-tier hosted models only; results describe those
  models and may differ for frontier models.
- Fictional funds and documents; single product category (funds).
- Sandbox measurement of model behavior, not financial advice.
