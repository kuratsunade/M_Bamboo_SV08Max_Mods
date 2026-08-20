#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d /tmp/M_Bamboo_RC4_test.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/config" "$TMP/extras"
STOCK=${MB_STOCK_CONFIG_DIR:-/mnt/data/stock_extract/home/sovol/printer_data/config}
cp "$STOCK/printer.cfg" "$STOCK/Macro.cfg" "$STOCK/buffer_stepper.cfg" "$TMP/config/"
python3 - "$TMP/config/printer.cfg" "$TMP/save_tail.stock" <<'PY2'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text(); m='#*# <---------------------- SAVE_CONFIG ---------------------->'
i=s.find(m); Path(sys.argv[2]).write_text(s[i:] if i>=0 else '')
PY2
FIX="$ROOT/validation/fixtures/stock_backend"
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do cp "$FIX/$f" "$TMP/extras/$f"; done
# preserve exact originals for backend comparison
mkdir "$TMP/original_backend"; cp "$TMP/extras"/*.py "$TMP/original_backend/"
python3 "$ROOT/installer.py" all --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null
# Diagnostics are formally owned by all and installed exactly once.
grep -q '^# >>> M_Bamboo_SV08MAX_MOD:DIAGNOSTICS_XY_STRESS BEGIN >>>$' "$TMP/config/Macro.cfg"
[ "$(grep -c '^\[gcode_macro XY_STRESS_BASELINE\]$' "$TMP/config/Macro.cfg")" -eq 1 ]
[ "$(grep -c '^\[gcode_macro XY_STRESS_RUN\]$' "$TMP/config/Macro.cfg")" -eq 1 ]
[ "$(grep -c '^\[gcode_macro XY_STRESS_CHECK\]$' "$TMP/config/Macro.cfg")" -eq 1 ]
# Idempotency: zero writes.
out=$(python3 "$ROOT/installer.py" all --config-dir "$TMP/config" --extras-dir "$TMP/extras")
echo "$out" | grep -q 'Planned writes: 0; deletes: 0'
# No config persistent backup litter / no pycache.
! find "$TMP/config" -maxdepth 1 -type f \( -name '*.mb_*' -o -name '*.last_mb_*' \) | grep -q .
! find "$TMP/extras" -type d -name __pycache__ | grep -q .
test -f "$TMP/extras/mb_bak/MANIFEST.json"
# SAVE_CONFIG generated tail must remain byte-identical after apply.
python3 - "$TMP/config/printer.cfg" "$TMP/save_tail.stock" <<'PY2'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text(); m='#*# <---------------------- SAVE_CONFIG ---------------------->'
i=s.find(m); now=s[i:] if i>=0 else ''
assert now == Path(sys.argv[2]).read_text(), 'SAVE_CONFIG tail changed during apply'
PY2
# Inject failure and prove byte-exact transaction rollback.
cp "$TMP/config/printer.cfg" "$TMP/printer.before"
cp "$TMP/extras/ldc1612.py" "$TMP/ldc.before"
python3 - "$TMP/config/printer.cfg" <<'PY2'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(); m='#*# <---------------------- SAVE_CONFIG ---------------------->'
i=s.find(m)
assert i >= 0
p.write_text(s[:i] + '# user mutation after install\n' + s[i:])
PY2
# restore is a convenient write transaction; injected failure must revert to immediately-pre-transaction state
cp "$TMP/config/printer.cfg" "$TMP/printer.pre_fail"
if MB_TEST_FAIL_AFTER_WRITE=1 python3 "$ROOT/installer.py" all --restore --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null 2>&1; then
  echo 'expected injected failure' >&2; exit 1
fi
cmp "$TMP/config/printer.cfg" "$TMP/printer.pre_fail"
cmp "$TMP/extras/ldc1612.py" "$TMP/ldc.before"
# An unknown backend mutation after ownership is established must be refused.
printf '\n# third-party mutation\n' >> "$TMP/extras/probe.py"
if python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null 2>&1; then
  echo 'expected unknown backend hash refusal' >&2; exit 1
fi
# Put canonical target back so full restore can proceed.
cp "$ROOT/backend/probe.py" "$TMP/extras/probe.py"

# Keep the unrelated user line: full restore must preserve user-owned config outside MB blocks.
python3 "$ROOT/installer.py" all --restore --apply --no-restart --config-dir "$TMP/config" --extras-dir "$TMP/extras" >/dev/null
! grep -R 'M_Bamboo_SV08MAX_MOD' "$TMP/config" >/dev/null
! grep -q '^\[gcode_macro XY_STRESS_BASELINE\]$' "$TMP/config/Macro.cfg"
! grep -q '^\[gcode_macro XY_STRESS_RUN\]$' "$TMP/config/Macro.cfg"
! grep -q '^\[gcode_macro XY_STRESS_CHECK\]$' "$TMP/config/Macro.cfg"
grep -q '^# user mutation after install$' "$TMP/config/printer.cfg"
# Semantic original values restored.
grep -q '^max_velocity: 700' "$TMP/config/printer.cfg"
grep -q '^max_accel: 40000' "$TMP/config/printer.cfg"
grep -q '^speed: 400' "$TMP/config/printer.cfg"
grep -q '^retries: 15' "$TMP/config/printer.cfg"
grep -q '^max_adjust: 20' "$TMP/config/printer.cfg"
grep -q '^position_min: -10' "$TMP/config/printer.cfg"
grep -q '^velocity: 150' "$TMP/config/buffer_stepper.cfg"
grep -q '^accel: 5000' "$TMP/config/buffer_stepper.cfg"
grep -q '^push_length: 25' "$TMP/config/buffer_stepper.cfg"
# Exact stock macro sections reconstructed.
grep -q '^\[homing_override\]' "$TMP/config/printer.cfg"
grep -q '^\[gcode_macro G28\]' "$TMP/config/Macro.cfg"
grep -q '^\[gcode_macro CLEAN_NOZZLE\]' "$TMP/config/Macro.cfg"
# Backend exact original state restored, MB-added file absent.
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do cmp "$TMP/extras/$f" "$TMP/original_backend/$f"; done
test ! -e "$TMP/extras/M_Bamboo_Safe_Homing.py"
# SAVE_CONFIG generated tail must also remain byte-identical after restore.
python3 - "$TMP/config/printer.cfg" "$TMP/save_tail.stock" <<'PY2'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text(); m='#*# <---------------------- SAVE_CONFIG ---------------------->'
i=s.find(m); now=s[i:] if i>=0 else ''
assert now == Path(sys.argv[2]).read_text(), 'SAVE_CONFIG tail changed during restore'
PY2
# Persistent backup remains exactly one centralized directory.
test -d "$TMP/extras/mb_bak"
! find "$TMP/extras" -maxdepth 1 -type f \( -name '*.mb_baseline' -o -name '*.last_mb_*' \) | grep -q .

# If automatic rollback itself fails, the transaction snapshot MUST survive.
RF="$TMP/rollback_failure"
mkdir -p "$RF/config" "$RF/extras"
cp "$STOCK/printer.cfg" "$STOCK/Macro.cfg" "$STOCK/buffer_stepper.cfg" "$RF/config/"
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do cp "$FIX/$f" "$RF/extras/$f"; done
python3 "$ROOT/installer.py" all --apply --no-restart --config-dir "$RF/config" --extras-dir "$RF/extras" >/dev/null
set +e
rf_out=$(MB_TEST_FAIL_AFTER_WRITE=1 MB_TEST_FAIL_DURING_ROLLBACK=1 python3 "$ROOT/installer.py" all --restore --apply --no-restart --config-dir "$RF/config" --extras-dir "$RF/extras" 2>&1)
rf_rc=$?
set -e
[ "$rf_rc" -ne 0 ] || { echo 'expected rollback-failure injection' >&2; exit 1; }
echo "$rf_out" | grep -q 'Recovery snapshot retained at /tmp/M_Bamboo_SV08MAX.'
rf_dir=$(printf '%s\n' "$rf_out" | sed -n 's/.*Recovery snapshot retained at \([^ ]*\)\. Rollback errors:.*/\1/p' | tail -n 1)
[ -n "$rf_dir" ]
test -d "$rf_dir"
find "$rf_dir" -type f -name '*.orig' | grep -q .
rm -rf "$rf_dir"

echo 'release installer v2 matrix: PASS'
