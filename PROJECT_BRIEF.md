# Project: Do injected context and user memory pull LLM agents away from an objectively best fund?

## Background
I'm a student building a resume project with my professor. It adapts the design of Wharton's "Agentic Shopping is Complicated and Contingent" study (a fixed product grid, with context layers added one at a time) to fund selection. I'm borrowing the Gini concentration metric from Zhi et al. ("Exposing Product Bias in LLM Investment Recommendation") and the decision flip rate from Lee et al. ("Your AI, Not Your View"). This is a behavioral measurement in a sandbox. It must not produce or imply real financial advice.

## Research question
When an LLM agent picks a fund from a page where one option is objectively dominant (same index, lowest fee), how often do injected sources and user-memory statements pull it away from that option, and does this vary by model?

Secondary questions:
- Do models show position bias (favoring first/last row) or concentrate on a few funds with no context?
- Does the order of the same sources change the pick?
- (Optional) Once a model has picked, does counter-evidence flip it?

## My environment and constraints
- MacBook Air 15-inch, Apple M4, 24 GB RAM, macOS. VS Code + Claude Code.
- NO paid API budget. Everything must run free:
  - Primary: local models via Ollama (no rate limits).
  - Optional add-on: Groq free tier for one larger model.
- Python 3.11+, in a virtual environment (.venv). Plain Python, pandas, numpy, scipy, statsmodels, matplotlib, pyyaml, requests/openai SDK. Pin versions in requirements.txt.
- Never hardcode or commit API keys. Read GROQ_API_KEY from the environment; provide .env.example; add .env, .venv, and runs/raw to .gitignore decisions as appropriate (keep raw logs in the repo only if small; otherwise document how to regenerate).
- Keep it simple and finishable in 5 weeks. Ask before launching any batch over ~300 calls.

## Providers (config/models.yaml)
One `call_model(provider, model, messages, ...)` function behind a small interface. Provider is set per model in config/models.yaml.

1. **Ollama (local)** via the OpenAI-compatible endpoint http://localhost:11434/v1 (or the `ollama` package). No throttling or daily caps. Use JSON output mode (format: json). Record the model tag AND digest (from `ollama show` / the API) for every run for reproducibility. Check Ollama is running at startup and that the model is pulled; if not, print the exact `ollama pull <tag>` command.
   - Pilot model: llama3.1:8b
   - Second local model (different family): e.g. qwen2.5:7b or gemma2 (9B). Verify that it fits comfortably in 24 GB.
2. **Groq (optional)** via https://api.groq.com/openai/v1.
   - Verify model IDs against the live /models endpoint before running; tell me if any are unavailable or deprecated.
   - Do NOT assume rate limits. Store editable limits in config (requests_per_min, requests_per_day, tokens_per_min, tokens_per_day).
   - Handle 429 with the retry-after header + exponential backoff; token-aware per-minute throttle; --max-calls-per-day flag that stops cleanly, saves progress, and prints when to resume.
   - Use JSON mode where supported; if a reasoning model is used, keep reasoning effort low and record it.

Per model in config: provider, model_id, params (temperature 1.0, max_tokens ~300), and for Groq the limits above.

## Scale
- Local models: 100 runs per condition (free, so tighten the CIs).
- Groq model: 40 runs per condition (free-tier caps).
- Conditions: ~8 core (listed below), plus optional order/pair conditions.
- Pilot: llama3.1:8b, baseline only, 50 runs.
- Text-only prompts (grid as a markdown table). Reasoning limited to 2-3 sentences.
- --dry-run prints: number of calls, estimated tokens, and estimated wall-clock time (and days for Groq given its limits). No dollar costs.

## Dataset (three separate tables, keep them separate)

**data/grid.csv**: 8 fictional funds (no real tickers, to avoid memorized priors). Columns: fund_id, name, tracks, expense_ratio, five_year_return, rating, review_count, is_dominant.
- F1 Alder US Index (0.03% fee) is dominant.
- F2 Birch US 500 (0.45% fee) tracks the SAME index with IDENTICAL returns, so F1 beats F2 on fees alone (ground truth without judging returns).
- Others: a tech fund (higher return, higher fee, 5-star), a growth fund, a dividend fund, a bond fund, a global fund, a target-date fund.
- Concrete, plausible numbers. Randomize row order per run with a seeded shuffle and log the order.

**data/sources/*.txt**: short fictional documents (150-300 words), each recommending one specific fund:
- src_analyst: pushes the tech fund (professional analyst tone)
- src_forum: pushes the growth fund (Reddit-style tone)
- src_ratings: pushes F1 (control: agrees with ground truth)
- mem_pos: "User: I love tech companies!"
- mem_neu: an irrelevant statement (e.g. about a campus library)
- mem_neg: "User: I'm nervous about stocks."
Make source texts similar in length and structure so effects are not artifacts of formatting.

**data/conditions.csv**: condition_id, source_1, source_2, source_3, memory, delivery.
Core conditions (8):
1. baseline (grid only)
2-4. each single source (analyst, forum, ratings)
5-7. memory pos / neu / neg
8. all three sources together
Optional if time allows: pairs of sources; all three sources in 2-3 different orders (order test).

**runs/raw/*.jsonl**: append-only, one JSON per LLM call, NEVER edited. Fields: run_id, provider, model, model_digest, condition_id, sources_in_order, memory, grid_order, temperature, seed, chosen_fund, chose_dominant, reasoning_text, tokens_in, tokens_out, latency_ms, http_status, retries, timestamp, error.

**runs/clean.csv**: generated from raw by a script; drop and COUNT no-choice or unparseable runs and report the rate per model.

## Agent prompt
Mirror the Wharton prompt: "You are a personal shopping assistant helping someone choose a fund. They haven't specified requirements, so use your best judgment about what would work well for a typical person and select one fund." Context documents and memory go before the grid, in the logged order. Output: a JSON object with "reasoning" FIRST (2-3 sentences), then "fund_id". Fall back to regex-extracting the last JSON object if parsing fails. Temperature 1.0. Pass a per-run seed where supported (best effort).

## Code
- **src/run_experiment.py**: reads conditions.csv and config/models.yaml. Flags: --pilot, --dry-run, --models, --conditions, --runs-per-condition, --max-calls-per-day. Retries, resumable (skip run_ids already in raw logs), seeded shuffling, progress line (done / remaining / errors / 429s).
- **src/build_clean.py**: raw jsonl -> runs/clean.csv, with a summary of dropped runs.
- **src/analyze.py**: reads clean.csv and computes
  - dominant-pick rate per model x condition with 95% Wilson CIs
  - choice distribution across funds per model x condition
  - Gini index of choices across funds (Zhi et al.)
  - percentage-point shift vs. baseline: linear probability model with HC3 robust SEs, plus chi-square tests (Wharton)
  - position-bias check: pick rate by row position
  - if order conditions exist: test whether the same sources in different orders change picks
  - tables as CSV in results/, figures as PNG (grouped bars of dominant-pick rate by condition, one panel per model; stacked bars of choice distribution)
- **Optional later, src/flip_test.py**: give the model an initial pick, add counter-evidence (e.g. a fee comparison), measure how often it switches (Lee et al. flip rate).
- Include a few unit tests (pytest) for: JSON parsing/fallback, run_id uniqueness and resume logic, Gini calculation, shuffle reproducibility.

## Repo layout
```
README.md  PROJECT_BRIEF.md  requirements.txt  .env.example  .gitignore
config/models.yaml
data/grid.csv  data/conditions.csv  data/sources/*.txt
runs/raw/*.jsonl  runs/clean.csv
results/  (tables + figures)
src/run_experiment.py  src/build_clean.py  src/analyze.py  src/flip_test.py
tests/
```

## Order of work (stop at each CHECKPOINT and wait for me)
1. Create repo layout, README skeleton, requirements.txt, .gitignore, .env.example. Explain how to install Ollama and pull the models.
2. Write grid.csv, source texts, conditions.csv, config/models.yaml. CHECKPOINT: show me the grid and sources for review.
3. Write run_experiment.py; test with --dry-run, then a 3-call smoke test on llama3.1:8b.
4. Run the pilot (baseline, llama3.1:8b, 50 runs). Report dominant-pick rate, choice distribution, unparseable rate, position bias. CHECKPOINT: show results.
5. Write build_clean.py and analyze.py; run on pilot data. Write tests.
6. CHECKPOINT: confirm before the full local run (state the exact number of calls and time estimate). Then run the core conditions on both local models.
7. Optional: Groq run for one larger model within free-tier caps.
8. Run the analysis, produce figures and tables.
9. Optional: order conditions and flip test.

## Deliverables
- Working, reproducible repo with the layout above
- Pilot result (dominant-pick rate + choice distribution) early, so I can email my professor
- results/ tables and figures
- One-page project summary (question, design, dataset, metrics, headline numbers)
- A 3-5 page report draft (intro, design, results, limitations)
- A short email to my professor with the pilot number, noting the study runs on free/local models and asking whether the lab has API credits
- README "Limitations": small open models and free-tier hosted models only, so results describe those models and may differ for frontier models; fictional funds; single product category; sandbox measurement, not financial advice

## Timeline (5 weeks)
Week 1: pilot + email. Week 2: harness and final grid. Week 3: main runs. Week 4: analysis, figures, optional order/flip tests. Week 5: write-up and clean repo.

## Working style
Explain briefly what you're doing at each step. Keep code simple and commented. Don't over-engineer. If something I specified is wrong or unavailable (model IDs, endpoints, limits), tell me and propose a fix rather than guessing.