#!/bin/bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DST="/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit"

"$SRC_DIR/preflight.sh"

rm -rf "$DST.tmp"
mkdir -p "$DST.tmp"
cp -a "$SRC_DIR"/. "$DST.tmp"/
rm -rf "$DST"
mv "$DST.tmp" "$DST"
chmod +x "$DST"/*.sh 2>/dev/null || true

echo "Installed: $DST"
echo "Backend policy: READ-ONLY; /home/sovol/klipper/klippy/extras was not modified."
echo "Run: cd $DST && ./run_matrix.sh"
