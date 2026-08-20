# M_Bamboo_SV08Max_Mods v1.0.0-rc4 Validation

This **Release Candidate** has passed the RC4 installer/package offline gates, substantial real-machine healthy-path validation, one real old-lineage installer migration using exact-SHA256 Sovol factory-mirror recovery, and one naturally occurring FS1.1 raw-34 quarantine/recovery path end-to-end on hardware. It remains an RC because broader repeated natural-fault soak and long-term field confidence are still in progress.

## Passed offline checks

- Python bytecode compilation for all candidate backend files.
- `homing.py` remains byte-identical to exact ES-R3 payload.
- `probe.py` now has one generic persistent-config validation hook used by Eddy safety before `PROBE_CALIBRATE` / `Z_OFFSET_APPLY_PROBE` writes pending config.
- No `bed_mesh.py` or MCU firmware file is included/modified.
- Public Safe Home G-code names remain unchanged.
- ZC-FR1 HOME-FIRST path now uses the atomic Safe Home real-Z-reference API.
- Stock/Sovol `SENSOR_ERROR -> reg_drive_current=0` mutation is absent from candidate `probe_eddy_current.py`.
- Structured I2C bit decoding and monotonic `transport_fault_seq` are present.
- Scan transaction does not request trsync stop unless `trsync_active` is true.


## EC2 release-readiness audit additions

- Pending serial-thread → reactor transport-fault gap is explicitly gated before new Eddy operations.
- Fault classification is monotonic in severity; direct I2C evidence can upgrade an earlier `PROBE_NO_TRIGGER`.
- First-fault state/reason are retained separately from the strongest current fault.
- Drive-current calibration no longer restores an I2C-read `old_config`; it restores the known Sovol measurement-mode CONFIG value.
- A previous transport fault in the same Klipper session blocks drive-current calibration until `FIRMWARE_RESTART`.
- Distribution package must contain no `__pycache__` or `.pyc` files.
- `M_BAMBOO_EDDY_STATUS` now exposes a bounded relative-time event timeline for the latest transaction.
- Interface registry gate (`validation/validate_interface_registry.py`) passes for both EN/CN references, including backend-registered `Z_OFFSET_APPLY_PROBE`.

## Required hardware validation

See `docs/ES_R4_ENGINEERING_CANDIDATE.md`.

## Command Reference coverage validation

The project-level Command Reference was expanded after EC2 implementation review.

- All candidate backend `M_BAMBOO_*` commands are documented in EN/CN.
- `Z_OFFSET_CALIBRATION`, `RUN_PROBE_VIR_CONTACT`, `LDC_CALIBRATE_DRIVE_CURRENT`, `PROBE_EDDY_CURRENT_CALIBRATE`, and `EDDY_QUERY_LOOP` are documented.
- Project-managed/wrapped macros `G28`, `CLEAN_NOZZLE`, `QUAD_GANTRY_LEVEL`, `BED_MESH_CALIBRATE`, and `START_PRINT` are documented.
- Formal Diagnostics `XY_STRESS_*` macros are documented and owned by the installer; `all` installs them without executing stress tests.
- M_Bamboo-added Z-offset parameters are documented with defaults/ranges.
- Safe Home, Eddy Safety, and config-optimization managed configuration surfaces are summarized.
- `G80` was audited across the recovered current project/candidate artifacts; no active registration/macro/override was found, so no behavior is invented for it.

- Manual Eddy calibration is preflight-checked before motion and before pending calibration persistence.
- `PROBE_CALIBRATE` / `Z_OFFSET_APPLY_PROBE` use the Eddy persistent-config validation hook.
- ZC-FR1 guarded sensor calls explicitly invalidate Z on early safety aborts before `HomingMove`.

## Release documentation gate

- `README.md` and `README_CN.md` are present as package entry points.
- `RELEASE_NOTES.md` and `RELEASE_NOTES_CN.md` are present.
- Release Notes are append-only version history and include `ES-R4-EC2`, `ES-R4-EC1`, `v1.0.0-rc3`, `v1.0.0-rc2`, and `v1.0.0-rc1`.
- Release Notes are treated separately from Technical FAQ and Command Reference: version deltas, design rationale, and interface usage have distinct documentation ownership.
- Offline validation now fails if package entry pages or required release-history sections are missing.

## EC2 hardware-validation recovery revision

Additional offline gates now cover the no-motion `M_BAMBOO_EDDY_RECOVERY_CHECK`, explicit `TRANSPORT_FAULT -> TRANSPORT_RECOVERED` state, one-shot Safe Home recovery integration, and transport-specific error wording for an ES-R4-requested trsync SENSOR_ERROR stop. Interface registry coverage is now 28 required interfaces in both English and Chinese references.

The recovery check intentionally does not run automatically from an active-motion transport-fault callback. It performs repeated identity reads with reactor settle windows and a fault-sequence guard. The healthy path additionally has a bounded **pre-arm** no-motion readiness gate; offline tests cover clean pass, transient fault -> two clean windows -> recovery, persistent pre-arm failure, delayed-callback sequence de-duplication, and the distinction between pre-arm recovery (no G28 required) and active-motion recovery (armed G28 required). One naturally occurring active-motion raw-34 event has now validated the stricter recovery-check -> armed-G28 path on hardware; broader soak remains required before stable promotion.


### FS1 additions
- deterministic LDC bulk-client removal gate present;
- runtime transport-stream quarantine gate present;
- forced-quarantine diagnostics present;
- Transport Hardening R3 -> FS1 -> exact rollback simulation passes.

## Hardware validation status refresh — 2026-08-20

Healthy-path hardware validation is now complete enough for normal-print soak: repeated Safe Home/contact/nozzle-clean/Z-calibration flows, QGL, adaptive rapid mesh, final XY re-home, complete START_PRINT, a real cube print, END_PRINT including the stock `clear_plr` cleanup hook, and post-print status all passed. The latest session accumulated 30 pre-arm checks with zero transport faults, zero transient recoveries, zero pre-arm failures, zero forced quarantines, and zero repeated-fault suppressions.

A subsequent natural raw-34 event closed that previously missing one-event fault-path gate. During active contact verification, raw `34` (`I2C_BUS_NACK | I2C_BUS_BUSY`) produced an active trsync stop request, transaction failure, Z de-trust, and one forced LDC stream quarantine. The host remained responsive; `M_BAMBOO_EDDY_RECOVERY_CHECK` passed with three correct identity reads and no new fault sequence; one armed `G28` completed `ARMED RECOVERY SUCCESS`; the remaining print-preparation chain then completed and printing started without firmware reset.

This validates the intended end-to-end recovery architecture on one naturally occurring event. Stable promotion still requires continued natural-fault soak rather than another specific missing mechanism demonstration.


## RC4 installer schema-v2 validation — 2026-08-20

The release installer was rebuilt around the final backup/restore policy:

- cfg/macros create no persistent whole-file backup;
- every managed cfg mutation has an explicit inverse;
- stock `[homing_override]`, `G28`, and `CLEAN_NOZZLE` are reconstructed from release-owned restore templates;
- `SAVE_CONFIG` tail is preserved byte-for-byte by the transformer;
- backend Python uses exactly one centralized `extras/mb_bak/` original-state archive;
- legacy `.mb_baseline` is migration input only;
- M_Bamboo-added backend files originally absent are recorded as absent and deleted on full restore;
- write/delete operations have immediate `/tmp` transaction rollback; successful rollback cleans scratch, while rollback failure retains the exact recovery snapshot path;
- Python compile checks write bytecode into the temporary transaction directory, never live `__pycache__`.

Offline matrix includes clean stock install, idempotent second install, injected post-write failure with byte-exact rollback, full restore, legacy-baseline migration, unknown-mutated backend refusal, SAVE_CONFIG-tail preservation, Python 3.9 syntax checks, public-interface registry checks, transport-preflight state-machine tests, backend target hashes, and no-cache packaging checks.


## RC4 scope normalization refresh

- First-takeover provenance classification is exact-SHA256 based, can recover a recognized M_Bamboo lineage from an independently hash-validated Sovol factory mirror when a legacy baseline is missing or polluted, and still refuses unknown third-party backends before persistent backup creation.
- Real-machine migration validated this path: existing RC4 backend lineage with no `mb_bak` created a centralized original archive from the exact Sovol factory mirror; `ldc1612.py` recorded stock SHA256 `5992b2189b40bc4ae7a33d804a5584f74620e3db6d75ab3f6151daca2c895547`, while the originally absent `M_Bamboo_Safe_Homing.py` was recorded as `state=absent`.
- An unknown same-name file at an originally-absent M_Bamboo backend path is refused.
- Diagnostics is a formal feature and is included by `all`; it never runs automatically.
- Hardware Cooling is a formal explicit-only feature and is never included by `all`.
- PLR is not included in RC4.
- Generic historical downgrade is not an RC4 feature or validation gate; the supported path is Full Restore followed by the target historical release installer.
- Transaction scratch is retained if automatic rollback itself fails, preventing loss of the last byte-exact pre-transaction snapshot.
