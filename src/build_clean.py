"""Build runs/clean.csv from the append-only raw logs.

  python src/build_clean.py                 # main phase -> runs/clean.csv
  python src/build_clean.py --phase pilot   # pilot      -> runs/clean_pilot.csv

Raw logs are never modified. For each run_id the latest successful API response is used
(earlier errored attempts are retries). Runs with no valid fund choice are dropped and
counted per model, and the counts are written to results/<phase>/tables/dropped_runs.csv.
"""

import argparse

import pandas as pd

from common import DATA, RAW_DIR, ROOT, load_grid, parse_response, read_jsonl

LOW_FEE_MAX = 0.25  # pre-registered: "low-fee" = expense ratio <= 0.25%


def out_paths(phase):
    clean = ROOT / "runs" / ("clean.csv" if phase == "main" else f"clean_{phase}.csv")
    tables = ROOT / "results" / ("" if phase == "main" else phase) / "tables"
    return clean, tables


def fund_flags(grid_file):
    """Per-grid lookup: dominant fund id, dominated fund id (F2), low-fee fund ids."""
    g = load_grid(DATA / f"{grid_file}.csv")
    fee = g.expense_ratio.str.rstrip("%").astype(float)
    dominant = g.loc[g.is_dominant == "1", "fund_id"].iloc[0]
    # The dominated fund tracks the same index as the dominant one at a higher fee.
    same_index = g[(g.tracks == g.set_index("fund_id").loc[dominant, "tracks"]) & (g.fund_id != dominant)]
    return {"ids": set(g.fund_id), "dominant": dominant, "dominated": same_index.fund_id.iloc[0],
            "low_fee": set(g.fund_id[fee <= LOW_FEE_MAX])}


def build(phase):
    records = [r for f in sorted(RAW_DIR.glob(f"{phase}_*.jsonl")) for r in read_jsonl(f)]
    if not records:
        raise SystemExit(f"No raw logs for phase '{phase}' in {RAW_DIR}")
    raw = pd.DataFrame(records)

    # One row per run_id: latest successful attempt; runs that never succeeded are API errors.
    ok = raw[raw.error.isna()].drop_duplicates("run_id", keep="last")
    api_failed = raw[~raw.run_id.isin(ok.run_id)].drop_duplicates("run_id", keep="last")

    flags = {gf: fund_flags(gf) for gf in ok.grid_file.unique()}
    rows = []
    for r in ok.itertuples(index=False):
        fl = flags[r.grid_file]
        fund, reasoning, method = parse_response(r.raw_response, fl["ids"])  # re-parse from raw text
        rows.append({
            "run_id": r.run_id, "phase": r.phase, "model_key": r.model_key, "provider": r.provider,
            "model": r.model, "model_digest": r.model_digest, "grid_file": r.grid_file,
            "condition_id": r.condition_id, "run_index": r.run_index,
            "sources_in_order": "|".join(r.sources_in_order), "ratings_position": r.ratings_position,
            "memory": r.memory, "grid_order": "|".join(r.grid_order),
            "dominant_position": r.dominant_position,
            "chosen_fund": fund,
            "chosen_position": r.grid_order.index(fund) + 1 if fund else None,
            "chose_f1": int(fund == fl["dominant"]) if fund else None,
            "chose_f2": int(fund == fl["dominated"]) if fund else None,
            "chose_low_fee": int(fund in fl["low_fee"]) if fund else None,
            "parse_method": method, "reasoning_text": reasoning,
            "tokens_in": r.tokens_in, "tokens_out": r.tokens_out, "latency_ms": r.latency_ms,
            "seed": r.seed, "temperature": r.temperature, "timestamp": r.timestamp,
        })
    parsed = pd.DataFrame(rows)
    clean = parsed[parsed.chosen_fund.notna()]

    # Drop summary per model
    summary = []
    for mk in sorted(raw.model_key.unique()):
        p = parsed[parsed.model_key == mk]
        n_api = int((api_failed.model_key == mk).sum())
        n_noparse = int(p.chosen_fund.isna().sum())
        n_total = len(p) + n_api
        summary.append({
            "model_key": mk, "planned_runs_attempted": n_total, "api_errors": n_api,
            "no_choice_or_unparseable": n_noparse, "kept": n_total - n_api - n_noparse,
            "drop_rate": round((n_api + n_noparse) / n_total, 4) if n_total else None,
            "no_choice_breakdown": p.loc[p.chosen_fund.isna(), "parse_method"].value_counts().to_dict(),
        })
    summary = pd.DataFrame(summary)

    clean_path, tables = out_paths(phase)
    tables.mkdir(parents=True, exist_ok=True)
    clean.to_csv(clean_path, index=False)
    summary.to_csv(tables / "dropped_runs.csv", index=False)

    print(f"Wrote {len(clean)} runs -> {clean_path.relative_to(ROOT)}")
    print("Dropped runs per model:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="main")
    build(ap.parse_args().phase)
