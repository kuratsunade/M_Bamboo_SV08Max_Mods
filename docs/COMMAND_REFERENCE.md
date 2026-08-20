# M_Bamboo SV08 Max — Command & Public Interface Reference

> **Maintainer:** Master_Bamboo / 竹子  
> **Scope:** Entire `M_Bamboo_SV08Max_Mods` project, not only ES-R4.  
> **Release rule:** This document is an **authoritative public-interface registry** and must be reviewed whenever a command, macro, parameter, compatibility alias, diagnostic interface, or installer-facing interface is added, changed, deprecated, or removed.

This reference documents **interfaces that M_Bamboo adds, replaces, wraps, materially changes, or intentionally carries forward because modified backends expose them**. It is not a copy of the complete Klipper or Sovol G-code manual.

---

## 0. Quick legend

| Label | Meaning |
|---|---|
| **Public / Stable** | Intended for normal user use and expected to remain compatible. |
| **Public / Soak-test** | User-callable, but behavior is still being validated. |
| **Compatibility ABI** | Name/behavior must remain available because the touchscreen, Sovol macros, slicer flow, or another compatibility path may depend on it. |
| **Advanced / Diagnostic** | Intended mainly for testing, diagnosis, calibration, or expert use. |
| **Internal** | Implementation detail; do not call from user macros. |
| **Deprecated** | Kept temporarily for compatibility; new code must not depend on it. |
| **Planned** | Design exists, but the interface is not implemented in the current candidate. |

Motion symbols used in the overview:

- **No** — no axis motion.
- **Yes** — command can move one or more axes.
- **Conditional** — motion depends on state/parameters.

---

# 1. Overview / Table of Contents

## 1.1 Interface overview

| Interface | Type | Feature / owner | Stability | Motion | Short purpose |
|---|---|---|---|---|---|
| [`G28`](#2-g28--safe-homing-compatibility-override) | Stock name replaced by macro | Safe Home | Compatibility ABI | Yes | Preserve touchscreen `G28`, route calibrated homing through Safe Home. |
| [`M_BAMBOO_HOME_X`](#3-m_bamboo_home_x) | New G-code | Safe Home | Compatibility ABI | Yes | Safe-clearance X homing. |
| [`M_BAMBOO_HOME_Y`](#4-m_bamboo_home_y) | New G-code | Safe Home | Compatibility ABI | Yes | Safe-clearance Y homing. |
| [`M_BAMBOO_HOME_XY`](#5-m_bamboo_home_xy) | New G-code | Safe Home | Compatibility ABI | Yes | One clearance, then raw X/Y homing. |
| [`M_BAMBOO_HOME_Z`](#6-m_bamboo_home_z) | New G-code | Safe Home | Compatibility ABI | Yes | Clearance before XY travel, then real Eddy Z home. |
| [`M_BAMBOO_HOME_ALL`](#7-m_bamboo_home_all) | New G-code | Safe Home | Compatibility ABI | Yes | Atomic clearance → XY → real Z sequence. |
| [`M_BAMBOO_EDDY_STATUS`](#8-m_bamboo_eddy_status) | New G-code | Eddy Safety | Public / Soak-test | No | Eddy safety state + event/fault evidence. |
| [`M_BAMBOO_EDDY_RECOVERY_CHECK`](#8a-m_bamboo_eddy_recovery_check) | New G-code | Eddy Transport Recovery | Public / Soak-test | No | No-motion transport health check that can arm one Safe Home recovery. |
| [`RUN_PROBE_VIR_CONTACT`](#9-run_probe_vir_contact) | Existing Sovol interface, safety-guarded | Eddy Safety / contact | Compatibility / Advanced | Yes | Virtual-contact probe used by cleaning/calibration. |
| [`PROBE`](#10-standard-probe-commands-with-m_bamboo-safety-semantics) | Standard Klipper command, behavior affected | Eddy Safety | Upstream ABI | Yes | Ordinary non-contact probing with M_Bamboo safety envelope. |
| [`PROBE_ACCURACY`](#10-standard-probe-commands-with-m_bamboo-safety-semantics) | Standard Klipper command, behavior affected | Eddy Safety | Upstream ABI | Yes | Repeated probes, same safety semantics. |
| [`PROBE_CALIBRATE`](#10-standard-probe-commands-with-m_bamboo-safety-semantics) | Standard Klipper command, backend carried | Eddy backend | Upstream ABI | Yes | Standard probe calibration path. |
| [`QUERY_PROBE`](#10-standard-probe-commands-with-m_bamboo-safety-semantics) | Standard Klipper command, backend carried | Probe backend | Upstream ABI | No | Query probe state. |
| [`Z_OFFSET_CALIBRATION`](#11-z_offset_calibration) | Sovol command materially modified | Z Calibration | Public / Soak-test | Yes | M_Bamboo safe two-stage Z-offset workflow. |
| [`CLEAN_NOZZLE`](#12-clean_nozzle) | Sovol macro replaced/managed | Nozzle Cleaner NC-R1 | Public / Soak-test | Yes | One contact datum + randomized cross-hatch cleaning. |
| [`QUAD_GANTRY_LEVEL`](#13-quad_gantry_level) | Klipper command wrapped | Config optimization / Eddy Safety | Compatibility ABI | Yes | Home if needed, then run base QGL under M_Bamboo safety. |
| [`BED_MESH_CALIBRATE`](#14-bed_mesh_calibrate) | Klipper command wrapped | Config optimization / Eddy Safety | Compatibility ABI | Yes | Pre-flight calibration/QGL and adaptive rapid scan. |
| [`START_PRINT`](#15-start_print) | Sovol slicer macro materially modified | Print orchestration | Compatibility ABI | Yes | Full Safe Home / cleaner / Z-cal / QGL / mesh sequence. |
| [`LDC_CALIBRATE_DRIVE_CURRENT`](#16-ldc_calibrate_drive_current) | Existing Sovol/Klipper-derived interface, guarded | LDC1612 | Advanced / Calibration | No axis motion | Drive-current calibration; EC2 rejects transport-tainted results. |
| [`PROBE_EDDY_CURRENT_CALIBRATE`](#17-probe_eddy_current_calibrate) | Existing Eddy calibration interface, carried | Eddy calibration | Advanced / Calibration | Yes | Manual Eddy frequency-to-height calibration. |
| [`EDDY_QUERY_LOOP`](#18-eddy_query_loop) | Existing Sovol diagnostic interface, carried | LDC1612 | Advanced / Diagnostic | No | Low-level LDC query-loop control. |
| [`XY_STRESS_BASELINE`](#19-xy_stress_baseline) | M_Bamboo diagnostic macro | Diagnostics | RC / Diagnostic | Yes | Establish XY/TMC baseline. |
| [`XY_STRESS_RUN`](#20-xy_stress_run) | M_Bamboo diagnostic macro | Diagnostics | RC / Diagnostic | Yes | 400 mm/s / 15000 mm/s² CoreXY stress sequence. |
| [`XY_STRESS_CHECK`](#21-xy_stress_check) | M_Bamboo diagnostic macro | Diagnostics | RC / Diagnostic | Yes | Re-home and capture post-stress XY/TMC state. |
| [`M_BAMBOO_Z_RELIEF`](#22-m_bamboo_z_relief-planned) | Planned G-code | Recovery | Planned | Yes (+Z only) | Proposed post-fault mechanical unload; **not implemented**. |
| [`./install.sh <feature>`](#23-rc4-release-installer-cli) | Shell installer interface | Installer / Release tooling | RC / Public | N/A | Dry-run/apply/status/diff/restore interface with transactional rollback. |

## 1.2 Compatibility/base aliases — normally do not call directly

| Alias / base command | Created by | Purpose |
|---|---|---|
| `M9928` | `G28 rename_existing` | Preserved underlying/raw `G28` compatibility target. |
| `QUAD_GANTRY_LEVEL_BASE` | `QUAD_GANTRY_LEVEL rename_existing` | Original Klipper QGL command behind the M_Bamboo/Sovol wrapper. |
| `BED_MESH_CALIBRATE_BASE` | `BED_MESH_CALIBRATE rename_existing` | Original bed-mesh command behind the wrapper. |

> These are **implementation/compatibility targets**, not preferred user-facing commands.

## 1.3 Parameters added or materially changed by M_Bamboo

| Command | Parameter | Default / range | M_Bamboo meaning |
|---|---|---|---|
| `Z_OFFSET_CALIBRATION` | `USE_CURRENT_Z` | `0`; `0/1` | Preserve an already-trusted current Z reference instead of legacy large fake-Z acquisition. |
| `Z_OFFSET_CALIBRATION` | `USE_CURRENT_Z_ALLOWANCE` | `0.0`; `0..5 mm` | Temporary logical search room for the first contact only; no motor motion when applied. |
| `Z_OFFSET_CALIBRATION` | `USE_CURRENT_Z_MAX` | `15.0 mm`; `>0` | Sanity ceiling for `USE_CURRENT_Z`. |
| `Z_OFFSET_CALIBRATION` | `REHOME_XY` | `0`; `0/1` | Explicit final XY mechanical reseat before post-mesh contact calibration. |
| `Z_OFFSET_CALIBRATION` | `REHOME_XY_Z_TOLERANCE` | `0.02 mm`; `0..0.25` | Maximum allowed Z change during raw X/Y reseat. |
| `Z_OFFSET_CALIBRATION` | `ZDBG` | `0`; `0/1` | Concise Z-calibration runtime tracing; does not change motion policy. |
| Eddy probe config | `probe_below_trigger_allowance` | project soak-test value `2.0 mm` | Dynamic non-contact descent envelope below the lowest trusted Eddy trigger. |
| Eddy probe config | `eddy_diagnostic_level` | project soak-test typically `2` | M_Bamboo Eddy diagnostic verbosity. |

---

# 2. `G28` — Safe Homing Compatibility Override

> **Type:** Stock/standard name replaced by macro  
> **Owner:** M_Bamboo Safe Home  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes  
> **Preferred user entry point:** Yes

### Purpose

Preserves the `G28` command expected by the SV08 Max touchscreen and existing macros while routing calibrated operation through `M_BAMBOO_HOME_*`.

### Syntax

```gcode
G28
G28 X
G28 Y
G28 Z
G28 X Y
```

### M_Bamboo behavior

When Eddy calibration exists, axis-specific calls route to the matching Safe Home command; bare `G28` routes to `M_BAMBOO_HOME_ALL`.

The underlying renamed command is `M9928`. **Do not use `M9928` as the normal user homing command.**

### Safety notes

- Unknown/untrusted Z must establish positive Z clearance before XY travel.
- A latched Eddy safety fault is not cleared by `G28`.
- Failed Eddy probing/homing invalidates Z trust through the homing safety layer.

---

# 3. `M_BAMBOO_HOME_X`

> **Owner:** Safe Home  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes

Establishes Z clearance when required, then performs raw X homing. It does not establish a Z datum.

```gcode
M_BAMBOO_HOME_X
```

---

# 4. `M_BAMBOO_HOME_Y`

> **Owner:** Safe Home  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes

Same safety semantics as `M_BAMBOO_HOME_X`, for Y.

```gcode
M_BAMBOO_HOME_Y
```

---

# 5. `M_BAMBOO_HOME_XY`

> **Owner:** Safe Home  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes

Establishes Z clearance **once**, then raw-homes X and Y.

```gcode
M_BAMBOO_HOME_XY
```

---

# 6. `M_BAMBOO_HOME_Z`

> **Owner:** Safe Home  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes

### Sequence

1. Establish positive-only Z clearance before any XY travel.
2. Require X and Y to already be homed.
3. Move to the configured Z-home XY position.
4. Perform a real Eddy-backed raw Z home.
5. Move to configured post-home Z clearance.

```gcode
M_BAMBOO_HOME_Z
```

### Fault behavior

This command does **not** clear an Eddy fault. If the Eddy session is fault-latched, probing remains blocked and `FIRMWARE_RESTART` is required before establishing a new session.

---

# 7. `M_BAMBOO_HOME_ALL`

> **Owner:** Safe Home  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes

Atomic sequence:

```text
positive Z clearance once
→ raw X
→ raw Y
→ Z-home XY
→ real Z home
→ post-home Z
```

```gcode
M_BAMBOO_HOME_ALL
```

---

# 8. `M_BAMBOO_EDDY_STATUS`

> **Owner:** Eddy Safety Core  
> **Stability:** **Public / Soak-test**  
> **Moves machine:** No  
> **Allowed while fault-latched:** Yes

Reports the authoritative Eddy safety state and latest transaction/fault evidence.

```gcode
M_BAMBOO_EDDY_STATUS
```

### ES-R4-EC2 evidence includes

EC2 additionally separates **first fault** from the strongest current fault and reports transport-fault sequence `handled/current`.  If the serial callback has already recorded a fault but the reactor safety callback has not consumed it yet, that pending sequence itself blocks a new Eddy operation.


- session fault state;
- transaction ID/caller/mode/state;
- start/target/final information;
- `transport_fault_seq`, trusted-through watermark, and transaction taint;
- current transport state versus historical last-error telemetry;
- session transport fault count/type/context statistics;
- pre-arm check / transient-recovery / failure counters and whether Z recovery is required;
- decoded raw I2C transport evidence;
- active-stop request / `trsync_active` information;
- halt-position reconstruction state;
- bounded last-transaction event timeline with relative timestamps, for example `TRANSPORT_FAULT -> STOP_REQUESTED -> ABORTED -> HALT_RECONSTRUCTED`;
- trusted-trigger / dynamic-floor information where applicable.

### Does not

- clear a fault;
- retry probing;
- home an axis;
- move the toolhead.

After an Eddy abort, this is the preferred evidence command. For a transport fault, follow `Recovery guidance` and run `M_BAMBOO_EDDY_RECOVERY_CHECK`; `FIRMWARE_RESTART` becomes mandatory only when recovery remains unstable/fails or the armed recovery attempt fails.

---

# 8A. `M_BAMBOO_EDDY_RECOVERY_CHECK`

> **Owner:** Eddy Transport Recovery  
> **Stability:** **Public / Soak-test**  
> **Moves machine:** No  
> **Allowed while fault-latched:** Yes

Runs an explicit **no-motion** LDC1612 transport recovery health check after a communication fault. It does not revive the failed transaction and does not restore Z trust. If the fault was caught by the pre-arm gate **before any bed-facing Z motion**, Z trust was never invalidated; in that case a PASS returns transport directly to `HEALTHY` and normal operations may resume without a recovery G28.

```gcode
M_BAMBOO_EDDY_RECOVERY_CHECK
```

### Behavior

- waits for a short settle window;
- reads the LDC1612 manufacturer/device IDs three times;
- leaves a reactor settle window after each read so Sovol's asynchronous `ldc1612_i2c_report` can arrive;
- requires `transport_fault_seq` to remain unchanged for the whole check;
- reports `TRANSPORT_RECOVERED` only when all identity reads are valid and no new transport evidence appeared.

### After PASS

For a fault that occurred after HOMING/PROBE motion became active:

```text
Transport state = TRANSPORT_RECOVERED
Z trust         = UNTRUSTED
Recovery armed  = YES
```

The user should then issue **one** `G28`. Safe Home establishes positive Z clearance and XY home first, then consumes the one-shot recovery authorization only for the fresh Z home. Transport returns to `HEALTHY` only after that fresh Z home succeeds.

For a fault caught by the pre-arm gate before bed-facing Z motion:

```text
Transport state = HEALTHY
Z trust         = unchanged
Recovery armed  = NO
```

Normal operations may resume; no recovery G28 is required.

### After FAIL

No Z motion is attempted. The user may wait and run the check again, or use `FIRMWARE_RESTART`. Repeated faults should trigger inspection of the Eddy cable/connector and the `extra_mcu` I2C path.

### Explicit non-goals

- does not continue the failed probe;
- does not automatically run `G28`;
- does not automatically run `FIRMWARE_RESTART`;
- does not confuse recovered transport with recovered Z coordinates;
- ordinary QGL/contact/mesh operations cannot consume recovery authorization.

---

# 9. `RUN_PROBE_VIR_CONTACT`

> **Owner:** Sovol virtual-contact path, guarded by M_Bamboo Eddy Safety  
> **Stability:** **Compatibility interface / Advanced use**  
> **Moves machine:** Yes

Runs the Eddy virtual-contact probe used by `CLEAN_NOZZLE` and Z-offset calibration.

```gcode
RUN_PROBE_VIR_CONTACT
```

### M_Bamboo safety semantics

- Contact probing is kept separate from the ordinary non-contact dynamic envelope.
- Transport-fault-tainted transactions cannot be accepted as successful.
- A latched Eddy fault cannot be bypassed by invoking this command directly.

Use directly only for controlled diagnostics; normal users should call the higher-level workflow that owns the contact operation.

---

# 10. Standard probe commands with M_Bamboo safety semantics

> **Interfaces:** `PROBE`, `PROBE_ACCURACY`, `PROBE_CALIBRATE`, `QUERY_PROBE`, `Z_OFFSET_APPLY_PROBE`  
> **Owner:** Standard Klipper probe API; project carries a modified `probe.py`  
> **Stability:** **Upstream ABI**

M_Bamboo intentionally keeps these standard names. The important project-level change is not a new command name but the safety behavior under ordinary **non-contact** Eddy probing.

### `PROBE`

```gcode
PROBE
```

Ordinary probe movement is bounded by the M_Bamboo trusted-trigger descent envelope when applicable.

### `PROBE_ACCURACY`

```gcode
PROBE_ACCURACY
```

Repeated probing inherits the same probe backend and safety policy.

### `PROBE_CALIBRATE`

Standard Klipper probe-calibration interface carried by the modified backend. It is not the same workflow as Sovol/M_Bamboo `Z_OFFSET_CALIBRATION`. On the Eddy backend, ES-R4-EC2 validates the shared fault authority before the calibration result may enter pending config; a latched or still-pending transport fault blocks persistence.

### `QUERY_PROBE`

State query only; no axis motion.

> **Important:** M_Bamboo does not document these as replacements for the full Official Klipper command manual. This section only records the behavior that the project materially affects.


### `Z_OFFSET_APPLY_PROBE`

**Stability:** Upstream ABI / advanced configuration command.  It reads the current G-code Z homing-origin offset, subtracts it from the configured probe `z_offset`, and places the resulting value into Klipper's pending config state for a later `SAVE_CONFIG`.  It performs no axis motion.

This is **not** a replacement for the project `Z_OFFSET_CALIBRATION` workflow. Use it only when intentionally applying an already-established G-code Z offset into the probe configuration. On the Eddy backend, EC2 invokes the same persistent-config safety validator before writing the pending value, so a faulted/pending-fault session is rejected.


---

# 11. `Z_OFFSET_CALIBRATION`

> **Owner:** Z Calibration / modified Sovol backend  
> **Stability:** **Public / Soak-test**  
> **Moves machine:** Yes

This is the main SV08 Max Eddy/contact Z-offset workflow. M_Bamboo materially changes its safety and sequencing while preserving the command name.

### Syntax examples

First refinement pass:

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay USE_CURRENT_Z=1 ZDBG=1
```

Post-mesh final pass:

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay USE_CURRENT_Z=1 USE_CURRENT_Z_ALLOWANCE=1.25 REHOME_XY=1 ZDBG=1
```

### Parameters

| Parameter | Default / accepted values | Purpose |
|---|---|---|
| `METHOD` | default `default`; project flow commonly uses `force_overlay` | Select calibration behavior. With existing Eddy data, `default` may return without recalibrating. |
| `USE_CURRENT_Z` | `0`; `0/1` | Preserve an already-trusted Z reference. It does **not** home unknown Z. |
| `USE_CURRENT_Z_ALLOWANCE` | `0.0`; `0..5 mm` | Adds temporary **logical** first-contact search room. Applying it does not move motors and does not lower global `position_min`. |
| `USE_CURRENT_Z_MAX` | `15.0 mm`; `>0` | Rejects implausibly high Z when `USE_CURRENT_Z=1`. |
| `REHOME_XY` | `0`; `0/1` | Explicitly reseats X/Y before final contact calibration, without `G28 Z`. |
| `REHOME_XY_Z_TOLERANCE` | `0.02 mm`; `0..0.25` | Maximum allowed absolute Z change during raw X/Y reseat. Exceeding it aborts. |
| `ZDBG` | `0`; `0/1` | Prints concise `ZDBG:` event tracing; no intended motion change. |
| `BED_TEMP` | Sovol backend default `65` °C unless caller overrides | Calibration bed target. |
| `EXTRUDER_TEMP` | Sovol backend default `130` °C unless caller overrides | Calibration nozzle target. |

### Key safety semantics

- `USE_CURRENT_Z=1` requires a trusted/homed Z and does not perform the old large `Zmax+15` runtime relabel.
- `position_min` is a safety endpoint, not a valid contact result.
- Post-mesh search allowance is temporary coordinate headroom, not part of the calibrated datum.
- `REHOME_XY=1` uses raw X/Y homing with a dZ guard and never homes Z.
- HOME-FIRST work in the ES-R4 candidate calls the atomic Safe Home real-Z-reference backend to avoid split preparation/double-hop behavior.

---

# 12. `CLEAN_NOZZLE`

> **Owner:** Nozzle Cleaner NC-R1  
> **Stability:** **Public / Soak-test**  
> **Moves machine:** Yes  
> **Depends on:** Safe homing + working `RUN_PROBE_VIR_CONTACT`

M_Bamboo manages/replaces the Sovol cleaning macro to keep all wiping planes relative to one verified contact datum and to avoid the legacy secondary plunge below the configured Z safety boundary.

```gcode
CLEAN_NOZZLE
```

### Behavior

- clears bed mesh;
- ensures safe homing as needed;
- heats nozzle for contact/cleaning;
- randomizes the contact location within the known pad area;
- runs **one** `RUN_PROBE_VIR_CONTACT`;
- performs repeated horizontal / cross-hatch wiping;
- keeps the secondary wiping stage on the validated contact-relative plane;
- finishes at a predictable Z for the following `USE_CURRENT_Z=1` calibration.

No second contact probe is intentionally added.

---

# 13. `QUAD_GANTRY_LEVEL`

> **Type:** Standard Klipper command wrapped by macro  
> **Owner:** Config optimization / print orchestration  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes

```gcode
QUAD_GANTRY_LEVEL
```

Wrapper behavior:

```text
if XYZ not homed → G28
→ QUAD_GANTRY_LEVEL_BASE
```

`QUAD_GANTRY_LEVEL_BASE` is the renamed underlying command and is not the preferred normal user entry point.

### Project configuration policy

Normal project tuning currently uses reduced QGL speed/retry/adjustment limits. A future GSL recovery interface is separate and is **not active** merely by calling this wrapper.

---

# 14. `BED_MESH_CALIBRATE`

> **Type:** Standard Klipper command wrapped by macro  
> **Owner:** Config optimization / print orchestration  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes

```gcode
BED_MESH_CALIBRATE
```

Current wrapper orchestration:

1. establish required Z calibration state if not already done;
2. run QGL if it is not applied;
3. temporarily reduce square-corner velocity for mesh motion;
4. invoke:

```gcode
BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=1 METHOD=rapid_scan
```

5. restore square-corner velocity.

### ES-R4 note

Scan/rapid-scan sessions are checked by the same Eddy fault authority. A transport-fault-tainted scan must not be accepted as a valid mesh result.

---

# 15. `START_PRINT`

> **Owner:** Print orchestration / modified Sovol macro  
> **Stability:** **Compatibility ABI**  
> **Moves machine:** Yes  
> **Normally called by:** slicer/start G-code

`START_PRINT` is not merely a stock passthrough; the project intentionally manages the Z-calibration/QGL/mesh sequence.

Current conceptual sequence:

```text
CLEAN_NOZZLE
→ reset G-code Z offset
→ first current-Z Z_OFFSET_CALIBRATION
→ QUAD_GANTRY_LEVEL
→ real G28 Z / Safe Home path
→ BED_MESH_CALIBRATE
→ final post-mesh Z_OFFSET_CALIBRATION
→ remaining Sovol print-start flow
```

Typical managed calibration calls use:

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay BED_TEMP=<target> USE_CURRENT_Z=1 ZDBG=1
```

and final pass:

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay BED_TEMP=<target> USE_CURRENT_Z=1 USE_CURRENT_Z_ALLOWANCE=1.25 REHOME_XY=1 ZDBG=1
```

> The exact macro body is release-managed; use `START_PRINT` rather than manually reproducing this chain unless performing controlled diagnostics.

---

# 16. `LDC_CALIBRATE_DRIVE_CURRENT`

> **Owner:** LDC1612 backend  
> **Stability:** **Advanced / Calibration**  
> **Moves axes:** No intended axis motion by the command itself  
> **Changes calibration state:** Yes

Typical form:

```gcode
LDC_CALIBRATE_DRIVE_CURRENT CHIP=<chip_name>
```

### ES-R4-EC2 integrity guard

A new/unrecovered LDC I2C transport fault blocks this command. After `M_BAMBOO_EDDY_RECOVERY_CHECK` succeeds and the armed fresh Safe Home `G28` completes successfully, the Eddy Safety Core marks the current transport fault sequence as trusted-through; historical faults at or below that watermark no longer block drive-current calibration. Any newer fault immediately blocks it again. During calibration it no longer reads and later restores a potentially transport-tainted `old_config`; it restores this Sovol fork's known measurement-mode CONFIG value and only exposes a pending `SAVE_CONFIG` result after the transaction-wide fault sequence remains clean.

The candidate records a transport-fault sequence at calibration start and rejects the calculated value if an I2C transport fault occurs during that transaction. A transport-tainted register read must not become persistent `reg_drive_current` configuration.

Use only when calibrating/troubleshooting the Eddy/LDC sensor.

---

# 17. `PROBE_EDDY_CURRENT_CALIBRATE`

> **Owner:** Eddy calibration backend  
> **Stability:** **Advanced / Calibration**  
> **Moves machine:** Yes  
> **Changes calibration data:** Yes

Existing mux command carried by the modified Eddy backend. It starts the manual Eddy frequency-to-height calibration flow.

```gcode
PROBE_EDDY_CURRENT_CALIBRATE CHIP=<chip_name>
PROBE_EDDY_CURRENT_CALIBRATE CHIP=<chip_name> PROBE_SPEED=5
```

| Parameter | Default | Meaning |
|---|---:|---|
| `CHIP` | required mux selector | Select the configured Eddy probe instance. |
| `PROBE_SPEED` | `5 mm/s` | Speed used by the manual calibration movement. |

This is a sensor calibration interface, not the normal print-time `Z_OFFSET_CALIBRATION` workflow. Use only when intentionally rebuilding Eddy calibration data.

**EC2 safety behavior:** the command checks the Eddy Safety Core before manual calibration begins, again before calibration motion after the manual-probe phase, and once more before writing the generated `calibrate=` table into pending config. Any latched or unhandled transport fault rejects the calibration result; transport-tainted data must not become persistent calibration.

---

# 18. `EDDY_QUERY_LOOP`

> **Owner:** Sovol LDC1612 backend carried by the project  
> **Stability:** **Advanced / Diagnostic**  
> **Moves machine:** No

Low-level query-loop control exposed by the Sovol LDC backend.

```gcode
EDDY_QUERY_LOOP SWITCH=ON
EDDY_QUERY_LOOP SWITCH=OFF
```

This is not part of normal printing or normal Eddy recovery. It is listed because the project replaces/modifies the backend that exposes it.

---

# 19. `XY_STRESS_BASELINE`

> **Owner:** M_Bamboo Diagnostics  
> **Stability:** **Optional / Diagnostic**  
> **Moves machine:** Yes

Homes the printer, records position, and dumps X/Y TMC state before a CoreXY stress test.

```gcode
XY_STRESS_BASELINE
```

Save the console output and do not restart Klipper/MCU before the matching check.

---

# 20. `XY_STRESS_RUN`

> **Owner:** M_Bamboo Diagnostics  
> **Stability:** **Optional / Diagnostic**  
> **Moves machine:** Yes — fast XY stress motion

Runs the project CoreXY stress sequence using the validated test envelope:

```text
velocity = 400 mm/s
acceleration = 15000 mm/s²
```

```gcode
XY_STRESS_RUN
```

Run only with a clear build volume and after `XY_STRESS_BASELINE`.

---

# 21. `XY_STRESS_CHECK`

> **Owner:** M_Bamboo Diagnostics  
> **Stability:** **Optional / Diagnostic**  
> **Moves machine:** Yes

Re-homes after the stress sequence and records position/TMC state for comparison with the baseline.

```gcode
XY_STRESS_CHECK
```

Recommended workflow:

```text
XY_STRESS_BASELINE
→ save output
→ XY_STRESS_RUN
→ XY_STRESS_CHECK
→ compare baseline/check output
```

---

# 22. `M_BAMBOO_Z_RELIEF` — PLANNED

> **Owner:** Recovery / Safe Home  
> **Stability:** **Planned — NOT IMPLEMENTED in ES-R4-EC2**  
> **Intended motion:** Positive Z only

Proposed purpose: mechanically unload nozzle/bed pressure after an **eligible downward-probe fault** without clearing the Eddy safety latch.

Expected design constraints if implemented:

- fault must already be latched;
- last transaction must be explicitly relief-eligible;
- +Z only;
- no XY movement;
- no Eddy probing;
- Z remains untrusted/unhomed;
- fault remains latched;
- `FIRMWARE_RESTART` is still required for a new session.

**Do not call or depend on this command yet.**

---

# 23. RC4 release installer CLI

> **Owner:** Installer / release tooling  
> **Stability:** **RC / public release interface**  
> **Changes machine state:** only with `--apply`  
> **Default mode:** dry-run

### Canonical install

```bash
./install.sh all
./install.sh all --apply
```

### Feature-scoped install

```bash
./install.sh safe_home --apply
./install.sh config_optimization --apply
./install.sh eddy_safety --apply
./install.sh diagnostics --apply
./install.sh hardware_cooling --apply
```

### Status and diff

```bash
./install.sh all --status
./install.sh all --raw-diff
```

### Restore

```bash
./install.sh all --restore
./install.sh all --restore --apply
```

`restore` means return M_Bamboo-owned surfaces to the pre-M_Bamboo state. It is not the same as downgrading to the immediately previous project release.

RC4 has no generic historical downgrade CLI. To install an older release, complete Full Restore first, then run that historical release's installer.

### Persistent backup contract

```text
CFG / macros: no persistent backup
Backend Python: /home/sovol/klipper/klippy/extras/mb_bak/ only
Transaction scratch: /tmp/M_Bamboo_SV08MAX.* only while installer is running
```

Config restore reverses the managed transformation: added blocks are removed, replaced stock parameters are restored, removed stock sections are reconstructed from release templates, and the `SAVE_CONFIG` generated tail is left untouched.

The backend backup manifest is created once and never overwritten. Legacy `.mb_baseline` may be consumed as migration input when necessary, but RC4 does not create new `.mb_baseline` or `.last_mb_*` slots.

### `--no-restart`

```bash
./install.sh all --apply --no-restart
./install.sh all --restore --apply --no-restart
```

Development/testing only. Python changes do not become active until the Klipper host process restarts.

See `docs/DEPLOYMENT_AND_ROLLBACK.md` for first-takeover provenance, atomic failure rollback, migration, Restore, and the RC4 policy of **not** implementing a generic downgrade command.

---

# 24. Project configuration interface

This section records configuration knobs or managed values that are part of the M_Bamboo project contract even though they are not standalone G-code commands.

## 24.1 Safe Home config — `[M_Bamboo_Safe_Homing]`

| Key | Candidate/default | Meaning |
|---|---:|---|
| `home_xy_position` | project value `271, 251` | XY point used before real Z home. |
| `xy_speed` | `150 mm/s` | Travel speed to the Z-home XY point. |
| `z_hop` | `5 mm` | Unknown/untrusted-Z clearance distance. |
| `z_hop_speed` | `10 mm/s` | Clearance/recovery-lift speed. |
| `post_home_z` | `10 mm` | Real post-Z-home clearance position. |

## 24.2 Eddy Safety config

| Key | Project policy | Meaning |
|---|---|---|
| `probe_below_trigger_allowance` | soak-test currently `2.0 mm` | Non-contact safety floor = lowest trusted trigger − allowance. |
| `eddy_diagnostic_level` | `0..2`, soak-test typically `2` | `0=ERROR`, `1=NORMAL`, `2=VERBOSE`. |

## 24.3 Global/config-optimization values managed by the project

These values are **configuration policy**, not new G-code syntax:

| Area | Stock / previous | M_Bamboo managed policy |
|---|---:|---:|
| `[printer] max_velocity` | `700` | `400` |
| `[printer] max_accel` | `40000` | `15000` |
| X/Y `run_current` | `3.0 A` | `2.3 A` |
| QGL `speed` | `400` | `200` |
| QGL `retries` | `15` | `5` |
| QGL `max_adjust` | `20` | `5` |
| Adaptive mesh `PGP` | `0` | `1` |
| Buffer stepper `velocity` | `150` | `80` |
| Buffer stepper `accel` | `5000` | `1900` |
| Buffer stepper `push_length` | `25` | `27` |
| `[stepper_z] position_min` | stock approximately `-10` | `-1` |

The exact release manifest/managed blocks remain the source of truth for whether a config-optimization feature is installed.

## 24.4 Hardware Cooling config

Hardware Cooling is a formal but hardware-dependent optional feature. It is **not included by `all`** and must be installed explicitly only on machines with the corresponding physical cooling modification.

Current RC4 owned transformation:

```ini
[heater_fan bed_fan]
fan_speed: 0.6
```

The installer refuses ambiguous existing values rather than taking ownership by guess.

---

# 25. Internal / deprecated backend interfaces

## `establish_real_z_reference(...)`

**Internal Python API.** Safe Home owns the atomic sequence used by HOME-FIRST Z calibration. User macros should call the public Safe Home/Z-calibration commands instead.

## `prepare_xy_for_calibration(...)`

**Internal / Deprecated.** Retained temporarily for compatibility only. New code must not split “prepare XY” and “home Z” into separate calls; use the atomic real-Z-reference backend.

## `_safe_z_hop(...)`

**Internal / Deprecated alias** in the recovery refactor. The semantic owner is the new “establish Z clearance” path.

---

# 26. Interface audit notes

## `G80`

The current recovered RC4 / ES-R4-EC2 source artifacts audited for this reference contain **no active `G80` macro, registration, or override**. Therefore this document does not invent a `G80` contract.

If an older M_Bamboo/Sovol package contains a real `G80` override, that exact source should be restored into the interface audit and documented here before the next release.

## Stock Sovol macros not listed individually

The SV08 Max `Macro.cfg` contains many stock interfaces (`PAUSE`, `RESUME`, `M109`, `M190`, `M106`, `M107`, filament macros, etc.). They are **not automatically M_Bamboo public interfaces**. They should enter this registry only when the project starts owning, replacing, or materially changing their behavior.

---

# 27. Publish / release documentation gate

Every publish must check:

- [ ] all new commands/macros appear in this registry;
- [ ] all new public parameters/variables are documented with defaults/ranges;
- [ ] every replaced stock/Klipper/Sovol command records its compatibility alias/base command;
- [ ] deprecated/removed interfaces are marked explicitly;
- [ ] fault/recovery semantics match the current backend;
- [ ] examples match the current code;
- [ ] touchscreen/slicer compatibility ABI names did not change unintentionally;
- [ ] English and Chinese references are synchronized;
- [ ] README links to this reference;
- [ ] release notes mention public-interface additions/changes/removals;
- [ ] future automated validation compares registered `M_BAMBOO_*`, managed macros, and documented interfaces.

