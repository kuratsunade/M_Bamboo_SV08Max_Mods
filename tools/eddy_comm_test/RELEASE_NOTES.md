# Release Notes — M_Bamboo EAR Public Test Toolkit v0.1.1

## Fixed from v0.1.0

- Restored `M_Bamboo_Soak.cfg` as the core Klipper-side test state machine.
- Restored established soak/matrix commands, counters, stage attribution and bounded RC4 recovery orchestration.
- `run_matrix.sh` is now only a convenience wrapper that starts the Klipper-side matrix instead of reimplementing the matrix in shell.
- Added marker-managed install/remove of `[include M_Bamboo_Soak.cfg]`.
- Removed the dependency on HF1/HF2/HF2.1 Python logger backends by providing config-only no-op `M_BAMBOO_EAR_LOG_*` compatibility hooks.
- Kept strict RC4 backend hash preflight.
- No `klippy/extras/*.py` payloads are included or modified.

## Baseline

M_Bamboo_SV08Max_Mods v1.0.0-rc4.
