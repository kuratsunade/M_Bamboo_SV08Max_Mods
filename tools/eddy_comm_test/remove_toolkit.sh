#!/bin/bash
set -euo pipefail
DST="/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit"
if [ -d "$DST" ]; then
  rm -rf "$DST"
  echo "Removed: $DST"
else
  echo "Toolkit is not installed: $DST"
fi
echo "Backend policy: /home/sovol/klipper/klippy/extras was not modified."
