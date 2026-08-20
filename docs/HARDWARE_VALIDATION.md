# ES-R4-EC2 Hardware Validation Guide

Status: **RC4 healthy-path validation passed; one natural FS1.1 raw-34 fault/recovery path passed end-to-end; continued soak remains open**

The purpose of this test plan is to validate ordering and safety semantics, not only successful printing.

## A. Healthy regression first

Run these before any fault experiment:

1. Fresh Klipper restart -> `M_BAMBOO_EDDY_STATUS`.
2. Bare `G28`.
3. Repeated `G28`.
4. `G28 X`, `G28 Y`, `G28 Z` from a normal safe position.
5. Healthy `QUAD_GANTRY_LEVEL`.
6. Healthy `RUN_PROBE_VIR_CONTACT`.
7. Healthy `Z_OFFSET_CALIBRATION` using the RC4/ZC-FR1 flow.
8. Healthy `BED_MESH_CALIBRATE` / rapid scan.
9. HOME-FIRST Z calibration: verify exactly one pre-XY clearance hop.

After each major step, capture:

```gcode
M_BAMBOO_EDDY_STATUS
```

## B. Recovery-clearance regression

The critical invariant is:

> An untrusted Z must obtain positive-only clearance before any XY travel.

Test the software sequence from a controlled low-but-safe Z position:

1. Ensure X/Y are homed.
2. Use a controlled test path that leaves Z marked unhomed without mechanically pressing the bed.
3. Issue `M_BAMBOO_HOME_Z`.
4. Confirm the log shows the unknown-Z positive clearance **before** the move to the Z-home XY position.
5. Confirm there is no double-hop in `M_BAMBOO_HOME_ALL` and HOME-FIRST Z calibration.

Do not create the test state by intentionally crashing the nozzle.

## C. Transport-fault sequencing

Validate these observable properties from real logs:

- Every non-zero `ldc1612_i2c_report` increments `transport_fault_seq`.
- The decoded bit names and raw bitmask are retained.
- A pending sequence that has not yet been consumed by the reactor blocks a new Eddy operation.
- `transport_fault_seq_handled` catches up after the safety core consumes the event.
- If `NO_TRIGGER` is seen first and direct I2C evidence arrives later, state upgrades to `HARD_COMM_FAULT` while first-fault evidence remains visible.

## D. Active-probe stop validation

This is the most important hardware gate and must be done only with a controlled test setup that limits possible nozzle/bed force.

Required evidence:

```text
I2C transport fault
-> transaction TAINTED
-> active trsync SENSOR_ERROR stop requested
-> downward Z motion halts
-> HomingMove reconstructs halt position
-> final transaction is ABORTED, never SUCCESS
-> Z becomes untrusted
```

Do **not** deliberately short, hot-plug, or disconnect the live I2C wiring during a normal bed-facing descent unless a physically constrained test fixture makes that experiment safe. A fault already reproducible by the machine is preferable to manufacturing a new electrical hazard.

Record the first `err_code` timestamp and the motion-stop / command-error timestamp from `klippy.log` so the host-side stop latency can be estimated.

## E. Trigger-race invariant

If a transport fault and `ENDSTOP_HIT` occur in the same transaction, the acceptance rule is simple:

```text
fault_seq_end != fault_seq_start
=> transaction MUST NOT become SUCCESS
```

This must remain true even if the endstop event is logged first at the G-code layer.

## F. Rapid-scan failure behavior

On a transport fault during scan / rapid scan:

- no trsync stop should be sent merely because a scan transaction is active;
- the scan transaction becomes tainted;
- no mesh result may be accepted;
- the active gather session is cleaned on command error;
- the persistent Eddy fault latch blocks subsequent Eddy-dependent operations until restart.

## G. Drive-current calibration integrity

Healthy case:

```gcode
LDC_CALIBRATE_DRIVE_CURRENT CHIP=eddy
```

should still return a candidate drive-current value.

Faulted-session case:

- after any transport fault in the same Klipper session, the command must refuse to run and require `FIRMWARE_RESTART`;
- a transport-tainted calibration must not create a pending persistent config value.

## Remaining RC4 soak criteria

EC2 may be promoted from engineering candidate only if:

- healthy regressions remain equivalent to ES-R3/ZC-FR1 behavior;
- no false-success transaction is observed;
- active stop is demonstrated on hardware or explicitly disabled/deferred before release;
- recovery clearance always precedes XY when Z is untrusted;
- rapid-scan failure produces no accepted mesh;
- logs contain enough evidence to reconstruct the event order.


## EC2 transport recovery validation

For a naturally observed transport fault (do not intentionally short/disconnect the live I2C bus):

1. Confirm the active action aborts and Z is invalidated where applicable.
2. Run `M_BAMBOO_EDDY_STATUS`; record raw code, transport state, fault sequence, callback delay, and event timeline.
3. After all motion has stopped, run `M_BAMBOO_EDDY_RECOVERY_CHECK`.
4. On PASS, confirm `Transport state: TRANSPORT_RECOVERED`, `Recovery armed: Yes`, while Z remains untrusted.
5. Run exactly one `G28`. Confirm Safe Home establishes clearance before XY, then performs one fresh Eddy Z home.
6. On success, confirm `Transport state: HEALTHY`, `Fault latched: No`, and Z is homed again.
7. If the armed G28 faults/fails, confirm another recovery attempt is blocked and `FIRMWARE_RESTART` is required.

Do not use ordinary `PROBE`, QGL, contact, mesh, or calibration as the recovery command.

### Pre-arm transport readiness validation

1. On a healthy session, run `G28`, ordinary `PROBE`, contact probing, and rapid scan. Confirm `M_BAMBOO_EDDY_STATUS` increments `Pre-arm checks` while transport remains `HEALTHY`.
2. Normal healthy transactions must not show `PREARM NOT READY`; the nominal preflight should add only a short startup pause per session/action.
3. If a natural transient fault is caught during pre-arm, confirm the console reports that motion was held and no bed-facing Z motion started. A successful bounded recovery should report `PREARM RECOVERED`, keep Z trust unchanged, and increment `transient recoveries`.
4. If pre-arm cannot stabilize, confirm the requested Z motion never starts. After `M_BAMBOO_EDDY_RECOVERY_CHECK` PASS, normal operations should resume **without** an armed recovery G28 because `Z recovery required` is `No`.
5. A fault after HOMING/PROBE becomes ACTIVE must still set `Z recovery required: Yes` and follow the existing explicit recovery-check -> armed G28 flow.
6. Confirm one physical I2C report increments the session fault count once even if the pending sequence is observed before its reactor callback.


## FS1 fault-storm containment

After any natural runtime Eddy transport fault, confirm that console fault output is bounded and does not continue indefinitely after the command aborts. `M_BAMBOO_EDDY_STATUS` should show `Forced LDC stream quarantines` >= 1 when an active bulk stream was quarantined. Repeated same-episode fault messages may be suppressed while `Transport faults this session` continues to preserve evidence. After the bus stabilizes, use the normal recovery-check / armed-G28 policy; a new probe session must be able to restart a clean bulk stream.

## Current real-machine evidence snapshot — 2026-08-20

The healthy path has now progressed beyond isolated command testing into a complete real print flow.

Validated on the SV08 Max under test:

- repeated fresh/known-Z `G28` / Safe Home;
- direct `RUN_PROBE_VIR_CONTACT`;
- repeated `CLEAN_NOZZLE` without leaked Eddy activity afterward;
- repeated `Z_OFFSET_CALIBRATION` including contact verification and Eddy recalibration;
- QGL, including one normal retry from range `0.120445` to `0.010404` against `0.100000` tolerance;
- adaptive rapid mesh with pre-arm authorization;
- HOME_Z and final XY re-home with reported raw X/Y `dZ=0`;
- complete slicer-driven `START_PRINT`;
- actual cube print to `Finish Print!`; the observed slicer-driven end sequence also executed the machine's existing PLR cleanup command, but PLR itself is not an RC4 package feature;
- post-print `M_BAMBOO_EDDY_STATUS`.

Latest post-print diagnostic snapshot:

```text
State: HEALTHY
Transport fault seq handled/current: 0 / 0
Transport state: HEALTHY
Transport faults this session: 0
Repeated fault messages suppressed: 0
Forced LDC stream quarantines: 0
Pre-arm checks: 30
transient recoveries: 0
failures: 0
```

Interpretation: this is strong healthy-path evidence that pre-arm transport quiescence is compatible with the complete print lifecycle and is associated with a marked reduction in the previously observed raw-34 fault incidence. It is not evidence that the fault is impossible. Do not deliberately short, hot-plug, or disconnect the live Eddy I2C path to manufacture a failure.

### Natural raw-34 fault/recovery evidence — 2026-08-20

A later normal-use session naturally produced raw transport code `34` (`I2C_BUS_NACK | I2C_BUS_BUSY`) during `RUN_PROBE_VIR_CONTACT` contact verification. This was not an intentionally induced electrical fault.

Observed sequence:

```text
ACTIVE contact probe
-> raw34 transport fault seq=1
-> active trsync SENSOR_ERROR stop requested
-> transaction FAILED / current action aborted
-> Z homing state invalidated xyz -> xy
-> LDC periodic stream force-quarantined
-> host remained responsive
-> M_BAMBOO_EDDY_RECOVERY_CHECK
-> three valid 5449/3055 identity reads, fault_seq unchanged
-> recovery armed, Z still untrusted
-> one fresh G28 / Safe Home
-> ARMED RECOVERY SUCCESS
-> transport HEALTHY and Z trust re-established
-> CLEAN_NOZZLE / Z calibration / QGL / HOME_Z / adaptive mesh / final XY re-home / final calibration
-> print started successfully without FIRMWARE_RESTART
```

The later status snapshot reported `Transport faults this session: 1`, `Forced LDC stream quarantines: 1`, `Recovery checks: 1/2 passed`, `armed recovery successes: 1`, `Transport fault seq handled/current: 1 / 1`, `Transport trust watermark/current: 1 / 1`, `Transport state: HEALTHY`, `Z recovery required: No`, and `Restart required: No`. Historical `err_code=34` remained visible while current transport state was correctly healthy, validating the design choice not to treat the last historical error code as the live health authority.

This closes the previously missing one-event end-to-end natural fault-path gate for RC4. Continued natural-fault soak remains required for confidence across repeated events and different timing/fault combinations.
