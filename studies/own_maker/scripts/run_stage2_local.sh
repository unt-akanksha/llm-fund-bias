#!/usr/bin/env bash
# Stage 2 main run on the local models (200 calls). Launch detached:
#   caffeinate -i nohup studies/own_maker/scripts/run_stage2_local.sh > studies/own_maker/runs/stage2_main.out 2>&1 &
# Auto-stop is inside run_stage2.py. Re-running resumes from the log.
set -u
cd "$(dirname "$0")/../../.."
source .venv/bin/activate
curl -sf http://localhost:11434/api/version > /dev/null || { echo "AUTO-STOP: Ollama not responding"; exit 1; }
for m in llama3.1-8b qwen2.5-7b; do
  python studies/own_maker/src/run_stage2.py --models "$m" --yes || { echo "STOPPED on $m (exit $?)"; exit 1; }
done
echo "STAGE2 MAIN DONE $(date -u +%FT%TZ)"
