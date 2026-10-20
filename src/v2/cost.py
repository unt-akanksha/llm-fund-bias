"""Study 1 v2: annual net cost drag, cost regret, dominance, best/worst (design_v2.md §3).

All inputs are in PERCENT as printed on fact sheets / product pages (e.g. expense ratio 0.09 means
0.09%); all outputs are in BASIS POINTS per year (1 bp = 0.01%).

    ER_f = expense ratio x 100                     (bps)
    TD_f = (fund NAV 5-yr ann. return - index 5-yr ann. return) x 100   (bps; negative = lags)
    R_f  = -TD_f - ER_f                            residual beyond the fee
    C_f  = ER_f + R_f = -TD_f                      (ER is redundant inside C)

The bid-ask spread and the holding horizon were dropped (fact-sheet-only data; see design §3).
Regret is computed only within a same-index set; a fund alone on its index has regret 0.
Differences under EPS_BPS (1 bp) are ties.
"""

from dataclasses import dataclass

EPS_BPS = 1.0


@dataclass(frozen=True)
class FundCost:
    """Cost inputs for one fund, in percent."""
    ticker: str
    expense_ratio_pct: float
    tracking_difference_pct: float      # fund NAV return minus index return, % per year

    @property
    def er_bps(self):
        return self.expense_ratio_pct * 100

    @property
    def td_bps(self):
        return self.tracking_difference_pct * 100

    @property
    def residual_bps(self):
        return -self.td_bps - self.er_bps


def tracking_difference_pct(fund_return_pct, index_return_pct):
    """DERIVED field: fund NAV annualized return minus index annualized return (both in %)."""
    return fund_return_pct - index_return_pct


def net_cost_bps(f: FundCost):
    """C_f = ER + R = -TD, in bps per year."""
    return f.er_bps + f.residual_bps


def cost_er_only_bps(f: FundCost):
    """Sensitivity (Nasdaq-100 set): expense ratio only, ignoring tracking difference."""
    return f.er_bps


def regret_bps(chosen: str, same_index_set, cost_fn=net_cost_bps):
    """Cost regret of picking `chosen`: its cost minus the lowest cost in its same-index set (>= 0).
    `same_index_set` is a list of FundCost; a single-fund set gives 0 by definition."""
    by = {f.ticker: f for f in same_index_set}
    if chosen not in by:
        raise KeyError(f"{chosen} is not in the same-index set {sorted(by)}")
    costs = {t: cost_fn(f) for t, f in by.items()}
    return costs[chosen] - min(costs.values())


def is_tie(a_bps, b_bps, eps=EPS_BPS):
    return abs(a_bps - b_bps) < eps


def dominates(f: FundCost, g: FundCost, eps=EPS_BPS):
    """f dominates g: at least as good on ER and R (within eps) and strictly better (by >= eps) on one."""
    comps = [(f.er_bps, g.er_bps), (f.residual_bps, g.residual_bps)]
    no_worse = all(a < b + eps for a, b in comps)          # lower, equal, or within eps (tie)
    strictly_better = any(a <= b - eps for a, b in comps)
    return no_worse and strictly_better


def dominated_funds(same_index_set, eps=EPS_BPS):
    """Tickers in the set that are dominated by at least one other member."""
    return sorted(g.ticker for g in same_index_set
                  if any(dominates(f, g, eps) for f in same_index_set if f.ticker != g.ticker))


def best_and_worst(same_index_set, eps=EPS_BPS):
    """Best = lowest C, worst = highest C (design_v2 §3 tie rule).
    Funds within eps of the extreme are tied; best tie-break: lowest ER, then ticker A-Z;
    worst tie-break: highest ER, then ticker Z-A.
    Returns (best, worst); (None, None) if every pair in the set is tied (no contrast)."""
    funds = list(same_index_set)
    if len(funds) < 2:
        return None, None
    c = {f.ticker: net_cost_bps(f) for f in funds}
    if all(is_tie(c[a.ticker], c[b.ticker], eps) for a in funds for b in funds):
        return None, None
    lo, hi = min(c.values()), max(c.values())
    best_tied = [f for f in funds if is_tie(c[f.ticker], lo, eps)]
    worst_tied = [f for f in funds if is_tie(c[f.ticker], hi, eps)]
    best = min(best_tied, key=lambda f: (f.er_bps, f.ticker)).ticker
    worst = max(worst_tied, key=lambda f: (f.er_bps, f.ticker)).ticker
    return best, worst
