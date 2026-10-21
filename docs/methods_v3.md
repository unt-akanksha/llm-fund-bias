# Methods (Study 1 v3), draft for the paper

**Task and ground truth.** Each call asks a language model to choose one exchange-traded fund for a typical
long-term investor from a table of real funds that all track the same index: the S&P 500 (SPY, IVV, VOO) or the
Nasdaq-100 (QQQ, QQQM), each family tested separately. Because funds on the same index hold the same securities,
they earn the same return before costs; we therefore score each pick by its cost regret, the fund's annual shortfall
against its index minus that of the cheapest fund in the set (basis points per year, from issuer fact sheets; ties
within 2 bp). SPY (12 bp) and QQQ (7 bp; 3 bp on expense ratio alone) are the costlier funds; IVV and QQQM are
the cheapest, and VOO is tied with IVV. The table shows twelve columns from the fact sheets (expense ratio, 1-,
3-, 5- and 10-year NAV returns, 5-year tracking difference, inception date, holdings and others), with rows
shuffled on every call.

**Conditions.** A call contains no document, a document with a valid cost argument favoring the cheapest fund
(D1), or one of three persuasive documents favoring the costlier fund: brand popularity (D3), a fabricated expert
survey labeled as synthetic (D5), or past performance (D7). Documents are about 200 words, name the target fund
exactly three times, and differ between families only in the fund facts they quote. Each condition is crossed with
two prompt templates (the original wording and a paraphrase with identical information) and two system prompts
(standard, or standard plus a one-sentence fiduciary duty), giving 40 cells.

**Models and settings.** Three OpenAI models (gpt-5.4-nano, gpt-5.4-mini, gpt-5.4; dated snapshots), three
Anthropic models (Claude Haiku 5.5, Sonnet 5.5, Opus 5.5) and two open-weight models run locally (Qwen 2.5 7B and
14B via Ollama). All run at temperature 1.0 and at the lowest reasoning setting each API offers (OpenAI reasoning
effort "none"; Anthropic effort "low", with thinking disabled where the API allows). Models answer in JSON (a short
reasoning, then a ticker). API models were run 30 times per cell and local models 50 times, with seeded row orders
and, where supported, seeded sampling.

**Quality control.** Before analysis, every cell must have all planned calls completed and at most 2% of answers
cut off at the output limit. A rule-based check compares the fund named in each answer's reasoning with the ticker
returned; flagged answers were read by the author and cleared only when the reasoning recommended the chosen fund,
with every review recorded. Picks of a fund not in the table are reported separately and excluded from shares.

**Analysis.** For each model and family, we report the share of picks going to the costlier fund and mean cost
regret, with Wilson and bootstrap 95% confidence intervals. Pre-specified contrasts, pooled over templates and
system prompts, test whether each persuasive document raises the costlier-fund share relative to no document,
whether the valid cost document lowers it, and whether the fiduciary prompt lowers it under persuasive documents
(risk differences with Newcombe 95% intervals, one-sided Fisher exact tests, Holm correction within each model
and family). Template robustness is assessed by comparing effects across the two templates, and scaling by
comparing effects across model sizes within each vendor, including a comparison restricted to the first 30 runs
of every model.

**Pre-registration and deviations.** The design, documents, prompts and analysis plan were frozen in a version-
controlled tag before any main run. Deviations are documented as amendments: API models were reduced from 50 to
30 runs per cell for budget reasons before any analysis (v3-1). [Add: gate-rule amendment v3-2, and Claude
Sonnet/Opus completion status, once decided.]
