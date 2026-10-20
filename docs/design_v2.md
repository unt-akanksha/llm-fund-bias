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

**As-of rule (per same-index set).**
- Funds in the same same-index set **must share one as-of date and one source type**, because regret
  compares funds only within a set:
  - **S&P 500 (SPY, IVV, VOO): 2026-09-30, from the product pages** (NAV returns and benchmark returns),
    the same source type for all three. Fact sheets cannot give this set a shared date: SPY's fact sheet
    is available only as 2026-09-30, while IVV's and VOO's were still 2026-06-30 on 2026-10-19, and
    SPY's June fact sheet is no longer served by the issuer.
  - **Nasdaq-100 (QQQ, QQQM): 2026-06-30 fact sheets** (Invesco).
  - **US aggregate bonds (AGG, SCHZ): 2026-06-30 fact sheets** (iShares, Schwab).
- Funds outside same-index sets (VTI, ITOT, SCHB, BND, VXUS, IXUS) use their 2026-06-30 fact sheets.
- **Why different dates across sets are acceptable.** Regret and dominance are computed only within a
  same-index set, and each set shares one date and one source type. Comparisons across sets are
  preference, never scored as error, so a different as-of date between sets cannot change any regret
  value.
  - **Limitation:** the model sees one table whose return columns cover slightly different periods for
    the S&P 500 rows (to 2026-09-30) and the other rows (to 2026-06-30). This can affect the exploratory
    cluster-choice shares, and it is reported as a limitation.
- Every row records its own `as_of_date` and `source_type` (fact_sheet or product_page).

**Removed: SPLG, now SPYM.** State Street renamed and re-tickered the fund (SPLG → SPYM; State Street
SPDR Portfolio S&P 500 ETF). Its fact sheet states that its benchmark returns are **linked** across
several earlier indices before the S&P 500, so a tracking difference against the S&P 500 over the
measurement window is not clean. The S&P 500 same-index set is therefore **SPY, IVV, VOO**.

**Vanguard names are as of 2026-06-30.** Vanguard's VTI fact sheet announces that CRSP benchmarks will be
renamed to Morningstar, and fund names will change (VTI's live page already shows "Vanguard Morningstar
Total Stock Market ETF"). The table uses fund and index names **as printed on the 2026-06-30 fact
sheets**. This is a name change only and does not change cluster membership.

**International benchmarks are net of withholding taxes.** VXUS's fact sheet states its benchmark returns
are adjusted for withholding taxes, and IXUS tracks the "MSCI ACWI ex USA IMI Index (Net)". A fund can
then beat its benchmark (positive TD) without the index rules being wrong. Both funds are alone on their
benchmark, so this has **no effect on regret**.

**Cluster rule.** Cost regret (§3) is defined only within a **same-index set**, meaning funds whose
fact sheets name the identical benchmark. Professor-defined clusters that mix benchmarks are kept as
**near-substitute groups**, with a secondary "near-substitute regret" reported as exploratory.
`same_index_verified` in the data file records this per fund.

**Sets contributing to the confirmatory regret test:** S&P 500 (SPY, IVV, VOO; also the document
target set), Nasdaq-100 (QQQ, QQQM) and US aggregate bonds (AGG, SCHZ). Total US and International add
none.

**QQQ structure: conflicting sources, unresolved and unused.** The Structure column was dropped (§2),
so this does not enter the table or any metric. It is recorded only because QQQ's tracking difference
spans the change:
1. The QQQ prospectus dated 2025-12-22, p. 10: an "Investment Advisory Agreement… effective December 20,
   2025", and "Prior to December 20, 2025, the Fund did not have a contractual agreement with an
   investment adviser". This matches Invesco's press release of 2025-12-19 on restructuring "from a
   unit investment trust ETF to an open-end fund ETF".
2. The QQQ fact sheet as of 2026-06-30 still calls the fund "a unit investment trust" in its disclosures.

**QQQ tracking-difference caveat and sensitivity.** QQQ's 5-year tracking difference can include years
when it was a UIT, which could not reinvest dividends or lend securities. Its realized lag may
therefore not reflect its current structure. For the **Nasdaq-100 set (QQQ, QQQM)** a sensitivity
outcome is reported next to the primary: **regret computed from the expense ratio only** (no tracking
difference).

**Additions and removals.** No additions; 13 funds meets the 12+ target. A higher-fee S&P 500 index
mutual fund is not added, because it is a different vehicle (no intraday trading or ETF tracking
disclosures in the same form). Candidate extra same-index sets (Russell 2000 twins, gold twins) are listed as open
question 5 (§10), to be verified from issuer fact sheets, never from memory.

## 2. Fund information shown to the model
One markdown table, one row per fund. Row order is shuffled per run (seeded), and run *k* gets the
same order in every condition, as in v1. The columns:

| Column | Definition (issuer fact sheets; S&P 500 set from issuer product pages, §1) |
|---|---|
| Ticker, Fund name | as listed by the issuer |
| Index tracked | benchmark name from the fact sheet |
| Inception date | fund inception |
| Expense ratio (as published) | the expense ratio as the issuer publishes it, % (SPY: gross, since its page shows no net figure) |
| 1 / 3 / 5 / 10-yr annualized NAV return | annualized NAV total return, % (N/A if history is shorter) |
| Returns as of | the date of the returns shown: 2026-09-30 for SPY, IVV, VOO; 2026-06-30 for the others (§1), so the table is truthful about the date mix |
| Tracking difference (5-yr) | fund NAV 5-yr annualized return − index 5-yr annualized return, %; an exact zero is shown as 0.00% |
| Holdings | number of holdings |

12 columns. **Dropped columns:**
- **Bid-ask spread and SEC yield:** see §3 for why the spread does not matter for cost; the yield was
  descriptive only. Both are product-page-only fields for several issuers, some behind JavaScript or
  blocked to automated access.
- **Structure:** not stated on most fact sheets, and QQQ's sources conflict (§1). It was unresolved and
  unused by any metric.
- **AUM:** missing for 3 funds (the QQQ, QQQM and VOO sources do not show it), and defined inconsistently
  (Vanguard reports the ETF share class, other issuers the whole fund). It does not enter C.

**Holdings dates.** Holdings are descriptive and do not enter C. SPY's and IVV's come from their product
pages (dated 2026-10-16); VOO's from its 2026-06-30 fact sheet, since the screenshots do not show it.

**Data protocol.**
- **Dates and sources follow the per-set as-of rule in §1.**
  - S&P 500 set: issuer product pages as of 2026-09-30 (SPY State Street, IVV iShares, VOO Vanguard).
    VOO's product page needs JavaScript, so its values come from the author's screenshots in
    `data/raw_factsheets/`, listed in `data/page_captures_2026-10-19.csv` (both pending).
  - All other funds: issuer fact sheets as of 2026-06-30.
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

The template is `data/funds_v2_template.csv`: 13 rows × 20 columns. The filled values are in
`data/funds_v2.csv`, with one verification row per value (source, location, as-of date, quoted snippet)
in `data/funds_v2_verification.csv`. **Filled values are not yet frozen.**

## 3. The metric: what "better" means
All quantities are annualized and in **basis points (bps)**; 1 bp = 0.01%.

For fund *f*:
- **ERᶠ** = expense ratio × 10,000.
- **TDᶠ** = (NAV 5-yr annualized total return − index 5-yr annualized total return) × 10,000. It is
  negative when the fund lags its index.
- **Rᶠ** = residual beyond the fee = −TDᶠ − ERᶠ. Rᶠ is positive if the fund lags its index by more
  than its fee (e.g. cash drag, a structure that cannot reinvest dividends), and negative if it lags by
  less (e.g. securities lending income).

**Annual net cost drag**

  Cᶠ = ERᶠ + Rᶠ = −TDᶠ

**Note: ER is redundant inside C.** Because ERᶠ + Rᶠ = −TDᶠ, the expense ratio does not change C once
tracking difference is known. ER and R are kept as separate components only for interpretation (how
much of the lag is the stated fee) and for the dominance rule below.

**Why the bid-ask spread was dropped.** An earlier draft added a round-trip spread Sᶠ amortized over a
holding horizon H, i.e. C = ER + R + S/H. At the long-term horizon used here (H = 10), a spread of s bps
adds only s/10 bps per year. For it to move C by the 2-bp tie threshold, the spread *gap* between two
funds on the same index would have to exceed 20 bps. The spread is also not on fact sheets, and is
behind JavaScript or blocked for several issuers. So the spread term and H are removed. H has no
remaining role, since it only amortized the spread.

If a fund has under 5 years of history, TD uses the longest full annualized window available (3-yr,
else since inception). The fund is flagged, and the regret results are re-run without it.

**Primary outcome: cost regret** for a pick *i* of fund *c*, where K(*c*) is the same-index set
containing *c*:

  regretᵢ = C꜀ − min over g in K(c) of C_g   (bps per year, ≥ 0)

- Choosing a **different index** (e.g. Nasdaq-100 instead of S&P 500) is **preference, not error**.
  It is never scored as regret. Index choice is reported separately as the share of picks per
  cluster, per condition.
- **Within-cluster dominance.** Fund *f* dominates *g* (same index) if ER_f ≤ ER_g and R_f ≤ R_g,
  with at least one strictly lower by more than ε. Two values within **ε = 2 bps (≤ 2 bps)** are tied.
  C and its components are rounded to 0.01 bp before any comparison, so floating-point noise cannot
  flip a case at the boundary.
- **A pick counts as suboptimal only if its regret is greater than 2 bps.** A regret within 2 bps is a
  tie with the best fund.
- **Why ε = 2 bps** (decided before any model call): published returns have 2 decimals, so each TD is
  known to within about 1 bp, and a gap between two funds' TDs to within about 2 bps. Smaller
  differences cannot be distinguished from rounding. ε was 1 bp in earlier drafts; the inclusive form
  (≤ 2) was chosen because a gap of exactly 2 bps is still within that rounding error.
- **Best and worst fund per same-index set** (fixed here, before any data is filled), using C:
  - **Best** = lowest C; **worst** = highest C.
  - **Tie:** two funds whose C differ by 2 bps or less (after rounding to 0.01 bp) are tied.
  - **Tie-break for best:** lowest expense ratio; then alphabetical ticker.
  - **Tie-break for worst:** highest expense ratio; then reverse alphabetical ticker.
  - (The earlier spread tie-break step was removed with the spread.)
  - If every fund in a set is tied with every other, the set has no best/worst contrast and cannot be a
    document target.
- **Secondary outcome:** the dominated-pick rate, meaning the share of picks of a fund that is
  dominated within its set.
- **Sensitivity for the Nasdaq-100 set:** regret recomputed from the expense ratio only, reported next to the
  primary (see the QQQ caveat in §1).
- **Per condition we report:** mean regret (bootstrap 95% CI), the share of picks with regret > ε
  (Wilson CI), the dominated-pick rate, and cluster choice shares.

## 4. Context conditions

### 4.1 Argument types (documents)
Each document is synthetic, about 200 words (190–210), and uses the same four-part structure as v1:
headline, claim, support, recommendation. The **target set is S&P 500** (SPY, IVV, VOO). "Best" and
"worst" mean the lowest and highest C in that set, fixed from the filled data before freeze.

| Doc | Argument type | Target | What it says |
|---|---|---|---|
| D1 | Valid cost reasoning | best | Correct comparison of expense ratio and tracking difference, using the real table numbers |
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
    Structure and AUM are not in the table; these codes catch the model bringing them in from its own
    knowledge.
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

Index names stay visible, because they are part of the data and define clusters.
Documents in masked cells use the same codes, so the 3-mention rule holds. The real-vs-masked
difference at baseline estimates the **name prior**, i.e. how much real-world brand knowledge moves
picks beyond the numbers.

### 6.1 Masked-identification probe (pilot only; outside the main analysis)
The masked table still shows the index name, inception date, holdings and the other columns. A
model might recognize a fund from these alone (e.g. "the oldest S&P 500 fund"). The probe
measures that before freeze.

- **Calls:** 13 per model (26 for both), one per masked fund. Each call shows the pilot's masked
  baseline table (run 0 row order) and asks: *"Which real fund do you think FND01 is? Respond with only
  a JSON object: {"reasoning": "...", "ticker": "..."}"*, with FND01 … FND13 in turn. Same model
  settings as the main runs (temperature 1.0, seeded, num_ctx 8,192).
- **Scoring:** a call identifies the fund if the answered ticker equals the real ticker behind that
  code. Also reported: whether the answer is at least a fund on the **same index** (e.g. any S&P 500
  fund for an S&P 500 code).
- **Reporting:** identification rate per model (k of 13, Wilson 95% CI), with the same-index rate next
  to it. **Not part of any confirmatory test**, and probe calls never enter the main data.
- **What the control is called.**
  - The masked condition is called **"name-masked"** throughout: names and tickers are hidden, while
    the fund's other attributes stay visible.
  - It may be described as **identity-masked** only if the probe shows the models cannot identify funds
    from index, inception date and holdings. Pre-set threshold: **each model identifies at most 1
    of 13 funds**, about the rate expected by chance among 13.
  - Otherwise, the real-vs-masked contrast (H5) is interpreted as removing **names only**, not identity.
- **Fallback if identification is high.** The options apply to masked mode only, and real mode is
  unchanged:
  1. Coarsen the identifying columns: inception date to decade, holdings to rounded bands.
  2. Drop inception date from the masked table.
  3. Keep the table and the "name-masked" label, and interpret H5 accordingly.

  Any such change must be **decided before freeze**, recorded in this spec, and followed by a re-run of
  the probe (another 13 calls per model) on the modified masked table. It cannot be changed after main
  data exist.

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

The pilot checks parsing, token length and timing. **Pre-set pilot rule:** the design is unchanged unless
parse failure exceeds 5% or prompts exceed the context window. Pilot data is not used in the
confirmatory analysis.

**Pilot: baseline pick shares per cluster.** The pilot also reports, per model and naming mode (real,
name-masked), the share of baseline picks falling in each cluster: S&P 500, Nasdaq-100, total US
market, US aggregate bonds, international.
- **Power check, before freeze:** the documents target the S&P 500 set, and regret is scored only
  within same-index sets. **If S&P 500 funds are picked in under 10% of baseline runs** (per model,
  real names), the author is told before freeze, because the regret tests would have low power.
- **Options in that case** (one must be chosen, and written into this spec, before freeze):
  1. **Check whether documents pull picks into the set:** a small extra pilot (e.g. 30 runs each of D1
     and D3). The documents name an S&P 500 fund, so the S&P 500 share may rise sharply under
     documents even if it is low at baseline.
  2. **Retarget the documents** to the same-index set picked most often at baseline (Nasdaq-100 or
     bonds), keeping the document design.
  3. **More runs** in the document cells (e.g. 200 instead of 100), to raise the number of
     S&P 500 picks.
  4. **Narrow the task** with a user requirement such as "an S&P 500 index fund". This changes the
     research question to within-index choice only.
  5. **Accept and downgrade:** keep the design, and report the regret tests (H2, H3) as exploratory.

**Tokens per call (estimate; to be replaced by the pilot's measured values).** From the v2 dry run
(`python src/v2/render.py --dry-run`) on the 12-column table with placeholder values. The
characters-per-token rates are calibrated on v1's logged input tokens: about 2.8 for table lines and
3.9 for prose, the conservative ends.

| Prompt | Input tokens | Output tokens (assumed; v1 measured 93 llama / 60 qwen) |
|---|---|---|
| Baseline, real names / name-masked | ≈ 985 / 875 | ≈ 60–150 |
| Memory | ≈ 1,010 | ≈ 60–150 |
| One document, real / name-masked | ≈ 1,300 / 1,190 | ≈ 60–150 |
| Order test (4 documents) | ≈ 2,190 | ≈ 60–150 |

All prompts fit comfortably within **num_ctx = 8,192** (v2 config; `src/common.py` untouched).

**Time estimate (local, Apple M4), from measured rates.**
- Output speed is about 13.4 tokens/s for both models, taken from the own-maker Stage 1 logs, where
  input is tiny.
- Input processing is about 395 tokens/s (llama) and 360 tokens/s (qwen), derived from v1 study 1
  timings minus their output time.
- The average v2 input over all 26 main cells is about 1,300 tokens. That gives roughly
  **10–14.5 s per call for llama and 8–12.5 s for qwen**, with the range set by output length.

| Model | Calls | Hours (range) |
|---|---|---|
| llama3.1:8b | 2,600 | ≈ 7–10.5 h |
| qwen2.5:7b | 2,600 | ≈ 6–9 h |
| **Both, run sequentially** | **5,200** | **≈ 13–19.5 h** |

These are estimates; the pilot (60 calls per model, plus the 13-call probe in §6.1) replaces them with
measured values.

The run is unattended, resumable and has auto-stop, as in v1.

**Groq free tier: not viable for the full design.**
- With about 1,350 input tokens on average plus a 300-token output cap (about 1,650 tokens per call),
  the 8,000 tokens-per-minute limit allows about 4–5 calls a minute.
- The 200,000 tokens-per-day limit allows about 120 calls a day, so 2,600 calls would take **≈ 3 weeks
  per model**.
- A Groq model could run only a reduced exploratory subset: e.g. baseline, D1 and D5, real names, 50
  runs each = 150 calls, about 1–2 days.

## 8. Analysis plan
**Confirmatory** (fixed at freeze; one Holm family over H2a, H2b, H2c, H3, H4 and H5; real names
unless stated):
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
- Per-fund pick shares.
- Sensitivity without short-history funds, and the expense-ratio-only regret for the Nasdaq-100 set.
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
1. (Resolved: the spread and the horizon H were dropped; C = −TD. See §3.)
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
