# Sovol STM32F1 I2C / Eddy Root-Cause Audit and M_Bamboo Host Boundary

> Status: **RC5 engineering reference**  
> Scope: source-history audit and host-side design boundary for `M_Bamboo_SV08Max_Mods`.  
> Project rule: **M_Bamboo does not modify, rebuild, flash, or replace MCU firmware.** MCU source is inspected only to understand the lower-layer behavior that the Klipper host must not blindly trust.

## Executive summary

The SV08 Max Eddy stack does not fail because of one isolated Python bug. The lower layer is a Sovol-custom STM32F1 I2C/LDC1612 implementation whose design goal was reasonable: an intermittent STM32F1 I2C disturbance should not automatically shut down the entire printer. Sovol therefore moved away from upstream Klipper's simple fail-hard model toward a recoverable model with richer I2C error telemetry, peripheral recovery, and host-side retry.

The source history shows that this direction was deliberate. It also shows that the migration was incomplete. The current firmware can report useful bitmask evidence such as `NACK | BUSY` or `TIMEOUT | BUSY`, but some MCU-side consumers still use scalar-error semantics; the STM32F1 BUSY errata helper attempts to recover the physical bus through an invalid reverse lookup of SCL/SDA pins; and failed I2C reads are not consistently prevented from flowing further into the LDC sample/homing pipeline.

M_Bamboo intentionally cuts the dependency at that boundary. It does **not** attempt to correct the MCU implementation. Instead it treats any confirmed transport fault as authoritative evidence that the current Eddy transaction is invalid, stops or quarantines the active measurement lifecycle, separates transport recovery from Z-coordinate trust, and only permits bounded host-side recovery from a clean checkpoint.

The RC5 goal is therefore not to make `raw34` / `raw36` impossible. It is to make a lower-layer communication fault unable to silently become a trusted probe result, an unsafe Z descent, or a corrupted `START_PRINT` dependency chain.

## 1. Source lineage examined

The current machine archive contains the Sovol Klipper checkout used by the SV08 Max Eddy stack:

- branch: `klipper-eddy_contact_probe`
- current machine commit: `d4031b31daa4c896365f5c688a472086f6e43f49`
- commit date: 2025-10-18
- commit message: `zoffset校准增加前置电流校准动作`

The repository does not preserve a normal upstream-Klipper ancestry; its own history starts from a Sovol repository root. However, the Sovol commits that introduced the STM32F1 I2C recovery/error model are retained and can be audited directly.

Relevant 2024-12 patch sequence includes:

- `93b121b...`: retry LDC identity reads when I2C interference produces incorrect device data;
- `060eada...`: disable `i2c_shutdown_on_err` for STM32F1 (`有待优化` / "needs further optimization");
- `79c9992...`: introduce I2C bus error codes;
- `ee6f394...`: rework `i2c_busy_errata`, `i2c_wait`, and error-exit behavior;
- `265b3f7...`: add delay to the BUSY errata path;
- `fe4df8b...`: add LDC1612 I2C error classification.

No later commit between that patch series and the current machine HEAD repairs the low-level `src/stm32/i2c.c` / `src/i2ccmds.c` behavior discussed below.

## 2. What Sovol was trying to achieve

The design intent is understandable and in several respects useful.

A high-rate Eddy sensor performs far more I2C activity than a peripheral that is read occasionally. Treating every transient I2C anomaly as a fatal MCU shutdown can turn a recoverable disturbance into an immediate failed print. The Sovol patch series instead attempted to implement:

```text
transient I2C anomaly
-> do not immediately shut down STM32F1
-> record detailed error state
-> recover/reinitialize the I2C peripheral/bus
-> allow host-side identity/read retry
-> continue if the transport is healthy again
```

That objective is compatible with M_Bamboo's reliability goal. The disagreement is not with the desire for recovery; it is with accepting ambiguous transaction state as valid after an error.

## 3. The bitmask error model is intentional and useful

Sovol's `I2C_BUS_*` enum values are best understood as **bit positions**, not final wire values. The MCU builds error telemetry with `1 << I2C_BUS_*`, and the Sovol host code also tests the corresponding bits that way.

Known relevant positions include:

- bit 1: NACK -> `2`
- bit 2: TIMEOUT -> `4`
- bit 5: BUSY -> `32`
- bit 7: bus error / BERR -> `128`

Therefore:

```text
raw34 = 34 = 2 + 32 = NACK | BUSY
raw36 = 36 = 4 + 32 = TIMEOUT | BUSY
```

This is richer than a single scalar status because it preserves both the transaction symptom and concurrent bus-state evidence. M_Bamboo keeps this interpretation and decodes the full bitmask instead of special-casing one numeric value.

### What is actually inconsistent

Some MCU code still checks the returned bitmask as though the enum were itself the scalar return value, for example conceptually:

```c
if (ret == I2C_BUS_BUSY)
```

With the bitmask model, a BUSY condition is represented by bit 5 (`32`), not scalar `5`. A representation-safe check would test the bit. The issue is therefore an **incomplete scalar-to-bitmask migration**, not evidence that Sovol's bit assignments themselves are wrong.

This distinction matters: M_Bamboo should preserve the useful telemetry while refusing to assume the MCU's internal retry branch necessarily ran successfully.

## 4. STM32F1 BUSY errata pin lookup

Sovol changed the BUSY recovery helper from a function that directly receives SCL/SDA pin numbers into one that receives only an `I2C_TypeDef *` and attempts to recover the corresponding `struct i2c_info` with `container_of`.

Conceptually the metadata is:

```c
struct i2c_info {
    I2C_TypeDef *i2c;
    uint8_t scl_pin, sda_pin;
};
```

A valid `container_of` requires the **address of the member storage** (`&ii->i2c`). The recovery function instead has the **value stored in that member** (the peripheral address, such as I2C2). Those are different pointers.

Because `i2c` is the first member, its offset is zero. The erroneous reverse lookup therefore treats the STM32 I2C peripheral register base itself as if it were a `struct i2c_info` object.

On STM32F1 the structure offsets align such that the supposed `scl_pin` / `sda_pin` bytes are read from the I2C register block near `CR2`. The recovery code clears `CR2` before using those values, so the interpreted pin values become zero. In Klipper's STM32 GPIO numbering, zero corresponds to `PA0`.

For the SV08 Max `extra_mcu`, the real I2C2 lines are PB10/PB11. The intended physical BUSY-unlock pulse therefore does not target the actual I2C2 SCL/SDA pins in the current firmware. The I2C peripheral reset/reinitialization still occurs, which helps explain why some faults can recover despite the incorrect physical-pin operation.

### Why M_Bamboo does not "just fix the pin lookup"

Correcting the lookup would make the GPIO portion of the recovery routine operate on the real electrical bus for the first time. That changes physical line behavior and therefore crosses the project's MCU/firmware boundary. It would also require auditing the GPIO mode, open-drain semantics, transition sequence, delays, pull-ups, and the exact STM32F1 silicon errata behavior as a single firmware change.

M_Bamboo deliberately does not take ownership of that electrical/firmware behavior.

## 5. Failed transaction data-validity boundary

The more important system-level weakness is not that Sovol avoids shutdown. Avoiding shutdown can be beneficial. The weakness is that a failed I2C transaction is not consistently prevented from producing downstream data.

Examples in the audited firmware include:

- STM32F1 paths that report an I2C error but do not call the generic fatal shutdown path;
- generic read handling that can still emit an `i2c_read_response` even though the underlying STM32F1 read reported an error;
- LDC register helpers whose return type does not propagate read success/failure to the sampling caller;
- LDC sampling/homing logic that may therefore continue toward status/data parsing and `check_home()` without a strict transaction-validity contract;
- loops in which a later operation can overwrite a previous `ret`, weakening first-error preservation.

Modern upstream Klipper has moved toward a clearer rule in the LDC path: an I2C failure invalidates that sensor sample and is propagated as a sample error instead of being consumed as normal measurement data.

M_Bamboo adopts that **semantic rule** at the host boundary without replacing the MCU implementation.

## 6. Where M_Bamboo cuts the dependency

The project boundary is explicit:

```text
Sovol MCU firmware
    detects/reports low-level I2C behavior
    may attempt its own peripheral recovery
                 |
                 |  CUT / TRUST BOUNDARY
                 v
M_Bamboo host layer
    never repairs MCU firmware
    never assumes a failed Eddy transaction became valid
```

M_Bamboo accepts the MCU's fault telemetry as evidence, but does not accept its post-fault transaction result as trustworthy merely because another response arrived afterward.

The host-side invariants are:

1. a new confirmed transport fault taints the active Eddy transaction;
2. a tainted transaction can never be promoted back to success;
3. active measurement streams are quarantined/stopped so fault storms do not continue indefinitely;
4. transaction/client/session lifecycle is terminally cleaned even when failure arrives late during sample collection;
5. transport health and Z-coordinate trust are separate states;
6. bed-facing motion is gated by PREARM before it starts;
7. if a fault occurs after a Z-dependent transaction has begun, Z trust is invalidated where required;
8. recovery validates the **transport**, then separately rebuilds **Z trust** through one fresh Safe Home when needed;
9. failed probe/QGL/mesh/Z-calibration work is never resumed mid-transaction; the owning atomic stage is restarted from a clean checkpoint.

## 7. PREARM and automatic recovery in RC5

PREARM is a prevention gate, not proof that the next I2C transaction can never fail. Its job is to prevent known or newly observed transport instability from entering a bed-facing Z action.

RC5 extends this into bounded automatic startup recovery. The intended startup behavior is:

```text
PREARM / active-stage transport fault
-> abort or hold the current atomic stage
-> quarantine/clean the Eddy lifecycle
-> no-motion transport health verification
-> if Z trust is lost, perform one armed fresh Safe Home recovery
-> restore stage-local temporary state
-> rerun the complete failed startup stage
-> continue START_PRINT only after the stage completes cleanly
```

The retry budget is deliberately bounded:

- one armed Z-recovery attempt per fault episode;
- a failed recovery attempt is terminal and is never blindly repeated;
- a new independent fault may recover only after the previous stage has completed cleanly;
- the current RC5 design target is a total START_PRINT recovery budget of three successful independent episodes; final release value remains subject to hardware fault-injection validation.

## 8. What host-side RC5 can and cannot fix

### RC5 can fix or contain

- stale/late host transaction state after a sample failure;
- accepting transport-tainted data as a successful host transaction;
- continued bulk sampling after a confirmed transport fault;
- unsafe Z trust after bed-facing failures;
- starting a dangerous Z transaction while transport is already unstable;
- START_PRINT dependency corruption after a recoverable fault;
- stale temporary startup state such as calibration flags and mesh scan motion parameters;
- safe bounded re-execution of an atomic startup stage after transport/Z recovery.

### RC5 cannot change

- why the STM32F1 produced the first NACK/TIMEOUT/BUSY condition;
- the compiled BUSY retry comparison inside the MCU;
- the compiled `i2c_busy_errata()` pin lookup;
- the physical GPIO recovery sequence inside MCU firmware;
- MCU-side LDC read/sample propagation code.

Those lower-layer limitations are documented, not patched.

## 9. Why this is not merely "working around a bug"

The host layer is the correct owner of several policies even if the MCU were perfect:

- whether a failed probe transaction is allowed to affect Z trust;
- whether a workflow stage is atomic;
- whether QGL/mesh/Z calibration must restart after an interrupted transaction;
- how many automatic recoveries are acceptable during `START_PRINT`;
- when uncertainty must become a hard stop.

The MCU can report and recover the bus. It cannot determine whether a half-completed QGL or mesh is semantically safe for the rest of the slicer startup chain. RC5 therefore completes the system-level recovery semantics that belong on the host, while refusing to take ownership of the firmware/electrical layer.

## 10. Evidence and interpretation limits

The investigation has reproduced natural transport faults, including `raw34 = NACK | BUSY`, and demonstrated bounded host recovery on real hardware. Churn/HF testing also proved that a simple nominal dwell threshold is not an adequate explanation: actual STOP-ACK-to-next-start timing already included substantial host/motion overhead.

The evidence supports the following statements:

- transport faults are real and not solely host client bookkeeping;
- Sovol's firmware contains the implementation inconsistencies documented above;
- host lifecycle bugs can amplify or obstruct recovery and must be fixed;
- PREARM materially protects against starting unsafe Z descent with an already unhealthy transport state;
- a recovered transport does not validate the failed transaction or automatically restore Z trust.

The evidence does **not** prove the physical cause of the first I2C anomaly, nor does it prove that host-side containment eliminates the occurrence of raw34/raw36.

For full test statistics and experiment chronology, see [RC5 Test Evidence](RC5_TEST_EVIDENCE.md).

## 11. Project decision

`M_Bamboo_SV08Max_Mods` intentionally does not modify MCU firmware. This is a project-level constraint, not an RC5-only temporary choice.

The engineering decision is therefore:

> **Use Sovol's existing I2C telemetry as lower-layer evidence; terminate trust at the MCU/host boundary; complete transaction isolation, Z safety, lifecycle cleanup, and bounded workflow recovery entirely in the Klipper host/config layer.**

This keeps the project reversible, avoids firmware/electrical ownership, preserves the existing Sovol hardware ABI, and still addresses the dangerous consequences that are observable and controllable above that boundary.
