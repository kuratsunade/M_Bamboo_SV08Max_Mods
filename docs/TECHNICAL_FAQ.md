# Technical FAQ — Confirmed Sovol Eddy / I2C Safety Findings

> Status: **v1.0.0-rc4 technical reference.** Healthy-path validation is complete and one naturally occurring FS1.1 raw-34 fault/recovery path has been validated end-to-end on hardware; continued natural-fault soak remains open. This document distinguishes source/code facts, hardware observations, engineering inference, and remaining uncertainty.

## Why can an Eddy probe failure continue into a dangerous Z move?

Sovol's STM32F1 LDC1612 path can detect an I2C transaction fault and report it to the host without making the active LDC sample invalid at the API boundary. On STM32F1, `sensor_ldc1612.c` intentionally does not call `i2c_shutdown_on_err(ret)`. Its `read_reg()` returns `void`, so callers cannot distinguish a failed register read from a valid one. The sampling path may therefore continue parsing status/data and may call `check_home()` after a failed I2C read.

M_Bamboo policy: a confirmed LDC transport fault is first-class safety evidence. It must taint subsequent Eddy data, latch an Eddy communication fault, abort an active Eddy probe where safely possible, invalidate Z trust, and block further Eddy-dependent Z operations until restart.

## What does Sovol `err_code=36` mean?

In Sovol's modified STM32 I2C driver, the returned value is a bitmask whose set bits use the `I2C_BUS_*` enum values as bit positions. `36` is therefore:

- bit 2: `I2C_BUS_TIMEOUT`
- bit 5: `I2C_BUS_BUSY`

So `36 = 4 + 32 = TIMEOUT | BUSY`.

This is not the same semantic as documentation that prints an Eddy amplitude value such as `(36)` or `(48)`.

## Are there other Sovol I2C error codes worth monitoring?

Yes. Relevant known bits are:

- `1 << 1` (`2`): NACK
- `1 << 2` (`4`): TIMEOUT
- `1 << 5` (`32`): BUSY
- `1 << 7` (`128`): BERR / bus error

Combinations are possible (for example 34, 36, 38, 130, 132, 134, 162, 164, 166). M_Bamboo should decode the bitmask rather than special-case only value 36. Unknown non-zero bits should be reported and conservatively blocked.

## What is wrong with Sovol's error representation?

The modified STM32 driver builds a bitmask (`1 << I2C_BUS_*`), but some later code still compares the returned value directly to the enum (`ret == I2C_BUS_BUSY`). Since `I2C_BUS_BUSY` is the bit index 5 while the bitmask is 32, the intended BUSY retry path is not representation-safe.

The generic `i2c_shutdown_on_err()` switch also expects the upstream single-enum return convention, so applying it to the modified bitmask can map errors incorrectly. The SV08 Max Eddy MCU is STM32F1 and Sovol bypasses that shutdown path entirely for this MCU family.

## Can a failed LDC register read still be consumed as sensor data?

Yes, by code structure. On STM32F1 `read_reg()` does not propagate its I2C return status. `read_reg_status()` therefore has no validity signal, and `ldc1612_query()` can continue to the DATA0 reads and `check_home()` without an explicit successful-transaction contract. This can produce either a missed trigger or, in principle, a false trigger if stale/invalid bytes happen to satisfy the trigger condition.

## Does Sovol preserve every I2C error correctly?

Not necessarily. Some byte-write loops overwrite `ret` on each byte instead of stopping on the first failure. A later successful call can therefore overwrite an earlier transaction error. The STOP-phase `i2c_wait()` result is also discarded. These differ from current upstream Klipper patterns that preserve the first error and propagate STOP failures.

## Is `ldc1612_i2c_report` guaranteed to come from the LDC1612?

No at the protocol-design level. Sovol emits that message from the generic STM32 hardware-I2C driver and does not include device address, bus ID, or transaction owner in the report. On the current SV08 Max configuration under test, `extra_mcu:i2c2` appears dedicated to the Eddy LDC1612, so the attribution is reasonable for this machine. Installer/preflight logic should verify that assumption rather than hard-code it for every future configuration.

## Why is the current Python `i2c_err_flag` not a live bus-health flag?

The MCU sends `ldc1612_i2c_report` on an error, but does not send a matching zero report after a successful transaction. Therefore `i2c_err_flag` is effectively the last observed error / historical evidence, not proof that the bus is currently still bad. M_Bamboo should latch a safety fault from the event itself and preserve event metadata rather than poll this field as live health.

## Which existing ES-R3 protections remain necessary after ES-R4?

- `homing.py` Z invalidation remains necessary because geometry/no-trigger failures can occur even with healthy I2C transport.
- The dynamic non-contact descent envelope remains necessary because it limits blind descent when a trigger is absent for non-communication reasons, especially while MCU firmware remains unchanged.
- Existing trsync communication/sensor-error handling remains necessary because it covers a different transport layer than the LDC I2C transaction fault.
- The old conclusion that `ldc1612.py` is "telemetry only" is superseded: it should remain the hardware decode/source layer, but must publish transport-fault events to the Eddy Safety Core.

## Should M_Bamboo reflash or patch the MCU firmware?

Not for RC4. The preferred design is to consume Sovol's existing asynchronous I2C error report, decode it at the lowest host-side hardware layer, pass a structured fault to `probe_eddy_current.py`, and reuse Klipper's existing trsync/homing machinery to stop and invalidate unsafe operations. MCU-side defects are documented for transparency, while the release remains a user-space/Klipper modification.

## Confirmed Sovol Eddy/I2C implementation defects relevant to ES-R4

The current SV08 Max Sovol fork contains several internally inconsistent error-handling behaviors. These are documented because ES-R4 intentionally repairs their safety consequences at the host/Python layer without requiring MCU firmware recompilation.

- The modified STM32 I2C driver builds an error **bitmask** (`1 << enum_index`), while some later comparisons still treat the enum value itself as the returned error code. This can break intended BUSY retry/error mapping semantics.
- STM32F1 LDC register reads may report I2C errors without propagating a failed read result to the LDC caller. Runtime sampling can therefore continue without a trustworthy data-validity contract.
- The generic STM32 I2C error report is named `ldc1612_i2c_report` even though the report originates in the generic I2C driver and does not carry a device identity.
- `i2c_err_flag` is a last-observed error value, not a live bus-health value; successful transactions do not clear it. ES-R4 therefore uses a monotonic `transport_fault_seq` instead of treating that flag as transaction-local truth.
- Stock/Sovol runtime `SENSOR_ERROR` handling writes `reg_drive_current=0` into the pending config state. ES-R4 removes that behavior: a runtime fault must not silently mutate persistent calibration state.
- Drive-current calibration consumes register values without transaction-local transport integrity. ES-R4 rejects persistence if the I2C fault sequence changes during the calibration transaction.

## Why selective backport instead of upgrading the whole Klipper fork?

Sovol's SV08 Max stack includes custom Eddy contact behavior, custom MCU commands, touchscreen-facing G-code ABI, Z-calibration behavior, and other vendor integration. M_Bamboo therefore follows a selective semantic backport policy:

- Backport low-risk correctness semantics such as structured error propagation, transaction taint, lifecycle cleanup, and abort handling.
- Preserve the existing Sovol MCU ABI where replacing it would require reflashing firmware or destabilize already validated contact/Z-calibration flows.
- Prefer Official Klipper ownership boundaries and invariants, but do not wholesale copy implementations whose dependencies do not exist in the Sovol fork.

## Why does ES-R4 track both a sensor fault sequence and a "handled" sequence?

Sovol reports the I2C error from a serial receive callback.  That callback can
increment the raw transport-fault sequence before the corresponding reactor
callback has had a chance to latch `HARD_COMM_FAULT`.  Without a second
"handled" sequence, a new operation could begin in that scheduling gap and
snapshot the already-incremented value as if it were healthy history.

ES-R4-EC2 therefore blocks a new Eddy operation whenever
`transport_fault_seq > transport_fault_seq_handled`.  The raw evidence itself
is authoritative; safety does not depend on reactor callback timing.

## Why can the displayed fault state change from `PROBE_NO_TRIGGER` to `HARD_COMM_FAULT`?

Fault severity is monotonic.  `PROBE_NO_TRIGGER` is weaker evidence because it
can be caused by geometry as well as sensor failure.  If direct I2C transport
evidence arrives afterward, EC2 upgrades the current classification to
`HARD_COMM_FAULT` while retaining the first fault separately for the evidence
timeline.  A stronger later fact must not be hidden by whichever symptom was
observed first.


## Why does ES-R4-EC2 modify generic `probe.py` at all?

The change is intentionally small: `ProbeCommandHelper` asks the active probe
object for an optional persistent-config validator before `PROBE_CALIBRATE` or
`Z_OFFSET_APPLY_PROBE` writes a pending `z_offset`.  Normal probes that do not
provide the hook behave exactly as before.  The Eddy backend implements the hook
to enforce the same fault latch used by probing and sensor calibration.

This avoids an uglier command-replacement wrapper while keeping Eddy-specific
policy out of generic `probe.py`.


## Why does Z-offset calibration explicitly invalidate Z if a guarded sensor call aborts early?

`Z_OFFSET_CALIBRATION` can temporarily rebase the logical Z coordinate to provide a small `USE_CURRENT_Z_ALLOWANCE` without moving the motors. With the stronger EC2 preflight, a pending transport fault may now reject the contact/non-contact operation *before* `HomingMove` begins. In that early-abort case, generic `homing.py` never receives a probe failure and therefore cannot revoke the temporary Z trust. EC2 wraps those sensor calls and explicitly marks Z unhomed on command error, so a temporary logical rebase cannot survive as a trusted coordinate.

## Which persistent calibration paths are protected by the shared Eddy fault authority?

EC2 covers the project-relevant persistence paths: drive-current calibration, manual `PROBE_EDDY_CURRENT_CALIBRATE`, standard `PROBE_CALIBRATE`, and `Z_OFFSET_APPLY_PROBE`. The generic `probe.py` change is only an optional validation hook; non-Eddy probes behave as before. The invariant is that transport-tainted or fault-latched Eddy data must not become pending persistent configuration.


---

## Does `NACK | BUSY` mean the Eddy sensor is permanently broken?

No. On this Sovol STM32F1 driver, BUSY is commonly additional bus-state evidence observed after the transaction has already failed due to NACK/TIMEOUT. One `NACK | BUSY` is sufficient to invalidate the **current transaction**, but it is not proof of permanent sensor-hardware failure. EC2 therefore stops/taints/aborts the active action and revokes Z trust for bed-facing Z contexts, then permits the no-motion `M_BAMBOO_EDDY_RECOVERY_CHECK`. Only repeated valid LDC identity reads with no new `transport_fault_seq` move transport to `TRANSPORT_RECOVERED`; Z is still not restored, and only one fresh Safe Home `G28` is armed.

Why not auto-scan/retry inside the fault callback? The Sovol ABI has both synchronous I2C responses and asynchronous error reports, and their host ordering is not yet fully characterized on hardware. An explicit recovery check can leave a reactor settle window after each read and never initiates Z motion automatically.

EC2 now makes a narrower automatic exception **before motion starts**: a pre-arm readiness gate may repeat only no-motion identity reads in a bounded sequence. If a transient `NACK|BUSY` is absorbed there, Z trust is unchanged because there was no descent to invalidate. This is intentionally different from retrying an active probe. Once trsync/Z motion is active, any transport fault still aborts and taints that transaction immediately.


## Why could an Eddy fault keep repeating forever after a command already failed?

The Sovol/Official-lineage `BatchBulkHelper` unregisters a sensor client when that client is called by a later batch and returns `False`. If the I2C path is already faulted badly enough that no successful batch arrives, a graceful `finish()` flag alone cannot remove the client or call the stop callback. The MCU-side periodic LDC query may therefore continue generating fresh I2C error reports after the owning G-code has already aborted. FS1 closes this lifecycle hole with deterministic client removal plus an immediate LDC stream quarantine on confirmed runtime transport faults. The quarantine stops the periodic query and resets the batch helper so a later explicit recovery can start a fresh stream.

## Why was the pre-arm transport quiescence gate added, and what has testing shown?

### The problem it is intended to solve

Before pre-arm hardening, the real SV08 Max reproduced an Eddy homing transport failure after the Z transaction had already become ACTIVE: `err_code=34`, decoded from Sovol's STM32F1 bitmask as `NACK | BUSY`. Once a bed-facing transaction is active, transport integrity has already been lost and the safe response is to stop/taint/abort the action and invalidate Z where applicable. Retrying the same active descent would weaken the safety model.

The failure pattern, together with the vendor I2C implementation, suggested a narrower working hypothesis: at least some raw-34 events may be associated with **I2C / measurement-session transition boundaries**, where a new Eddy action begins before the transport/peripheral state is fully quiescent.

### What M_Bamboo changed

ES-R4 transport hardening therefore adds a **pre-arm transport quiescence gate** before safety-relevant Eddy actions, including Safe Home Z, ordinary/contact probe sessions, Eddy calibration, and rapid bed-mesh scan startup. The gate is deliberately no-motion. It applies a bounded settle window, performs known LDC manufacturer/device identity reads, and confirms that the monotonic transport fault sequence has not advanced before allowing the motion/session to arm.

This is not an active-motion retry mechanism. If the gate observes a transient while Z is still stationary, it may perform a bounded readiness re-check and require later clean windows before proceeding. Once HOMING/PROBE is ACTIVE, any confirmed transport fault still follows the strict stop -> taint -> abort policy.

The design goal is therefore:

`do not start a safety-critical Eddy transaction while transport is unsettled`

rather than:

`start the descent and retry the sensor if communication fails`.

### Real-machine result so far

After the pre-arm gate was introduced, hardware validation covered repeated G28/Safe Home cycles, direct contact probing, repeated `CLEAN_NOZZLE`, repeated Z-offset calibration, QGL, adaptive rapid mesh, final XY re-home, and a full slicer-driven `START_PRINT` followed by an actual cube print and post-print status inspection. In the latest post-print session, `M_BAMBOO_EDDY_STATUS` reported **30 pre-arm checks with 0 transport faults, 0 transient recoveries, 0 pre-arm failures, 0 forced stream quarantines, and 0 repeated-fault suppressions**.

That is strong evidence that the gate is not merely regression-free but is likely reducing the observed fault incidence. It also supports, but does not prove, the transition-boundary hypothesis above. The project therefore describes this as a **material reduction in observed raw-34 incidence**, not as elimination of error 34.

Longer soak testing remains necessary, but the first high-value natural FS1.1 transport-fault gate has now been crossed. On 2026-08-20 a naturally occurring raw `34` (`I2C_BUS_NACK | I2C_BUS_BUSY`) during active contact verification was safely aborted, Z trust was invalidated, the active LDC stream was quarantined, a no-motion recovery check passed with three valid LDC identity reads and an unchanged fault sequence, one armed Safe Home `G28` re-established transport/Z trust, and the machine subsequently completed the remaining START_PRINT preparation and began printing without a firmware reset. This is one-event hardware validation, not statistical proof that every future transport fault will recover identically.

## How do pre-arm prevention and FS1 fault-storm containment differ?

They solve different stages of the same failure chain:

- **Prevent — pre-arm quiescence gate:** tries to keep an unsettled transport state from entering a safety-critical motion/session at all.
- **Detect/Stop — ES-R4 transaction safety:** if a transport fault occurs after motion is active, stop/taint/abort and de-trust Z as required.
- **Contain — FS1 stream quarantine:** if a faulted bulk stream would otherwise keep generating I2C reports after the command aborts, deterministically remove the client and force the periodic LDC stream to stop.
- **Recover — recovery check + fresh Safe Home Z:** re-proves transport health separately from coordinate trust and restores Z only through a fresh trusted home when required.

Keeping these layers separate is intentional: pre-arm should reduce how often the dangerous state is entered, while FS1 must still bound the failure if one gets through.

## Is PLR part of RC4?

No. PLR is explicitly deferred from RC4. The stock Sovol resume design relies on coordinate fabrication and command-line text matching that do not meet the current coordinate-trust and checkpoint-identity requirements. RC4 does not depend on PLR for normal printing.

## Does RC4 implement downgrade?

No generic downgrade command is part of RC4. Full Restore is the authoritative removal path. After Restore, a user may install any supported historical release using that release's own exact installer artifact.

## What survives Full Restore?

Unrelated user cfg content outside M_Bamboo-owned regions is preserved. M_Bamboo-added cfg blocks are removed or reversed; original backend Python is restored from the centralized `extras/mb_bak/` archive, and M_Bamboo Python files recorded as originally absent are deleted.
