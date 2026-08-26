# RC5 START_PRINT Recovery Design

> Status: **design/audit reference for `rc5-dev`**  
> Public baseline: RC4. RC5 implementation and hardware fault-injection are still pending.

## Purpose

RC5 must automatically contain and recover an eligible Eddy/PREARM transport fault during print startup without blindly continuing from a partially completed startup action.

The design is deliberately narrow. It owns only the Eddy-sensitive `START_PRINT` core. It does not add MCU firmware changes, a daemon, a general workflow framework, or PLR behavior.

## Critical Klipper execution constraint

A normal Klipper G-code macro is not an exception-resumable workflow. If a nested command raises `command_error`, that macro chain unwinds. When `START_PRINT` originates from a virtual-SD print, an uncaught error that reaches `virtual_sdcard` stops file execution and marks the print errored.

Therefore automatic startup recovery cannot be:

```text
START_PRINT macro faults
-> macro terminates
-> later recovery macro runs
-> old START_PRINT magically continues
```

A start-flow owner must catch only specifically recoverable Eddy transport faults **before** they escape the top-level `START_PRINT` call.

Klipper may still emit the normal `gcode:command_error` event / `!!` response for the nested failed command. That event is useful because probe/session/gcode-move listeners perform cleanup from it. Moonraker forwards the response but does not itself cancel a print merely because the response text begins with `!!`; the decisive condition is whether the exception ultimately reaches `virtual_sdcard`.

## Minimal ownership boundary

RC5 does **not** move the whole `START_PRINT` implementation into Python.

Preferred structure:

```text
START_PRINT
  -> existing non-Eddy setup
  -> M_BAMBOO_START_SEQUENCE     # RC5 coordinator owns this core only
       CLEAN
       PRE_ZCAL
       QGL
       Z_HOME
       MESH
       POST_ZCAL
  -> existing MANUAL_FEED / LED / M400 / NOZZLE_CLOG_CHECK / final prep
  -> print body
```

The coordinator calls existing macros/commands. It must not duplicate the implementation of Safe Home, QGL, bed mesh, nozzle cleaning, or Z calibration.

## Existing dependency chain

Conceptually the current managed core is:

```text
CLEAN_NOZZLE
-> SET_GCODE_OFFSET Z=0
-> PRE-QGL Z_OFFSET_CALIBRATION
-> has_z_offset_calibrated=True
-> QUAD_GANTRY_LEVEL
-> G28 Z
-> BED_MESH_CALIBRATE
-> POST-MESH Z_OFFSET_CALIBRATION
-> has_z_offset_calibrated=False
```

`BED_MESH_CALIBRATE` also carries dependency behavior: it may establish missing calibration state and it can require QGL to be applied before scanning.

Recovery therefore has to preserve both physical completion state and software dependency state.

## Atomic stages

The coordinator treats the managed core as explicit atomic stages, not G-code line offsets:

```text
S0 CLEAN
S1 PRE_ZCAL
S2 QGL
S3 Z_HOME
S4 MESH
S5 POST_ZCAL
DONE
```

A stage is incomplete until its command returns successfully and its required completion state is accepted.

## Recovery policy by stage

### S0 CLEAN

The RC4 nozzle-cleaning flow performs its Eddy contact before the wiping moves. If that contact faults, the wipe sequence has not started.

Recovery policy:

- invalidate the failed contact transaction;
- recover transport and Z trust if required;
- restart `CLEAN_NOZZLE` from the beginning.

No wipe-progress checkpoint is required.

### S1 PRE_ZCAL

A failed pre-QGL `Z_OFFSET_CALIBRATION` is invalid as a whole.

- recover transport;
- establish fresh Z if Safety Core or current `homed_axes` requires it;
- restart the complete calibration;
- set `has_z_offset_calibrated=True` only after successful completion.

A calibration transaction is never resumed mid-contact / mid-verification / mid-Eddy calibration.

### S2 QGL

If QGL faults:

- the entire QGL attempt is incomplete;
- recover transport/Z as required;
- rerun QGL from the beginning;
- the prior successful PRE_ZCAL does not need to be repeated solely because QGL was partial.

Klipper's QGL `applied` flag is set only after an accepted completed result. Starting a new QGL resets it. A normal G28 does not clear an already successful QGL; motor-off does.

### S3 Z_HOME

If the explicit post-QGL Z home faults and bounded recovery itself successfully performs the required fresh Safe Home, that recovery homing **satisfies S3**.

Do not issue a second redundant `G28 Z`. Advance only after transport is healthy and Z trust is established.

### S4 MESH

If mesh scanning faults:

- restart the complete mesh stage;
- do not accept a partial scan;
- retain a previously completed QGL if its `applied` state remains true.

Upstream `BED_MESH_CALIBRATE` clears the active mesh at command start and installs a new mesh only after complete `probe_finalize()`. A partial scan is therefore not a completed new mesh.

The existing mesh wrapper also temporarily changes `square_corner_velocity`. RC5 must snapshot the true pre-stage value and restore it on success, recoverable failure, and terminal failure; otherwise a failed scan can leave SCV at the temporary value and poison both the retry and the eventual print.

### S5 POST_ZCAL

If final Z calibration faults:

- preserve previously completed QGL/mesh unless another condition explicitly invalidates them;
- recover transport and Z trust;
- restart the complete post-mesh calibration, including its XY reseat path.

This stage can use a temporary logical-Z search allowance. Its own guarded error path may mark Z unhomed even when PREARM caught the fault before bed-facing motion. Therefore fresh-Z decision must reconcile both layers:

```text
need_fresh_z_home =
    safety_core.z_recovery_required
    OR
    ('z' not in current_homed_axes)
```

## Error classification

The coordinator must not classify a caught `command_error` as recoverable merely because historical Safety Core state happens to contain `HARD_COMM_FAULT`.

Before each atomic stage it records the current monotonic transport fault sequence. A stage error is eligible for the Eddy recovery path only when the Safety Core classifies it as recoverable **and** the transport fault sequence advanced during that stage (or the Safety Core provides equivalent transaction-local evidence).

This prevents unrelated QGL/macro/configuration errors from being swallowed as communication recovery.

## Recovery episode rules

The budget counts independent successfully recovered fault episodes, never blind retries of the same failed Z recovery.

Current RC5 design target:

```text
MAX_START_AUTO_RECOVERIES = 3
MAX_RECOVERY_ATTEMPTS_PER_EPISODE = 1
```

Rules:

1. An eligible fault enters no-motion transport health evaluation.
2. If Z trust must be rebuilt, exactly one armed fresh Safe Home is allowed for that episode.
3. If that armed recovery fails, stop immediately. The unused start-flow budget does **not** authorize a second recovery G28 for the same episode.
4. After recovery succeeds, the failed atomic stage must complete successfully before the consecutive-fault condition is cleared.
5. If another transport fault occurs before that stage reaches a clean completion checkpoint, stop rather than repeatedly recovering the same unstable stage.
6. Only a later fault after clean stage completion is a new independent episode that may consume another start-flow budget slot.
7. Exceeding the per-start budget stops startup and requires operator inspection.

The final numeric default remains subject to RC5 hardware fault-injection validation.

## PREARM-specific recovery

PREARM remains fail-closed and performs no bed-facing motion.

A PREARM-only fault does not automatically invalidate a previously trusted physical Z reference. After no-motion transport recovery, the same stage may retry without an unnecessary G28 **only if**:

- Safety Core reports Z recovery is not required; and
- the current kinematics status still reports Z homed; and
- the owning stage has not independently invalidated/relabelled Z state.

This last condition matters for Z calibration, which deliberately revokes Z homing after certain guarded failures to prevent temporary logical-coordinate state from escaping.

## Ownership

### Eddy Safety Core remains authoritative for

- transport fault detection and monotonic fault sequence;
- PREARM fail-closed gating;
- transaction taint/abort and stream quarantine;
- Z-trust invalidation;
- no-motion transport health verification;
- one-shot armed Safe Home recovery authorization;
- hard-fault / restart-required classification.

### START coordinator owns

- current atomic startup stage;
- stage-local entry state;
- per-start recovery budget;
- classifying whether the failed stage observed a new recoverable transport episode;
- restoring startup-only temporary state;
- choosing which complete stage must rerun after successful recovery;
- returning to the outer `START_PRINT` macro only after the complete managed core succeeds.

The Eddy backend must never contain workflow knowledge such as "QGL fault means run mesh next".

## State hygiene

At every new managed start sequence:

- initialize stage/recovery state;
- normalize `has_z_offset_calibrated=False`;
- snapshot any stage-local state that must be restored;
- do not trust a stale checkpoint from a prior failed/aborted print.

After successful PRE_ZCAL:

- set `has_z_offset_calibrated=True`.

After successful POST_ZCAL, successful managed-core completion, or any terminal managed-core failure:

- restore `has_z_offset_calibrated=False`.

Mesh-stage SCV restoration and Eddy transaction/session cleanup must also run on all terminal paths.

## Feature / installer ownership

RC5 should not introduce a new installer feature solely for the coordinator.

Preferred dual-path integration:

```jinja
{% if 'M_Bamboo_Start_Sequence' in printer %}
    M_BAMBOO_START_SEQUENCE
{% else %}
    # existing RC4 managed start core
{% endif %}
```

This preserves feature independence:

- `config_optimization` without Eddy Safety -> legacy RC4 managed core remains usable;
- Eddy Safety can own coordinator backend/config without forcing START_PRINT changes by itself;
- when both are installed -> bounded coordinator path is enabled;
- restoring Eddy Safety removes the coordinator object and START_PRINT automatically falls back to the RC4 path.

START_PRINT takeover must remain provenance/lineage gated. Recognized stock/RC4/RC5 managed lineages may be transformed; unknown custom sequences must fail closed for manual review.

## Validation requirements before RC5 release

At minimum, real-machine fault injection/reproduction must verify:

1. PREARM fault before motion: no descent; bounded auto recovery; same stage restarts; trusted Z preserved only when both safety and kinematics agree.
2. CLEAN contact fault: no wipe begins; recovery followed by complete CLEAN rerun.
3. PRE_ZCAL fault: complete calibration rerun; `has_z_offset_calibrated` becomes true only after success.
4. QGL fault after partial probing/adjustment: incomplete QGL rejected; complete QGL rerun.
5. Z_HOME fault: successful recovery G28 satisfies stage; no double-home loop.
6. MESH mid-scan fault: mesh remains unset until full rescan; prior valid QGL retained; SCV restored correctly.
7. POST_ZCAL fault: prior mesh retained; stage-local Z trust reconciled; full POST_ZCAL rerun.
8. Recovery G28 itself faults: immediate terminal lock; no same-episode second armed G28.
9. A second fault before the recovered stage completes: terminal stop, not another recovery loop.
10. A new fault after clean stage completion: new episode may recover until total start budget is exhausted.
11. Non-Eddy error: propagates normally and is not auto-recovered.
12. Terminal failure / next print: no stale calibration flag, SCV, checkpoint, recovery token, active transaction, client, or budget survives incorrectly.
13. Moonraker/UI: nested recovered `!!` remains diagnostic only and does not cause an independent external cancel in the supported SV08 Max UI path.

## Release gate

Mock tests are useful for state-machine correctness but are insufficient to promote the coordinator. RC5 remains engineering/development status until the real-machine fault-injection matrix above validates the actual Klipper/Moonraker/Sovol execution chain.
