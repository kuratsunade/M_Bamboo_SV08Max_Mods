#!/bin/bash
set -euo pipefail
DST="/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit"
CFG_DIR="/home/sovol/printer_data/config"
PRINTER_CFG="$CFG_DIR/printer.cfg"
SOAK_CFG="$CFG_DIR/M_Bamboo_Soak.cfg"
BEGIN="# >>> M_Bamboo_EAR_PUBLIC_TOOLKIT BEGIN >>>"
END="# <<< M_Bamboo_EAR_PUBLIC_TOOLKIT END <<<"
if [ -f "$PRINTER_CFG" ]; then
python3 - "$PRINTER_CFG" "$BEGIN" "$END" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); begin=sys.argv[2]; end=sys.argv[3]
text=p.read_text(); bs=text.find(begin); es=text.find(end)
if bs >= 0:
    if es < bs: raise SystemExit('ERROR: malformed toolkit marker block')
    es += len(end)
    left=text[:bs].rstrip('\n'); right=text[es:].lstrip('\n')
    p.write_text(left + ('\n\n'+right if right else '\n'))
    print('Removed printer.cfg toolkit include marker.')
else:
    print('Toolkit include marker not present.')
PY
fi
if [ -f "$SOAK_CFG" ]; then
  if grep -q 'M_Bamboo EAR Public Test Toolkit v0.1.1' "$SOAK_CFG"; then
    rm -f "$SOAK_CFG"
    echo "Removed: $SOAK_CFG"
  else
    echo "WARNING: leaving unknown $SOAK_CFG untouched"
  fi
fi
rm -rf "$DST"
echo "Removed public tester directory: $DST"
echo "Backend policy: klippy/extras was not modified. Run Klipper RESTART to unload tester macros."
