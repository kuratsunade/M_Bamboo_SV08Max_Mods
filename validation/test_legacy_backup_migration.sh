#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d /tmp/M_Bamboo_RC4_migrate.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/config" "$TMP/extras"
STOCK=${MB_STOCK_CONFIG_DIR:-/mnt/data/stock_extract/home/sovol/printer_data/config}
cp "$STOCK/printer.cfg" "$STOCK/Macro.cfg" "$STOCK/buffer_stepper.cfg" "$TMP/config/"
# First create current RC4 config using byte-exact validated Sovol stock baselines.
FIX="$ROOT/validation/fixtures/stock_backend"
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do cp "$FIX/$f" "$TMP/extras/$f"; cp "$FIX/$f" "$TMP/extras/$f.mb_baseline"; done
# Put release targets in place, simulating an already-modified engineering machine with legacy baselines.
for f in ldc1612.py probe_eddy_current.py probe.py M_Bamboo_Safe_Homing.py z_offset_calibration.py; do cp "$ROOT/backend/$f" "$TMP/extras/$f"; done
python3 "$ROOT/installer.py" safe_home --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null
python3 "$ROOT/installer.py" config_optimization --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null
# all install must migrate legacy .mb_baseline into one central mb_bak, not snapshot targets.
python3 "$ROOT/installer.py" all --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do cmp "$TMP/extras/mb_bak/$f" "$TMP/extras/$f.mb_baseline"; done
python3 "$ROOT/installer.py" all --restore --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do cmp "$TMP/extras/$f" "$TMP/extras/$f.mb_baseline"; done
test ! -e "$TMP/extras/M_Bamboo_Safe_Homing.py"
echo 'legacy baseline -> centralized mb_bak migration: PASS'
