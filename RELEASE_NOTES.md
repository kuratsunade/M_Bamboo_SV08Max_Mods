# M_Bamboo_SV08Max_Mods — v1.0.0-rc1

First release candidate for the `safe_home` feature.

## Safe Home v1.0.0

- Adds `M_Bamboo_Safe_Homing.py`.
- Replaces the active Sovol `z_offset_calibration.py` with the validated M_Bamboo runtime version.
- Removes active `[homing_override]` and leaves an explicit managed tombstone.
- Preserves the touchscreen `G28` ABI through a managed macro.
- Uses genuine Z homing before normal Eddy recalibration when Z is unknown.
- Keeps explicit `USE_CURRENT_Z=1` refinement semantics for callers with a trustworthy Z reference.
- Removes the Sovol `Zmax + 15` / approximately `Z520` bootstrap path from the M_Bamboo runtime backend.
- Treats missing Eddy calibration as an explicit runtime/install boundary: complete Sovol factory Eddy calibration first.
- Does not modify `probe_eddy_current.py` or MCU firmware.

## Installer

- Dry-run by default.
- Validates Eddy calibration data before install.
- Recognizes the stock snapshot and validated H3 development backend hashes.
- Uses bounded `.mb_baseline` and `.last_mb_ver` backups.
- Migrates development managed markers to production Safe Home markers.
- Compiles Python payloads before and after installation.
- Restarts Klipper and checks service state by default.
- Automatically rolls back exact pre-apply bytes if installation validation/restart fails.
- Supports `--rollback`, `--restore-baseline`, `--raw-diff`, and `--no-restart`.

## RC status

Normal Home All, touchscreen homing, HOME-FIRST Eddy recalibration, contact verification, SAVE_CONFIG and restart behavior have been validated during development.

Before tagging final v1.0.0, run the production package regression checklist, including a controlled missing-Eddy runtime fail-safe test.
