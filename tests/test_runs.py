"""run_id uniqueness, resume logic, and shuffle reproducibility."""

import json
from types import SimpleNamespace

from common import completed_run_ids, load_conditions, load_config, load_grid, plan_run
from run_experiment import build_jobs

GRID = load_grid()
CONDS = load_conditions()
FUNDS = list(GRID.fund_id)


def cond(cid):
    return CONDS[CONDS.condition_id == cid].iloc[0]


def args(**kw):
    base = dict(phase="main", models=None, conditions=None, runs_per_condition=None, grid="grid")
    return SimpleNamespace(**{**base, **kw})


def test_run_ids_unique_across_full_design():
    all_conds = ",".join(CONDS.condition_id)
    _, jobs = build_jobs(args(conditions=all_conds), load_config(), GRID, CONDS)
    ids = [j["run_id"] for _, j in jobs]
    assert len(ids) == len(set(ids)) > 0


def test_phases_do_not_share_run_ids():
    _, main = build_jobs(args(conditions="baseline", runs_per_condition=5), load_config(), GRID, CONDS)
    _, pilot = build_jobs(args(phase="pilot", conditions="baseline", runs_per_condition=5), load_config(), GRID, CONDS)
    assert not {j["run_id"] for _, j in main} & {j["run_id"] for _, j in pilot}


def test_resume_skips_successes_but_retries_errors(tmp_path):
    log = tmp_path / "main_x.jsonl"
    rows = [{"run_id": "a", "error": None},
            {"run_id": "b", "error": "HTTP 500"},
            {"run_id": "c", "error": None, "chosen_fund": None}]  # unparseable but answered: not retried
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert completed_run_ids(log) == {"a", "c"}
    assert completed_run_ids(tmp_path / "missing.jsonl") == set()


def test_shuffle_is_reproducible():
    assert plan_run("main", "grid", cond("src_all"), 7, FUNDS) == plan_run("main", "grid", cond("src_all"), 7, FUNDS)


def test_grid_order_is_shared_across_conditions_but_varies_across_runs():
    orders = {c: plan_run("main", "grid", cond(c), 3, FUNDS)[0] for c in ["baseline", "src_all", "mem_pos"]}
    assert len({tuple(o) for o in orders.values()}) == 1
    assert sorted(orders["baseline"]) == sorted(FUNDS)
    assert len({tuple(plan_run("main", "grid", cond("baseline"), i, FUNDS)[0]) for i in range(20)}) > 15


def test_sources_shuffled_only_when_requested():
    fixed = cond("ord_RAF")
    assert all(plan_run("main", "grid", fixed, i, FUNDS)[1] == ["src_ratings", "src_analyst", "src_forum"]
               for i in range(10))
    shuffled = {tuple(plan_run("main", "grid", cond("src_all"), i, FUNDS)[1]) for i in range(30)}
    assert len(shuffled) > 1 and all(sorted(s) == ["src_analyst", "src_forum", "src_ratings"] for s in shuffled)


def test_order_conditions_form_latin_square():
    ords = CONDS[CONDS.condition_id.str.startswith("ord_")]
    for col in ["source_1", "source_2", "source_3"]:
        assert set(ords[col]) == {"src_analyst", "src_forum", "src_ratings"}
