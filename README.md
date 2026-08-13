# M_Bamboo_SV08Max_Mods

[English](README.md) | [简体中文](README_CN.md)

A modular collection of safety, configuration, and quality-of-life improvements for the **Sovol SV08 Max (500 × 500)**.

> Maintainer: **Master_Bamboo / 竹子**

## Project goals

This project avoids MCU firmware recompilation whenever practical. It prefers Klipper configuration, G-code macros, user-space Python extras, and reversible installer tooling. Where Sovol-specific behavior diverges from upstream Klipper, the project generally moves behavior back toward standard Klipper semantics while preserving the SV08 Max touchscreen command ABI.

## Features

| Feature | Status | Description |
|---|---|---|
| `safe_home` | v1.0.0 RC | Safer homing and Z-offset / Eddy recalibration behavior |
| `config_optimization` | v1.0.0 RC | Validated `printer.cfg` and `Macro.cfg` tuning |
| `hardware_cooling` | Planned | Electrical enclosure / bed cooling configuration for modified hardware |
| `plr` | Planned | Power-loss recovery redesign |
| `restore` | Planned | Restore / rollback helpers |

## Safe Home

Safe Home provides safe unknown-Z clearance, controlled XY/Z homing, genuine Z homing before normal Eddy recalibration, and an explicit factory-bootstrap boundary. It also manages `[stepper_z] position_min: -1` as a Safe Home safety dependency.

**Prerequisite:** complete the stock Sovol Eddy Current Sensor Calibration and confirm `SAVE_CONFIG` before installing Safe Home. M_Bamboo does not retain the stock `Zmax + 15` / approximately `Z520` bootstrap fallback in its active runtime backend.

## Config Optimization

`config_optimization` is a separate feature and depends on Safe Home because its `START_PRINT` flow uses the validated `USE_CURRENT_Z` calibration semantics.

Validated changes in this RC:

- `[printer]` `max_velocity: 700 → 400`
- `[printer]` `max_accel: 40000 → 15000`
- X/Y TMC5160 `run_current: 3.0 → 2.3`
- QGL `speed: 400 → 200`
- QGL `retries: 15 → 5`
- QGL `max_adjust: 20 → 5`
- adaptive mesh `PGP=0 → PGP=1`
- randomized contact point + cross-hatch `CLEAN_NOZZLE`
- `START_PRINT` acceleration limit `15000 / 7500`
- current-Z Z-offset verification before QGL and again after mesh

The feature does **not** own Safe Home's G28 routing or Z safety backend.

## Quick install

### Recommended: download bootstrap, inspect, then run

Dry-run both currently released features:

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh all
```

Apply after reviewing the preview:

```bash
sh M_Bamboo_bootstrap.sh all --apply
```

Individual features remain available:

```bash
sh M_Bamboo_bootstrap.sh safe_home
sh M_Bamboo_bootstrap.sh config_optimization
```

`config_optimization` requires Safe Home to already be present, or use `all` to install them in dependency order.

### Convenience one-liner

```bash
wget -qO- https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh \
  | sh -s -- all
```

Add `--apply` only after reviewing a dry-run.

The bootstrap downloads the complete repository snapshot into an installer-owned `/tmp/M_Bamboo_SV08MAX.XXXXXX` directory, verifies `SHA256SUMS`, launches the feature installer, and removes its temporary files on success or failure.

## Direct installer commands

From an extracted release directory:

```bash
./install.sh all                    # dry-run both features
./install.sh all --apply            # install both
./install.sh safe_home              # Safe Home only
./install.sh config_optimization    # Config Optimization only
./install.sh all --raw-diff
```

Rollback is feature-aware. Config Optimization must be rolled back before Safe Home if both are installed because Config Optimization depends on Safe Home.

## Backup policy

Every modified active file receives a persistent first-seen baseline:

```text
<file>.mb_baseline
```

Shared config files also use bounded feature-scoped previous-version slots, for example:

```text
printer.cfg.last_mb_safe_home
printer.cfg.last_mb_config_optimization
```

This prevents one feature rollback from silently restoring another feature's older configuration state.

## Documentation

- [Safe Home installation & recovery](docs/SAFE_HOME_INSTALL.md)
- [Config Optimization](docs/CONFIG_OPTIMIZATION.md)
- [Safe Home regression checklist](docs/SAFE_HOME_REGRESSION.md)
- [Release notes](RELEASE_NOTES.md)
- [中文 Release Notes](RELEASE_NOTES_CN.md)

## Release status

`v1.0.0-rc2` combines the productionized Safe Home feature with the first release-candidate packaging of Config Optimization. Run a dry-run and review the generated diff before applying to any additional machine.

---

## AI-assisted development disclosure

AI tools, including **OpenAI ChatGPT**, were used as development aids for selected tasks such as code drafting, review, documentation, test planning, and technical discussion. AI-generated suggestions are **not accepted blindly**: safety-critical behavior is reviewed by the maintainer and validated on real SV08 Max hardware before being promoted to a production release. The maintainer remains responsible for the final project decisions, published files, and release approval.

Because this software can control moving and heated hardware, users should still review dry-run output, keep backups, and treat release-candidate builds as test software.
