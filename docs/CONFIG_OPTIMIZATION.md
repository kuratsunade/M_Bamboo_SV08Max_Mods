# Config Optimization / 配置优化

`config_optimization` manages validated changes in `printer.cfg`, `Macro.cfg`, and `buffer_stepper.cfg`. It is intentionally separate from `safe_home` but depends on Safe Home for the `START_PRINT` current-Z calibration calls.

## Managed printer.cfg values

| Setting | Stock | Managed |
|---|---:|---:|
| `max_velocity` | 700 | 400 |
| `max_accel` | 40000 | 15000 |
| X `run_current` | 3.0 | 2.3 |
| Y `run_current` | 3.0 | 2.3 |
| QGL `speed` | 400 | 200 |
| QGL `retries` | 15 | 5 |
| QGL `max_adjust` | 20 | 5 |

## Managed buffer_stepper.cfg values

| Setting | Stock | Managed |
|---|---:|---:|
| `velocity` | 150 | 80 |
| `accel` | 5000 | 1900 |
| `push_length` | 25 | 27 |

These values are managed inside `[buffer_stepper filament_buffer]` using a dedicated `CONFIG_BUFFER_STEPPER` block.

`[stepper_z] position_min=-1` is **not** owned here. It belongs to Safe Home because it is a Z safety dependency.

## Managed Macro.cfg behavior

- Adaptive mesh changes `PGP=0` to `PGP=1`.
- `CLEAN_NOZZLE` uses a randomized contact point and a cross-hatch wiping pattern to distribute wear.
- `START_PRINT` uses `ACCEL=15000 ACCEL_TO_DECEL=7500`.
- Before QGL, `START_PRINT` runs `Z_OFFSET_CALIBRATION ... USE_CURRENT_Z=1`.
- After QGL, Z home and bed mesh, `START_PRINT` re-verifies Z offset with `USE_CURRENT_Z_ALLOWANCE=1.25`.

## Install

```bash
./install.sh config_optimization
./install.sh config_optimization --apply
```

If Safe Home is not installed, installation is blocked. Use `./install.sh all` to install both features in dependency order.

## Rollback

```bash
./install.sh config_optimization --rollback
```

Config files use feature-scoped bounded previous-version slots so this rollback can return to the state immediately before Config Optimization without removing Safe Home.

## Post-install restart note

The installer requests a Klipper service restart and verifies that the service reports `active`. If you do not observe a normal printer/Klipper restart cycle, or the printer state appears inconsistent, perform a manual **Firmware Restart** before continuing.
