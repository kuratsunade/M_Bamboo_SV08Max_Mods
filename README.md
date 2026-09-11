# M_Bamboo_SV08Max_Mods

A modular Klipper improvement project for the **Sovol SV08 Max (500 × 500)**, focused on safety, calibration, configuration maintenance, diagnostics, and recoverable release management.

> Maintainer: **Master_Bamboo / 竹子**\
> Public release baseline: **v1.0.0-rc4**\
> This branch: **1.0.0-rc5-dev; SR1 + RS1 + GR1**\
> Runtime Safety: **ES-R4-EC2-FS1.1**\
> Status: **Development candidate; partial hardware validation; installation and restore gates remain open**\
> [简体中文 README](README_CN.md)

## Project Overview

`M_Bamboo_SV08Max_Mods` is a modular set of improvements for the Sovol SV08 Max Klipper software stack. It does not replace the complete Sovol firmware and does not require rebuilding or flashing MCU firmware. Instead, it applies bounded changes while preserving the touchscreen, Eddy contact probe behavior, hardware interfaces, and calling conventions that the printer depends on.

The objective is not simply to run the newest Official Klipper. The project addresses several practical weaknesses observed in the SV08 Max stack:

- loose boundaries between homing, probing, and Z coordinate trust;
- insufficient coupling between Eddy transport failures and later Z motion;
- repeatability and movement-boundary problems in parts of Z calibration and nozzle cleaning;
- aggressive or difficult-to-maintain stock motion, QGL, current, and mesh settings;
- limited observability when the customized Eddy stack misbehaves;
- lack of a unified, verifiable, and recoverable lifecycle for modified configuration and Python backends.

M_Bamboo aims to make these behaviors safer, more deterministic, easier to diagnose, and easier to restore while keeping changes attributable to explicit features.

Detailed failure models, implementation mechanics, evidence boundaries, and open engineering questions live in the technical documentation rather than this README.

## Feature Overview

| Feature | Purpose | Current status | Included by `all` |
|---|---|---|---:|
| **Safe Home** | Establishes safe clearance when Z is untrusted, then performs XY homing and a real Eddy Z home before treating Z as trusted | Hardware validated | Yes |
| **Config Optimization** | Refines motion, QGL, currents, adaptive mesh, buffer stepper, and related SV08 Max configuration | Hardware validated lineage | Yes |
| **Eddy Safety / Calibration** | Hardens Eddy transport, probing, Z trust, calibration transactions, fault blocking, recovery checks, and diagnostics | Healthy flows and one natural QGL fault with automatic recovery validated; broader fault coverage pending | Yes |
| **Z Calibration Refinement** | Improves two-stage calibration, contact verification, and final XY reseat repeatability | Existing validated lineage; contact repeatability investigation remains open | With Eddy Safety |
| **Nozzle Cleaner** | Uses a real contact datum for the wipe plane and removes the deterministic stock-style below-limit plunge path | Integrated and hardware validated | With Config Optimization |
| **Diagnostics** | Provides Eddy status, recovery checks, and XY stress interfaces without automatically running stress motion | Formal release-owned feature | Yes |
| **Hardware Cooling** | Provides configuration for the corresponding physical cooling modification | Optional, hardware dependent | **No** |
| **Full Restore** | Removes M_Bamboo-owned configuration changes and restores trusted pre-M_Bamboo backend state | Required contract; current candidate has an open config restore defect | Installer capability |

The current RC does not include the PLR redesign or the experimental Gantry Safe Leveler. They are not normal-install dependencies. See the [Release Notes](RELEASE_NOTES.md) for exact per-release scope.

## Installation

This branch is a development candidate. The public bootstrap below installs `main`, not this branch. Candidate testing uses the installer from an identified development checkout/package. The current candidate rejects direct stock installation and has an incomplete Full Restore; these are tracked in [Deployment & Restore](docs/DEPLOYMENT_AND_ROLLBACK.md). Do not treat public-release instructions as proof that the candidate has passed those gates.


### GitHub Bootstrap Installation

For the GitHub mirror, download the repository bootstrap directly from the `main` branch:

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh all
```

Review the dry-run output. To apply:

```bash
sh M_Bamboo_bootstrap.sh all --apply
```

The bootstrap downloads the GitHub repository snapshot, verifies the repository-root `SHA256SUMS`, and only then launches `install.sh`.

### Before Installation

Before installing:

1. Make sure the printer is idle and not printing or calibrating.
2. Confirm that you can SSH into the Sovol host.
3. Confirm that Klipper currently starts normally.
4. If other mods have changed `printer.cfg`, `Macro.cfg`, or `klippy/extras/*.py`, identify those changes first.
5. Do not bypass installer provenance or conflict checks simply to make an installation continue.

Download or copy the release package to the printer, extract it, and enter the project directory.

The installer is **dry-run by default**. A command without `--apply` does not write changes.

### Local Package Preview and Apply

Inspect the current machine state:

```bash
./install.sh all --status
```

Preview the planned installation:

```bash
./install.sh all
```

Inspect exact configuration and backend differences when needed:

```bash
./install.sh all --raw-diff
```

For an identified supported upgrade, apply only after the preview is correct and the candidate limitations have been reviewed:

```bash
./install.sh all --apply
```

`all` installs the normal software features, including Diagnostics. It does **not** install Hardware Cooling.

After installation and a successful Klipper restart, check Eddy Safety before the first motion:

```text
M_BAMBOO_EDDY_STATUS
```

If no unexpected fault is present, perform a normal:

```text
G28
```

After a first install or major upgrade, follow the [Hardware Validation Guide](docs/HARDWARE_VALIDATION.md) for basic motion, probing, QGL, Z calibration, and a small print before returning to unattended use.

### Installing an Individual Feature

Features can be previewed and installed independently:

```bash
./install.sh safe_home
./install.sh safe_home --apply

./install.sh config_optimization
./install.sh config_optimization --apply

./install.sh eddy_safety
./install.sh eddy_safety --apply

./install.sh diagnostics
./install.sh diagnostics --apply
```

Some features have dependencies. The installer enforces feature ownership and dependencies; the manifest records the release scope. Do not substitute manual copying of individual backend files for the normal installation flow.

#### Hardware Cooling

Hardware Cooling is explicitly opt-in and is never installed by `all`:

```bash
./install.sh hardware_cooling
./install.sh hardware_cooling --apply
```

Only enable it after the corresponding physical cooling modification has been completed.

### Updating an Existing M_Bamboo Installation

Use the installer from the **new release package**.

Start by checking detected state and lineage:

```bash
./install.sh all --status
```

Then preview the upgrade:

```bash
./install.sh all
./install.sh all --raw-diff
```

Apply only after the detected provenance and planned changes are correct:

```bash
./install.sh all --apply
```

The installer uses exact SHA256 identities and known lineages for managed backend files. If an existing backend cannot be identified safely, it fails closed rather than assuming that the file is stock.

### Installation Troubleshooting

Installer refusals are generally protection mechanisms. Resolve the reason first rather than editing the installer or manually overwriting files to bypass the check.

#### Unknown Backend or Provenance Refusal

If an existing backend is reported as unknown or first takeover is refused:

1. Save the complete installer output.
2. Run:

```bash
./install.sh all --status
./install.sh all --raw-diff
```

3. Determine whether the affected file came from:
   - another Sovol firmware build;
   - a third-party modification;
   - a manually edited Klipper backend;
   - an older M_Bamboo engineering package.
4. Do not overwrite it until the provenance is understood.

The installer deliberately does not provide a generic `--force` option for taking ownership of unknown Python backends.

#### Configuration Conflict

If an existing configuration cannot be transformed safely:

1. Inspect the reported section or managed block.
2. Use `--raw-diff` to review the intended change.
3. Determine whether the conflicting content belongs to the user, another mod, or an older M_Bamboo block.
4. Reconcile it only after ownership is clear, then rerun the dry-run.

M_Bamboo should not silently overwrite unrelated user configuration just to complete an install.

#### Failure During a Write Transaction

Actual writes are transactional.

Normally:

```text
write failure
→ automatic rollback
→ restore immediate pre-transaction state
```

If automatic rollback itself cannot complete, the installer deliberately retains the recovery snapshot and reports a path similar to:

```text
/tmp/M_Bamboo_SV08MAX.*
```

Do not delete that directory until the machine has been recovered or the snapshot has been copied somewhere safe.

#### Klipper Does Not Start After Installation

Do not immediately run `G28`, probe, QGL, or other motion.

Preserve:

- complete installer output;
- `klippy.log`;
- output of `./install.sh all --status`;
- the retained transaction snapshot path, if one was reported.

Preserve the evidence before choosing a recovery path. The current candidate has an incomplete Full Restore; use the version-specific guidance in [Deployment & Restore](docs/DEPLOYMENT_AND_ROLLBACK.md).

### Full Restore

Full Restore is the project removal contract: reverse owned configuration changes and restore trusted original backend state. It is distinct from rolling back a failed write transaction.

The current development candidate does not yet meet the complete config restore contract. Do not use its restore command as a complete removal or downgrade procedure. The [Deployment & Restore guide](docs/DEPLOYMENT_AND_ROLLBACK.md) separates public baseline behavior, candidate limitations and the intended historical-version path.

## Overview FAQ

### Is this a replacement third-party Sovol firmware?

No. The project currently does not rebuild or flash Sovol MCU firmware and is not a complete replacement system. It primarily manages Klipper user-space Python, configuration, macros, and installer lifecycle behavior while preserving the SV08 Max hardware interfaces and calling conventions that remain necessary.

### Why not just update the SV08 Max to the newest Official Klipper?

The SV08 Max relies on Sovol-specific Eddy contact behavior, Z calibration, touchscreen calling conventions, and other hardware integrations. Replacing the complete stack with current upstream Klipper could break those interfaces. M_Bamboo selectively adopts clearer upstream semantics where appropriate while preserving the Sovol ABI and hardware behavior that the printer requires.

### What is the main purpose of the project?

It is not primarily a speed-tuning package. The core work tightens the boundaries between Z trust, probe failures, Eddy transport faults, calibration transactions, and recovery behavior, while also improving homing, Z calibration, nozzle cleaning, QGL, configuration tuning, and diagnostics.

### Does `all` modify everything on the printer?

No. `all` means the default software feature set for the current release. Hardware Cooling is intentionally excluded because it requires a physical modification. The installer should only modify backends and configuration transformations that have explicit M_Bamboo ownership.

### Does installing Diagnostics automatically run an XY stress test?

No. Diagnostics installs public diagnostic interfaces only. XY stress motion requires an explicit user command.

### Does the current release include PLR?

No. The stock resume design has checkpoint-identity and coordinate-trust issues that require a separate redesign. PLR is therefore deferred as an independent feature rather than being carried into this RC unchanged.

### Can the printer be restored to its original or pre-install state?

That is the Full Restore contract, backed by one trusted original backend archive. The public baseline has historical validation; this development candidate still has an open config restoration defect. See Deployment & Restore before attempting removal.

### Can the installer directly downgrade to any historical M_Bamboo release?

There is no generic downgrade engine. The intended path is a validated Full Restore followed by the target historical installer. The current candidate restore defect must be resolved before relying on that path.

### Does the candidate automatically recover Eddy faults?

For supported operations and new recoverable transport/PREARM evidence, yes. The outer operation checks transport, rebuilds Z trust when needed, and repeats the complete failed operation once. Another fault before completion or a failed recovery stops it. START_PRINT owns its nested stages and has a bounded total budget. See the [Technical FAQ](docs/TECHNICAL_FAQ.md) for scope and rationale.

### Does this prove that every Eddy fault condition is solved?

No. Healthy operation and one natural QGL fault with automatic recovery have been observed on the combined candidate. Active rapid scan fault recovery, broader startup fault coverage and long term confidence remain open. [Test Evidence](docs/RC5_TEST_EVIDENCE.md) separates those results from earlier release tests.

## File Ownership, Backup Policy, and Project Principles

### File Ownership

The project keeps responsibilities attributable to explicit components instead of placing all logic in one macro or replacing entire configuration files.

| File / scope | Primary responsibility |
|---|---|
| `M_Bamboo_Safe_Homing.py` | Safe Home and coordinate-trust orchestration |
| `probe.py` | Safe endpoint policy for ordinary non-contact probing |
| `probe_eddy_current.py` | Eddy state, fault handling, diagnostics, transaction trace, and bounded operation/startup recovery |
| `ldc1612.py` | LDC1612 transport, telemetry, and related low-level state |
| `z_offset_calibration.py` | Z calibration, contact verification, and final XY reseat |
| `printer.cfg` | Feature-owned reversible configuration transformations only |
| `Macro.cfg` | Stable M_Bamboo managed blocks for macros and orchestration |
| `installer.py` | Provenance, feature ownership, transactions, restore, and release lifecycle |

See the [Command & Public Interface Reference](docs/COMMAND_REFERENCE.md) for exact public commands, parameters, compatibility interfaces, and feature ownership.

### Configuration Policy

User configuration files such as `printer.cfg` and `Macro.cfg` do not use persistent whole-file backups as the normal restore mechanism.

M_Bamboo prefers stable machine-readable markers:

```text
# >>> M_Bamboo_SV08MAX_MOD:<FEATURE> BEGIN >>>
...
# <<< M_Bamboo_SV08MAX_MOD:<FEATURE> END <<<
```

Restore reverses only M_Bamboo-owned transformations while preserving unrelated user content and `SAVE_CONFIG` generated content wherever applicable.

### Python Backend Backup Policy

Managed Klipper backends retain one provenance-validated pre-M_Bamboo original state under:

```text
/home/sovol/klipper/klippy/extras/mb_bak/
```

That original state is not overwritten during normal upgrades.

Legacy `.mb_baseline` files are accepted only when their exact SHA256 proves stock provenance. For recognized M_Bamboo lineage, a missing or polluted legacy baseline may be recovered from Sovol's factory mirror only when that mirror independently matches an exact known stock SHA256. Neither source is trusted by pathname alone.

### Transaction Snapshots

Every real write transaction uses a temporary recovery snapshot.

- successful transaction: cleaned up;
- failed transaction with successful automatic rollback: cleaned up;
- rollback failure: retained and reported for manual recovery.

### Project Principles

- no requirement to rebuild or flash Sovol MCU firmware;
- preserve touchscreen and Sovol G-code / hardware ABI compatibility where required;
- move behavior toward clearer Klipper semantics without casually breaking hardware integration;
- keep feature ownership explicit and support independent installation, upgrade, and restore where practical;
- prefer reversible local configuration transformations over whole-file user-config replacement;
- fail closed on unknown backend provenance;
- make installer writes transactionally recoverable;
- distinguish code-proven facts, hardware-observed facts, engineering inference, and pending validation;
- do not add unvalidated features to the default release merely to complete a checklist.

## Documentation

The README provides project orientation, feature scope, and installation guidance. Release-specific and implementation-specific information is maintained separately:

- **[Release Notes](RELEASE_NOTES.md)**: exact changes, scope, and known limitations for each release.
- **[Command & Public Interface Reference](docs/COMMAND_REFERENCE.md)**: G-code, macros, installer CLI, parameters, compatibility aliases, and public interface contract.
- **[Technical FAQ](docs/TECHNICAL_FAQ.md)**: confirmed Sovol behavior, design rationale, safety model, error interpretation, evidence boundaries, and open questions.
- **[RC5 Recovery Design](docs/RC5_RECOVERY_SUPERVISOR_DESIGN.md)** / **[START Design](docs/RC5_START_RECOVERY_DESIGN.md)**: outer ownership, replay contracts and budgets.
- **[Rapid Scan Restoration](docs/RC5_RS1_RAPID_SCAN_RESTORATION.md)**: session lifetime protection with unchanged healthy measurement semantics.
- **[Test Evidence](docs/RC5_TEST_EVIDENCE.md)** / **[Current Test Plan](docs/RC5_TEST_PLAN.md)**: completed observations, remaining coverage and practical testing.
- **[Sovol I2C Source Audit](docs/I2C_ROOT_CAUSE_AND_HOST_BOUNDARY.md)**: lower layer findings and the host boundary.
- **[Eddy Safety Engineering Design](docs/ES_R4_ENGINEERING_CANDIDATE.md)**: deeper Eddy Safety architecture, transport fault handling, and transaction model.
- **[Hardware Validation Guide](docs/HARDWARE_VALIDATION.md)**: hardware validation order, pass/fail criteria, and current evidence.
- **[Deployment & Restore](docs/DEPLOYMENT_AND_ROLLBACK.md)**: installer transactions, restore mechanics, and recovery details.
- **[Offline Validation](VALIDATION.md)**: package, code, and static release gates.
- **[Version Map](VERSION_MAP.md)** / **[Manifest](MANIFEST.md)**: exact artifacts, lineage, ownership, and release package information.

## Disclaimer

This project changes Klipper behavior on a large CoreXY 3D printer, including homing, probing, Z calibration, motion configuration, and related safety flows. Review the dry-run before installation and validate basic machine motion and printing on the real printer before unattended use.

This is a community-maintained project and is not affiliated with or endorsed by Sovol. Users remain responsible for evaluating compatibility with their machine state, hardware modifications, and third-party changes.

Development and technical documentation may include AI-assisted work. Hardware behavior and safety claims should ultimately be evaluated through source inspection, maintainer review, reproducible testing, and explicit real-machine evidence.
