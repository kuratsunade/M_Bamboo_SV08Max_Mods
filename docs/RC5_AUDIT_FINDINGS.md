# RC5 Safety / START Recovery Audit Findings

Status: historical design audit for `rc5-dev`. SR1/RS1/GR1 are now implemented. The implementation-order list below is historical rationale, not a current task list. Current validation and blockers are in [RC5 Test Evidence](RC5_TEST_EVIDENCE.md).

This document records source-level findings that materially affect RC5 implementation. It is not release marketing copy.

## 1. PREARM remains a safety invariant

Real-machine history established that bed-strike risk existed before PREARM and was stopped after PREARM was added. RC5 therefore treats the PREARM semantics as locked unless an equal-or-stronger replacement is demonstrated.

Main protected entry paths currently include:

- Safe Home Z (`SAFE_HOME_Z`);
- normal automatic probe sessions used by QGL / ProbePoints (`PROBE_SESSION`);
- Eddy scan / rapid-scan sessions (`BED_MESH_SCAN`);
- explicit contact probe (`CONTACT_PROBE`);
- non-contact Eddy calibration (`EDDY_CALIBRATION`).

PREARM is intentionally session/operation-level rather than per-point for a multi-point probe session. A new fault during the active session is handled by the runtime transaction/fault-sequence guard. Adding multiple identity-read health checks before every individual point would increase I2C traffic and is not justified by current evidence.

## 2. RC4 production still has the HF2 late-terminal cleanup bug

The current RC4 release `probe_eddy_current.py` catches `command_error` around `phoming.probing_move()`, but sample finalization occurs afterward:

```python
result = self._gather.pull_probed(probe_method=method)[0]
self._require_transaction_transport_clean(tx, 'PROBE')
```

If `pull_probed()` raises (for example `probe_eddy_current sensor outage`), `_active_transaction` is not cleared by `_run_logged_probe()`.

This is the exact failure class demonstrated during HF2: the physical LDC stream can already be stopped/quarantined while the host safety object still retains a stale active transaction. HF2.1 corrected the engineering backend, but that terminal-cleanup correction was not carried into the RC4 release backend.

### Rapid scan has the same structural hole

`EddyScanningProbe.pull_probed_results()` can raise during gather/final transport acceptance. `gcode:command_error` invokes `end_probe_session()`, which removes the gather/client and clears `_active_scan_session`, but the current `end_probe_session()` does not terminalize/clear the scan transaction in `_active_transaction`.

RC5 must provide a single terminal cleanup rule for both triggered probes and scan transactions:

- snapshot failure state/evidence;
- preserve transport taint/fault sequence;
- fail a consumed armed-recovery attempt if applicable;
- never rewrite an already-aborted transaction as success;
- clear `_active_transaction` on every terminal exception path;
- close/finish the gather/session deterministically.

This correction is a prerequisite for automatic START recovery.

## 3. `gcode:command_error` is compatible with a top-level START coordinator

Klipper nested macro execution emits an error response (`!!`) and sends `gcode:command_error` before re-raising the `CommandError`.

Relevant listeners are cleanup-oriented (notably probe session cleanup and G-code move state resynchronization). Moonraker forwards G-code responses as `server:gcode_response`; it does not cancel a print merely because the response string begins with `!!`.

The virtual-SD print becomes errored only if the exception ultimately escapes the top-level command executed from the print file. Therefore a Python START coordinator may:

1. invoke an existing stage/macro;
2. allow normal Klipper command-error cleanup/event semantics to run;
3. catch the re-raised exception at the coordinator boundary;
4. verify it is specifically a recoverable Eddy transport fault;
5. recover and rerun/advance the atomic stage;
6. return success to the original `START_PRINT` call only after the entire start flow succeeds.

A hard/non-Eddy/exhausted fault must be re-raised so virtual SD terminates normally.

The visible transient `!!` should remain as fault/recovery evidence unless hardware/UI validation demonstrates an unacceptable Sovol frontend side effect.

## 4. Existing START_PRINT has a stale dependency flag failure mode

Current START flow sets:

```text
_global_var.has_z_offset_calibrated = True
```

after PRE-ZCAL and resets it only near the end of START_PRINT. If QGL, Z home, mesh, or POST-ZCAL aborts before that final reset, the flag can remain `True`.

The wrapped `BED_MESH_CALIBRATE` consults that flag and may subsequently skip a prerequisite Z calibration. Thus a failed START can poison the dependency state of a later independent mesh/start action.

RC5 START ownership must normalize this startup-only flag:

- false at new start entry;
- true only after successful PRE-ZCAL when needed by the mesh wrapper;
- false after successful POST-ZCAL/start completion;
- false on every terminal failure/abort path.

## 5. Recovery checkpoints must track semantic stages, not G-code line offsets

Current recommended atomic stages:

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

A failed stage is not resumed mid-command. The whole atomic stage is either rerun or, where recovery itself satisfies the stage, marked complete.

Key dependencies:

- partial QGL -> rerun complete QGL;
- successful QGL remains applied across a normal G28 as long as Z motors remain enabled;
- BED_MESH_CALIBRATE clears the active mesh at command start and installs a new mesh only after complete finalization, so a mid-scan fault -> rerun full mesh;
- POST-ZCAL failure does not by itself invalidate an already complete mesh;
- a successful armed Safe Home G28 caused by an S3 Z-home fault itself satisfies S3; do not immediately double-home.

## 6. Eddy `z_recovery_required` is not sufficient to decide whether START needs a fresh Z home

This is a cross-layer issue.

POST-ZCAL with `USE_CURRENT_Z_ALLOWANCE` may temporarily relabel logical Z upward to create search room, then relabel a valid contact datum to Z=0. `z_offset_calibration.py` deliberately wraps sensor calls and invalidates Z homing on a sensor `command_error`, including a PREARM rejection that may occur before physical Z motion.

At the same time, the Eddy Safety Core intentionally does **not** set `_z_recovery_required` for a PREARM fault caught before bed-facing motion, because the safety core itself did not invalidate the pre-existing physical Z reference.

Therefore the START coordinator must reconcile both layers after transport recovery:

```text
fresh Z home required if:
    Eddy Safety says z_recovery_required
    OR
    toolhead current homed_axes does not contain Z
```

If the transport fault was PREARM-only and Z remains homed, no unnecessary G28 is required. If ZCAL deliberately revoked Z because a temporary coordinate transaction was interrupted, perform a fresh Safe Home even if Eddy Safety's own `z_recovery_required` flag is false.

## 7. Recovery episode policy

Initial RC5 START policy remains:

```text
MAX_START_AUTO_RECOVERIES = 3
MAX_RECOVERY_ATTEMPTS_PER_EPISODE = 1
```

The first number counts independent fault episodes that each recover successfully during one START flow. It does not authorize repeated blind G28 attempts for one fault.

For one episode:

- no-motion health evaluation may be bounded/repeated without Z motion if desired;
- if Z must be rebuilt, exactly one armed Safe Home recovery transaction is allowed;
- failure of that armed transaction immediately hard-locks the episode and terminates START;
- after a full successful recovery, a later independent transport fault is a new episode and may consume another START budget slot.

The exact number/schedule of automatic **no-motion** health-check retries remains an implementation/validation question. It is distinct from the one-shot armed Z recovery limit.

## 8. Immediate RC5 implementation order

1. Fix triggered-probe late terminal cleanup in production.
2. Fix scan-session terminal transaction cleanup in production.
3. Add tests/simulation covering stale-transaction regression.
4. Add the small START coordinator with stage/checkpoint state and unconditional terminal cleanup of startup-only flags.
5. Add bounded automatic transport recovery at the coordinator boundary.
6. Validate every START stage fault injection/reproduction path before enabling transparent recovery by default.

Do not build the coordinator on top of the unfixed RC4 transaction-lifecycle bug.
