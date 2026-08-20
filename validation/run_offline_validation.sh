#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
rm -rf backend/__pycache__ validation/__pycache__ __pycache__

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

echo '[1/10] RC4 release-installer transaction matrix'
sh validation/test_release_installer_v2.sh

echo '[2/10] legacy backup migration matrix'
sh validation/test_legacy_backup_migration.sh

echo '[3/10] transport pre-arm state machine'
python3 validation/test_transport_preflight.py

echo '[4/10] public interface registry EN/CN'
python3 validation/validate_interface_registry.py

echo '[5/10] backend safety invariants'
[ "$(sha256sum backend/homing.py | awk '{print $1}')" = "e4a069d0fd4c91a150788b325af9c87d7d0c804ecf16f536e19e7e6b5a3bfedb" ] \
    || fail 'homing.py no longer matches exact ES-R3 reference'
[ ! -e backend/bed_mesh.py ] || fail 'bed_mesh.py unexpectedly included'
[ ! -e backend/mcu.py ] || fail 'mcu.py unexpectedly included'
grep -q 'preflight_transport_ready' backend/probe_eddy_current.py || fail 'pre-arm gate missing'
grep -q 'preflight_safe_home_z' backend/M_Bamboo_Safe_Homing.py || fail 'Safe Home pre-arm gate missing'
grep -q 'quarantine_transport_stream' backend/ldc1612.py || fail 'forced LDC stream quarantine missing'
grep -q 'remove_client' backend/ldc1612.py || fail 'deterministic LDC client cleanup missing'
grep -q 'M_BAMBOO_EDDY_RECOVERY_CHECK' backend/probe_eddy_current.py || fail 'recovery command missing'
grep -q 'Transport faults this session' backend/probe_eddy_current.py || fail 'transport statistics missing'
grep -q 'Forced LDC stream quarantines' backend/probe_eddy_current.py || fail 'quarantine diagnostics missing'
grep -q 'validate_persistent_probe_config' backend/probe.py || fail 'probe persistence guard missing'
grep -q 'validate_persistent_probe_config' backend/probe_eddy_current.py || fail 'Eddy persistence guard missing'
if grep -q 'if fault_seq_start:' backend/ldc1612.py; then
    fail 'historical fault sequence still permanently blocks drive-current calibration'
fi
if grep -q 'configfile.set.*reg_drive_current.*0' backend/probe_eddy_current.py; then
    fail 'legacy SENSOR_ERROR drive-current-zero mutation returned'
fi

echo '[6/10] Python 3.9 grammar / compile-to-temp'
TMP=$(mktemp -d /tmp/M_Bamboo_RC4_compile.XXXXXX)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
python3 - "$TMP" <<'PY'
import ast, py_compile, sys
from pathlib import Path
out = Path(sys.argv[1])
files = [Path('installer.py')] + sorted(Path('backend').glob('*.py')) + sorted(Path('validation').glob('*.py'))
for i, p in enumerate(files):
    src = p.read_text(encoding='utf-8')
    ast.parse(src, filename=str(p), feature_version=(3, 9))
    py_compile.compile(str(p), cfile=str(out / ('%03d.pyc' % i)), doraise=True)
print('PASS: Python 3.9 grammar and compile-to-temp')
PY
rm -rf "$TMP"
trap - EXIT HUP INT TERM
if find . \( -name '__pycache__' -o -name '*.pyc' \) -print | grep -q .; then
    fail 'compiled Python artifacts present in package'
fi

echo '[7/10] RC4 docs / installer contract'
for f in README.md README_CN.md RELEASE_NOTES.md RELEASE_NOTES_CN.md MANIFEST.md VERSION_MAP.md VALIDATION.md \
         docs/COMMAND_REFERENCE.md docs/COMMAND_REFERENCE_CN.md docs/TECHNICAL_FAQ.md docs/TECHNICAL_FAQ_CN.md \
         docs/DEPLOYMENT_AND_ROLLBACK.md installer.py installer_manifest.json install.sh; do
    [ -f "$f" ] || fail "required release file missing: $f"
done
# README keeps only compact current-release identity in the quick-about header; implementation-specific detail belongs in Release Notes / technical docs.
grep -q 'RELEASE_NOTES.md' README.md || fail 'README missing Release Notes link'
grep -q 'RELEASE_NOTES_CN.md' README_CN.md || fail 'README_CN missing Release Notes link'
grep -q './install.sh all --apply' README.md || fail 'README missing primary install flow'
grep -q './install.sh all --apply' README_CN.md || fail 'README_CN missing primary install flow'
grep -q 'Current Release Candidate:.*v1.0.0-rc4' README.md || fail 'README missing current RC quick-about metadata'
grep -q '当前 Release Candidate：.*v1.0.0-rc4' README_CN.md || fail 'README_CN missing current RC quick-about metadata'
grep -q 'Runtime Safety:.*ES-R4-EC2-FS1.1' README.md || fail 'README missing runtime-safety quick-about metadata'
grep -q 'Runtime Safety：.*ES-R4-EC2-FS1.1' README_CN.md || fail 'README_CN missing runtime-safety quick-about metadata'
# Version/runtime identifiers are permitted in the quick-about header. Keep the body narrative release-agnostic.
for f in README.md README_CN.md; do
    body=$(awk 'BEGIN{meta=0} /^## /{meta=1} meta{print}' "$f")
    if printf '%s\n' "$body" | grep -E 'v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+|ES-R[0-9]+-EC[0-9]+-FS[0-9]+' >/dev/null; then
        fail "$f repeats concrete release/runtime identifiers outside quick-about metadata"
    fi
done
grep -q 'v1.0.0-rc4' RELEASE_NOTES.md || fail 'Release Notes missing RC4'
grep -q 'v1.0.0-rc4' RELEASE_NOTES_CN.md || fail 'Chinese Release Notes missing RC4'
grep -q 'mb_bak' docs/DEPLOYMENT_AND_ROLLBACK.md || fail 'deployment doc missing centralized mb_bak policy'
grep -q 'no persistent' docs/DEPLOYMENT_AND_ROLLBACK.md || grep -q 'NO persistent' docs/DEPLOYMENT_AND_ROLLBACK.md || fail 'deployment doc missing no-persistent-cfg-backup policy'
# RC4 may mention legacy .mb_baseline only as migration input; it must never create
# previous-version slots or advertise the old two-slot policy as active behavior.
if grep -n -E '\.last_mb_' installer.py >/dev/null; then
    fail 'installer still implements .last_mb_* persistent backup slots'
fi
if grep -R -n --exclude='RELEASE_NOTES.md' --exclude='RELEASE_NOTES_CN.md' --exclude-dir='.git' \
      -E 'feature-scoped bounded previous|fixed rollback slot|creates previous-version|keeps previous-version' \
      README.md README_CN.md MANIFEST.md VERSION_MAP.md VALIDATION.md docs installer_manifest.json 2>/dev/null; then
    fail 'active release docs still describe old previous-version persistent backup policy'
fi

echo '[8/10] FS1.1 status diagnostic regression'
python3 - <<'PY'
import ast
from pathlib import Path
mod = ast.parse(Path('backend/probe_eddy_current.py').read_text())
func = next(n for n in ast.walk(mod) if isinstance(n, ast.FunctionDef) and n.name == 'get_diagnostic_report')
assign = []
uses = []
for n in ast.walk(func):
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'raw' for t in n.targets):
        assign.append(n.lineno)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == 'raw' and n.func.attr == 'get':
        uses.append(n.lineno)
assert assign and uses and min(assign) < min(uses), (assign, uses)
print('PASS: FS1.1 status raw diagnostic snapshot initialized before use')
PY

echo '[9/10] first-takeover provenance matrix'
sh validation/test_first_takeover_provenance.sh

echo '[10/10] Hardware Cooling ownership matrix'
sh validation/test_hardware_cooling.sh

echo 'PASS: v1.0.0-rc4 offline release gates'

