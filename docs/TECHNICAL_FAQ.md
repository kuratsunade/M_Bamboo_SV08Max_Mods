# Technical FAQ — Eddy Safety, PREARM, I2C Faults, and RC5 Recovery

> Status: **RC5 engineering reference.** RC4 remains the public baseline while RC5 transaction cleanup and bounded `START_PRINT` recovery are being prepared for hardware validation.

## Does M_Bamboo modify or reflash MCU firmware?

No. This is a project-level boundary, not a temporary RC5 choice.

M_Bamboo does not patch, rebuild, flash, or replace Sovol MCU firmware. MCU source is audited only to understand the behavior below the host trust boundary. All production mitigation is implemented in Klipper host Python, configuration, macros, and installer-managed orchestration.

Detailed source-history and pin-lookup analysis: [Sovol STM32F1 I2C / Eddy Root-Cause Audit](I2C_ROOT_CAUSE_AND_HOST_BOUNDARY.md).

## What does `raw34` mean?

Sovol's STM32F1 I2C telemetry is a bitmask. Relevant bits include:

- bit 1 -> NACK -> `2`
- bit 2 -> TIMEOUT -> `4`
- bit 5 -> BUSY -> `32`
- bit 7 -> bus error / BERR -> `128`

Therefore:

```text
raw34 = 34 = NACK | BUSY
raw36 = 36 = TIMEOUT | BUSY
```

The bitmask model itself is useful because it preserves concurrent bus-state evidence. M_Bamboo decodes the complete bitmask rather than special-casing one numeric value.

## Is Sovol's I2C error definition wrong?

Not in the simple sense of "BUSY should not be 5". The enum values are used as **bit positions**. The implementation problem is that some MCU code still consumes the returned bitmask using old scalar-error comparisons, such as conceptually comparing `ret == I2C_BUS_BUSY` instead of testing the BUSY bit.

The detailed audit therefore describes this as an **incomplete scalar-to-bitmask migration**.

## What is the `i2c_busy_errata()` pin-lookup problem?

Sovol's STM32F1 BUSY recovery helper receives an I2C peripheral pointer and tries to reverse-map it to SCL/SDA metadata with `container_of`. The pointer available to that function is the **value stored in** the `i2c` member, not the **address of that member**. The reverse lookup therefore treats the peripheral register block as if it were the `struct i2c_info` object.

Because the recovery code clears `CR2` before reading the falsely reconstructed `scl_pin` / `sda_pin`, the interpreted pin values become zero (`PA0`) instead of the SV08 Max extra-MCU I2C2 pins PB10/PB11. The peripheral reset/reinitialization still occurs; the intended GPIO bus-unlock sequence does not target the real I2C2 lines.

M_Bamboo documents this finding but does not modify the firmware or physical bus-recovery behavior.

## Why can an I2C failure be dangerous to Eddy probing?

The key system issue is transaction validity. On the audited STM32F1 path, an I2C fault can be reported without consistently forcing the current LDC register/sample transaction to become invalid at every downstream API boundary. Some paths can continue producing/consuming data after the low-level failure.

M_Bamboo therefore treats a confirmed transport fault as authoritative evidence that the active Eddy transaction is tainted. A tainted transaction can never be promoted back to success even if later responses look normal.

## Does `NACK | BUSY` mean the Eddy sensor is permanently broken?

No. It proves that the **current transaction is not trustworthy**. It does not by itself prove permanent sensor, cable, or PCB failure.

That distinction is the reason recovery is separated into two questions:

1. is the transport healthy again?
2. is the machine's Z reference still trustworthy?

A successful transport check answers only the first question.

## Why isn't `i2c_err_flag` treated as live bus health?

Sovol reports errors asynchronously, but a later successful transaction does not necessarily emit a matching zero report that clears the old value. The field is therefore historical/last-observed evidence, not proof of current health.

M_Bamboo uses a monotonic transport fault sequence and transaction-local sequence comparisons instead.

## Why track both `transport_fault_seq` and a handled sequence?

The raw serial callback may increment the transport sequence before the reactor callback has latched the full safety state. Without a separate handled watermark, a new operation could start in that scheduling gap and snapshot the already-incremented sequence as its apparently healthy baseline.

New Eddy operations therefore reject the state whenever the raw transport sequence is ahead of the handled sequence.

## Why can a displayed fault escalate from `PROBE_NO_TRIGGER` to `HARD_COMM_FAULT`?

Fault evidence is monotonic by severity. A no-trigger can be caused by geometry or sensor/transport failure. If direct I2C transport evidence arrives later, the stronger fact must replace the weaker current classification while the first symptom remains available in the trace.

## What is PREARM?

PREARM is a no-motion readiness gate before safety-critical Eddy operations such as Safe Home Z, contact/non-contact probing, and mesh session startup.

Its purpose is simple:

> **Do not begin a bed-facing Eddy action while transport is already unhealthy or newly unstable.**

PREARM performs bounded health/readiness checks before motion. If the transport cannot be proven stable, motion remains held and the operation fails closed.

## Does PREARM guarantee that a transport fault can never occur after motion starts?

No. PREARM is prevention, not prediction. A new fault can still occur after a transaction becomes active.

That is why the runtime safety layers remain necessary:

- transaction taint;
- trsync abort where applicable;
- stream quarantine;
- Z-trust invalidation;
- terminal transaction/session cleanup;
- bounded recovery.

## Why keep PREARM if runtime abort already exists?

Because they protect different phases.

PREARM prevents an already unhealthy transport state from entering dangerous Z motion. Runtime abort protects against a **new** fault that occurs after motion/session activation. Real-machine history showed bed strikes before PREARM was added; after PREARM, the known unhealthy-state-to-descent path has been blocked.

RC5 therefore treats PREARM as a safety invariant, not a cleanup candidate.

## Will RC5 automatically recover a PREARM or Eddy transport fault during `START_PRINT`?

That is the intended RC5 behavior for faults that meet the safety core's recoverable criteria.

RC5 adds a small startup coordinator above the existing Eddy Safety Core. A recoverable fault is contained before it escapes to the virtual-SD print executor, then the coordinator:

1. cleans/quarantines the failed Eddy lifecycle;
2. verifies transport health without Z motion;
3. performs one fresh armed Safe Home if Z trust must be rebuilt;
4. restores temporary state owned by the interrupted startup stage;
5. reruns the complete failed atomic stage;
6. continues `START_PRINT` only after that stage succeeds.

## Is that just automatic retry?

No. Recovery is deliberately bounded.

- **One armed Z-recovery attempt per fault episode.**
- If that recovery fails, the episode is terminal. RC5 does not issue another blind G28.
- A later independent fault is eligible only after the previously recovered atomic stage has completed successfully.
- The full `START_PRINT` sequence has a total recovery budget so repeated faults eventually stop for inspection.
- Non-Eddy errors and errors without a new transport fault sequence are not swallowed by the coordinator.

The current design target is up to **3 successfully recovered independent startup episodes**; the final release value remains subject to hardware fault-injection validation.

## Why restart a whole startup stage instead of retrying the failed sensor command?

Because transport recovery does not retroactively validate the failed transaction, and startup stages can have dependencies that are only meaningful after complete success.

RC5 treats the Eddy-sensitive startup sequence as atomic stages, including:

- nozzle cleaning/contact datum;
- pre-QGL Z calibration;
- QGL;
- explicit Z home;
- bed mesh;
- post-mesh Z calibration.

A failed QGL is rerun as QGL. A failed mesh is rescanned from the beginning. A failed Z calibration is restarted as a calibration transaction.

The explicit post-QGL Z-home stage is special: if the recovery itself has already completed the required fresh Safe Home, that recovery home satisfies the stage and RC5 must not issue a redundant second G28.

## Why does START recovery need a coordinator instead of only macros?

A normal Klipper macro is not an exception-resumable workflow. If a nested command raises `command_error`, the macro unwinds. If that exception reaches `virtual_sdcard`, the print file stops and `print_stats` enters error state.

The coordinator therefore owns only the Eddy-sensitive startup checkpoints and catches **eligible** transport failures before they escape the top-level `START_PRINT` call. It does not reimplement QGL, mesh, Safe Home, or Z calibration.

## What startup state must be cleaned after a failure?

Audit identified both workflow and temporary execution state that can otherwise leak across retries or into the next print.

Examples include:

- `has_z_offset_calibrated`;
- `square_corner_velocity` temporarily changed by the mesh wrapper;
- current Z homing/trust state;
- active Eddy transaction/session pointers;
- sensor clients / bulk stream lifecycle;
- calibration-local logical Z state.

RC5 requires terminal cleanup on success, recoverable failure, and hard failure paths.

## Why does Z calibration sometimes force Z unhomed even if PREARM caught the fault before descent?

`Z_OFFSET_CALIBRATION` can temporarily relabel logical Z while preparing a bounded search allowance. If a guarded sensor call then aborts, the calibration layer intentionally revokes Z homing so that temporary coordinate state cannot escape as trusted Z.

Therefore recovery must reconcile both layers:

```text
fresh Z home required if
    Eddy Safety says Z recovery is required
    OR
    current homed_axes no longer contains Z
```

This preserves PREARM's "no descent occurred" semantics without trusting a calibration-local coordinate state that has already been invalidated.

## Why quarantine the LDC stream after a transport fault?

A graceful client `finish()` can depend on a later successful batch callback. If the bus is already faulted badly enough that no good batch arrives, the periodic LDC query can otherwise continue producing more errors after the owning G-code has aborted.

Quarantine forces the active stream to stop and creates a clean lifecycle boundary for later recovery.

## Why must late sample exceptions release `_active_transaction`?

HF2 testing showed a real case where motion had already stopped and the LDC stream/client had been cleaned, but `pull_probed()` later raised a sensor-outage exception. RC4 production can leave `_active_transaction` stale on that path, causing later recovery to be blocked by software state even though the physical stream is already stopped.

RC5 productionizes the HF2.1 whole-terminal-lifecycle cleanup and applies the same principle to rapid scan.

## Does a successful QGL remain valid after a later recovery G28?

Normally yes. Klipper's QGL `applied` state is reset when a new QGL starts or Z motors are disabled; a normal G28 does not automatically clear an already completed QGL. Therefore a mesh-stage fault can recover and restart the mesh without unnecessarily repeating a previously completed QGL, provided the QGL status still reports applied.

A QGL that itself faulted is different: that QGL attempt is incomplete and must be rerun from the beginning.

## Can an interrupted mesh leave a half-valid mesh active?

The upstream bed-mesh command clears the active mesh at calibration start and installs the new mesh only after the complete dataset finalizes successfully. RC5 still explicitly restarts the entire mesh stage after a fault, but it does not need to treat a partial scan as a valid mesh.

## Why does M_Bamboo modify generic `probe.py` at all?

The change is intentionally narrow. Generic probe code asks the active probe object for an optional persistent-config validator before certain probe-derived values are accepted for pending persistence. Non-Eddy probes without that hook behave normally. Eddy policy remains in the Eddy backend.

## Does RC5 prove the original physical cause of the first I2C anomaly?

No. Source audit proves important implementation boundaries and inconsistencies, but it does not prove why the very first NACK/TIMEOUT/BUSY condition occurs.

Possible lower-layer causes still include STM32F1 peripheral state/timing, the LDC1612/device interaction, electrical signal integrity, and workload/timing interactions.

Because MCU firmware is intentionally out of project scope, RC5 focuses on making these lower-layer faults safe and recoverable at the host boundary rather than claiming to eliminate their physical origin.

## What did the churn / HF tests change in our interpretation?

They ruled out a simplistic "100 ms quiet time fixes the bus" conclusion. The actual STOP-ACK-to-next-start wall-clock gap was already around the 1.4 s range even in nominal zero-dwell cells because motion/macro overhead dominated the sequence.

The test campaign instead provided evidence for:

- real transport faults during active contact/homing contexts;
- deterministic lifecycle cleanup requirements;
- bounded recovery behavior;
- the value of PREARM;
- the need to separate transport recovery from transaction validity and Z trust.

Complete statistics and chronology are kept in [RC5 Test Evidence](RC5_TEST_EVIDENCE.md), not repeated here.

## Is PLR part of RC5?

No. PLR remains a separate feature. Its checkpoint identity and coordinate-trust behavior require an independent redesign and are not mixed into the RC5 Eddy/START recovery work.

## What should users read next?

- [Sovol STM32F1 I2C / Eddy Root-Cause Audit](I2C_ROOT_CAUSE_AND_HOST_BOUNDARY.md) — low-level source findings and project cut line.
- [RC5 START Recovery Design](RC5_START_RECOVERY_DESIGN.md) — checkpoint/recovery architecture.
- [RC5 Test Evidence](RC5_TEST_EVIDENCE.md) — full statistics and interpretation limits.
- [Eddy Safety Engineering Design](ES_R4_ENGINEERING_CANDIDATE.md) — transaction and transport safety internals.
