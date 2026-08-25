#!/bin/bash
set -euo pipefail
EXTRAS="/home/sovol/klipper/klippy/extras"
EXPECT_LDC="aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04"
EXPECT_PROBE="6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e"
fail=0
check_hash() {
  local path="$1" expected="$2" label="$3"
  if [ ! -f "$path" ]; then
    echo "FAIL: missing $label: $path"
    fail=1
    return
  fi
  local actual
  actual="$(sha256sum "$path" | awk '{print $1}')"
  printf '%-24s %s\n' "$label" "$actual"
  if [ "$actual" != "$expected" ]; then
    echo "  expected RC4: $expected"
    fail=1
  fi
}
echo "=== M_Bamboo EAR Public Test Toolkit v0.1.1 preflight ==="
check_hash "$EXTRAS/ldc1612.py" "$EXPECT_LDC" "ldc1612.py"
check_hash "$EXTRAS/probe_eddy_current.py" "$EXPECT_PROBE" "probe_eddy_current.py"
if [ "$fail" -ne 0 ]; then
  echo "RC4 backend check: FAIL"
  echo "Refusing installation/reference test because backend differs from RC4 baseline."
  exit 2
fi
echo "RC4 backend check: PASS"
