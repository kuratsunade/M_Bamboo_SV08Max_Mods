#!/bin/bash
set -euo pipefail
STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="$HOME/M_Bamboo_EAR_Public_Test_Toolkit/exports"
OUT="$BASE/ear-public-$STAMP"
mkdir -p "$OUT"
cp "$HOME/M_Bamboo_EAR_Public_Test_Toolkit/VERSION" "$OUT/VERSION.txt" 2>/dev/null || true
sha256sum /home/sovol/klipper/klippy/extras/ldc1612.py \
          /home/sovol/klipper/klippy/extras/probe_eddy_current.py \
          > "$OUT/backend_sha256.txt" 2>&1 || true
cp /home/sovol/printer_data/config/M_Bamboo_Soak.cfg "$OUT/" 2>/dev/null || true
for f in /home/sovol/printer_data/logs/klippy.log /home/sovol/printer_data/logs/moonraker.log; do
  [ -f "$f" ] && cp "$f" "$OUT/"
done
uname -a > "$OUT/system.txt" 2>&1 || true
date -Is >> "$OUT/system.txt"
tar -C "$BASE" -czf "$OUT.tar.gz" "$(basename "$OUT")"
echo "Export: $OUT.tar.gz"
