#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
FIX="$ROOT/validation/fixtures/stock_backend"
TMP=$(mktemp -d /tmp/M_Bamboo_RC4_provenance.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

snapshot_tree() {
  dir=$1
  out=$2
  (cd "$dir" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$out"
}

make_stock() {
  rm -rf "$TMP/extras"
  mkdir -p "$TMP/extras"
  cp "$FIX"/*.py "$TMP/extras/"
}

# 1. Exact Sovol stock first takeover must pass and preserve exact originals.
make_stock
python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$TMP/extras" >/dev/null
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do
  cmp "$TMP/extras/mb_bak/$f" "$FIX/$f"
done
python3 - "$TMP/extras/mb_bak/MANIFEST.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
for n,v in m['files'].items():
    if n == 'M_Bamboo_Safe_Homing.py':
        assert v['state']=='absent' and v['provenance']=='known-originally-absent'
    else:
        assert v['state']=='present' and v['provenance']=='known-sovol-stock-current'
PY

# 2. Known M_Bamboo lineage + validated stock legacy baseline must pass.
make_stock
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do
  cp "$FIX/$f" "$TMP/extras/$f.mb_baseline"
  cp "$ROOT/backend/$f" "$TMP/extras/$f"
done
cp "$ROOT/backend/M_Bamboo_Safe_Homing.py" "$TMP/extras/M_Bamboo_Safe_Homing.py"
python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$TMP/extras" >/dev/null
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do
  cmp "$TMP/extras/mb_bak/$f" "$FIX/$f"
done

# 3. Known M_Bamboo target with no trustworthy original must refuse, byte-identically.
make_stock
cp "$ROOT/backend/probe.py" "$TMP/extras/probe.py"
snapshot_tree "$TMP/extras" "$TMP/before.hashes"
if python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$TMP/extras" >"$TMP/refuse.log" 2>&1; then
  echo 'expected target-without-original refusal' >&2; exit 1
fi
snapshot_tree "$TMP/extras" "$TMP/after.hashes"
cmp "$TMP/before.hashes" "$TMP/after.hashes"
test ! -e "$TMP/extras/mb_bak"
grep -q 'no trustworthy .mb_baseline exists' "$TMP/refuse.log"

# 4. Unknown third-party current hash must refuse, byte-identically.
make_stock
printf '\n# third-party mutation\n' >> "$TMP/extras/probe.py"
snapshot_tree "$TMP/extras" "$TMP/before.hashes"
if python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$TMP/extras" >"$TMP/refuse.log" 2>&1; then
  echo 'expected unknown first-takeover refusal' >&2; exit 1
fi
snapshot_tree "$TMP/extras" "$TMP/after.hashes"
cmp "$TMP/before.hashes" "$TMP/after.hashes"
test ! -e "$TMP/extras/mb_bak"
grep -q 'First-takeover provenance refusal' "$TMP/refuse.log"

# 5. Unknown file using the originally-absent Safe_Homing name must also refuse.
make_stock
printf '# unrelated third-party module\n' > "$TMP/extras/M_Bamboo_Safe_Homing.py"
snapshot_tree "$TMP/extras" "$TMP/before.hashes"
if python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$TMP/extras" >"$TMP/refuse.log" 2>&1; then
  echo 'expected originally-absent-name collision refusal' >&2; exit 1
fi
snapshot_tree "$TMP/extras" "$TMP/after.hashes"
cmp "$TMP/before.hashes" "$TMP/after.hashes"
test ! -e "$TMP/extras/mb_bak"
grep -q 'possible user/third-party file' "$TMP/refuse.log"

# 6. A forged/unknown legacy baseline must not become trusted merely by filename.
make_stock
cp "$ROOT/backend/probe.py" "$TMP/extras/probe.py"
printf '# forged legacy baseline\n' > "$TMP/extras/probe.py.mb_baseline"
snapshot_tree "$TMP/extras" "$TMP/before.hashes"
if python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$TMP/extras" >"$TMP/refuse.log" 2>&1; then
  echo 'expected unknown legacy-baseline refusal' >&2; exit 1
fi
snapshot_tree "$TMP/extras" "$TMP/after.hashes"
cmp "$TMP/before.hashes" "$TMP/after.hashes"
test ! -e "$TMP/extras/mb_bak"
grep -q 'Legacy baseline provenance refusal' "$TMP/refuse.log"

echo 'first-takeover provenance matrix: PASS'

# 7. Known M_Bamboo lineage + no legacy baseline may recover the original only
#    from the standard Sovol factory mirror, and only with exact stock hashes.
STD="$TMP/home/sovol/klipper/klippy/extras"
MIR="$TMP/home/sovol/zhongchuang/MKSDEB/home/sovol/klipper/klippy/extras"
rm -rf "$TMP/home"
mkdir -p "$STD" "$MIR"
cp "$FIX"/*.py "$MIR/"
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py M_Bamboo_Safe_Homing.py; do
  cp "$ROOT/backend/$f" "$STD/$f"
done
python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$STD" >/dev/null
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py; do
  cmp "$STD/mb_bak/$f" "$FIX/$f"
done
python3 - "$STD/mb_bak/MANIFEST.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
for n,v in m['files'].items():
    if n == 'M_Bamboo_Safe_Homing.py':
        assert v['state']=='absent' and v['provenance']=='known-M_Bamboo-created'
    else:
        assert v['state']=='present'
        assert v['provenance']=='validated-sovol-factory-mirror'
PY

# 8. A polluted legacy baseline must be ignored only when the exact stock
#    factory mirror independently proves the original bytes.
rm -rf "$TMP/home"
mkdir -p "$STD" "$MIR"
cp "$FIX"/*.py "$MIR/"
for f in ldc1612.py probe_eddy_current.py probe.py z_offset_calibration.py M_Bamboo_Safe_Homing.py; do
  cp "$ROOT/backend/$f" "$STD/$f"
done
printf '# polluted historical M_Bamboo runtime, not stock\n' > "$STD/ldc1612.py.mb_baseline"
python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$STD" >/dev/null
cmp "$STD/mb_bak/ldc1612.py" "$FIX/ldc1612.py"
python3 - "$STD/mb_bak/MANIFEST.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
v=m['files']['ldc1612.py']
assert v['provenance']=='validated-sovol-factory-mirror-after-invalid-legacy'
PY

# 9. Factory mirror presence must never authorize an unknown current file.
rm -rf "$TMP/home"
mkdir -p "$STD" "$MIR"
cp "$FIX"/*.py "$STD/"
cp "$FIX"/*.py "$MIR/"
printf '\n# third-party mutation\n' >> "$STD/probe.py"
snapshot_tree "$STD" "$TMP/before.hashes"
if python3 "$ROOT/installer.py" eddy_safety --apply --no-restart --extras-dir "$STD" >"$TMP/refuse.log" 2>&1; then
  echo 'expected unknown-current refusal despite stock factory mirror' >&2; exit 1
fi
snapshot_tree "$STD" "$TMP/after.hashes"
cmp "$TMP/before.hashes" "$TMP/after.hashes"
test ! -e "$STD/mb_bak"
grep -q 'First-takeover provenance refusal' "$TMP/refuse.log"

echo 'factory-mirror provenance recovery matrix: PASS'
