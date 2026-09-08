# RC5 Combined RS1 + GR1 Hardware Candidate

Status: **development / hardware validation pending**. Not a public release.

## Identity

Materialized build chain:

```text
RC4 exact public backend
  -> exact 2026-09-08 hardware-tested RC5 intermediate
     probe_eddy_current.py SHA256:
     dcb78d4d7d5108236eca23a225e6e582e1b128419bf10c8a5b83cf8de346ced0
  -> RS1 rapid-scan lifecycle restoration
  -> GR1 generic bounded Recovery Supervisor
```

Combined runtime target:

```text
probe_eddy_current.py
5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29
```

The intermediate `dcb78d...` hash is development migration lineage only because it was installed on the hardware validation machine. It is not a public release compatibility promise.

Offline / Actions ZIP hashes are validation evidence only and must not enter final public release lineage unless the corresponding artifact is intentionally published.

## RS1 scope

RS1 intentionally preserves healthy rapid-scan measurement semantics:

- no `SAMPLE_TIME` change;
- no scan-speed change;
- no scan-height change;
- no path/interpolation change;
- no sample timestamp/window change;
- no added LDC I2C query rate.

RS1 adds callback/session lifetime protection so already-queued rapid lookahead callbacks become no-ops after the owning scan session has ended or released its gather object. This directly addresses the 2026-09-08 `Exception in flush_handler` traceback where a stale callback dereferenced `_gather=None` after an active-scan transport fault.

## GR1 scope

GR1 provides bounded automatic recovery at synchronous public-command boundaries for:

```text
G28
RUN_PROBE_VIR_CONTACT
CLEAN_NOZZLE
Z_OFFSET_CALIBRATION
QUAD_GANTRY_LEVEL
BED_MESH_CALIBRATE
```

Rules:

1. only the outermost supported public command owns recovery;
2. nested supported commands pass through to that owner;
3. while `M_Bamboo_Start_Sequence` is active, the START coordinator remains the sole recovery owner;
4. only new stage/invocation-local `transport_fault_seq` or `preflight_failed_count` evidence is eligible;
5. non-Eddy command errors propagate unchanged;
6. one direct-command recovery attempt per invocation;
7. the failed operation is replayed from its beginning;
8. a second Eddy/PREARM fault before replay completes is terminal;
9. recovery failure itself is terminal;
10. recovery never begins from sensor/bulk/lookahead/toolhead-flush callbacks.

## START_PRINT ownership

`START_PRINT` continues to use the hardware-tested `M_Bamboo_Start_Sequence` stage coordinator and its total recovery budget. GR1 wrappers explicitly yield while that coordinator is active, preventing double recovery by nested QGL / mesh / ZCAL commands.

The managed macro now uses one `CONFIG_START_PRINT_CORE` dual-path block:

```text
M_Bamboo_Start_Sequence ready -> managed RC5 sequence
otherwise                    -> RC4-compatible fallback
```

## Installer lineage

Development installer target:

```text
probe_eddy_current.py = 5e108f1d...
```

Recognized development migration source for the hardware-test machine:

```text
dcb78d4d...
```

The development manifest explicitly marks this as non-public lineage.

## Automated validation

GitHub Actions `RC5 combined validation`, run `34204058321`, passed all gates after correcting a test-only floating-point equality assertion:

- exact combined runtime identity;
- Python compile;
- actual-class RS1 callback regression;
- actual-class GR1 success / non-Eddy / recover-replay / second-fault / nested-owner / recovery-failure regression;
- config parser comment-colon regression;
- real unknown-key fail-closed regression;
- RC4 START_PRINT -> RC5 managed-core transformation;
- second-pass START_PRINT idempotence;
- public/dev lineage separation;
- development candidate packaging.

## Hardware validation required before release

The combined candidate is ready for staged hardware validation, not release promotion.

Order:

1. post-install status / no motion;
2. normal G28;
3. direct rapid-scan baseline repeated at fixed thermal state;
4. full `BED_MESH_CALIBRATE` wrapper;
5. confirm any natural active-scan transport fault aborts without Klipper shutdown;
6. confirm direct-command GR1 automatically performs bounded recovery and whole-operation replay;
7. healthy QGL / ZCAL / CLEAN direct-command paths;
8. complete START_PRINT healthy path;
9. controlled recovery matrix including second-fault stop and recovery-failure stop.

Do not change rapid-scan speed, sample time, scan height, or calibration caching during this validation cycle; those changes would contaminate RC4-vs-RS1 reliability attribution.
