#!/bin/bash
set -euo pipefail
BASE_URL="${MOONRAKER_URL:-http://127.0.0.1:7125}"
curl -fsS -G "$BASE_URL/printer/gcode/script" --data-urlencode "script=M_BAMBOO_EDDY_RECOVERY_CHECK" >/dev/null
echo "Sent M_BAMBOO_EDDY_RECOVERY_CHECK. Review Mainsail/klippy.log for the authoritative RC4 result."
