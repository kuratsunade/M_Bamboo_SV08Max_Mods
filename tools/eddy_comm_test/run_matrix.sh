#!/bin/bash
set -euo pipefail
BASE_URL="${MOONRAKER_URL:-http://127.0.0.1:7125}"
PASSES_PER_CELL="${PASSES_PER_CELL:-5}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/preflight.sh"
curl -fsS -G "$BASE_URL/printer/gcode/script" \
  --data-urlencode "script=M_BAMBOO_CHURN_MATRIX_START PASSES_PER_CELL=$PASSES_PER_CELL" >/dev/null
echo "Started Klipper-side M_Bamboo churn matrix; PASSES_PER_CELL=$PASSES_PER_CELL"
echo "Use M_BAMBOO_SOAK_STATUS in Mainsail to inspect progress."
