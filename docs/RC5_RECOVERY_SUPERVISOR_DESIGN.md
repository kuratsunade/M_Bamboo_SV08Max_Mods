# RC5 Generic Recovery Supervisor

> Status: development only on `rc5-dev`; not released.
>
> Public baseline remains RC4. This document supersedes the START-only ownership assumption in `RC5_START_RECOVERY_DESIGN.md` while preserving the validated START stage/replay rules.

## Goal

RC5 should prefer automatic recovery whenever an Eddy/PREARM transport fault can be proven safe to contain and replay. The command category does not decide whether recovery is automatic; the physical/transport state and the existence of a known replay contract do.

The central rule is:

> **Recovery policy is global; replay policy is operation-specific.**

A supported operation should behave as:

```text
new transport evidence
-> invalidate the current atomic operation
-> reach a safe synchronous owner boundary
-> no-motion transport identity recovery
-> rebuild Z trust only when required
-> replay the whole operation once
-> success, or fail closed
```

## Why recovery must stay outside rapid-scan callbacks

The 2026-09-08 hardware fault showed that a queued rapid-scan lookahead callback can execute from Klipper's motion flush context after the scan owner has already entered teardown. A callback that dereferences released scan state can escape as an internal `flush_handler` exception and shut Klipper down.

Therefore:

- I2C / bulk / timing / lookahead callbacks may latch, taint, quarantine, request abort, or become no-ops;
- they must not run G28, retry a command, or throw a workflow recovery exception;
- recovery begins only after the failed operation reaches a normal synchronous G-code command owner.

RS1 owns the callback/session lifetime fix. GR1 owns the later recovery/replay decision.

## Supported direct-operation contracts in GR1

The first generalized supervisor wraps these public commands:

```text
G28
RUN_PROBE_VIR_CONTACT
CLEAN_NOZZLE
Z_OFFSET_CALIBRATION
QUAD_GANTRY_LEVEL
BED_MESH_CALIBRATE
```

The contract for each is a whole-operation replay, never an offset/point continuation.

### G28

A failed homing operation is replayed from the beginning after transport recovery. If the Safety Core requires fresh Z trust during recovery, one direct Safe Home reconstruction is allowed. Failure of that reconstruction is terminal.

### RUN_PROBE_VIR_CONTACT

The failed contact transaction is discarded. After transport/Z recovery, run a new contact transaction once.

### CLEAN_NOZZLE

The current NC-R1 path performs Eddy contact before the wiping sequence. A contact fault therefore invalidates CLEAN as a whole; after recovery CLEAN restarts from the beginning.

### Z_OFFSET_CALIBRATION

Contact, verification, and Eddy calibration are one atomic calibration operation for recovery purposes. Partial results are discarded and the entire command is replayed once.

### QUAD_GANTRY_LEVEL

A partial QGL is not continued from a remaining point. After recovery, the complete public QGL command runs again from the current real gantry state.

### BED_MESH_CALIBRATE

A partial mesh is always invalid. After recovery, the complete public BED_MESH wrapper runs again. No partial rapid-scan dataset is accepted.

## Outermost-owner rule

Only one recovery owner may exist for an invocation tree.

Example, direct BED_MESH:

```text
BED_MESH_CALIBRATE          <-- owner
  G28                       pass-through
  Z_OFFSET_CALIBRATION      pass-through
  QUAD_GANTRY_LEVEL         pass-through
  BED_MESH_CALIBRATE_BASE   pass-through / native
```

If a nested command faults, the error propagates to BED_MESH, which performs one recovery and replays the whole BED_MESH operation.

For START_PRINT:

```text
START_PRINT
  M_BAMBOO_START_SEQUENCE   <-- existing outer owner
    CLEAN
    PRE_ZCAL
    QGL
    Z_HOME
    MESH
    POST_ZCAL
```

While `M_Bamboo_Start_Sequence.active` is true, generic wrappers are transparent. This prevents a nested QGL/MESH command from consuming one recovery and then allowing START to consume another recovery for the same episode.

The current START coordinator remains in place for this hardware candidate because its healthy path has already been exercised on the machine. A later cleanup may consolidate both owners behind one internal API after hardware validation.

## Eligibility

A command error is eligible for automatic transport recovery only when the command-local monotonic marker changes:

```text
(transport_fault_seq, preflight_failed_count)
```

This catches both active transport faults and PREARM failures that exhaust without a new asynchronous fault-sequence report.

A normal macro/config/motion error without new Eddy evidence propagates unchanged.

## Recovery action

For one eligible episode:

1. run the existing no-motion LDC identity recovery check;
2. require transport state `HEALTHY` or `TRANSPORT_RECOVERED`;
3. reject `restart_required=True`;
4. if Safety Core reports `z_recovery_required`, or kinematics no longer reports Z homed, run exactly one fresh M_Bamboo Safe Home reconstruction;
5. replay the owning operation from its beginning exactly once.

## Budgets

### Direct public command

```text
MAX_AUTO_RECOVERIES_PER_INVOCATION = 1
```

If the replay sees a second new Eddy/PREARM fault before completion, stop immediately.

### START_PRINT

The existing START policy remains:

```text
MAX_START_AUTO_RECOVERIES = 3 independent episodes
MAX_RECOVERY_ATTEMPTS_PER_EPISODE = 1
```

A recovered START stage must complete cleanly before a later fault can count as a new independent episode.

## Fail-closed cases

Automatic replay is refused when:

- no new command-local Eddy/PREARM evidence exists;
- transport identity recovery fails;
- Safety Core requires firmware restart;
- fresh Safe Home recovery fails;
- the replay experiences a second Eddy/PREARM fault before completion;
- a non-Eddy error occurs on the initial attempt or replay.

## Rapid-scan compatibility rule

GR1 must not modify:

- `SAMPLE_TIME`;
- rapid-scan speed, path, scan height;
- lookahead timestamp calculation;
- measurement window;
- `note_probe_and_position()` semantics;
- mesh interpolation;
- LDC query/sample rate.

RS1 adds only session lifetime guards so stale queued callbacks cannot touch an ended gather object.

## Hardware validation plan

### 1. Status / load

After restart:

```gcode
M_BAMBOO_EDDY_STATUS
M_BAMBOO_RECOVERY_STATUS
```

Supervisor must be ready and must report the expected wrapped command set.

### 2. Healthy direct rapid baseline

Use the existing RC4-like rapid scan path repeatedly. Healthy scans must show no recovery and no change in accuracy/timing behavior attributable to GR1.

### 3. Full BED_MESH wrapper

Run the public `BED_MESH_CALIBRATE`. If a natural raw34/raw36 occurs in a prerequisite or rapid scan, expected behavior is:

```text
current BED_MESH invalid
-> no Klipper shutdown
-> automatic transport recovery
-> optional fresh Safe Home if required
-> full BED_MESH replay once
```

### 4. Direct command recovery

Validate natural or controlled host-side fault evidence for CONTACT, ZCAL and QGL. Each direct command may recover once and must stop on a second same-invocation fault.

### 5. START nested ownership

Run START_PRINT and verify generic wrappers do not independently consume recovery while `M_Bamboo_Start_Sequence` is active.

## Release status

GR1 is not release behavior until the combined RS1 + GR1 candidate passes healthy-path rapid-scan regression and real-machine recovery tests.
