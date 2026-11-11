# Replication guide: "When AI Knows Better but Chooses Worse" (Study 1 v3 / v3.1)

This maps every table, figure and in-text number in the journal draft to the data, code and command that
produce it. Everything below is in this archive (release tag `v3.1-journal` of the GitHub repository).

## 1. Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

- API keys go in `.env` (never committed); `python src/v3/run.py --keys` prints only "key found: yes/no".
- Qwen 2.5 7B and 14B run locally with Ollama (`ollama pull qwen2.5:7b`, `ollama pull qwen2.5:14b`).
- Re-running the analysis needs no keys: every model response is already logged in `runs/raw_v3/`.

## 2. Inputs

| What | Where |
|---|---|
| Design, hypotheses, analysis plan, amendments | `docs/design_v3.md` (frozen at tags `v3.0-frozen-design`, `v3.1-frozen-design`; amendments in section 5c) |
| Fund data, S&P 500 and Nasdaq-100 | `data/funds_v2.csv` (verification log `data/funds_v2_verification.csv`) |
| Fund data, Russell 2000 and Dow 30 | `data/v3/funds_v3_ext.csv` (44 scripted source checks: `data/v3/funds_v3_ext_verification.csv`) |
| Issuer source pages | URL and as-of date per fund in the `source_url` and `as_of_date` columns of the two fund files. The saved PDFs in `data/raw_factsheets/` are issuer documents and are not redistributed in git |
| Documents D1, D3, D5, D7 | S&P 500: `data/sources_v2/D1.txt`, `D3.txt`, `D5.txt`, `D7.txt`; other families: `data/v3/sources/` (D5 is shared except for the Russell 2000 version) |
| Models (vendor IDs, sizes, settings) | `config/models_v3.yaml`; the model version each API returned is logged per call |
| Prompts and conditions (80 cells) | `src/v3/prompts.py`, `data/v3/conditions_v3.csv`; printed in the paper's Appendix A and B |
| Raw responses (29,600 calls plus pilots) | `runs/raw_v3/main_<model>.jsonl`, one JSON line per call (prompt cell, seed, row order, model ID returned, raw response, parsed ticker, tokens, cost) |
| Manual reviews of flagged answers | `data/gate_reviews_v3.csv` (404 flags: 401 false positives, 3 real mismatches) |

## 3. Re-running the calls (optional, costs money)

```bash
python src/v3/run.py --models gpt-5.4-nano,gpt-5.4-mini,gpt-5.4 --runs 30            # API models, 30 runs per cell
python src/v3/run.py --models qwen2.5-7b,qwen2.5-14b --runs 50                       # local models, 50 runs per cell
python src/v3/run.py --models gpt-6-luna,gpt-6-sol,gpt-6-astra --runs 30 --families all
```

The runner is append-only and resumable; seeds and row orders are fixed, so a re-run regenerates the same
prompts. Model outputs at temperature 1.0 will differ in detail; total API cost was $67.03.

## 4. Re-running the analysis

```bash
python src/v3/report.py --families all --analyze-all --figures --summary --replace
python scripts/paper_reasoning_counts.py
```

The first command runs `src/v3/analyze.py` for every model (quality gate, cell and pooled shares, tests, and
the matched 30-run comparison), then builds the figures and `results/v3_1_analysis/RESULTS_SUMMARY.md`.
Without `--families all` it reproduces the submitted SWDSI 2027 results (S&P 500 and Nasdaq-100, 8 models)
in `results/v3_analysis/`.

## 5. Where each result comes from

| Paper item | Source file | Produced by |
|---|---|---|
| Section 3.2 family table (lowest cost, tie, costlier, regret) | `data/funds_v2.csv`, `data/v3/funds_v3_ext.csv`; regret rule in `src/v2/cost.py` | `src/v3/analyze.py` |
| Table 1 (no-document picks) | `results/v3_1_analysis/<model>/pooled.csv` (context `baseline`); RESULTS_SUMMARY section 1 | `report.py --analyze-all` |
| Table 2 (persuasive documents pooled, Wilson CI, mean regret) | RESULTS_SUMMARY sections 2 and 2c; `results/v3_1_analysis/scaling.csv` | `report.py --summary` |
| Table 3 (change by document, Newcombe CI, Holm p) | `results/v3_1_analysis/<model>/tests.csv` | `report.py --analyze-all` |
| Table 4 (fiduciary vs standard) | `tests.csv` (HF rows) and `pooled.csv` (family x context x system); RESULTS_SUMMARY section 3 | `report.py --analyze-all` |
| Table 5 (gpt-5.4 vs gpt-6) | RESULTS_SUMMARY section 2b | `report.py --summary` |
| Figure 1 | `results/v3_1_analysis/figures/scaling_all.png` (data: `figures/scaling_data.csv`) | `report.py --figures` |
| Template robustness (128 of 132 contrasts) | RESULTS_SUMMARY section 3 | `report.py --summary` |
| Matched 30-run check | `results/v3_1_analysis/matched30/<model>/` | `report.py --analyze-all` |
| Quality gate (404 flags, 10 invalid picks, no cut-offs) | `results/v3_1_analysis/<model>/gate.txt`, `data/gate_reviews_v3.csv` | `analyze.py` |
| Cost mentions in costlier picks; synthetic-label mentions in D5 answers; Qwen's QQQ track-record reasons; Qwen 7B's IWM picks (track record, misread expense ratio); the 10 invalid picks by kind | printed by the script | `scripts/paper_reasoning_counts.py` |
| API cost ($67.03) | `cost_usd` field in `runs/raw_v3/main_*.jsonl` | sum over main and pilot logs |
| Human comparison (9%, 19%, 10%) | Choi, Laibson & Madrian (2010), Figure 2 | external |

## 6. Notes

- Analyzed runs are run_index 0-29 for API models and 0-49 for the local models; any extra rows in a log are
  not analyzed.
- Families are never pooled; the Dow 30 (ETF vs mutual fund) is reported separately.
- The conference results (`results/v3_analysis/`) are kept exactly as submitted to SWDSI 2027. Three name-vs-ticker
  flags in Qwen answers (S&P 500 and Nasdaq-100) were reviewed and cleared only later, for v3.1
  (`data/gate_reviews_v3.csv`), so re-running the conference analysis now reports them as cleared in `gate.txt`
  and `summary.txt`; every share, test and figure is unchanged.
- The journal manuscript itself is kept outside git, in `paper/`: `paper/journal_draft.md` is the source text
  and `paper/out/` holds the Word versions.
