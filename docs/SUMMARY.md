# Project summary: context and memory steer LLM fund choices

**In one sentence:** When a small open-weight LLM picks a fund "for a typical person," a single injected
document or a single sentence of user memory decides the pick almost completely, overriding an objectively
dominant option.

*Sandboxed behavioral measurement with fictional funds. Not financial advice.*
Full details and reproduction steps are in the [README](../README.md).

## Question
When an LLM agent chooses from a page where one fund is objectively dominant, how often do injected sources
and user-memory statements pull it away from that fund, and does this differ by model?

## Design
- **Grid:** 8 fictional funds shown as a table, with row order shuffled per run.
  - F1 (index fund, 0.03% fee) is the normative pick.
  - F2 tracks the same index with the same return at a 0.45% fee, so F2 is strictly dominated.
- **Context:** added one layer at a time.
  - Three ~200-word documents, each recommending one fund: an analyst note (tech fund), a forum post
    (growth fund) and a ratings report (F1).
  - Three one-line memories: "I love tech companies!", a campus-library remark, and "I'm nervous about stocks."
- **Conditions:**
  - 8 core: baseline, each source, each memory, and all three sources in shuffled order.
  - 3 fixed-order conditions for a confirmatory order test.
- **Models:** `llama3.1:8b` and `qwen2.5:7b`, run locally via Ollama at temperature 1.0, with JSON output.
- **Scale:** 100 runs per model × condition, 2,200 runs in total, with 0 dropped.
- **Rigor:**
  - Outcome measures and design were fixed before the main runs, tagged `v0.1-design` and
    `v0.2-frozen-design`, after a baseline pilot.
  - Every call is logged, seeded and resumable.

## Metrics
- **Primary:** F1 pick rate, with Wilson 95% CIs.
- **Assumption-free error:** F2 pick rate (by output fund ID; see the post-hoc name/ID check below).
- **Shift vs. baseline:** linear probability model with HC3 robust SEs, plus chi-square and Fisher tests.
- **Also:** Gini concentration of choices, row-position bias, and the order effect.

## Headline results
| Condition | llama3.1:8b F1 rate | qwen2.5:7b F1 rate | Where the picks went |
|---|---|---|---|
| Baseline (no context) | 86% | 75% | mostly F1 |
| Analyst note (pushes tech fund) | 0% | 3% | tech fund 100% / 93% |
| Forum post (pushes growth fund) | 0% | 0% | growth fund 98% / 98% |
| Ratings report (pushes F1) | 100% | 100% | F1 |
| "I love tech companies!" | 1% | 0% | tech fund 98% / 100% |
| Campus-library remark | 83% | 48% | qwen: target-date fund 37% |
| "I'm nervous about stocks." | 63% | 5% | qwen: bond 54%, target-date 39% |
| All three sources, shuffled | 86% | 76% | |
| Same three sources, fixed orders | 73–99% | 41–98% (name-based: 53–99%) | ratings-first: 98–99% for both |

All shifts from baseline are significant at p < 0.001, except the library remark for llama (p = 0.56) and
all three sources shuffled (both models).

## Takeaways
1. **One document or one sentence of memory is enough.** Each single source moved 93–100% of picks to the
   fund it recommended. "I love tech companies!" was as strong as a full analyst report.
2. **Models differ most on memory.** The anxious-user line moved qwen almost entirely to bond and target-date
   funds (F1 5%) but llama only partly (F1 63%). An irrelevant-looking memory moved qwen by −27 pp.
3. **Order matters.** With the same three documents, putting the ratings report first gave 98–99% F1 for both
   models. Other orders dropped F1 to 73% (llama) and 41% (qwen; 53% when mislabeled IDs are read by the
   fund named in the reasoning), and the order that hurt differed by model. The order effect holds under
   both readings (χ² p < 0.001).
4. **The strictly dominated fund was rarely chosen, and some "F2" picks were mislabeled F1 picks.**
   A post-hoc check (found by my professor's review after the main analysis) compared the fund named in each
   reasoning with the output ID. About half of qwen's F2 picks by ID (17 of 33) actually recommend Alder (F1)
   by name; llama had no mismatches. Read by the named fund, the F2 rate is 0–1% in most conditions (16 of 22
   model × condition cells; qwen's analyst condition is 2%). It is higher only at baseline (6% llama, 9% qwen)
   and under two memories (library remark 5–6%, anxious user 11% for llama). The earlier reading that F2 picks
   reflect a misread fee is not supported: many of those reasonings were correctly describing F1.

## Limitations
- **Models:** only two small open models (7–8B), so results may differ for larger models.
- **Scope:** one fictional grid and one product category.
- **Floor effects:** several manipulations hit the floor, so they cannot be ranked against each other.
- **Neutral memory:** the "neutral" memory is not a clean control for qwen.
- **Fund-ID mislabeling:** qwen sometimes outputs one fund ID while recommending another by name (24 of
  1,100 runs), so the ID-based F1 rate may understate the true F1 rate. This check is post-hoc.
- **Order test:** the 3-order design ties the ratings report's position to which document comes first, so
  why each order hurts remains a hypothesis.
