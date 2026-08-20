# M_Bamboo_SV08Max_Mods — Release Notes

[English](RELEASE_NOTES.md) | [简体中文](RELEASE_NOTES_CN.md)

This file is the append-only version history for public releases and engineering candidates. It answers **what changed in each version**. Design rationale belongs in `docs/TECHNICAL_FAQ.md`; command usage belongs in `docs/COMMAND_REFERENCE.md`.

---

## v1.0.0-rc4 — Release Candidate (2026-08-20)

- First-takeover migration can recover trusted original backend bytes from Sovol's factory mirror when a recognized M_Bamboo lineage has a missing or polluted legacy baseline; the mirror is accepted only by exact known-stock SHA256.
- Real-machine migration validated this fallback on an existing M_Bamboo machine: `mb_bak/MANIFEST.json` was created from exact-SHA256 factory originals, while `M_Bamboo_Safe_Homing.py` was correctly recorded as originally absent.

RC4 freezes the currently validated `ES-R4-EC2-FS1.1` runtime and promotes the project from an engineering-only backend package to a whole-project release-candidate installer. Runtime safety Python is unchanged from the validated FS1.1 payload.

### Installer / restore architecture v2

- Configuration files no longer receive persistent whole-file backups. RC4 owns only stable `M_Bamboo_SV08MAX_MOD` managed transformations and restores them by explicit inverse operations.
- Added blocks are removed; replaced stock parameters are restored; removed/replaced stock sections use release-owned exact restore templates. The `SAVE_CONFIG` generated tail is never modified.
- Backend Python keeps exactly one centralized `/home/sovol/klipper/klippy/extras/mb_bak/` original-state archive with `MANIFEST.json`, created once and never overwritten.
- Existing `.mb_baseline` files are accepted only as migration input for older M_Bamboo installations. RC4 creates no new `.mb_baseline`, `.last_mb_*`, or timestamp backup series.
- Install/restore writes are transactional through installer-owned `/tmp/M_Bamboo_SV08MAX.*` scratch storage and roll back exact immediate pre-transaction bytes on failure.
- Python compile verification writes bytecode only to transaction scratch; the release does not intentionally create live `__pycache__`.
- Full Restore is the only release-removal primitive in RC4: it returns M_Bamboo-owned surfaces to the pre-M_Bamboo/original state. RC4 intentionally does not implement a generic historical-downgrade command; users who want an older release restore first, then run that historical release's installer.
- Unknown backend content after M_Bamboo ownership is established is refused rather than overwritten as a guessed lineage.

### Feature ownership and scope

- Formalized `diagnostics` ownership for the exact `XY_STRESS_BASELINE`, `XY_STRESS_RUN`, and `XY_STRESS_CHECK` macro lineage. Diagnostics is included by `all` but never runs automatically.
- Added formal `hardware_cooling` ownership for the validated `[heater_fan bed_fan]` `fan_speed: 0.6` transformation. It is hardware-dependent, explicit-install only, and never included by `all`.
- PLR is deliberately **deferred from RC4**. The stock Sovol checkpoint/coordinate-trust design is not promoted into this release.
- Generic in-installer downgrade is deliberately **out of RC4 scope**. Restore followed by installation of the desired historical artifact is the supported path.

### Hardware evidence

Healthy-path validation now covers repeated G28/Safe Home, contact probing, NC-R1 cleaning, Z calibration, QGL, adaptive rapid mesh, final XY re-home, a complete slicer START_PRINT, a real cube print, END_PRINT including the stock `clear_plr` cleanup hook, and post-print Eddy status. The latest recorded session reached 30 pre-arm checks with zero transport faults, zero transient recoveries, zero pre-arm failures, zero forced quarantines, and zero repeated-fault suppressions.

A subsequent naturally occurring raw-34 (`I2C_BUS_NACK | I2C_BUS_BUSY`) event during active contact verification then validated the missing fault/recovery path end-to-end: active trsync stop request, transaction abort, Z trust invalidation, one forced LDC stream quarantine, responsive host, explicit no-motion recovery check with three valid identity reads, one armed fresh Safe Home `G28`, return to `HEALTHY`, and successful continuation through print preparation into printing without firmware reset.

RC4 therefore no longer has an unobserved natural fault-path mechanism gate. It still does **not** claim raw-34 is eliminated or that one successful recovery event predicts every future timing/fault combination. Continued natural-fault soak remains part of the RC-to-stable evidence requirement.

---

## ES-R4-EC2 — Engineering Candidate

### Fault-storm safety hotfix FS1 (2026-08-19)

- Fixes a real-machine failure observed immediately after `CLEAN_NOZZLE` inside `START_PRINT`: an Eddy/I2C fault could leave the LDC periodic bulk-query stream alive after the owning contact-probe command had aborted, causing an unbounded `ldc1612_i2c_report` / transport-fault storm until power-cycle.
- Adds deterministic Eddy bulk-client removal; session cleanup no longer depends on a future successful sample batch.
- Adds an LDC transport-stream quarantine that forcibly stops the active periodic query and resets `BatchBulkHelper` state on confirmed runtime transport faults, so recovery can later start a clean stream.
- Adds `try/finally` contact-probe cleanup and explicit calibration-client cleanup.
- Suppresses repeated same-episode HARD_COMM_FAULT console spam while retaining monotonic fault counters and last evidence.
- `M_BAMBOO_EDDY_STATUS` now reports forced LDC stream quarantine count/last reason and repeated-message suppression count.
- Installer accepts Transport Hardening R3 as a direct upgrade lineage and validates exact rollback to R3.

**Status:** Offline validated; hardware validation pending.  

### Package/readme/installer refresh before hardware validation

- Rebuilds the package README as a project-level entry point based on the RC-lineage structure: project goals, feature overview, safety model, installation/testing flow, documentation map, boundaries, and a concise overview FAQ.
- Adds a strict `es_r4_ec2` test installer with dry-run by default, status/raw-diff/apply/rollback modes, exact base/target hash recognition, bounded backups, `py_compile`, post-write checksum verification, Klipper host restart/health check, and automatic rollback on failed apply.
- The EC2 test installer intentionally accepts only the recognized RC4/ES-R3 + ZC-FR1/Safe Home lineage or an already-installed EC2 target state; unknown backend hashes are blocked and there is no `--force` mode.
- Keeps manual deployment instructions as a fallback rather than the primary test workflow.

**Lineage:** RC4 development baseline + ES-R3 + ZC-FR1; supersedes ES-R4-EC1 before hardware validation.

### First real transport-fault validation and recovery UX

#### Transport hardening follow-up (2026-08-19)

- Adds a **pre-arm transport quiescence gate** before Safe Home Z homing, normal/contact probe-session startup, Eddy calibration, and bed-mesh scan-session startup. It performs only no-motion LDC identity reads before bed-facing motion or measurement-session startup.
- Healthy preflight exits after one two-read clean window (~75 ms nominal host-side settle budget). If a transient/failed readiness check is observed, motion remains held and the gate requires two consecutive clean windows within a bounded three-attempt sequence before proceeding. There is no unbounded retry loop.
- A transport fault observed inside preflight is recorded and reported immediately but is not allowed to taint a motion transaction because no bed-facing motion has started. If the bounded gate recovers, current Z trust is unchanged and the fault sequence is marked trusted-through without erasing history.
- If preflight cannot establish a stable bus, the requested motion is rejected before Z descent. `M_BAMBOO_EDDY_RECOVERY_CHECK` can then restore transport without requiring a recovery `G28`, because the pre-arm failure did not invalidate Z. Active-motion faults still require the existing explicit recovery-check -> one-shot armed G28 path.
- Adds sequence de-duplication for the pending-sequence vs delayed-reactor-callback race so one I2C report cannot be processed twice and re-latch an already absorbed pre-arm transient.
- Adds session transport statistics (fault count/type/context, pre-arm recovery/failure counts, recovery-check counts, armed-recovery successes) and separates **current transport health** from stale Sovol `err_code/i2c_report_seen` historical telemetry in `M_BAMBOO_EDDY_STATUS`.
- No duplicate-G28 suppression, automatic G28, or retry of an already-started downward transaction is introduced.

- Fixed a real-machine recovery integration bug: `LDC_CALIBRATE_DRIVE_CURRENT` previously treated any historical nonzero `transport_fault_seq` as permanently fatal, so `Z_OFFSET_CALIBRATION` remained blocked even after `RECOVERY_CHECK -> armed G28 -> HEALTHY`. LDC now uses a monotonic trusted-through recovery watermark granted only after the fresh recovery Z home succeeds; any newer transport fault blocks calibration again.
- Fixed partial-upgrade rollback coherence: whenever any EC2 managed file changes, all five backend rollback slots are refreshed before the first write so rollback returns to one coherent pre-apply state.
- The installer now recognizes the first hardware-installed EC2 target hashes as a valid upgrade lineage; no rollback is required before upgrading to this recovery revision.
- A real SV08 Max captured `err_code=34` during back-to-back `G28`, decoded as `I2C_BUS_NACK | I2C_BUS_BUSY`; the current action was tainted/aborted and the active trsync `SENSOR_ERROR` stop request was observed on hardware.
- User-facing semantics now distinguish the ES-R4 transport-abort channel from a proven sensor hardware error: when reason 5 was requested because of I2C evidence, the error is reported as a transport fault / action aborted.
- Added transport states `HEALTHY`, `TRANSPORT_FAULT`, `TRANSPORT_RECOVERED`, and `HARD_COMM_FAULT`; bus recovery is kept separate from transaction validity and Z-coordinate trust.
- Added `M_BAMBOO_EDDY_RECOVERY_CHECK`: no-motion three-pass LDC identity reads, per-read reactor settle windows, and a transport-fault-sequence guard. PASS means transport recovered only; Z remains untrusted.
- A PASS arms exactly one Safe Home Z recovery. Ordinary PROBE/QGL/contact/mesh paths cannot consume the token. Only a successful fresh Z home returns the session to `HEALTHY`; a failed armed recovery requires `FIRMWARE_RESTART`.
- Transport faults now immediately provide actionable recovery guidance instead of presenting BUSY/NACK/TIMEOUT as permanent sensor hardware failure.
- No duplicate-`G28` debounce and no automatic recovery scan/G28 are added in this revision.

### Transport-fault integrity hardening

- Adds an explicit pending/unhandled transport-fault gate so a newly received I2C fault cannot be bypassed during the serial-thread → reactor scheduling window.
- Keeps the monotonic `transport_fault_seq` transaction-integrity model and adds acknowledgement/handled tracking at the Eddy Safety Core boundary.
- Makes fault classification monotonic in severity: stronger direct transport evidence may upgrade an earlier weaker symptom such as `PROBE_NO_TRIGGER`.
- Preserves first-fault evidence separately from the strongest/current fault for diagnostics.
- Keeps active trsync-backed downward probing eligible for `SENSOR_ERROR` stop requests while scan/rapid-scan transactions are tainted/rejected without pretending they own a Z trsync.

### Transaction lifecycle and event tracing

- Makes failed transactions terminally `ABORTED`; later halt-position reconstruction events remain evidence and cannot revive an aborted transaction.
- Records halt-position reconstruction for both homing and ordinary probing paths.
- Keeps probe success provisional until transport-integrity checks and the full probe result path complete.
- Adds a bounded per-transaction fault evidence timeline exposed through `M_BAMBOO_EDDY_STATUS`.
- Records host receive time, reactor handling time, and reactor scheduling delay for transport-fault events to support active-stop latency analysis.

### Persistent calibration safety

- Extends the unified Eddy safety preflight to `PROBE_EDDY_CURRENT_CALIBRATE` before calibration motion and before pending calibration persistence.
- Adds a small generic `probe.py` persistent-config validation hook used by the Eddy backend before `PROBE_CALIBRATE` and `Z_OFFSET_APPLY_PROBE` write pending configuration.
- Keeps `LDC_CALIBRATE_DRIVE_CURRENT` transaction-guarded and prevents transport-tainted results from becoming persistent configuration.
- Stops restoring a potentially transport-corrupted `old_config` after drive-current calibration; restores the known Sovol measurement-mode CONFIG value instead.
- Continues to remove the Sovol runtime `SENSOR_ERROR -> reg_drive_current=0` configuration mutation.

### Z calibration and coordinate-trust safety

- Adds guarded Z-sensor calls in ZC-FR1 so an early safety abort explicitly invalidates Z even when the actual `HomingMove` never starts.
- Prevents the temporary logical Z rebase used by current-Z allowance from surviving as trusted Z after a preflight fault.
- Retains the atomic Safe Home real-Z-reference orchestration introduced in EC1.

### Documentation and release hygiene

- Expands the project-wide Command Reference and adds the previously omitted `Z_OFFSET_APPLY_PROBE` interface.
- Adds machine-checkable EN/CN Command Reference coverage validation.
- Adds this append-only Release Notes history and makes Release Notes presence/version coverage a package validation requirement.
- Adds package `README.md` / `README_CN.md` entry points.
- Adds deployment/rollback and hardware-validation guides.
- Removes `__pycache__` / `.pyc` artifacts from the distribution package.
- Rebuilds patches/checksums and validates patch round-trip against the exact base files.

### Patch surface change from EC1

EC2 intentionally adds `probe.py` as a deployable backend file for the generic persistent-config validation hook.

Still not modified:

- MCU firmware
- `bed_mesh.py`
- `mcu.py`
- `homing.py` remains the exact ES-R3 reference payload

---

## ES-R4-EC1 — Engineering Candidate

**Status:** Superseded by ES-R4-EC2 before hardware validation.

### Eddy transport safety

- Decodes the Sovol STM32 I2C error bitmask instead of treating only `err_code=36` as special.
- Adds monotonic transport-fault sequencing and transaction-local fault snapshots.
- Introduces structured transport-fault evidence and session fault latching in the Eddy Safety Core.
- Prevents any transaction touched by a transport fault from later being accepted as successful.
- Adds an active trsync `SENSOR_ERROR` stop path for armed downward Eddy homing/probing without modifying MCU firmware or `mcu.py`.
- Adds common fault authorization to scan/rapid-scan session creation and transaction taint/rejection semantics for scan faults.
- Selectively backports command-error scan cleanup behavior without replacing `bed_mesh.py`.

### Safe Home recovery orchestration

- Refactors Safe Home into an atomic real-Z-reference sequence so untrusted Z receives positive clearance before XY motion.
- Closes the `HOME_Z` recovery gap where X/Y could remain homed while Z was invalidated near the bed.
- Changes ZC-FR1 HOME-FIRST orchestration to call the atomic Safe Home API instead of `prepare_xy_for_calibration() + cmd_HOME_Z()`.
- Avoids double-hop behavior and keeps existing touchscreen/public G-code names unchanged.
- Marks `prepare_xy_for_calibration()` as internal/deprecated for new callers.

### Calibration safety

- Adds transport-sequence guarding to drive-current calibration.
- Removes the Sovol behavior that set pending `reg_drive_current` to zero after a runtime sensor error.

### Documentation

- Establishes the project-wide Command Reference / Public Interface Registry in English and Simplified Chinese.
- Expands the Technical FAQ with confirmed Sovol error-propagation and I2C design defects.
- Adds initial deployment, rollback, and hardware-validation documentation.

---

## v1.0.0-rc3

RC3 was a package-completeness and installer-UX update after successful RC2 real-machine regression.

### Config Optimization completeness

- Adds formal ownership of `[buffer_stepper filament_buffer]` tuning that RC2 packaging had omitted:
  - `velocity 150 -> 80`
  - `accel 5000 -> 1900`
  - `push_length 25 -> 27`
- Uses the stable `CONFIG_BUFFER_STEPPER` managed block.
- Includes the buffer-stepper settings in feature-scoped backup, idempotency, raw diff, validation, and rollback.

### Installer UX

- Reports that Klipper restart was requested and the service returned `active` after apply.
- Explicitly advises a manual **Firmware Restart** when no normal restart cycle is observed or machine state looks inconsistent.

### Documentation

- Normalizes Gitee bootstrap examples to the repository's `master` branch.

### Safe Home regression carried forward

RC2 real-machine regression covered fresh/repeated G28, individual X/Y/Z homing, touchscreen-style homing, raw X/Y `dZ=0`, HOME-FIRST Eddy recalibration, contact verification, absence of the `Z~520 / Z~500` normal runtime path, SAVE_CONFIG restart, and repeated installer-apply idempotency.

---

## v1.0.0-rc2

RC2 expanded the initial Safe Home-only package into two feature-aware modules.

### Safe Home

- Retains genuine HOME_Z before normal Eddy recalibration when required.
- Keeps the factory-bootstrap boundary: missing Eddy calibration aborts instead of falling back to `Zmax + 15` / approximately `Z520`.
- Adds formal Safe Home ownership of `[stepper_z] position_min: -1` as a Z-safety dependency.
- Continues to preserve touchscreen G28 compatibility.

### Config Optimization

Introduces the `config_optimization` feature with:

- `max_velocity 700 -> 400`
- `max_accel 40000 -> 15000`
- X/Y TMC5160 `run_current 3.0 -> 2.3`
- QGL `speed 400 -> 200`
- QGL `retries 15 -> 5`
- QGL `max_adjust 20 -> 5`
- Adaptive Mesh `PGP=0 -> PGP=1`
- randomized/cross-hatch `CLEAN_NOZZLE`
- START_PRINT acceleration and two-stage current-Z Z-offset verification

Config Optimization depends on Safe Home because its START_PRINT calibration calls rely on Safe Home current-Z semantics.

### Installer

- Adds `safe_home`, `config_optimization`, and `all` feature selection.
- Installs `all` in dependency order.
- Adds feature-scoped bounded previous-version snapshots for shared configuration files.
- Keeps `.mb_baseline` as the first-seen baseline.
- Bootstrap verifies `SHA256SUMS` and cleans installer-owned temporary files.

### Documentation

- Splits README and Release Notes into English and Simplified Chinese pages.
- Adds Config Optimization documentation and AI-assisted development disclosure.

---

## v1.0.0-rc1

First release candidate for the Safe Home feature.

### Safe Home

- Adds `M_Bamboo_Safe_Homing.py`.
- Replaces the active Sovol `z_offset_calibration.py` with the validated M_Bamboo runtime implementation.
- Removes active `[homing_override]` and retains an explicit managed tombstone.
- Preserves the touchscreen G28 ABI through managed macros.
- Uses genuine Z homing before normal Eddy recalibration when Z is unknown.
- Keeps explicit `USE_CURRENT_Z=1` refinement semantics for callers that already have a trustworthy Z reference.
- Removes the Sovol `Zmax + 15` / approximately `Z520` bootstrap path from the M_Bamboo-maintained runtime path.
- Treats missing Eddy calibration as an explicit install/runtime boundary and requires the stock Sovol bootstrap first.
- Does not modify MCU firmware.

### Installer

- Dry-run by default.
- Validates Eddy calibration before Safe Home installation.
- Uses bounded baseline/previous-version backups.
- Compiles Python payloads before/after installation.
- Restarts Klipper and checks service state by default.
- Automatically rolls back exact pre-apply bytes when validation/restart fails.
- Supports rollback, baseline restore, raw diff, and no-restart options.

### ES-R4-EC2-FS1.1 — diagnostic shutdown hotfix
- Fixes `M_BAMBOO_EDDY_STATUS` NameError (`raw` referenced before initialization) introduced by FS1 diagnostics.
- Status now snapshots low-level LDC diagnostics with `raw = self._raw_diag()` before formatting quarantine counters.
- Adds an offline AST regression gate so the status command cannot regress to this undefined-local failure.
- Fault-storm stream quarantine behavior is otherwise unchanged.

## ES-R4-EC2-FS1.1 — Documentation / hardware-evidence refresh (2026-08-20)

- No backend behavior change; safety label remains `ES-R4-EC2-FS1.1`.
- Documents the original active-motion raw-34 (`NACK | BUSY`) problem that motivated the pre-arm transport quiescence gate, the reason active-motion retry remains prohibited, and the separate FS1 fault-storm containment role.
- Records real-machine healthy-path evidence through repeated homing/contact/nozzle-clean/Z-calibration, QGL, adaptive rapid mesh, complete slicer START_PRINT, a real cube print, END_PRINT including the stock `clear_plr` cleanup hook, and post-print diagnostics.
- Latest post-print session: 30 pre-arm checks, 0 transport faults, 0 transient recoveries, 0 pre-arm failures, 0 forced quarantines, 0 repeated-fault suppressions.
- Interprets this as strong evidence of materially reduced observed raw-34 incidence and support for an I2C/session-transition-boundary hypothesis, **not** proof that error 34 is eliminated.
- Keeps FS1.1 at Engineering Candidate status pending the next natural transport fault to validate forced quarantine and complete recovery on hardware.
