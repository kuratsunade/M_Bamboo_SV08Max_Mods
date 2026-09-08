# RC5 Combined Hardware Candidate — Build Order

> Development-only build contract for the next SV08 Max hardware validation candidate.

## Canonical runtime lineage

Do **not** build the next candidate by treating the current intermediate `rc5-dev/backend/probe_eddy_current.py` as authoritative.

The canonical chain is:

```text
RC4 public exact release payload
    |
    +-- exact hardware-tested RC5 candidate reconstruction
    |     probe_eddy_current.py SHA256:
    |     dcb78d4d7d5108236eca23a225e6e582e1b128419bf10c8a5b83cf8de346ced0
    |
    +-- RS1 rapid-scan lifecycle guard
    |     patches/10_rc5_rs1_rapid_scan_lifecycle_guard.patch
    |
    +-- GR1 generic bounded recovery supervisor
          patches/11_rc5_gr1_generic_recovery_supervisor.patch

= next combined RS1 + GR1 hardware candidate
```

The hardware-tested exact candidate is the code that produced the 2026-09-08 dry-run with exactly two writes: the managed START_PRINT core and `probe_eddy_current.py`. It contains:

- terminal Eddy calibration client removal through `finally`;
- exposed PREARM check/failure counters;
- whole late-finalization terminal cleanup for normal probe transactions;
- rapid-scan terminal cleanup;
- embedded `MBambooStartSequence` (`RC5-SR1`);
- `M_Bamboo_Start_Sequence` printer object.

This exact candidate, not an earlier repository intermediate, is the runtime base for RS1/GR1.

## Why this order is mandatory

The machine has already exercised the exact candidate healthy path through:

```text
Safe Home
CONTACT
CLEAN_NOZZLE
Z_OFFSET_CALIBRATION
QUAD_GANTRY_LEVEL
```

The same candidate then exposed the rapid-scan stale-lookahead callback shutdown during a real transport fault.

Therefore the next test should change only the known fault-path lifetime bug plus the requested outer recovery ownership. Reintroducing an older backend intermediate would invalidate that comparison.

## Patch responsibility

### Exact candidate reconstruction

Reconstructs what was actually installed/tested on hardware. It is development lineage, not a public release claim.

### RS1

Only callback/session lifetime safety:

- ended scan callbacks become no-ops;
- released `_gather` is never dereferenced from queued lookahead callback;
- no rapid-scan measurement parameter changes.

### GR1

Only synchronous outer-owner recovery/replay:

- public command owner catches a normal propagated command error;
- command-local Eddy/PREARM evidence gates recovery;
- no-motion identity recovery;
- fresh Safe Home only when required;
- whole owning operation replayed once;
- second same-invocation transport fault stops.

GR1 does not execute from sensor/bulk/lookahead/flush callbacks.

## START ownership compatibility

The existing hardware-tested `MBambooStartSequence` remains the outer owner during START_PRINT for this candidate.

GR1 wrappers detect `M_Bamboo_Start_Sequence.active` and become transparent pass-throughs. This prevents nested direct-command recovery from double-counting/retrying a START stage.

A later refactor may unify both under one internal supervisor API, but only after the combined hardware candidate proves the behavior.

## Hash policy

The exact development backend hash `dcb78d...` may exist in `rc5-dev` as a development migration source because a real test machine contains it.

Offline ZIP hashes are validation evidence only and must not enter final public installer lineage.

Before final RC5 release, a build gate must reject development-only hashes from public compatibility/target tables unless the corresponding artifact was intentionally published and supported.

## Next hardware-test sequence

After offline/static validation of the combined runtime:

1. restart and check `M_BAMBOO_EDDY_STATUS` + `M_BAMBOO_RECOVERY_STATUS`;
2. direct `_BASE` rapid scan baseline x10 (GR1 intentionally idle);
3. RC4-like Safe Home -> rapid scan baseline;
4. public `BED_MESH_CALIBRATE` full wrapper, observing any natural recovery;
5. direct CONTACT/ZCAL/QGL recovery paths when safe evidence is available;
6. START_PRINT nested ownership and complete print;
7. controlled same-operation second-fault and recovery-failure fail-closed tests only after healthy behavior is proven.
