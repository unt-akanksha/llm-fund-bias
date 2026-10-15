#!/usr/bin/env bash
# Stage 1 main run for ONE Groq model, capped per rolling 24 h. Same command every day; it resumes:
#   caffeinate -i nohup studies/own_maker/scripts/run_stage1_groq.sh groq-qwen3.8-27b \
#     >> studies/own_maker/runs/stage1_groq-qwen3.8-27b.out 2>&1 &
# Stops cleanly at the daily cap (--max-calls-per-day, plus requests/tokens per day from the config).
# Auto-stop inside run_stage1.py: >5% failed/unparsed calls, or 3 consecutive errors (incl. 429s
# that still fail after retries with Retry-After + exponential backoff).
set -u
cd "$(dirname "$0")/../../.."
source .venv/bin/activate
MODEL="${1:?usage: run_stage1_groq.sh <model_key> [calls_per_day, default 400]}"
CAP="${2:-400}"
echo "START $MODEL cap=$CAP/day $(date -u +%FT%TZ)"
python studies/own_maker/src/run_stage1.py --models "$MODEL" --max-calls-per-day "$CAP" --yes
echo "EXIT $? $MODEL $(date -u +%FT%TZ)"
