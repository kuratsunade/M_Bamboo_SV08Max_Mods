# RC5-RS1 — Rapid Scan Compatibility / Safety Restoration

Status: development only; not released.

## Objective

Restore the proven RC4/stock rapid-scan measurement behavior while retaining M_Bamboo safety containment around it.

The design rule is:

> Healthy rapid-scan semantics stay unchanged. Safety code may invalidate a failed scan, but must not alter sample timing, path, speed, scan height, interpolation, or I2C transaction rate.

## Hardware finding — 2026-09-08

A real `BED_MESH_SCAN` transport fault (`raw34 = I2C_BUS_NACK | I2C_BUS_BUSY`) was followed by:

```text
Exception in flush_handler
...
probe_eddy_current.py::_rapid_lookahead_cb
self._gather.note_probe_and_position(...)
AttributeError: 'NoneType' object has no attribute 'note_probe_and_position'
```

The direct shutdown cause was therefore not the recoverable I2C fault itself. A queued rapid-scan lookahead callback executed after the owning scan session had already released `_gather`. The exception escaped through Klipper's motion flush path and caused printer shutdown.

## RS1 Phase 1

Patch: `patches/10_rc5_rs1_rapid_scan_lifecycle_guard.patch`

Phase 1 intentionally changes only callback/session lifetime handling:

1. Add explicit scan-session `_ended` state.
2. A queued rapid callback returns immediately when the session has ended.
3. A queued callback also returns if the gather object is unavailable.
4. `end_probe_session()` retires callback-visible state before releasing the measurement client.
5. Preserve RC5 transaction cleanup. Do not revert the entire scan fault path yet.

### Explicit non-changes

Phase 1 MUST NOT change:

- `SAMPLE_TIME`
- rapid-scan motion speed
- scan path
- scan height
- sample timestamp calculation
- `note_probe_and_position()` semantics
- mesh interpolation
- LDC I2C sample/query rate
- PREARM behavior
- probe descent envelope

## Why not fully revert `EddyScanningProbe` to RC4 immediately

RC4 had a known cleanup weakness: when `pull_probed_results()` raises, upstream `bed_mesh.py` does not provide a guaranteed `finally: end_probe_session()` boundary. A complete reversion would therefore risk restoring stale scan transactions/clients.

RS1 uses the smaller correction first: keep fault-path terminal cleanup, but make queued asynchronous callbacks lifetime-safe.

## Combined-candidate rule

RS1 remains independently scoped, but hardware validation may combine it with GR1 (`patches/11_rc5_gr1_generic_recovery_supervisor.patch`) because GR1 operates only at the synchronous public-command owner boundary and is explicitly forbidden from changing rapid-scan sampling semantics.

The combined test candidate therefore has two separable responsibilities:

```text
RS1
  -> make rapid-scan teardown/callback lifetime safe

GR1
  -> after a normal command_error reaches the outer command owner,
     perform bounded transport/Z recovery and replay the whole operation once
```

This combination is acceptable only while GR1 remains outside I2C, bulk, lookahead and motion-flush callbacks. Any future recovery change that enters the measurement path must be validated separately before being combined with RS1 testing.

## Validation gates

### Gate A — static / mock lifecycle

Must prove:

- healthy callback with active gather records a sample exactly once;
- callback after `_ended=True` is a no-op;
- callback after `_gather=None` is a no-op;
- ending a session removes the measurement client exactly once;
- fault cleanup leaves no active scan transaction/session;
- no new I2C read/query is introduced by RS1.

### Gate B — direct rapid baseline

Use the same machine/session and fixed thermal condition.

```gcode
G28
BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=1 METHOD=rapid_scan
```

Repeat 10 times.

Target:

```text
10/10 complete, or any transport fault aborts the scan without Klipper shutdown.
```

Record per attempt:

- `fault_seq`
- PREARM result
- scan result
- transport fault context/type
- duration
- whether Klipper remained Ready

GR1 should remain idle on this `_BASE` command because `_BASE` is not a wrapped public recovery contract. This makes Gate B a clean RS1/rapid-scan baseline even in the combined candidate.

### Gate C — historical workflow baseline

Repeat the RC4-like path:

```text
Safe Home -> rapid scan
```

Compare against prior successful ~4 s rapid-scan evidence.

### Gate D — full `BED_MESH_CALIBRATE` wrapper

Only after Gates B/C are stable.

This distinguishes rapid-scan reliability from prerequisite-chain load (`contact -> verify -> Eddy calibration -> rapid scan`). In the combined candidate, a natural eligible fault should be contained by RS1 and then recovered/replayed by GR1 at the public BED_MESH owner.

### Gate E — RC4 exact A/B if needed

If direct rapid scan is still unstable, compare on the same machine, same temperature, same path:

```text
RC4 exact probe_eddy_current backend
vs
RC5-RS1 backend
```

Do not change scan speed or sampling parameters during this A/B.

## Decision after Phase 1

- If direct rapid scan returns to historical stability, keep the measurement path unchanged and investigate workload coupling in the full wrapper separately.
- If direct rapid scan remains unstable only under RC5-RS1, perform a narrower RC4-vs-RS1 code A/B before changing measurement parameters.
- If RC4 exact also shows the same active-scan raw34 frequency, shift suspicion toward lower-layer LDC/STM32F1 transport/electrical state rather than RC5 measurement logic.

## Still deferred

Do not mix these changes into the RS1 + GR1 hardware candidate:

- calibration caching;
- additional dwell tuning;
- scan-speed reduction;
- SAMPLE_TIME changes;
- altered rapid-scan path/height/interpolation;
- any recovery action executed from async measurement callbacks.

Those would contaminate root-cause attribution and/or change the measurement behavior we are trying to preserve.
