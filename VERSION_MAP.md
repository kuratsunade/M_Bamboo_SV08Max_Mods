# M_Bamboo_SV08Max_Mods v1.0.0-rc4 Version Map

## Release identity

- Project release: `v1.0.0-rc4`
- Status: **Release Candidate**; not stable
- Runtime Eddy safety: `ES-R4-EC2-FS1.1`
- Installer schema: **v2**
- Machine target: Sovol SV08 Max 500x500
- MCU firmware: unchanged

## Runtime lineage

- Eddy Safety: `ES-R4-EC2-FS1.1`
- Safe Home: production M_Bamboo Safe Home + recovery/pre-arm integration
- Z calibration: `ZC-FR1`
- Nozzle cleaning: `NC-R1`
- `probe.py`: ES-R3 base + persistent-config safety hook
- `homing.py`: exact ES-R3 reference; included for audit, not deployed
- `bed_mesh.py`: unchanged / not shipped

## Exact backend targets

```text
ldc1612.py
  aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04
probe_eddy_current.py
  6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e
probe.py
  227d0c6b8527ece1793caf969d5292646ec185f65ca1c679ccf4195515dd529a
M_Bamboo_Safe_Homing.py
  5f85a1a397413a7ab5da28d2b19b586a6d371b49a4793b80bc685d5adb0f9038
z_offset_calibration.py
  1089df132131010f774d40b331fef4ff6ba02252f4b55c107846c6cc0a7a75ce
homing.py (reference only)
  e4a069d0fd4c91a150788b325af9c87d7d0c804ecf16f536e19e7e6b5a3bfedb
```

## Installer / restore policy v2

- Config/macros: no persistent backup; stable managed blocks + explicit inverse transformations.
- Backend Python: one centralized `/home/sovol/klipper/klippy/extras/mb_bak/` original-state archive, created once and never overwritten.
- Existing `.mb_baseline` is accepted only as migration input when establishing the centralized archive on machines already modified by an older M_Bamboo build.
- No new `.mb_baseline`, `.last_mb_*`, or timestamp backup series.
- Immediate failure rollback uses installer-owned `/tmp/M_Bamboo_SV08MAX.*` transaction storage. It is cleaned after success/confirmed rollback, but retained if rollback itself fails.
- Restore means pre-M_Bamboo/original state. RC4 intentionally has no generic downgrade command; install an older release only after Restore, using that release's own exact installer artifact.
- `SAVE_CONFIG` generated content is never modified by the cfg transformer.

## Hardware validation status

Healthy path: **PASS** across repeated Safe Home, contact, CLEAN_NOZZLE, Z calibration, QGL, adaptive rapid mesh, final XY re-home, complete START_PRINT, real cube print, END_PRINT including the stock `clear_plr` cleanup hook, and post-print status.

Latest recorded post-print session: 30 pre-arm checks, 0 transport faults, 0 transient recoveries, 0 pre-arm failures, 0 forced quarantines, 0 repeated-fault suppressions.

Remaining RC limitation: natural FS1.1 transport-fault quarantine/recovery end-to-end hardware validation is pending. This package does not claim raw-34 is eliminated.
