#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d /tmp/M_Bamboo_RC4_cooling.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/config"
STOCK=${MB_STOCK_CONFIG_DIR:-/mnt/data/stock_extract/home/sovol/printer_data/config}
cp "$STOCK/printer.cfg" "$TMP/config/printer.cfg"
cp "$TMP/config/printer.cfg" "$TMP/stock"

# Optional feature installs on stock without requiring Macro/buffer files.
python3 "$ROOT/installer.py" hardware_cooling --apply --no-restart --config-dir "$TMP/config" >/dev/null
grep -q '^# >>> M_Bamboo_SV08MAX_MOD:HARDWARE_COOLING_BED_FAN BEGIN >>>$' "$TMP/config/printer.cfg"
grep -A16 '^\[heater_fan bed_fan\]' "$TMP/config/printer.cfg" | grep -q '^fan_speed: 0.6$'
# It is idempotent.
out=$(python3 "$ROOT/installer.py" hardware_cooling --config-dir "$TMP/config")
echo "$out" | grep -q 'Planned writes: 0'
# Restore returns exact stock bytes for this clean-stock case.
python3 "$ROOT/installer.py" hardware_cooling --restore --apply --no-restart --config-dir "$TMP/config" >/dev/null
cmp "$TMP/config/printer.cfg" "$TMP/stock"

# Unknown user fan_speed must be refused and preserved.
cp "$TMP/stock" "$TMP/config/printer.cfg"
python3 - "$TMP/config/printer.cfg" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(); marker='tachometer_poll_interval: 0.001375\n'; assert marker in s
p.write_text(s.replace(marker,marker+'fan_speed: 0.4\n',1))
PY
cp "$TMP/config/printer.cfg" "$TMP/before"
if python3 "$ROOT/installer.py" hardware_cooling --apply --no-restart --config-dir "$TMP/config" >/dev/null 2>&1; then
  echo 'expected unknown fan_speed refusal' >&2; exit 1
fi
cmp "$TMP/config/printer.cfg" "$TMP/before"

echo 'hardware cooling ownership matrix: PASS'
