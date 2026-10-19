"""Study 1 v2: annual net cost drag, cost regret, dominance, best/worst (design_v2.md §3).

All inputs are in PERCENT as printed on fact sheets (e.g. expense ratio 0.09 means 0.09%);
all outputs are in BASIS POINTS per year (1 bp = 0.01%).

    ER_f = expense ratio x 100                     (bps)
    TD_f = (fund NAV 5-yr ann. return - index 5-yr ann. return) x 100   (bps; negative = lags)
    R_f  = -TD_f - ER_f                            residual beyond the fee
    S_f  = 30-day median bid-ask spread x 100      (bps; one round trip ~ one full spread)
    C_f(H) = ER_f + R_f + S_f / H   (= -TD_f + S_f / H; ER is redundant inside C)

Regret is computed only within a same-index set; a fund alone on its index has regret 0.
Differences under EPS_BPS (1 bp) are ties.
"""

from dataclasses import dataclass

EPS_BPS = 1.0
H_PRIMARY = 10


@dataclass(frozen=True)
class FundCost:
    ticker: str
    expense_ratio_pct: float
    tracking_difference_pct: float      # fund NAV return minus index return, % per year
    spread_pct: float                   # 30-day median bid-ask spread, %

    @property
    def er_bps(self):
        return self.expense_ratio_pct * 100

    @property
    def td_bps(self):
        return self.tracking_difference_pct * 100

    @property
    def residual_bps(self):
        return -self.td_bps - self.er_bps

    @property
    def spread_bps(self):
        return self.spread_pct * 100


def tracking_difference_pct(fund_return_pct, index_return_pct):
    """DERIVED field: fund NAV annualized return minus index annualized return (both in %)."""
    return fund_return_pct - index_return_pct


def net_cost_bps(f: FundCost, horizon_years=H_PRIMARY):
    """C_f(H) = ER + R + S/H, in bps per year."""
    if horizon_years <= 0:
        raise ValueError("horizon must be positive")
    return f.er_bps + f.residual_bps + f.spread_bps / horizon_years


def cost_er_spread_only_bps(f: FundCost, horizon_years=H_PRIMARY):
    """Sensitivity (Nasdaq-100 set): ER + S/H, ignoring tracking difference."""
    return f.er_bps + f.spread_bps / horizon_years


def regret_bps(chosen: str, same_index_set, horizon_years=H_PRIMARY, cost_fn=net_cost_bps):
    """Cost regret of picking `chosen`: its cost minus the lowest cost in its same-index set (>= 0).
    `same_index_set` is a list of FundCost; a single-fund set gives 0 by definition."""
    by = {f.ticker: f for f in same_index_set}
    if chosen not in by:
        raise KeyError(f"{chosen} is not in the same-index set {sorted(by)}")
    costs = {t: cost_fn(f, horizon_years) for t, f in by.items()}
    return costs[chosen] - min(costs.values())


def is_tie(a_bps, b_bps, eps=EPS_BPS):
    return abs(a_bps - b_bps) < eps


def dominates(f: FundCost, g: FundCost, eps=EPS_BPS):
    """f dominates g: at least as good on ER, R and S (within eps) and strictly better (by >= eps) on one."""
    comps = [(f.er_bps, g.er_bps), (f.residual_bps, g.residual_bps), (f.spread_bps, g.spread_bps)]
    no_worse = all(a < b + eps for a, b in comps)          # lower, equal, or within eps (tie)
    strictly_better = any(a <= b - eps for a, b in comps)
    return no_worse and strictly_better


def dominated_funds(same_index_set, eps=EPS_BPS):
    """Tickers in the set that are dominated by at least one other member."""
    return sorted(g.ticker for g in same_index_set
                  if any(dominates(f, g, eps) for f in same_index_set if f.ticker != g.ticker))


def best_and_worst(same_index_set, horizon_years=H_PRIMARY, eps=EPS_BPS):
    """Best = lowest C, worst = highest C (design_v2 §3 tie rule).
    Funds within eps of the extreme are tied; best tie-break: lowest ER, then lowest spread, then ticker A-Z;
    worst tie-break: highest ER, then highest spread, then ticker Z-A.
    Returns (best, worst); (None, None) if every pair in the set is tied (no contrast)."""
    funds = list(same_index_set)
    if len(funds) < 2:
        return None, None
    c = {f.ticker: net_cost_bps(f, horizon_years) for f in funds}
    if all(is_tie(c[a.ticker], c[b.ticker], eps) for a in funds for b in funds):
        return None, None
    lo, hi = min(c.values()), max(c.values())
    best_tied = [f for f in funds if is_tie(c[f.ticker], lo, eps)]
    worst_tied = [f for f in funds if is_tie(c[f.ticker], hi, eps)]
    best = min(best_tied, key=lambda f: (f.er_bps, f.spread_bps, f.ticker)).ticker
    worst = max(worst_tied, key=lambda f: (f.er_bps, f.spread_bps, f.ticker)).ticker
    return best, worst
