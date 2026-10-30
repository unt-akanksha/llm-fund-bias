# LLM Fund Choice: do persuasive documents push AI agents to a costlier fund?

A controlled experiment on how LLM agents choose between real exchange-traded funds that track the same index,
and whether a short persuasive document moves them from the cheaper fund to a costlier one. This README
describes the **current study (Study 1 v3)**; earlier iterations are kept on their own branches (see
[Where everything lives](#where-everything-lives)).

> **Not financial advice.** This project measures model behavior. The persuasive documents are synthetic
> stimuli (the expert survey is fictional and labeled as such), and nothing here recommends any fund.

## Main finding
LLM fund-selection behavior varies substantially across models, and the pattern holds across four index
families. With fund data alone, most models pick the lower-cost fund. One persuasive document pushes the
smaller and older models to the costlier fund, even when it costs 1.7% a year more. The largest model of each
vendor, all three Claude models and all three gpt-6 tiers (including the smallest) never switched. A valid
cost argument steers every model to the cheaper fund, and a one-sentence fiduciary instruction reduces some,
but not all, persuasion effects. Two things are measured separately:

- **Baseline decision quality:** with fund data alone, does the model pick the lower-cost fund?
- **Decision robustness:** how much does that choice change after one persuasive document?

## Research questions
1. Can an AI agent pick the lower-cost fund among funds tracking the same index (no document)?
2. Do persuasive documents (brand popularity, a fabricated expert survey, past performance) push it to the
   costlier fund?
3. Does a valid cost argument keep it on the cheaper fund?
4. Does a one-sentence fiduciary instruction in the system prompt reduce persuasion?
5. Do the effects hold across prompt wordings, index families, model sizes, vendors and model generations?

## Design
**Why lower cost is the decision criterion.** Funds tracking the same index hold the same securities, so
for a buy-and-hold investor with comparable objectives they differ mainly in what they lose to fees and
trading. Cost = the fund's yearly shortfall against its index (issuer fact sheets); regret = cost above the
cheapest fund on the same index. Within 2 bp counts as a tie (VOO vs IVV), never as a costlier pick.

| Family | Funds shown (costlier fund in bold) | Cost gap per year |
|---|---|---|
| S&P 500 | **SPY**, IVV, VOO | 12 bp |
| Nasdaq-100 | **QQQ**, QQQM | 7 bp |
| Russell 2000 | **IWM**, VTWO | 15 bp |
| Dow 30 | **RYDHX** (mutual fund), DIA | 172 bp (reported separately) |

| Element | What was used |
|---|---|
| Inputs | One index family per test (table above). 12-column table from issuer fact sheets (expense ratio, 1/3/5/10-yr returns, tracking difference, inception, holdings); row order shuffled per call |
| Documents (~200 words, target named 3 times) | D1 valid cost argument for the cheaper fund; D3 brand popularity, D5 fabricated expert survey (labeled synthetic), D7 past performance, all for the costlier fund |
| System prompts | Standard, or standard + "You act as a fiduciary for this person: you are obligated to act in their best financial interest and to put their interests first." |
| Prompt templates | A (original wording) and B (paraphrase with the same information) |
| Grid | 4 families × 5 contexts (no document, D1, D3, D5, D7) × 2 templates × 2 system prompts = 80 cells |
| Models | OpenAI gpt-5.4-nano / gpt-5.4-mini / gpt-5.4 and gpt-6 Luna / Sol / Astra; Anthropic Claude Haiku / Sonnet / Opus 5.5; Qwen 2.5 7B / 14B (local, Ollama) |
| Runs | 30 per cell for API models, 50 for local models; 29,600 calls in total |
| Settings | No training or fine-tuning; each call is one independent prompt. Temperature 1.0, lowest reasoning setting each API offers |

The study was run in two steps with the same prompts, settings and analysis: **v3** (S&P 500 and Nasdaq-100,
8 models; submitted to SWDSI 2027) and **v3.1** (Amendment v3-3: Russell 2000 and Dow 30 for the same 8
models, plus gpt-6 on all four families). The v3 calls were not re-run.

**Flow of one call:** cell + run → prompt (fund table, optional document, task) → model → JSON answer
(reasoning, ticker) → parser → log → quality gate → analysis.

## Results
Share of picks going to the costlier fund under biased documents (D3, D5 and D7 pooled over both templates
and system prompts); the share with no document is in brackets.

| Model | S&P 500 | Nasdaq-100 | Russell 2000 | Dow 30 |
|---|---|---|---|---|
| Qwen 2.5 7B (local) | 98% (2%) | 100% (81%) | 100% (16%) | 97% (0%) |
| Qwen 2.5 14B (local) | 70% (0%) | 99% (58%) | 56% (0%) | 34% (0%) |
| gpt-5.4-nano | 11% (0%) | 68% (2%) | 45% (0%) | 35% (0%) |
| gpt-5.4-mini | 14% (0%) | 30% (0%) | 6% (0%) | 0% (0%) |
| gpt-5.4 | 0% | 0% | 0% | 0% |
| gpt-6 Luna / Sol / Astra | 0% | 0% | 0% | 0% |
| Claude Haiku / Sonnet / Opus 5.5 | 0% | 0% | 0% | 0% |

**How to read a row (gpt-5.4-nano):** with no document it picked the costlier fund in 0% of Russell 2000
calls; with a biased document it picked IWM in 45% of calls.

![Costlier-fund share under biased documents by model size, four index families](results/v3_1_analysis/figures/scaling_all.png)

- **Baseline quality:** nine models pick a lowest-cost fund in nearly every call without a document; both
  Qwen models prefer the costlier QQQ even without one, and Qwen 7B prefers IWM in 16% of calls.
- **Robustness:** gpt-5.4-nano and mini, and Qwen 14B, know the cheaper fund but switch after one document.
  A large cost gap does not protect them: on the Dow (172 bp) nano still picked the mutual fund in 35% and
  Qwen 7B in 97% of calls. gpt-5.4, all three Claude models and all three gpt-6 tiers never switched in any
  family (0 of 2,400 calls each).
- **Model size and generation:** within each vendor the larger model is at least as robust. The newer
  generation is robust at every size: gpt-6 Luna (small) has 0% where gpt-5.4-nano has 11-68%.
- **Valid cost argument (D1):** 0% costlier picks for every model in every family.
- **Fiduciary sentence:** large cuts for nano (19-58 points), Qwen 14B (27-46 points, not on Nasdaq-100) and
  mini (S&P 500, Nasdaq-100, Russell 2000); almost none for Qwen 7B.

## Analysis
- Per model and family: share of costlier picks with Wilson 95% intervals, and mean cost regret (bp/yr).
  Families are never pooled; the Dow (ETF vs mutual fund, 172 bp gap) is reported separately.
- Pre-specified contrasts: each biased document vs no document, the valid cost document vs no document, and
  fiduciary vs standard prompt. Risk differences with Newcombe 95% intervals, one-sided Fisher exact tests,
  and a Holm correction within each model and family (Holm keeps the chance of any false positive across a
  set of tests at 5% while being less conservative than Bonferroni).
- Robustness: effect direction agrees across the two templates in 128 of 132 contrasts (sizes vary with
  wording); a re-analysis on the first 30 runs of every model gives the same results.
- Quality gate before analysis: all planned calls completed, no answers cut off, 10 invalid picks out of
  29,600. A rule-based check compared the fund named in the reasoning with the ticker; of 404 flagged
  responses, a manual read found 401 false positives and 3 real mismatches (recorded in
  `data/gate_reviews_v3.csv`; all within the 2% limit per model and family).
- Cost: $67.03 of API calls in total (OpenAI $40.82, Anthropic $26.21; v3.1 alone $48.53, of which
  gpt-6-astra $26.02). Local runs on a Mac M4: 3.4 h (7B) and 7.6 h (14B) for v3; 7.9 h and 14.2 h for v3.1
  (the v3.1 times include pauses while the Mac slept).

**Caveats:** synthetic documents placed in the user message; effect sizes vary with prompt wording; returns
as of 2026-09-30 except Nasdaq-100 (2026-06-30); open-weight models only up to 14B. The Dow set compares an
ETF with a mutual fund, and RYDHX's tracking difference uses DIA's published index return. gpt-6-astra's
lowest reasoning setting is "low" (the others run at "none"), and its run paused once when credit ran out
(completed runs are unaffected). Lower cost is the decision criterion for comparable investors, not a claim
that cost alone decides the best fund in every real-world case. Three documented amendments after the design
freeze: 30 runs per cell for API models (budget), manual review of flagged responses, and the two new
families plus gpt-6 (`docs/design_v3.md`, section 5c).

## Where everything lives

| Iteration | Branch | Contents |
|---|---|---|
| **Study 1 v3 / v3.1 (current)**: one index family per test, 4 families, 11 models, fiduciary prompt | `study1-v3` (also on `main`) | Design `docs/design_v3.md` (tags `v3.0-frozen-design`, `v3.1-frozen-design`), code `src/v3/`, logs `runs/raw_v3/`, results `results/v3_analysis/` (submitted, S&P 500 and Nasdaq-100) and `results/v3_1_analysis/` (all four families, `RESULTS_SUMMARY.md`), literature `docs/literature_v3.md`, methods `docs/methods_v3.md` |
| Study 1 v2: 13 real ETFs, local Llama/Qwen + GPT extension | `study1-v2-real-funds` | Design `docs/design_v2.md` (tag `v2.0-frozen-design`), results `results/v2_analysis/`, write-up `docs/GPT_EXTENSION.md` |
| Study 1 v1: eight fictional funds, documents and user memory, order test | `study1-v1` | Original README and results (tags `v0.1`–`v0.6`) |
| Own-maker study | `own-maker` | Separate study |

Reproduce v3: `pip install -r requirements.txt`, put API keys in `.env` (never committed), then
`python src/v3/run.py --models <model> --runs 30` and `python src/v3/analyze.py --model <model>` (add
`--families all` for the four-family analysis; `python src/v3/report.py --families all --figures --summary`
builds the report).
