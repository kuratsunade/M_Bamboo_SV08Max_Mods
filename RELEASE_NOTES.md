# M_Bamboo_SV08Max_Mods — v1.0.0-rc2

[English](RELEASE_NOTES.md) | [简体中文](RELEASE_NOTES_CN.md)

RC2 expands the initial production package from Safe Home only to two feature-aware modules.

## Safe Home

- Keeps the validated genuine HOME_Z recalibration path.
- Keeps the factory-bootstrap boundary: missing Eddy calibration aborts instead of falling back to `Zmax + 15` / approximately `Z520`.
- Adds formal ownership of `[stepper_z] position_min: -1` as a Safe Home safety dependency.
- Continues to preserve touchscreen G28 compatibility.
- Does not modify `probe_eddy_current.py` or MCU firmware.

## Config Optimization

New `config_optimization` feature:

- `max_velocity 700 → 400`
- `max_accel 40000 → 15000`
- X/Y TMC5160 `run_current 3.0 → 2.3`
- QGL `speed 400 → 200`
- QGL `retries 15 → 5`
- QGL `max_adjust 20 → 5`
- Adaptive Mesh `PGP=0 → PGP=1`
- Randomized/cross-hatch `CLEAN_NOZZLE`
- `START_PRINT` acceleration and two-stage current-Z Z-offset verification

Config Optimization depends on Safe Home because the START_PRINT calibration calls use Safe Home's validated current-Z semantics.

## Installer

- Adds `safe_home`, `config_optimization`, and `all` feature selection.
- `all` installs in dependency order.
- Adds feature-scoped bounded previous-version snapshots for shared config files.
- Keeps `.mb_baseline` as the persistent first-seen baseline.
- Bootstrap downloads a full snapshot, verifies `SHA256SUMS`, runs the installer, and cleans its temporary directory.

## Documentation

- English and Simplified Chinese README pages are separated and cross-linked.
- English and Simplified Chinese Release Notes are separated and cross-linked.
- Adds an explicit AI-assisted development disclosure.
- Adds Config Optimization documentation.
