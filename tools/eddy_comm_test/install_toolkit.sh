#!/bin/bash
set -euo pipefail
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DST="/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit"
CFG_DIR="/home/sovol/printer_data/config"
PRINTER_CFG="$CFG_DIR/printer.cfg"
SOAK_CFG="$CFG_DIR/M_Bamboo_Soak.cfg"
BEGIN="# >>> M_Bamboo_EAR_PUBLIC_TOOLKIT BEGIN >>>"
END="# <<< M_Bamboo_EAR_PUBLIC_TOOLKIT END <<<"
"$SRC_DIR/preflight.sh"
[ -f "$PRINTER_CFG" ] || { echo "ERROR: missing $PRINTER_CFG"; exit 3; }
# Refuse to replace an unrelated M_Bamboo_Soak.cfg.
if [ -f "$SOAK_CFG" ]; then
  current="$(sha256sum "$SOAK_CFG" | awk '{print $1}')"
  packaged="$(sha256sum "$SRC_DIR/M_Bamboo_Soak.cfg" | awk '{print $1}')"
  if [ "$current" != "$packaged" ] && ! grep -q 'M_Bamboo EAR Public Test Toolkit v0.1.1' "$SOAK_CFG"; then
    echo "ERROR: refusing to overwrite existing unknown $SOAK_CFG"
    exit 4
  fi
fi
cp -p "$SRC_DIR/M_Bamboo_Soak.cfg" "$SOAK_CFG"
python3 - "$PRINTER_CFG" "$BEGIN" "$END" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); begin=sys.argv[2]; end=sys.argv[3]
text=p.read_text()
block=begin+'\n[include M_Bamboo_Soak.cfg]\n'+end
bs=text.find(begin); es=text.find(end)
if bs >= 0:
    if es < bs: raise SystemExit('ERROR: malformed existing toolkit marker block')
    es += len(end)
    text=text[:bs].rstrip('\n')+'\n\n'+block+'\n'+text[es:].lstrip('\n')
else:
    text=text.rstrip('\n')+'\n\n'+block+'\n'
p.write_text(text)
PY
rm -rf "$DST.tmp"
mkdir -p "$DST.tmp"
cp -a "$SRC_DIR"/. "$DST.tmp"/
rm -rf "$DST"
mv "$DST.tmp" "$DST"
chmod +x "$DST"/*.sh
printf '%s\n' "Installed: $DST" "Installed cfg: $SOAK_CFG" "Backend policy: READ-ONLY; klippy/extras was not modified." "Run Klipper RESTART, then: M_BAMBOO_SOAK_STATUS or M_BAMBOO_CHURN_MATRIX_START PASSES_PER_CELL=5"
