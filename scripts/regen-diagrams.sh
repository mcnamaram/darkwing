#!/bin/bash
# Regenerate docs/img/*.svg from diagrams/*.excalidraw source files.
# Requires: npm install -g excalidraw-export
set -euo pipefail

cd "$(dirname "$0")/.."

shopt -s nullglob
files=(diagrams/*.excalidraw)
shopt -u nullglob

if [ ${#files[@]} -eq 0 ]; then
  echo "No .excalidraw files found in diagrams/"
  exit 0
fi

for src in "${files[@]}"; do
  base="${src##*/}"
  base="${base%.excalidraw}"
  svg="docs/img/${base}.svg"

  # Strip // comments so JSON parses; excalidraw-export doesn't handle them
  python3 - "$src" <<'PY'
import sys, json
src = sys.argv[1]
raw = open(src).read()
lines = [l for l in raw.split('\n') if not l.strip().startswith('//')]
clean = '\n'.join(lines)
json.loads(clean)  # verify
open('/tmp/darkwing_clean.excalidraw', 'w').write(clean)
PY

  excalidraw-export /tmp/darkwing_clean.excalidraw --svg -o "$svg"
  echo "✓ $svg"
done

echo "Done."
