#!/usr/bin/env bash
# Unattended Stage 1 main run on the local models. Launch detached:
#   caffeinate -i nohup studies/own_maker/scripts/run_stage1_local.sh > studies/own_maker/runs/stage1_main.out 2>&1 &
# Auto-stop is inside run_stage1.py (>5% failed/unparsed calls, or 3 consecutive errors = Ollama down).
# Re-running resumes from the log.
set -u
cd "$(dirname "$0")/../../.."
source .venv/bin/activate
curl -sf http://localhost:11434/api/version > /dev/null || { echo "AUTO-STOP: Ollama not responding"; exit 1; }
for m in llama3.1-8b qwen2.5-7b; do
  python studies/own_maker/src/run_stage1.py --models "$m" --yes || { echo "STOPPED on $m (exit $?)"; exit 1; }
done
echo "STAGE1 MAIN DONE $(date -u +%FT%TZ)"
