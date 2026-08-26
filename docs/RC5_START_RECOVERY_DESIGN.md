# RC5 START_PRINT Recovery Design

Status: design/audit draft for `rc5-dev`.

## Purpose

RC5 must allow a recoverable Eddy transport fault during print startup to be contained and, when safe, recovered without blindly continuing from a partially completed startup action.

The design is deliberately limited to print-start orchestration. It does not add MCU firmware changes, a daemon, or a general PLR subsystem.

## Critical execution constraint

A normal Klipper G-code macro is not an exception-resumable workflow. If a nested command raises `command_error`, the macro call unwinds. When the `START_PRINT` call originates from a virtual-SD print, an uncaught `command_error` also causes `virtual_sdcard` to stop processing the file and mark the print as errored.

Therefore a truly automatic startup recovery cannot be implemented as:

```text
START_PRINT macro faults
-> macro terminates
-> later recovery macro runs
-> old START_PRINT magically continues
```

A start-flow owner must retain the active checkpoint and absorb only specifically recoverable Eddy faults before they propagate to the virtual-SD file executor. Hard/non-Eddy faults must still propagate and terminate the print.

## Existing RC4 startup dependency chain

Conceptually:

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
-> MANUAL_FEED / LEDs / NOZZLE_CLOG_CHECK
-> print body
```

`BED_MESH_CALIBRATE` also contains its own dependency checks:

- if `has_z_offset_calibrated` is false, it establishes calibration state;
- if QGL is not applied, it runs QGL;
- then it starts a fresh adaptive rapid-scan mesh.

This means recovery must preserve both physical state and software completion flags.

## Proposed atomic stages

The coordinator should treat startup as explicit atomic stages, not line offsets:

```text
S0 CLEAN
S1 PRE_ZCAL
S2 QGL
S3 Z_HOME
S4 MESH
S5 POST_ZCAL
S6 FINALIZE
DONE
```

The checkpoint is the stage that must be considered incomplete if a recoverable fault occurs.

## Recovery policy by stage

### S0 CLEAN

If Eddy/contact transport faults during `CLEAN_NOZZLE`:

- abort the failed cleaner transaction;
- recover transport;
- if Z trust was invalidated, perform one armed Safe Home recovery;
- rerun `CLEAN_NOZZLE` from its beginning.

A partially completed wipe is not accepted as completion.

### S1 PRE_ZCAL

If the first `Z_OFFSET_CALIBRATION` faults:

- the calibration attempt is invalid;
- recovery must re-establish Z trust if required;
- rerun the complete pre-QGL calibration;
- set `has_z_offset_calibrated=True` only after successful completion.

`Z_OFFSET_CALIBRATION` resets G-code Z offset during its preparation and may temporarily relabel logical Z during the post-mesh path, so a failed calibration must never be resumed mid-function.

### S2 QGL

If QGL faults:

- QGL must be rerun from the beginning;
- partial actuator adjustments are not considered a completed level;
- the preceding successful pre-QGL calibration does not need to be rerun solely because QGL was partial;
- recovery G28 re-establishes the Z datum before QGL is retried.

Klipper's QGL `applied` flag is reset when a new QGL starts and becomes true only after a completed/retry-accepted result. A normal G28 does not reset an already-successful QGL; motor-off does.

### S3 Z_HOME

If the explicit post-QGL `G28 Z` faults and the bounded recovery path successfully performs a fresh Safe Home Z homing transaction, that recovery homing satisfies S3.

Do **not** immediately issue another redundant G28. Advance to S4 only after the recovery reports transport healthy and Z trust re-established.

### S4 MESH

If bed mesh faults:

- rerun the entire mesh stage;
- do not rerun a previously completed QGL unless QGL state is no longer applied;
- do not accept any partial scan.

Upstream `BED_MESH_CALIBRATE` clears the active mesh at command start and installs the new mesh only in `probe_finalize()` after a complete valid dataset. Therefore an interrupted mesh does not leave a half-built mesh as active state.

### S5 POST_ZCAL

If the final post-mesh Z calibration faults:

- preserve a previously completed mesh unless another condition invalidates it;
- recover Z trust;
- rerun the complete post-mesh Z calibration, including its explicit XY reseat path;
- do not rerun QGL/mesh solely because final Z calibration faulted.

### S6 FINALIZE

This stage contains non-Eddy print preparation (`MANUAL_FEED`, LEDs, clog check, etc.). A non-Eddy error is not eligible for Eddy auto-recovery and must propagate normally.

## Recovery episode rules

A recovery budget must count *independent successful fault episodes*, not blind retries of the same failed Z recovery.

Recommended initial policy for one `START_PRINT` invocation:

```text
MAX_START_AUTO_RECOVERIES = 3
MAX_RECOVERY_ATTEMPTS_PER_EPISODE = 1
```

Rules:

1. A recoverable transport fault may enter no-motion health evaluation.
2. If Z trust was invalidated, exactly one armed Safe Home recovery is allowed for that episode.
3. If that armed recovery fails, stop immediately and propagate a hard error. Do not attempt recovery #2/#3 for the same episode.
4. If recovery succeeds and startup later reaches another independent transport fault, that new episode may consume another start-flow recovery budget slot.
5. Exceeding the per-start budget stops startup and requires operator inspection.

PREARM-only faults caught before bed-facing motion do not automatically invalidate Z; after transport is re-verified, the same stage can be retried without an unnecessary G28 when the safety core explicitly reports Z trust unchanged.

## Ownership

### Eddy Safety remains authoritative for

- transport fault detection and monotonic fault sequence;
- PREARM fail-closed gate;
- transaction abort / stream quarantine;
- Z-trust invalidation;
- no-motion transport health verification;
- one-shot armed Safe Home recovery authorization;
- hard-fault / restart-required decision.

### START_PRINT coordinator owns

- current startup stage;
- stage completion state;
- per-start recovery budget;
- deciding which atomic stage must be rerun after a successful safety recovery;
- restoration/cleanup of startup-only macro state such as `has_z_offset_calibrated`;
- returning success to the slicer only after the complete start chain succeeds.

The Eddy backend must not contain hard-coded knowledge such as "fault happened in QGL, therefore run BED_MESH next".

## Implementation direction

A plain macro-only resume design is insufficient because an uncaught `command_error` terminates the virtual-SD print command stream. The preferred RC5 direction is a small host-side start-flow coordinator exposed through the existing `START_PRINT` ABI (for example, the existing macro may delegate to one coordinator command).

This coordinator is intentionally not a general workflow framework. It should:

- execute one existing public/compatibility stage at a time;
- catch only errors that the Eddy Safety Core classifies as recoverable transport faults;
- run bounded recovery through existing Eddy/Safe Home APIs;
- retry/advance according to the stage table above;
- propagate every non-recoverable, non-Eddy, exhausted-budget, or failed-recovery error unchanged enough to stop the print.

Implementation must avoid duplicating QGL, mesh, calibration, or Safe Home algorithms inside the coordinator.

## State hygiene

At a new `START_PRINT` invocation:

- initialize coordinator stage/budget state;
- normalize `has_z_offset_calibrated=False` before beginning the managed chain;
- do not trust stale checkpoint state from a previous failed/aborted print start.

After successful PRE_ZCAL:

- set `has_z_offset_calibrated=True`.

After successful POST_ZCAL / completed startup or any terminal startup failure:

- restore `has_z_offset_calibrated=False`.

A terminal cleanup path is mandatory so a failed start cannot poison the dependency logic of the next print.

## Validation requirements before RC5 release

At minimum inject/reproduce faults in each Eddy-bearing stage and verify:

1. PREARM fault before motion: no Z descent; transport can recover; same stage restarts; existing Z trust preserved when reported safe.
2. CLEAN contact fault: failed cleaner stays failed; recovery then complete cleaner rerun.
3. PRE_ZCAL contact/non-contact fault: calibration reruns from start; completion flag only changes after success.
4. QGL fault after at least one probe/adjustment: partial QGL not accepted; complete QGL rerun.
5. Z_HOME fault: successful recovery G28 satisfies stage; no double-home loop.
6. MESH mid-scan fault: mesh remains unset/invalid until full rescan; successful prior QGL retained.
7. POST_ZCAL fault after mesh completion: mesh retained; full post-ZCAL rerun.
8. Recovery G28 itself faults: immediate terminal lock; no same-episode second armed G28.
9. New independent fault after a successful recovery: new episode may recover until start budget is exhausted.
10. Non-Eddy startup error: coordinator does not misclassify or auto-recover it.
11. Terminal failure/new print: no stale `has_z_offset_calibrated`, checkpoint, token, or recovery budget survives incorrectly.

## Open implementation question

Nested G-code execution currently emits the normal `gcode:command_error` event and `!!` response before the coordinator can catch a raised `command_error`. The virtual-SD file can still be protected if the coordinator catches the exception before its top-level START_PRINT handler returns, but RC5 must validate Moonraker/UI behavior and ensure the transient internal error response does not itself trigger an unwanted cancel path.

If that UX/host behavior is unacceptable, a narrower direct-call/catch path or another minimal mechanism will be required. Do not alter generic Klipper `gcode.py` solely to suppress this message.
