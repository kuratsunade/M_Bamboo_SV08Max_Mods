# M_Bamboo_SV08Max_Mods RC5 Development Version Map

## Release identity

- Project release: `1.0.0-rc5-dev`; public baseline: `v1.0.0-rc4`
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
  5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29
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

## Current validation

See [RC5 evidence](docs/RC5_TEST_EVIDENCE.md) and [Validation](VALIDATION.md). SR1 startup coordination, RS1 scan session lifetime protection and GR1 generic recovery share the unchanged ES-R4-EC2-FS1.1 safety label. That label alone does not identify the runtime bytes.

One natural QGL raw34 automatic recovery passed on the combined candidate. Active rapid scan fault coverage remains pending. Direct stock installation and incomplete START_PRINT restore are release blockers.

Development migration identities remain in installer.py and installer_manifest.json; they are not public compatibility claims. See [lineage policy](docs/RC5_LINEAGE_POLICY.md).
