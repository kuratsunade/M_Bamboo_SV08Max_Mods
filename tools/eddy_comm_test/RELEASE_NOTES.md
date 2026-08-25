# Release Notes — M_Bamboo EAR Public Test Toolkit v0.1.0

## Purpose

Publish the reproducible field-test portion of the M_Bamboo Eddy communication investigation without shipping engineering Klipper Python backends.

## Included

- RC4 SHA256 preflight for `ldc1612.py` and `probe_eddy_current.py`
- contact-probe churn matrix runner
- configurable burst / dwell / passes
- RC4 Eddy status capture
- timestamped evidence collector
- manual wrapper for the existing RC4 recovery check
- self-contained installer/remover for the tester directory
- English and Chinese documentation

## Explicitly excluded

No modified `klippy/extras/*.py` files are included or installed.

The public tester does not contain HF1/HF2/HF2.1 engineering versions of:

- `probe_eddy_current.py`
- `ldc1612.py`
- engineering logger backend
- lifecycle instrumentation backend

## Reference matrix

```text
BURST=8
PASSES_PER_CELL=5
DWELLS_MS=0 10 25 50 75 100
```

The nominal dwell is an additional post-lift delay, not the complete LDC STOP-to-next-START interval. Results should be treated as field reproduction data, not as proof of a precise timing threshold.

## Safety

The runner never retries a failed contact transaction. RC4 Eddy Safety remains authoritative for fault classification and recovery.

## Baseline

M_Bamboo_SV08Max_Mods v1.0.0-rc4
