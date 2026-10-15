"""Stage 2 design: balanced profile assignment, row order, and the prompt table for each run.

  python studies/own_maker/src/stage2_design.py --show 0 --condition real_names   # print one prompt
  python studies/own_maker/src/stage2_design.py --check                           # balance report

ALL FINANCIAL FIGURES ARE HYPOTHETICAL (made up; see stage2/config.yaml). Not financial advice.
"""

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

import yaml

STUDY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY.parent.parent / "src"))
from common import stable_seed  # noqa: E402

CFG = STUDY / "stage2" / "config.yaml"
PROMPT = STUDY / "stage2" / "prompt.yaml"


def load():
    return yaml.safe_load(open(CFG)), yaml.safe_load(open(PROMPT))


def plan(cfg, i):
    """Run i -> {slot: rank} (randomized Latin square per block) and row order (list of slots), both seeded."""
    n = len(cfg["companies"])
    block, r = divmod(i, n)
    rng = random.Random(stable_seed(cfg["assignment_seed"], block))
    rho, sigma, tau = (rng.sample(range(n), n) for _ in range(3))
    # randomized Latin square per block of n runs: each company gets each rank once per block,
    # and the row/column/symbol shuffles break fixed rank relations between companies
    ranks = {j: tau[(rho[r] + sigma[j]) % n] + 1 for j in range(n)}
    rows = list(range(n))
    random.Random(stable_seed(cfg["row_order_seed"], i)).shuffle(rows)
    return ranks, rows


def table(cfg, pr, i, condition):
    ranks, rows = plan(cfg, i)
    names = cfg["companies"] if condition == "real_names" else cfg["fictional"]
    header = "| " + " | ".join(pr["columns"]) + " |"
    lines = [header, "|" + "---|" * len(pr["columns"])]
    for j in rows:
        g, m, pe, de, ret = cfg["profiles"][ranks[j]]
        lines.append(f"| {names[j]['name']} | {names[j]['ticker']} | {g} | {m} | {pe:.1f} | {de:.2f} | {ret} |")
    return "\n".join(lines), ranks, rows


def messages(cfg, pr, i, condition):
    t, ranks, rows = table(cfg, pr, i, condition)
    return [{"role": "system", "content": pr["system"]},
            {"role": "user", "content": pr["user_template"].format(table=t)}], ranks, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int)
    ap.add_argument("--condition", default="real_names", choices=["real_names", "fictional_names"])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    cfg, pr = load()
    if a.show is not None:
        msgs, ranks, rows = messages(cfg, pr, a.show, a.condition)
        for m in msgs:
            print(f"--- {m['role']} ---\n{m['content']}\n")
        print("rank by company:", {cfg["companies"][j]["id"]: r for j, r in ranks.items()})
    if a.check:
        n = cfg["runs_per_condition"]
        rank_counts = Counter((cfg["companies"][j]["id"], r) for i in range(n) for j, r in plan(cfg, i)[0].items())
        best_pos = Counter(plan(cfg, i)[1].index(next(j for j, r in plan(cfg, i)[0].items() if r == 1)) + 1
                           for i in range(n))
        print("each company x rank count over", n, "runs:", sorted(set(rank_counts.values())))
        print("row position of the rank-1 profile (position: runs):", dict(sorted(best_pos.items())))
        own_pos = {c: Counter(plan(cfg, i)[1].index(j) + 1 for i in range(n))
                   for j, c in enumerate(x["id"] for x in cfg["companies"]) if c in ("META", "BABA")}
        gaps = Counter(plan(cfg, i)[0][1] - plan(cfg, i)[0][0] for i in range(n))
        print("rank(BABA) - rank(META) across runs:", dict(sorted(gaps.items())))
        print("row positions of META / BABA:", {c: dict(sorted(v.items())) for c, v in own_pos.items()})


if __name__ == "__main__":
    main()
