#!/bin/zsh
# Builds a whole book unattended: re-runs the build after a crash until every Chapter is rendered.
#   nohup ./run.sh "books/<book>.txt" > work/run.log 2>&1 &
# Progress checklist: uv run --script audiobook.py status "books/<book>.txt"
# caffeinate stops idle sleep only; on battery with the lid closed macOS still sleeps and the build
# pauses until the Mac wakes, so keep it plugged in with the lid open.
cd "${0:A:h}"
BOOK="$1"
for attempt in {1..20}; do
  echo "== build attempt $attempt $(date)"
  caffeinate -is uv run --script audiobook.py build "$BOOK" 2>&1 | grep --line-buffered -E "^\[|Error|Traceback" \
    | tee work/last_build.log
  if grep -q "^\[m4b\] /" work/last_build.log; then
    echo "== all chapters done $(date)"
    exit 0
  fi
  sleep 30
done
echo "== gave up after 20 attempts $(date)"
exit 1
