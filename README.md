# M_Bamboo_SV08Max_Mods

A modular Klipper improvement project for the **Sovol SV08 Max (500 × 500)**, focused on Z safety, Eddy reliability, calibration behavior, configuration quality, diagnostics, and reversible release management.

> Maintainer: **Master_Bamboo / 竹子**  
> Public baseline: **v1.0.0-rc4**  
> RC5: **in development / validation preparation**  
> Runtime Safety baseline: **ES-R4-EC2-FS1.1**  
> [简体中文 README](README_CN.md)

## Project status

RC4 remains the current public release candidate. RC5 is a focused continuation of the same architecture, not a firmware rewrite.

RC5 work currently includes:

- productionizing the late probe/scan transaction cleanup proven during HF2.1 testing;
- retaining **PREARM** as the fail-closed gate before safety-critical Eddy Z motion;
- adding bounded **automatic recovery** for eligible PREARM / Eddy transport faults during the `START_PRINT` core sequence;
- restarting failed QGL / mesh / Z-calibration work from clean atomic checkpoints instead of resuming a failed sensor transaction;
- cleaning startup-only state so a failed print start cannot poison the next one;
- completing the Sovol STM32F1 I2C source audit and defining the exact MCU/host trust boundary;
- consolidating real-machine test statistics and revised hypotheses into release documentation.

RC5 hardware fault-injection and final release validation are still pending. Until RC5 is promoted, the installation commands below refer to the current `main` release.

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

RC5 keeps PREARM and extends it into bounded startup recovery.

A recoverable fault during the Eddy-sensitive `START_PRINT` chain follows this high-level policy:

```text
transport / PREARM fault
-> hold or abort the current atomic startup stage
-> clean/quarantine the Eddy lifecycle
-> verify transport health without Z motion
-> rebuild Z trust with one fresh armed Safe Home when required
-> restore stage-local temporary state
-> rerun the complete failed stage
-> continue START_PRINT only after the stage completes cleanly
```

This is **not blind retry**:

- one armed Z-recovery attempt per fault episode;
- if that recovery attempt fails, the episode is terminal;
- a later independent fault is eligible only after the recovered stage has completed successfully;
- `START_PRINT` has a total automatic-recovery budget so repeated faults eventually stop for inspection;
- non-Eddy errors are not swallowed by the recovery coordinator.

The current design target is up to **3 successfully recovered independent startup episodes**, subject to final RC5 hardware fault-injection validation.

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

Yes. Full Restore is the supported removal/recovery path for M_Bamboo-owned changes.

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
