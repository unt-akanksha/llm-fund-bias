#!/bin/bash
# Main-run wrapper around src/run_experiment.py (which it does not modify).
# Runs one model x condition at a time, checks it, and stops cleanly on trouble.
#
#   caffeinate -i nohup scripts/run_main.sh first &   # llama baseline (100) + first 50 src_analyst, then pause
#   caffeinate -i nohup scripts/run_main.sh rest  &   # everything else; resumes, skipping finished runs
#   caffeinate -i nohup scripts/run_main.sh order &   # order test: ord_* conditions, both models
#
# Progress: tail -f runs/progress.log
# Auto-stop: runner exits non-zero (Ollama down / 10 errors in a row), or a condition has
# > 5% errors + unparseable responses. Raw logs are committed + pushed after each model finishes.

set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=runs/progress.log
STAGE=${1:?usage: run_main.sh first|rest|order}
MODELS="llama3.1-8b qwen2.5-7b"
CONDS=$($PY -c "import pandas as pd; d=pd.read_csv('data/conditions.csv'); print(' '.join(d[d.core==1].condition_id))")
ORD_CONDS=$($PY -c "import pandas as pd; d=pd.read_csv('data/conditions.csv'); print(' '.join(d[d.condition_id.str.startswith('ord_')].condition_id))")

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

check() {  # model condition -> prints a CHECK line; non-zero exit if > 5% bad
  $PY - "$1" "$2" >> "$LOG" <<'EOF'
import collections, json, sys
m, c = sys.argv[1:3]
recs = [json.loads(l) for l in open(f"runs/raw/main_{m}.jsonl") if l.strip()]
recs = [r for r in recs if r["condition_id"] == c]
ids = {r["run_id"] for r in recs}
ok = {r["run_id"]: r for r in recs if not r.get("error")}
err = len(ids) - len(ok)
noparse = sum(r["chosen_fund"] is None for r in ok.values())
bad = (err + noparse) / len(ids) if ids else 1.0
picks = collections.Counter(r["chosen_fund"] for r in ok.values() if r["chosen_fund"])
n_ok = sum(picks.values())
lat = sum(r["latency_ms"] for r in ok.values()) / max(1, len(ok)) / 1000
dist = " ".join(f"{k}:{v}" for k, v in sorted(picks.items()))
print(f"CHECK {m}/{c}: n={len(ids)} errors={err} unparseable={noparse} bad={bad:.1%} "
      f"F1={picks.get('F1', 0) / max(1, n_ok):.0%} s/call={lat:.1f} picks[{dist}]", flush=True)
sys.exit(3 if bad > 0.05 else 0)
EOF
}

run_cond() {  # model condition [runs]
  local extra=""
  [ -n "${3:-}" ] && extra="--runs-per-condition $3"
  log "START $1/$2 ${3:+(first $3 runs)}"
  $PY -u src/run_experiment.py --models "$1" --conditions "$2" $extra --yes 2>&1 \
    | perl -pe 'BEGIN{$|=1; $/="\r"} s/\r/\n/g' >> "$LOG"   # split on \r so per-call lines appear live
  local rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    log "STOP: runner exited with code $rc on $1/$2 (Ollama not responding, or 10 errors in a row). Fix, then re-run: caffeinate -i nohup scripts/run_main.sh rest &"
    exit 1
  fi
  if ! check "$1" "$2"; then
    log "STOP: $1/$2 exceeded 5% errors + unparseable responses. Inspect runs/raw/main_$1.jsonl before resuming."
    exit 1
  fi
}

commit_model() {  # model "description": commit + normal push of one model's raw log, only if it changed
  local f="runs/raw/main_$1.jsonl"
  if [ -n "$(git status --porcelain -- "$f")" ]; then
    git add -- "$f" && git commit -q -m "Add main-run raw logs: $1 ($2)" -- "$f" \
      && log "COMMITTED raw logs for $1" || log "WARN: commit failed for $1"
    git push origin main >> "$LOG" 2>&1 && log "PUSHED $1" || log "WARN: push failed for $1 (not retried, no force)"
  fi
}

log "===== run_main.sh $STAGE (pid $$) ====="
if [ "$STAGE" = "first" ]; then
  run_cond llama3.1-8b baseline
  run_cond llama3.1-8b src_analyst 50
  log "PAUSE: first checkpoint reached (llama baseline + 50 src_analyst). Waiting for review."
elif [ "$STAGE" = "rest" ]; then
  for m in $MODELS; do
    for c in $CONDS; do run_cond "$m" "$c"; done
    log "MODEL DONE $m"
    commit_model "$m" "core conditions"
  done
  log "ALL DONE"
elif [ "$STAGE" = "order" ]; then
  for m in $MODELS; do
    for c in $ORD_CONDS; do run_cond "$m" "$c"; done
    log "MODEL DONE $m (order test)"
    commit_model "$m" "order-test conditions"
  done
  log "ALL DONE (order test)"
else
  echo "usage: run_main.sh first|rest|order"; exit 2
fi
