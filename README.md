# M_Bamboo_SV08Max_Mods

A modular Klipper improvement project for the **Sovol SV08 Max (500 × 500)**, focused on Z safety, Eddy reliability, calibration behavior, configuration quality, diagnostics, and reversible release management.

> Maintainer: **Master_Bamboo / 竹子**
> Public baseline: **v1.0.0-rc4**
> RC5: **development candidate; partial hardware validation, installer release blockers**
> Runtime Safety baseline: **ES-R4-EC2-FS1.1**
> [简体中文 README](README_CN.md)

## Project status

RC4 remains the public release candidate; bootstrap examples below select `main`. RC5 on `rc5-dev` contains SR1 startup coordination, RS1 retired rapid scan callback protection and GR1 bounded recovery for six public operations.

The September 8 hardware record includes repeated healthy G28/QGL/mesh and one natural raw34 QGL automatic recovery without firmware restart. Active scan fault recovery and complete print soak on this exact candidate remain open.

September 9 offline checks found release blockers: direct stock installation is refused, and Full Restore after RC4 to RC5 upgrade leaves the RC5 START_PRINT core in Macro.cfg despite reporting success. Do not use this candidate's Full Restore as a complete removal/downgrade procedure. RC5 is not a public release.

See [current test plan](docs/RC5_TEST_PLAN.md) and [evidence](docs/RC5_TEST_EVIDENCE.md).

## Project boundary

M_Bamboo does **not** modify, rebuild, flash, or replace Sovol MCU firmware. This is a project-level constraint, not an RC5-only choice.

Source audit has confirmed lower-layer Sovol STM32F1 I2C/LDC behaviors that can make a failed transaction ambiguous. M_Bamboo deliberately stops ownership at that boundary: existing MCU telemetry is used as fault evidence, while transaction isolation, PREARM, stream quarantine, Z-trust handling, lifecycle cleanup, and bounded workflow recovery are completed entirely in the Klipper host/config layer.

See [Sovol STM32F1 I2C / Eddy Root-Cause Audit](docs/I2C_ROOT_CAUSE_AND_HOST_BOUNDARY.md) for the high- and low-level analysis.

## Feature overview

| Feature | Purpose | Status |
|---|---|---|
| **Safe Home** | Establishes safe clearance and a real Eddy Z reference when Z is unknown or untrusted | Hardware validated |
| **Config Optimization** | Refines motion, QGL, currents, adaptive mesh, buffer stepper, and related SV08 Max settings | Hardware-validated lineage |
| **Eddy Safety / Calibration** | Transport-fault handling, PREARM, transaction taint, quarantine, Z trust, bounded recovery, and calibration integrity | RC4 validated; RC5 hardening in progress |
| **Z Calibration Refinement** | Two-stage Z calibration, contact verification, and final XY reseat | Hardware validated |
| **Nozzle Cleaner** | Uses a real contact datum for the wipe plane and avoids the old below-limit plunge path | Hardware validated |
| **Diagnostics** | Eddy status, recovery checks, and explicit stress/diagnostic interfaces | Included in default software set |
| **Hardware Cooling** | Configuration for the corresponding physical cooling modification | Optional; not installed by `all` |
| **Full Restore** | Removes M_Bamboo-owned changes and restores trusted pre-M_Bamboo backend state | Installer capability |

PLR redesign and the experimental Gantry Safe Leveler are **not** part of the current RC5 scope.

## Eddy recovery model

PREARM remains the gate before Eddy operations. GR1 wraps `G28`, `RUN_PROBE_VIR_CONTACT`, `CLEAN_NOZZLE`, `Z_OFFSET_CALIBRATION`, `QUAD_GANTRY_LEVEL` and `BED_MESH_CALIBRATE`.

Only the outer synchronous owner recovers on new transport/PREARM evidence after failed work has ended. It checks transport without motion, rebuilds Z trust with fresh Safe Home if required, and replays the whole failed operation once. A second fault or recovery failure terminates. Ordinary errors propagate. Async callbacks never launch workflow recovery.

During START_PRINT, SR1 remains owner. Each stage invocation gets at most one recovery; the whole START has a maximum of three independent episodes. This implemented budget still needs broader natural hardware coverage. Healthy rapid scan measurement parameters and the existing two stage Z calibration sequence remain unchanged.

## Installation

### GitHub bootstrap

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh all
```

The installer is dry-run by default. Review the result, then apply:

```bash
sh M_Bamboo_bootstrap.sh all --apply
```

The bootstrap verifies the repository-root `SHA256SUMS` before launching the installer.

### Local package / advanced use

Inspect current state:

```bash
./install.sh all --status
```

Preview:

```bash
./install.sh all
./install.sh all --raw-diff
```

Apply:

```bash
./install.sh all --apply
```

`all` installs the normal software feature set. **Hardware Cooling is not included** because it requires the matching physical modification.

Individual features may also be previewed/applied independently:

```bash
./install.sh safe_home
./install.sh config_optimization
./install.sh eddy_safety
./install.sh diagnostics
```

Add `--apply` only after reviewing the dry-run.

### Full Restore

The commands below describe the public RC4 path. The RC5 candidate has an open START_PRINT restoration defect; do not rely on it for complete removal until corrected.

Preview:

```bash
./install.sh all --restore
```

Apply:

```bash
./install.sh all --restore --apply
```

Full Restore reverses M_Bamboo-owned configuration transformations and restores managed Python backends from the trusted original-state archive.

The supported historical-version path is:

```text
current release
-> Full Restore
-> pre-M_Bamboo/original state
-> install the desired historical release with that release's installer
```

## Installer principles

- dry-run by default;
- exact backend SHA/provenance gates;
- fail closed on unknown backend lineage;
- stable feature-owned markers for `printer.cfg` / `Macro.cfg`;
- one trusted pre-M_Bamboo backend archive under `klippy/extras/mb_bak/`;
- transaction snapshot and automatic rollback for real writes;
- temporary installer/download/extraction files cleaned after successful or safely rolled-back operations;
- no generic force-overwrite path for unknown Python backends.

## FAQ

### Is this a replacement Sovol firmware?

No. M_Bamboo does not modify or flash MCU firmware. It works in Klipper host Python, configuration, macros, and the installer lifecycle while preserving the Sovol hardware/G-code ABI that the SV08 Max depends on.

### Why not simply upgrade to current Official Klipper?

The SV08 Max stack contains Sovol-specific Eddy contact behavior, MCU commands, Z calibration, touchscreen-facing calling conventions, and other integration. M_Bamboo selectively adopts clearer upstream semantics without casually replacing hardware-specific interfaces.

### Does PREARM guarantee that an I2C fault can never happen?

No. PREARM prevents an already unhealthy or newly unstable transport state from starting a safety-critical bed-facing action. A new fault can still occur after motion begins; runtime transaction guards then abort/taint the action and revoke Z trust where required.

### Will RC5 automatically recover a PREARM / transport fault during `START_PRINT`?

For faults that the safety core classifies as recoverable, yes. Recovery remains bounded and checkpoint based. A failed recovery attempt is never blindly repeated.

### Does a successful transport recovery validate the failed Probe/QGL/mesh transaction?

No. The failed transaction remains invalid. RC5 re-runs the owning atomic startup stage from a clean checkpoint.

### Does the project include PLR?

Not in the current RC5 scope. PLR remains a separate feature because its checkpoint identity and coordinate-trust model require independent work.

### Does `all` install Hardware Cooling?

No. Hardware Cooling is explicitly opt-in because it depends on a physical modification.

### Can the printer be restored?

Full Restore is the intended removal path. Public RC4 has historical validation; the current RC5 candidate has an open config restoration defect described above.

## Documentation

- **[Release Notes](RELEASE_NOTES.md)** — release history, exact scope, and known limitations.
- **[Technical FAQ](docs/TECHNICAL_FAQ.md)** — current safety/recovery rationale and fault interpretation.
- **[Sovol I2C / Eddy Root-Cause Audit](docs/I2C_ROOT_CAUSE_AND_HOST_BOUNDARY.md)** — source history, bitmask semantics, BUSY pin lookup, failed-data boundary, and M_Bamboo's MCU/host cut line.
- **[RC5 START Recovery Design](docs/RC5_START_RECOVERY_DESIGN.md)** — atomic stages, recovery ownership, dependency handling, and validation requirements.
- **[RC5 Test Evidence](docs/RC5_TEST_EVIDENCE.md)** — complete statistics, fault context, recovery results, revised hypotheses, and evidence limits.
- **[Eddy Safety Engineering Design](docs/ES_R4_ENGINEERING_CANDIDATE.md)** — transport-fault architecture and transaction safety model.
- **[Hardware Validation Guide](docs/HARDWARE_VALIDATION.md)** — hardware validation order and pass/fail criteria.
- **[Deployment & Restore](docs/DEPLOYMENT_AND_ROLLBACK.md)** — installer transactions, provenance, and restore mechanics.
- **[Command Reference](docs/COMMAND_REFERENCE.md)** — G-code, macros, installer CLI, and public interfaces.
- **[Offline Validation](VALIDATION.md)** — package/static release gates.
- **[Version Map](VERSION_MAP.md)** / **[Manifest](MANIFEST.md)** — exact artifacts, ownership, and lineage.

## Disclaimer

This project changes Klipper behavior on a large CoreXY printer, including homing, probing, Z calibration, motion configuration, and recovery logic. Review installer dry-runs and complete real-machine validation before returning to unattended use.

This is a community-maintained project and is not affiliated with or endorsed by Sovol. Development documentation may include AI-assisted analysis; safety claims should ultimately be grounded in source inspection, reproducible testing, maintainer review, and explicit hardware evidence.
