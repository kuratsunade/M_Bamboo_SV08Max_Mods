#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_BASE="${OUT_BASE:-$HOME/M_Bamboo_EAR_Public_Test_Toolkit/exports}"
OUT="$OUT_BASE/ear-public-$STAMP"
mkdir -p "$OUT"

cp "$SCRIPT_DIR/VERSION" "$OUT/VERSION.txt" 2>/dev/null || true
sha256sum /home/sovol/klipper/klippy/extras/ldc1612.py \
          /home/sovol/klipper/klippy/extras/probe_eddy_current.py \
          > "$OUT/backend_sha256.txt" 2>&1 || true

for f in \
  /home/sovol/printer_data/logs/klippy.log \
  /home/sovol/printer_data/logs/moonraker.log; do
  if [ -f "$f" ]; then
    cp "$f" "$OUT/"
  fi
done

if [ -d "$HOME/M_Bamboo_EAR_Public_Test_Toolkit/results" ]; then
  cp -a "$HOME/M_Bamboo_EAR_Public_Test_Toolkit/results" "$OUT/" 2>/dev/null || true
fi

uname -a > "$OUT/system.txt" 2>&1 || true
date -Is >> "$OUT/system.txt"

tar -C "$OUT_BASE" -czf "$OUT.tar.gz" "$(basename "$OUT")"
echo "Export: $OUT.tar.gz"
