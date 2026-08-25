#!/bin/bash
set -euo pipefail

BASE_URL="${MOONRAKER_URL:-http://127.0.0.1:7125}"
BURST="${BURST:-8}"
PASSES_PER_CELL="${PASSES_PER_CELL:-5}"
DWELLS_MS="${DWELLS_MS:-0 10 25 50 75 100}"
OUT_DIR="${OUT_DIR:-$HOME/M_Bamboo_EAR_Public_Test_Toolkit/results}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
RESULT="$OUT_DIR/matrix-$STAMP.log"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/preflight.sh" | tee -a "$RESULT"

send_gcode() {
  local script="$1"
  curl -fsS -G "$BASE_URL/printer/gcode/script" --data-urlencode "script=$script" >/dev/null
}

status() {
  send_gcode "M_BAMBOO_EDDY_STATUS" || true
}

printf 'START %s BURST=%s PASSES_PER_CELL=%s DWELLS_MS=%s\n' "$(date -Is)" "$BURST" "$PASSES_PER_CELL" "$DWELLS_MS" | tee -a "$RESULT"
status

for dwell in $DWELLS_MS; do
  echo "CELL dwell_ms=$dwell" | tee -a "$RESULT"
  pass=0
  attempt=0
  while [ "$pass" -lt "$PASSES_PER_CELL" ]; do
    attempt=$((attempt + 1))
    echo "ATTEMPT dwell_ms=$dwell attempt=$attempt" | tee -a "$RESULT"

    if ! send_gcode "G28"; then
      echo "FAULT stage=G28 dwell_ms=$dwell attempt=$attempt" | tee -a "$RESULT"
      status
      exit 20
    fi

    ok=1
    for i in $(seq 1 "$BURST"); do
      if ! send_gcode "RUN_PROBE_VIR_CONTACT"; then
        echo "FAULT stage=CONTACT burst_index=$i dwell_ms=$dwell attempt=$attempt" | tee -a "$RESULT"
        ok=0
        break
      fi
      if [ "$i" -lt "$BURST" ]; then
        # Match the field-test motion pattern: lift first, then add nominal dwell.
        if ! send_gcode "G91
G1 Z5 F300
G90
M400
G4 P$dwell"; then
          echo "FAULT stage=LIFT_DWELL burst_index=$i dwell_ms=$dwell attempt=$attempt" | tee -a "$RESULT"
          ok=0
          break
        fi
      fi
    done

    if [ "$ok" -ne 1 ]; then
      status
      echo "STOP: failed transaction is never retried by this tester." | tee -a "$RESULT"
      exit 21
    fi

    pass=$((pass + 1))
    echo "PASS dwell_ms=$dwell attempt=$attempt completed=$pass/$PASSES_PER_CELL" | tee -a "$RESULT"
  done
done

status
printf 'COMPLETE %s\n' "$(date -Is)" | tee -a "$RESULT"
echo "Result file: $RESULT"
