# Eddy Safety ES-R4-EC2 Engineering Candidate

Status: **engineering candidate / healthy-path hardware validation complete; one natural FS1.1 raw-34 fault/recovery path validated end-to-end; continued fault soak in progress**

## Scope

ES-R4-EC2 is an error-integrity and recovery-safety candidate built on the exact ES-R3 / ZC-FR1 lineage. It does not require MCU firmware recompilation and does not modify `bed_mesh.py`.

### Core invariants

1. A non-zero Sovol LDC I2C report is preserved as structured transport-fault evidence.
2. Every LDC/Eddy operation snapshots `transport_fault_seq`; if the sequence changes before the result is accepted, that transaction is tainted and cannot become SUCCESS.
3. During an armed downward Eddy homing/probe, a transport fault requests the existing trsync `SENSOR_ERROR` reason to stop the active move as early as possible.
4. `ENDSTOP_HIT` is not final success. Homing becomes SUCCESS only after `HomingMove` reconstructs the halt position and emits `homing:homing_move_end` with a clean transport sequence.
5. Scan / rapid-scan consumes the same persistent Eddy fault authority, but never sends a trsync stop unless a trsync-backed move is actually active.
6. Transport-tainted drive-current calibration must not persist a calculated `reg_drive_current`.
7. Untrusted Z must obtain positive-only clearance before any XY motion in Safe Home's real-Z-reference sequence.


## EC2 audit corrections

EC2 supersedes EC1 before hardware validation.  The patch surface is unchanged,
but two safety races and one calibration-integrity issue were corrected:

1. **Pending transport-fault gate.** The serial callback increments
   `transport_fault_seq` before its reactor notification runs.  A new Eddy
   operation now refuses to start if the sensor sequence is newer than the
   highest sequence already consumed by the Eddy Safety Core.  This closes the
   serial-thread → reactor scheduling gap.
2. **Monotonic fault severity.** A later `HARD_COMM_FAULT` upgrades an earlier
   weaker `PROBE_NO_TRIGGER` classification instead of being hidden by the
   first latched state.  The first fault is retained separately for evidence.
3. **Drive-current calibration restore integrity.** The calibration no longer
   reads an `old_config` value and writes it back after a potentially failed
   I2C read.  It restores this Sovol fork's known measurement-mode `REG_CONFIG`
   value and only persists the candidate drive current after a clean
   transaction-wide transport-sequence check.

4. **Persistent probe-config guard.** `probe.py` gains a generic optional
   validation hook before `PROBE_CALIBRATE` and `Z_OFFSET_APPLY_PROBE` write
   pending config.  Normal probes are unaffected; `PrinterEddyProbe` implements
   the hook by consuming pending transport faults and enforcing the session latch.

## Fault evidence

`ldc1612.py` decodes the Sovol bitmask:

- bit 1: `I2C_BUS_NACK`
- bit 2: `I2C_BUS_TIMEOUT`
- bit 5: `I2C_BUS_BUSY`
- bit 7: `I2C_BUS_ERR`

Unknown bits are preserved instead of discarded.

Each report increments `transport_fault_seq` and stores raw register evidence (`cr1/cr2/sr1/sr2/dr`, raw code, decoded bits, sequence).

## Active probe sequence

```text
TX CREATED
  -> fault_seq_start snapshot
TX ARMING
  -> TriggerDispatch.start()
  -> LDC setup_home()
TX ARMED
  -> re-check fault sequence
TX ACTIVE
  -> drip probing move

I2C fault while trsync_active
  -> TX TAINTED
  -> session HARD_COMM_FAULT
  -> trsync SENSOR_ERROR stop requested

ENDSTOP_HIT
  -> TX TRIGGERED (not SUCCESS)
  -> HomingMove reconstructs halt position
  -> homing:homing_move_end
  -> final seq/taint check
  -> SUCCESS or ABORTED
```

## Safe Home recovery refactor

`M_BAMBOO_HOME_Z`, `M_BAMBOO_HOME_ALL`, and HOME-FIRST Z calibration now converge on one atomic backend operation:

```text
establish positive Z clearance exactly once
-> home X/Y if required by the caller
-> verify XY homed
-> move to Z-home XY
-> raw real Z home
-> post-home Z clearance
```

This closes the previous case where Z could be invalidated while X/Y remained homed and `HOME_Z` could perform an XY move before lifting away from the bed.

`prepare_xy_for_calibration()` remains as a deprecated internal compatibility helper for one cycle, but new code no longer calls it.

## Deliberately deferred

- Automatic +Z retract after a live fault.
- Public `M_BAMBOO_Z_RELIEF` command.
- Automatic fault clearing/retry.
- MCU firmware changes.
- `bed_mesh.py` Eddy-specific safety logic.
- Wholesale backport of current Official Klipper `trigger_analog` / `descend_z` architecture.

## Hardware validation gates

Before ES-R4-EC2 can replace ES-R3 on a release branch:

1. Healthy G28 / QGL / contact / Z calibration / rapid scan regression.
2. Controlled I2C fault before probe motion: block before descent.
3. Controlled I2C fault during descent: trsync stop is observed and four Z motors stop without a second blind descent.
4. Fault racing with a trigger: transaction must fail if `fault_seq` changed, regardless of ENDSTOP_HIT.
5. Rapid-scan I2C fault: no mesh result accepted and gather session cleaned.
6. Firmware Restart then G28 from low physical Z: positive Z clearance occurs before XY.
7. HOME-FIRST Z calibration: exactly one clearance hop, no double-hop.


## Persistent calibration coverage

EC2 applies the shared Eddy fault authority to every currently identified persistence path in the modified stack: `LDC_CALIBRATE_DRIVE_CURRENT`, `PROBE_EDDY_CURRENT_CALIBRATE`, `PROBE_CALIBRATE`, and `Z_OFFSET_APPLY_PROBE`. The last two use a minimal optional validator hook in generic `probe.py`; non-Eddy probe behavior is unchanged.

ZC-FR1 also guards its contact/non-contact sensor calls. If a stronger preflight rejects an operation before `HomingMove` starts, the calibration backend explicitly invalidates Z so a temporary logical `USE_CURRENT_Z_ALLOWANCE` rebase cannot leak into the trusted coordinate state.


## Transport recovery UX (EC2 hardware-validation revision)

A confirmed I2C transport fault still taints and aborts the current transaction immediately. The new recovery model separates three truths:

```text
transport health != transaction validity != Z-coordinate trust
```

`M_BAMBOO_EDDY_RECOVERY_CHECK` is deliberately no-motion. After a short settle period it performs three manufacturer/device-ID read pairs, leaves a reactor settle window after every pair, and accepts recovery only if all IDs are correct and `transport_fault_seq` remains unchanged. PASS sets `TRANSPORT_RECOVERED` and arms one Safe Home recovery; Z remains untrusted.

After the one-shot recovery Z home succeeds, the safety core also grants the low-level LDC backend a monotonic **trusted-through transport-fault sequence watermark**. This does not erase history; it only means faults at or below that sequence have been explicitly recovered. Transport-sensitive drive-current calibration remains blocked whenever the current fault sequence exceeds the trusted-through watermark.

Safe Home consumes that authorization only immediately before a fresh raw Z home, after positive clearance and XY homing. A successful fresh Z home returns transport to `HEALTHY`; any failed armed recovery becomes restart-required. Ordinary PROBE/QGL/contact/mesh/calibration cannot consume this authorization.

The fault callback does not auto-scan or auto-retry. This avoids relying on unverified ordering between Sovol synchronous I2C responses and asynchronous error reports, and avoids initiating motion without explicit user intent.

### Pre-arm transport quiescence

The healthy path now performs a short no-motion readiness check **before** Safe Home Z homing and before Eddy probe/scan/calibration sessions start. Normal readiness uses two identity reads with reactor gaps and exits immediately on the first clean window. If a transient/failure occurs, a bounded three-attempt sequence requires two consecutive later clean windows before motion may proceed. This deliberately retries only readiness reads, never an already-started Z transaction.

While the pre-arm gate is active, asynchronous transport reports still increment the low-level monotonic fault sequence and are recorded in diagnostics/statistics. The safety callback does not create a motion fault latch because there is no active bed-facing transaction to taint. A delayed callback for a sequence already consumed by the pending-sequence gate is ignored for policy purposes, preventing duplicate re-latching.

If pre-arm recovery succeeds, the current sequence is granted the same trusted-through watermark semantics because the bus has been re-proven healthy while Z remained physically stationary. If pre-arm readiness never stabilizes, motion is rejected first; a later successful explicit recovery check may return transport directly to `HEALTHY` without a recovery G28 because coordinate trust was not invalidated. Active HOMING/PROBE transport faults continue to require the stricter armed-G28 recovery.

## Hardware evidence update — pre-arm transport hardening and FS1.1

### Problem statement

A real SV08 Max previously reproduced raw transport code `34` (`NACK | BUSY`) during an ACTIVE Eddy Z-homing transaction. The safety core successfully treated that transaction as untrusted, but the event demonstrated that allowing an unsettled I2C/session boundary to progress into bed-facing motion leaves only the emergency abort path available.

A later real START_PRINT incident exposed a second lifecycle failure: after an Eddy/contact fault, a periodic LDC bulk query could remain alive after the G-code aborted and continuously generate new transport reports. FS1 addresses this separately with deterministic client removal and forced stream quarantine.

### Design response

The resulting architecture intentionally separates four responsibilities:

1. **Prevent:** pre-arm transport quiescence before motion/session startup.
2. **Detect/Stop:** transaction-local fault sequencing, trsync stop request, taint/abort, and Z de-trust for active motion.
3. **Contain:** FS1 deterministic bulk cleanup and forced LDC periodic-stream quarantine so one fault episode cannot become an unbounded error source.
4. **Recover:** explicit no-motion transport recovery check and, when Z trust was lost, exactly one fresh Safe Home Z recovery before returning to HEALTHY.

The pre-arm gate uses bounded no-motion identity reads and fault-sequence stability. It never retries an already-started descent. This was chosen specifically to reduce exposure to suspected I2C/session-transition timing faults without weakening active-motion safety semantics.

### Hardware result as of 2026-08-20

Healthy-path hardware validation now includes repeated G28/Safe Home, direct contact probe, repeated nozzle cleaning, repeated Z-offset calibration, QGL with a normal correction/retry, adaptive rapid mesh, HOME_Z, final XY re-home, final contact calibration, a complete slicer-driven START_PRINT, a real cube print through END_PRINT including the stock `clear_plr` cleanup hook, and a post-print Eddy diagnostic snapshot.

The latest post-print snapshot recorded:

- `Pre-arm checks: 30`
- `Transport faults this session: 0`
- `transient recoveries: 0`
- `pre-arm failures: 0`
- `Forced LDC stream quarantines: 0`
- `Repeated fault messages suppressed: 0`
- current transport state `HEALTHY`

The final START_PRINT contact verification converged to approximately 0.001875 mm between the last two contact triggers, while the two Eddy calibration sampling passes in that print reported standard deviations around 545–548 with no I2C/sample error evidence.

### Interpretation and promotion boundary

These results materially strengthen the case that pre-arm quiescence reduces observed raw-34 incidence and support the working hypothesis that a significant portion of the previous `NACK | BUSY` events were associated with transport/session transition boundaries. They do not prove that raw-34 is impossible.

FS1.1 is carried inside **v1.0.0-rc4 as a soak-test runtime component**. The previously missing one-event natural hardware gate has now been crossed: a naturally occurring raw-34 active contact-probe fault demonstrated bounded abort semantics, forced stream quarantine, continued host responsiveness, explicit no-motion recovery checking, one armed fresh Safe Home Z recovery, return to `HEALTHY`, and successful continuation into printing without firmware reset. Stable promotion still requires continued natural-fault soak and confidence across repeated timing/fault combinations; one successful event is not statistical proof of universal recovery.
