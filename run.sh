#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-}"
EXPERIMENTS="${2:-ex-python}"

if [[ -z "$SOURCE" ]]; then
  echo "Usage: bash run.sh s3://bucket/prefix ex-python[,ex-pandas,...]"; exit 1
fi

mkdir -p results/raw
METRICS=results/metrics.csv
[[ -f "$METRICS" ]] || echo "tool,label,wall_time,max_rss_kb,user_time,sys_time" > "$METRICS"

measure(){
  local tool="$1"; shift
  local label="$1"; shift
  local cmd=("$@")
  local met="results/raw/${tool}_${label}_time.txt"
  /usr/bin/time -v "${cmd[@]}" >"results/raw/${tool}_${label}_stdout.txt" 2>"$met" || true
  local WCTIME=$(grep -E "Elapsed \(wall clock\) time" "$met" | awk -F: '{print $(NF-1)":"$NF}' | tr -d ' ')
  local MAXRSS=$(grep -E "Maximum resident set size" "$met" | awk '{print $6}')
  local U=$(grep -E "User time" "$met" | awk '{print $4}')
  local S=$(grep -E "System time" "$met" | awk '{print $4}')
  echo "$tool,$label,$WCTIME,$MAXRSS,$U,$S" >> "$METRICS"
}

IFS=',' read -ra EXPRS <<< "$EXPERIMENTS"
for ex in "${EXPRS[@]}"; do
  echo "==> Running $ex"
  for label in 5GB 10GB 15GB; do
    measure "$ex" "$label" uv run "$ex/main.py" "$SOURCE"
  done
done

# Report mínimo
python3 - <<'PY'
import pandas as pd, pathlib
m = pd.read_csv('results/metrics.csv')
rep = []
if not m.empty:
  rep.append('# Benchmark Report')
  rep.append('')
  rep.append('## Wall time')
  rep.append(m.pivot_table(index='label', columns='tool', values='wall_time', aggfunc='first').to_markdown())
  rep.append('')
  rep.append('## Max RSS (KB)')
  rep.append(m.pivot_table(index='label', columns='tool', values='max_rss_kb', aggfunc='first').to_markdown())
pathlib.Path('results').mkdir(exist_ok=True)
pathlib.Path('results/report.md').write_text('\n'.join(rep) if rep else 'No data')
print('Wrote results/report.md')
PY
