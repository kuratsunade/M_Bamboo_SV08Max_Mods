# RC5 Eddy Communication Test Evidence

> Branch: `rc5-dev`  
> Purpose: consolidate the engineering test evidence that informed the RC5 communication-safety design.  
> Scope: host-side Klipper / Eddy safety behavior only. This document does **not** claim that the underlying STM32F1/LDC1612 root cause has been eliminated.

## Why this document exists

RC5 should be evidence-led. The goal is not to present a perfect-looking pass rate; it is to record what was actually observed, what each test can and cannot prove, and which safety mechanisms earned their place through real failures and recoveries.

## Executive summary

- Repeated Eddy contact/homing churn reproduced intermittent transport faults under otherwise healthy operation.
- Confirmed transport codes seen in the Sovol stack include `raw34 = I2C_BUS_NACK | I2C_BUS_BUSY` and `raw36 = I2C_BUS_TIMEOUT | I2C_BUS_BUSY`.
- HF2.1 completed a six-cell matrix with **32 attempts / 30 PASS / 2 transport faults**.
- Of the two HF2.1 faults, **one occurred during active contact churn (10 ms nominal dwell)** and **one occurred during the initial Safe Home Z homing before the 25 ms churn cell began**.
- The nominal dwell values were later shown **not** to be the true LDC STOP_ACK -> next START gap: even the nominal 0 ms cell had roughly ~1.4 s wall-clock separation because the test sequence included a 5 mm Z lift, motion completion, and macro overhead. Therefore the data does **not** support a simple hard dwell threshold.
- Deterministic client removal, synchronous STOP acknowledgement, transport fault sequence tracking, active-stream quarantine, PREARM gating, and one-shot armed Safe Home recovery all proved useful in containing failures.
- PREARM is retained in RC5 because it prevented bed-facing Z motion from starting when transport was already unstable; this directly addresses the physical bed/nozzle strike failure mode observed before PREARM was introduced.

## Historical test sets

### EAR-R3E

Cumulative engineering observations recorded during R3E:

- Total recorded attempts: **41**
- PASS: **35**
- Faulted: **5**
- One attempt was interrupted / not classed as PASS or fault in the cumulative notes.

Zero-dwell subset:

- **25 attempts**
- **20 PASS**
- **5 faults**

Completed nominal dwell >=100 ms subset:

- **15 attempts**
- **15 PASS**
- Equivalent to **75 successful contact transactions** across the completed cells.

Cell notes:

| Cell | Result |
| --- | --- |
| B3 / 0 ms | 6 attempts, 5 PASS, 1 fault |
| B5 / 0 ms | 5/5 PASS |
| B8 / 0 ms | 7 attempts, 5 PASS, 2 faults |
| B10 / 0 ms | 7 attempts, 5 PASS, 2 faults |
| B5 / 100 ms | 5/5 PASS |
| B5 / 250 ms | 5/5 PASS |
| B5 / 500 ms | 5/5 PASS |
| B5 / 1000 ms | manually stopped after earlier cells; not used as completed proof |

Important later correction: these results originally suggested that >=100 ms might be a clean quiescence threshold. HF2.1 timing instrumentation later showed that the nominal dwell parameter was only *extra* dwell after motion. Actual STOP_ACK -> next ADD_CLIENT gaps were already on the order of ~1.4 s even at nominal 0 ms. Therefore R3E is useful as reproducibility evidence, not as proof of a 100 ms threshold.

### EAR-R3F / HF1 / HF2

R3F fixed BURST=8 and attempted nominal dwell cells 0/10/25/50/75/100 ms.

Early R3F runs reproduced transport faults and, in one 10 ms run, a transaction around #125 produced `raw36` followed by a cluster of `raw34/raw36` reports. At that stage the session became persistent/escalated and could no longer provide clean later-cell evidence.

HF1 added structured logging and showed an important negative result: some failures happened during PREARM before any measurement lifecycle had started. In those cases there was no ADD_CLIENT/START/BATCH/STOP sequence to blame.

HF2 fixed logger lifecycle behavior and automatic terminal stop, but exposed a separate host-side stale-transaction cleanup defect: after a real transport fault and a successful LDC stream STOP, a later `pull_probed()` / sample-finalization exception could leave `_active_transaction` stale. That contaminated the recovery classification. This was fixed in HF2.1 by making terminal transaction cleanup cover the entire post-transaction sample-finalization / acceptance stage.

### HF2.1 final matrix

HF2.1 completed the full six-cell matrix:

- **32 attempts**
- **30 PASS**
- **2 faults**
- Final logger stop reason: `MATRIX_COMPLETE`
- Final transport state: `HEALTHY`
- Recovery checks: **2/2 passed**
- Armed recovery successes: **2**
- Final homed axes: `xyz`

Nominal cell results:

| Nominal dwell | Result | Interpretation |
| ---: | --- | --- |
| 0 ms | 5/5 PASS | no confirmed churn fault |
| 10 ms | 6 attempts, 5 PASS, 1 fault | confirmed active-contact transport fault |
| 25 ms | 6 attempts, 5 PASS, 1 logged fault | fault occurred during initial Safe Home Z homing before churn; not attributable to 25 ms dwell |
| 50 ms | 5/5 PASS | clean |
| 75 ms | 5/5 PASS | clean |
| 100 ms | 5/5 PASS | clean |

Effective churn-associated faults by nominal dwell therefore were:

- 0 ms: 0
- 10 ms: 1
- 25 ms: 0 confirmed churn faults
- 50 ms: 0
- 75 ms: 0
- 100 ms: 0

This is **not** enough evidence for a hard 50 ms threshold.

## HF2.1 fault morphology

### Fault #1 - active contact churn

- Cell: nominal 10 ms
- Attempt: 4
- Transaction: #84
- Caller: `RUN_PROBE_VIR_CONTACT`
- Stream state at failure: active (`bulk_started=True`, client_count=1)
- Preceding batch telemetry: no batch errors / overflows reported
- Fault: `raw34 = NACK | BUSY`
- Containment: stream quarantined, client count returned 1 -> 0, STOP_ACK observed, bulk stopped
- Recovery: no-motion identity check passed with repeated `5449/3055` IDs and unchanged fault sequence
- Then one armed Safe Home G28 succeeded and restored Z trust

This is strong evidence of a transient active-transport fault rather than a host client leak.

### Fault #2 - Safe Home Z homing

- Nominal matrix cell: 25 ms
- Timing: before the 8-contact churn sequence began
- Context: `HOMING`
- Therefore this event cannot be used as evidence that the 25 ms churn dwell itself was unsafe.

## Timing correction

The churn sequence included:

```text
RUN_PROBE_VIR_CONTACT
G91
G1 Z5 F300
G90
M400
G4 P{dwell}
RUN_PROBE_VIR_CONTACT
```

Therefore `DWELL_MS` was only an *additional* delay layered on top of a 5 mm Z lift and completed motion.

Measured lifecycle traces showed roughly ~1.4 s median wall-clock separation from LDC STOP acknowledgement to the next measurement client/start even in nominal low-dwell cells.

Conclusion: the test matrix is useful for fault reproduction and recovery statistics, but it is not a controlled STOP_ACK -> START quiescence experiment.

## Safety behavior supported by testing

### PREARM

PREARM is retained as a safety invariant.

Before PREARM, real failures were observed where an unhealthy Eddy/transport state was followed by bed-facing Z motion and physical nozzle/bed contact. After PREARM was introduced, an unstable transport could be detected before the dangerous Z transaction was allowed to start.

PREARM does **not** guarantee that a new transport fault cannot occur after motion starts. Its job is narrower and important: do not begin bed-facing Z motion when transport is already unhealthy or has just exposed a transient that has not yet demonstrated stability.

### Fault sequence + identity reads

A valid LDC1612 identity read alone is not accepted as proof of health. Recovery requires repeated expected IDs (`0x5449 / 0x3055`) while the monotonic transport fault sequence remains unchanged, with reactor time allowed for the Sovol asynchronous I2C fault report path to arrive.

### Active stream quarantine

HF2.1 traces showed that fault containment could return the active periodic stream to client_count=0 / bulk stopped with STOP acknowledgement. This substantially reduced the likelihood that the repeated errors were caused by a host-side client leak.

### Failed transaction is never retried

The transaction that observed a bed-facing fault is aborted. Recovery, when allowed, is a fresh health-check plus a fresh Safe Home Z homing transaction, never a replay of the failed probe/homing transaction.

## RC5 recovery policy target

RC5 distinguishes a *fault episode* from a whole Klipper session:

1. Within one fault episode, allow at most **one** armed Z recovery transaction.
2. If that armed recovery fails, stop automatic recovery and require `FIRMWARE_RESTART` / operator intervention.
3. If recovery succeeds, transport returns to `HEALTHY` and Z trust is rebuilt. A later, genuinely new fault may begin a new recovery episode.
4. Add a session / print-start budget so repeated independent faults cannot create an unlimited automatic-recovery loop. Initial RC5 target: **MAX_AUTO_RECOVERIES=3**, **MAX_CONSECUTIVE_AUTO_RECOVERIES=1**.

The exact budget is a host-side policy knob and should be validated before RC5 is declared stable.

## What the statistics do NOT prove

The current data does not prove:

- that a specific dwell threshold eliminates the problem;
- that PREARM eliminates faults which occur after active motion starts;
- that the underlying physical / STM32F1 / LDC1612 root cause is fully known;
- that a power cycle is required for recovery;
- that the communication fault is purely electrical or purely software.

The evidence *does* support retaining fail-closed bed-facing safety gates and bounded recovery while the lower-level Sovol I2C behavior is audited.
