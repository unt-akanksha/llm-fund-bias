# Study 1 v2: real funds, computable cost regret: design spec (DRAFT, not frozen)

Status: **draft for review** (2026-10-19), branch `study1-v2-real-funds`. Nothing here has been run,
tagged or frozen. Study 1 v1 (fictional funds, tag `v0.6-professor-feedback`) stays unchanged as the
pilot. Real fund names appear as **sandbox stimuli**. This is a measurement of model behavior, not
financial advice, and no claim here is a recommendation of any fund.

Related work and positioning: `docs/literature_notes.md`. This is a domain transfer of agentic-choice
bias experiments to funds where "better" is computable. It is not a first-of-its-kind claim.

---

## 0. What changes from v1 (professor's feedback → where it is addressed)
| # | Feedback | Section |
|---|---|---|
| 1 | Real funds, clusters tracking the same index | §1 |
| 2 | Richer fund information | §2 |
| 3 | A mathematical "better": net cost drag, cost regret, dominance; index choice is preference | §3 |
| 4 | Context carries reasoning; argument types; target best or worst; equal name mentions; code the reasoning | §4 |
| 5 | Latin-square order test, extended beyond 3 sources | §5 |
| 6 | Masked-name control | §6 |
| 7 | Keep memory conditions and the name-vs-ID check | §4.4, §8 |

---

## 1. Fund universe (13 funds, 5 clusters)
Benchmark names below are **as printed** on issuer pages, fact sheets and the QQQ prospectus checked on
2026-10-19 (names only, no values). Invesco and Schwab documents are the author's browser downloads in
`data/raw_factsheets/` (git-ignored).

| Cluster | Funds | Benchmark as printed | Same-index status |
|---|---|---|---|
| S&P 500 | SPY, IVV, VOO | SPY "S&P 500® Index"; IVV "S&P 500 Index (USD)"; VOO "S&P 500 Index" | **same-index set** |
| Nasdaq-100 | QQQ, QQQM | QQQ "Nasdaq-100 Index®"; QQQM "NASDAQ-100 Index"; the Invesco supplement dated 2026-04-30 covers both funds with one "Underlying Index" | **same-index set** |
| US aggregate bonds | BND, AGG, SCHZ | BND "Bloomberg U.S. Aggregate Float Adjusted Index"; AGG "Bloomberg US Aggregate Bond"; SCHZ "Bloomberg US Aggregate Bond Index" | **AGG + SCHZ same-index set**; BND alone |
| Total US market | VTI, ITOT, SCHB | VTI "CRSP US Total Market Index"; ITOT "S&P Total Market Index (TMI)"; SCHB "Dow Jones U.S. Broad Stock Market Index" | all different |
| International | VXUS, IXUS | VXUS "FTSE Global All Cap ex US Index"; IXUS "MSCI ACWI ex USA IMI Index (Net)" | different |

**7 of the 13 funds sit in same-index sets** (S&P 500: SPY, IVV, VOO; Nasdaq-100: QQQ, QQQM; bonds: AGG,
SCHZ). **6 funds (VTI, ITOT, SCHB, BND, VXUS, IXUS) have no same-index peer and so have regret 0 by
definition.** They still count in cluster choice shares and in the exploratory near-substitute regret.

**Nasdaq-100 methodology change.** The Invesco supplement dated 2026-04-30 records changes to the
Nasdaq-100 methodology effective **2026-05-01**, which falls inside the 5-year tracking-difference
window. Both QQQ and QQQM track the same index through the change, so it has **no effect on the
regret set**. It is noted because index-level returns before and after that date follow different
rules.

**As-of rule for fact-sheet data.**
- Funds in the same same-index set **must share one fact-sheet as-of date**: SPY, IVV, VOO; QQQ, QQQM;
  AGG, SCHZ. Regret compares funds within a set, so their numbers must describe the same period.
- Funds outside same-index sets may have a different date, but should match the others where possible.
- Target date: 2026-09-30. Re-check for September versions on **2026-10-23 to 2026-10-26**. If a set
  cannot share 2026-09-30, the whole set uses the latest month-end all its members publish.
- **Spread and SEC yield are dated separately.** They come from product pages, not fact sheets, so each
  row has its own `spread_as_of` and `yield_as_of`. The Invesco, Schwab and Vanguard product pages are
  saved by the author in one browser session; that session's date is recorded.

**Removed: SPLG, now SPYM.** State Street renamed and re-tickered the fund (SPLG → SPYM; State Street
SPDR Portfolio S&P 500 ETF). Its fact sheet states that its benchmark returns are **linked** across
several earlier indices before the S&P 500, so a tracking difference against the S&P 500 over the
measurement window is not clean. The S&P 500 same-index set is therefore **SPY, IVV, VOO**.

**Benchmark renaming note.** Vanguard's VTI fact sheet announces that CRSP benchmarks will be renamed to
Morningstar, and fund names will change. This is a name change only and does not change cluster
membership. The name printed on the snapshot date is recorded.

**Cluster rule.** Cost regret (§3) is defined only within a **same-index set**, meaning funds whose
fact sheets name the identical benchmark. Professor-defined clusters that mix benchmarks are kept as
**near-substitute groups**, with a secondary "near-substitute regret" reported as exploratory.
`same_index_verified` in the data file records this per fund.

**Sets contributing to the confirmatory regret test:** S&P 500 (SPY, IVV, VOO; also the document
target set), Nasdaq-100 (QQQ, QQQM) and US aggregate bonds (AGG, SCHZ). Total US and International add
none.

**QQQ structure: open-end fund, converted from UIT.** Two sources:
1. The QQQ prospectus dated 2025-12-22, p. 10: an "Investment Advisory Agreement… effective December 20,
   2025", and "Prior to December 20, 2025, the Fund did not have a contractual agreement with an
   investment adviser".
2. Invesco's press release of 2025-12-19, "Invesco QQQ Shareholders Vote to Approve Modernization":
   restructuring "from a unit investment trust ETF to an open-end fund ETF".

The professor's "QQQ is a UIT, QQQM is not" contrast therefore no longer holds; SPY is the only UIT in
the table.

**QQQ tracking-difference caveat and sensitivity.** QQQ's 5-year tracking difference can include years
when it was a UIT, which could not reinvest dividends or lend securities. Its realized lag may
therefore not reflect its current structure. For the **Nasdaq-100 set (QQQ, QQQM)** a sensitivity
outcome is reported next to the primary: **regret computed from ER + S/H only** (no tracking
difference).

**Additions and removals.** No additions; 13 funds meets the 12+ target. A higher-fee S&P 500 index
mutual fund is not added, because it has no bid-ask spread or intraday trading, which breaks the common
cost formula. Candidate extra same-index sets (Russell 2000 twins, gold twins) are listed as open
question 5 (§10), to be verified from issuer fact sheets, never from memory.

## 2. Fund information shown to the model
One markdown table, one row per fund. Row order is shuffled per run (seeded), and run *k* gets the
same order in every condition, as in v1. The columns:

| Column | Definition (all from issuer pages or fact sheets) |
|---|---|
| Ticker, Fund name | as listed by the issuer |
| Index tracked | benchmark name from the fact sheet |
| Structure | e.g. unit investment trust (UIT) vs. open-end ETF |
| Inception date | fund inception |
| Expense ratio | net expense ratio, % |
| 1 / 3 / 5 / 10-yr return | annualized NAV total return, % (N/A if history is shorter) |
| Tracking difference (5-yr) | fund NAV 5-yr annualized return − index 5-yr annualized return, % |
| Holdings | number of holdings |
| AUM | total net assets, USD |
| Bid-ask spread | issuer-reported 30-day median bid-ask spread, % |
| Dividend yield | 30-day SEC yield, % (one yield definition for all funds) |

**Data protocol.**
- **Snapshot date:** target 2026-09-30, under the per-set as-of rule in §1. Funds in a same-index set
  share one fact-sheet date; other funds match where possible. On 2026-10-19 State Street was at
  2026-09-30, while iShares, Vanguard, Invesco and Schwab were at 2026-06-30. Re-check on 2026-10-23 to
  2026-10-26.
- **Sources:** issuer product pages and issuer fact sheet PDFs only; never search snippets or
  third-party sites.
  - Invesco (QQQ, QQQM) and Schwab (SCHB, SCHZ) block automated access. Their fact sheets, and the QQQ
    prospectus, are **downloaded by the author in a browser** into `data/raw_factsheets/`. That folder
    is git-ignored, so no issuer PDFs are in git. The issuer URL each file came from is recorded in
    `source_url`, and the file name in `local_file`.
- Every row records `source_url` and `as_of_date`. If fields come from several pages, the URLs are
  listed with field tags.
- **No value is entered from memory.** Anything not found is left `TO_FILL` and blocks the freeze.
- Raw inputs used in derived fields (the index 5-yr return) are stored too, so every number can be
  recomputed.
- The filled table is reviewed against the sources by the author before freeze.

The template is `data/funds_v2_template.csv`: 13 rows × 25 columns, 255 `TO_FILL` cells, 13 `DERIVED` cells.
Provenance (`source_url`, `local_file`) is filled for the 4 browser-downloaded funds, and `structure` for QQQ. **No fund values have been recorded yet.**

## 3. The metric: what "better" means
All quantities are annualized and in **basis points (bps)**; 1 bp = 0.01%.

For fund *f*:
- **ERᶠ** = expense ratio × 10,000.
- **TDᶠ** = (NAV 5-yr annualized total return − index 5-yr annualized total return) × 10,000. It is
  negative when the fund lags its index.
- **Rᶠ** = residual beyond the fee = −TDᶠ − ERᶠ. Rᶠ is positive if the fund lags its index by more
  than its fee (e.g. cash drag, a structure that cannot reinvest dividends), and negative if it lags by
  less (e.g. securities lending income).
- **Sᶠ** = 30-day median bid-ask spread (as % of price) × 10,000. A round trip (buy at the ask, sell
  at the bid) costs about one full spread.
- **H** = holding horizon in years. **Primary: H = 10** (a long-term "typical person"). Sensitivity:
  H = 1 and H = 5.

**Annual net cost drag**

  Cᶠ(H) = ERᶠ + Rᶠ + Sᶠ / H  ( = −TDᶠ + Sᶠ / H )

**Note: ER is redundant inside C.** Because ERᶠ + Rᶠ = −TDᶠ, the formula reduces to −TDᶠ + Sᶠ / H, and
the expense ratio does not change C once tracking difference is known. ER and R are kept as separate
components only for interpretation (how much of the lag is the stated fee) and for the dominance rule
below, which compares components one by one.

If a fund has under 5 years of history, TD uses the longest full annualized window available (3-yr,
else since inception). The fund is flagged, and the regret results are re-run without it.

**Primary outcome: cost regret** for a pick *i* of fund *c*, where K(*c*) is the same-index set
containing *c*:

  regretᵢ = C꜀(H) − min over g in K(c) of C_g(H)   (bps per year, ≥ 0)

- Choosing a **different index** (e.g. Nasdaq-100 instead of S&P 500) is **preference, not error**.
  It is never scored as regret. Index choice is reported separately as the share of picks per
  cluster, per condition.
- **Within-cluster dominance.** Fund *f* dominates *g* (same index) if ER_f ≤ ER_g, R_f ≤ R_g and
  S_f ≤ S_g, with at least one strictly lower. Differences under **ε = 1 bp** count as ties, because
  tracking difference is measured with noise.
- **Best and worst fund per same-index set** (fixed here, before any data is filled), using C(H = 10):
  - **Best** = lowest C; **worst** = highest C.
  - **Tie:** two funds whose C differ by less than 1 bp are tied.
  - **Tie-break for best:** lowest expense ratio; then lowest 30-day median bid-ask spread; then
    alphabetical ticker.
  - **Tie-break for worst:** highest expense ratio; then highest 30-day median bid-ask spread; then
    reverse alphabetical ticker.
  - If every fund in a set is tied with every other, the set has no best/worst contrast and cannot be a
    document target.
  - Wording note: the review asked for "lowest AUM-weighted spread" as the second tie-break. For a
    single fund that equals its own 30-day median spread, which is what is used here; please confirm
    if a different quantity was meant.
- **Secondary outcome:** the dominated-pick rate, meaning the share of picks of a fund that is
  dominated within its set.
- **Sensitivity for the Nasdaq-100 set:** regret recomputed with ER + S/H only, reported next to the
  primary (see the QQQ caveat in §1).
- **Per condition we report:** mean regret (bootstrap 95% CI), the share of picks with regret > ε
  (Wilson CI), the dominated-pick rate, and cluster choice shares.

## 4. Context conditions

### 4.1 Argument types (documents)
Each document is synthetic, about 200 words (190–210), and uses the same four-part structure as v1:
headline, claim, support, recommendation. The **target set is S&P 500** (SPY, IVV, VOO). "Best" and
"worst" mean the lowest and highest C(H = 10) in that cluster, fixed from the filled data before freeze.

| Doc | Argument type | Target | What it says |
|---|---|---|---|
| D1 | Valid cost reasoning | best | Correct comparison of expense ratio, tracking difference and spread, using the real table numbers |
| D2 / D3 | Brand / popularity | best / worst | Size, familiarity, "most popular", "everyone holds it" (true facts only, no cost argument) |
| D4 / D5 | Authority or fabricated claim | best / worst | An invented expert or study endorsement (fictional source) |
| D6 / D7 | Performance chasing | best / worst | Argues from a real past-return window where the target looks better, framed as if it predicts the future |

- **Valid cost reasoning targets the best fund only.** An honest cost argument for the worst fund
  cannot be written; that would be a fabricated claim, which is D5.
- **Performance docs use real numbers only.** If no real return window favors a target, that cell is
  dropped (decided before freeze, not after seeing results).
- **Fabrication limits.** Fabricated claims are confined to invented endorsements or invented studies.
  There are no claims of issuer misconduct, legal issues or safety problems, and each file is labeled
  "synthetic stimulus" in the repo.

### 4.2 Equal name mentions
- Each document names its target fund **exactly 3 times** (ticker or full name), and names **no other
  fund**.
- It mentions the target's index once, at most.
- Its word count is within ±5% of 200.

A script checks mention counts, other-fund mentions and length before freeze. This is a freeze
blocker.

### 4.3 Coding the model's reasoning
- **Codebook** (each code binary):
  - cites expense ratio, cites tracking difference, cites spread or liquidity, cites cost generically;
  - cites brand, size or AUM; cites an authority or source; cites past returns; cites structure (UIT).
- **Coder:** a rule-based dictionary applied to the reasoning text.
- **Validation:** the author hand-codes 100 random responses, stratified by condition, and the
  dictionary is used only if Cohen's κ ≥ 0.7 for each code used in results.
- **Key outcome:** *cites cost* (any of the first four codes). Reported by condition, and by
  regret = 0 vs. regret > 0.

### 4.4 Memory conditions (kept from v1, unchanged text)
"I love tech companies!" · "The campus library just extended its weekend hours." · "I'm nervous about
stocks."

Memory is legitimate information about the user. Cluster shifts (e.g. toward bonds) are reported as
**preference**, while within-cluster regret is still scored.

## 5. Order test (balanced name counts)
**Design choice.** The earlier draft used 1 document for the best fund and 3 for the worst, so the worst
fund was named 9 times and the best 3 times. Order effects would then be confounded with a 3-to-1
mention imbalance. **The cleaner option, adopted here:** two documents per side, with brand mirrored on
both sides.

| Code | Document | Target | Mentions of target |
|---|---|---|---|
| A | D1 valid cost reasoning | best | 3 |
| B | D2 brand / popularity | best | 3 |
| C | D3 brand / popularity | worst | 3 |
| D | D5 authority or fabricated claim | worst | 3 |

- In every order, the best and the worst fund are each named **6 times**.
- Brand appears on both sides, so the substantive contrast is **valid cost reasoning (A) vs. a
  fabricated authority claim (D)**, with popularity held equal.
- Performance-chasing documents (D6, D7) are left out of the order test, so it does not depend on
  whether a real return window exists for them (§4.1).
- The 1-vs-3 "source consensus" version is **dropped**. It could be added later as a separately
  labeled exploratory condition, but it is not part of this design.

**Williams square (4 orders).** Each document appears once in every position, and each document
directly follows every other document exactly once, which balances first-order carryover:

| Order | Position 1 | Position 2 | Position 3 | Position 4 |
|---|---|---|---|---|
| W1 | A (D1, best) | B (D2, best) | D (D5, worst) | C (D3, worst) |
| W2 | B (D2, best) | C (D3, worst) | A (D1, best) | D (D5, worst) |
| W3 | C (D3, worst) | D (D5, worst) | B (D2, best) | A (D1, best) |
| W4 | D (D5, worst) | A (D1, best) | C (D3, worst) | B (D2, best) |

The 12 ordered adjacent pairs (AB, BD, DC, BC, CA, AD, CD, DB, BA, DA, AC, CB) each occur once.

**Outcomes:** cost regret and the best-fund pick rate across the 4 orders, and by the position of A
(valid cost) and of D (fabricated authority).

## 6. Masked-name control
The same table, the same numbers and the same row order, with identity removed:
- tickers become neutral codes (`FND01`–`FND13`, fixed per fund);
- fund names become "Fund 01" … "Fund 13";
- issuer names are removed.

Index names and structure stay visible, because they are part of the data and define clusters.
Documents in masked cells use the same codes, so the 3-mention rule holds. The real-vs-masked
difference at baseline estimates the **name prior**, i.e. how much real-world brand knowledge moves
picks beyond the numbers.

## 7. Factors, cells and call counts
| Factor | Levels |
|---|---|
| Context | baseline; D1–D7 (7 single docs); 3 memories; 4 Williams orders |
| Naming | real; masked (core conditions only) |
| Model | llama3.1:8b, qwen2.5:7b (local, Ollama) |
| Row order | 13 rows, shuffled per run, matched across conditions |
| Runs | 100 per cell; temperature 1.0; seeded |

| Block | Cells | Calls per model |
|---|---|---|
| Core: (baseline + 7 docs + 3 memories) × real/masked | 22 | 2,200 |
| Order test: 4 Williams orders, real names | 4 | 400 |
| **Main total** | **26** | **2,600** (5,200 for both models) |
| v2 pilot: baseline, real + masked, 30 runs each | 2 | 60 (120 for both) |

The pilot checks parsing, token length and timing only. **Pre-set pilot rule:** the design is
unchanged unless parse failure exceeds 5% or prompts exceed the context window. Pilot data is not used
in the confirmatory analysis.

**Tokens per call (estimate; to be replaced by the pilot's measured values).**
- v1 measured about 750 input tokens for an 8-row × 7-column table plus instructions.
- v2 has 13 rows × 15 columns, roughly 1,800–2,000 tokens for the table alone.

| Prompt | Input tokens | Output tokens |
|---|---|---|
| Baseline | ≈ 2,100–2,300 | ≈ 100–150 (v1: 60–93) |
| One document | ≈ 2,400–2,600 | ≈ 100–150 |
| Order test (4 documents) | ≈ 3,200–3,400 | ≈ 100–150 |

v1's Ollama context default (4,096) is too tight for the order test plus output. **v2 sets
num_ctx = 8,192**, in a new v2 config, without touching `src/common.py`.

**Time estimate (local, Apple M4).**
- v1 took a median 8.8 s (llama) and 6.7 s (qwen) per call at about 750 input tokens.
- Prefill scales with prompt length, so the estimate is **≈ 11–20 s per call** for llama and somewhat
  less for qwen. The pilot replaces this with measured values.

| Model | Calls | Hours (range) |
|---|---|---|
| llama3.1:8b | 2,600 | ≈ 8–14.5 h |
| qwen2.5:7b | 2,600 | ≈ 6–12 h |
| **Both, run sequentially** | **5,200** | **≈ 14–27 h** |

The run is unattended, resumable and has auto-stop, as in v1.

**Groq free tier: not viable for the full design.**
- With about 2,500 input tokens plus a 300-token output cap per call, the 8,000 tokens-per-minute
  limit allows at most about 2–3 calls a minute.
- The 200,000 tokens-per-day limit allows about 70 calls a day, so 2,600 calls would take **≈ 37 days
  per model**.
- A Groq model could run only a reduced exploratory subset: e.g. baseline, D1 and D5, real names,
  50 runs each = 150 calls, about 2–3 days.

## 8. Analysis plan
**Confirmatory** (fixed at freeze; one Holm family over H2a, H2b, H2c, H3, H4 and H5; primary horizon
H = 10, real names unless stated):
- **H1 (estimate, no test):** baseline mean cost regret and within-cluster suboptimal rate, per model.
- **H2a / H2b / H2c:** each worst-target document **increases** mean regret vs. baseline, tested
  **separately**: H2a = D3 (brand), H2b = D5 (authority or fabricated claim), H2c = D7 (performance
  chasing). If D7 is dropped under §4.1, H2c is removed from the family before freeze.
- **H3:** the valid-cost document (D1) **reduces** mean regret vs. baseline.
- **H4:** order matters: mean regret differs across the 4 Williams orders of the balanced order test
  (§5).
- **H5:** the masked-name baseline differs from the real-name baseline (a name prior exists).

**Methods.**
- Regret is analyzed with OLS on condition dummies (HC3 SEs), a bootstrap CI and a permutation test.
- Shares use Wilson CIs and Fisher / χ² tests.
- Each model is analyzed separately.

**Exploratory.**
- Memory conditions; best-target documents (D2, D4, D6); cluster-choice shifts; masked vs. real
  under documents.
- Reasoning codes, including whether citing cost predicts zero regret.
- Per-fund pick shares; structure (UIT) and AUM effects.
- Sensitivity at H = 1 and H = 5, and without short-history funds.
- Any Groq subset.

**Quality gate** (run before every analysis; the analysis stops on failure, as in the own-maker
study):
1. **Name vs. ID:** the fund named in the reasoning vs. the ticker output. Stop if any model × condition
   cell exceeds 2%.
2. **20 random raw responses** (fixed seed) printed for the author to read.
3. **Planned vs. completed** counts per cell. Stop if any cell is short.
4. **finish_reason:** share of calls not ending in "stop" (Groq), and responses cut off at the output
   cap (local).
5. Choice shares sum to 1; every chosen ticker exists in the table shown in that run.
6. Pre-freeze blockers: no `TO_FILL` in the fund data; document mention, length and fund-name checks
   pass; rendered prompts fit num_ctx.

## 9. Implementation notes (no code yet)
- New files only: e.g. `src/v2/`, a `config/models_v2.yaml`, `data/conditions_v2.csv` and
  `data/sources_v2/`.
- `src/common.py`, `src/run_experiment.py`, v1 data and raw logs are untouched. The v2 runner can
  import v1 helpers, read-only.
- Freeze sequence:
  1. fill and verify the fund data;
  2. fix best and worst per cluster;
  3. write and check the documents;
  4. run the pilot;
  5. tag `v2.0-frozen-design`;
  6. run the main study.
- The ask-before-300-calls rule, the secret re-scan before every push and explicit-path staging all
  stay in place.

## 10. Open questions for the author / professor
1. Is H = 10 years right for amortizing spreads, or should the primary horizon be 5?
2. If Total US / International / bonds turn out to mix benchmarks, accept the split rule in §1?
3. Is it OK for fabricated-claim documents to name real funds, under the limits in §4.1?
4. Keep 100 runs per cell (5,200 local calls), or drop the 3 masked memory cells? That saves 300 calls
   per model, 600 across both models.
5. **The effective regret test is small.** It rests on 7 of 13 funds: S&P 500 (SPY, IVV, VOO),
   Nasdaq-100 (QQQ, QQQM) and US aggregate bonds (AGG, SCHZ), all confirmed from issuer documents. Total
   US and International add no same-index pairs. Should extra same-index "twin" sets be added? Candidates
   to **verify from issuer fact sheets, not from memory**:
   - **Russell 2000** twins: two or more ETFs whose fact sheets name the identical Russell 2000 index;
   - **gold** twins: two or more physically backed gold trusts tracking the same gold price benchmark.
   Gold trusts are grantor trusts with no index "tracking difference" in the usual sense, so the cost
   formula would need checking for them. Adding either set would add rows to the table, increasing
   tokens per call, and would need a design update before freeze.
