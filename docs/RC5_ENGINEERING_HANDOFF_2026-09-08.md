# M_Bamboo_SV08Max_Mods — RC5 Engineering Handoff

Date: 2026-09-08

Status: development handoff for continuation in a new engineering conversation. This document is intentionally exhaustive and preserves constraints, design rationale, exact identities, real-hardware evidence, unresolved questions, and next actions. It is **not** a public-release compatibility statement.

---

## 0. Executive state

Machine: Sovol SV08 Max 500×500, Klipper + Mainsail, Orca Slicer, 0.4 mm nozzle.

Project/repository: `M_Bamboo_SV08Max_Mods`

Maintainer identity used in managed blocks: `Master_Bamboo / 竹子`

Public baseline remains: `v1.0.0-rc4`

Runtime Safety baseline remains: `ES-R4-EC2-FS1.1`

Active development branch: **`rc5-dev` only**.

Current RC5 dev runtime under test combines:

- RC5 START recovery/orchestration work (`SR1`),
- rapid-scan lifecycle restoration (`RS1`),
- generic bounded automatic recovery (`GR1`).

Current combined `probe_eddy_current.py` SHA256:

`5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29`

Pre-RS1/GR1 hardware-tested development intermediate SHA256:

`dcb78d4d7d5108236eca23a225e6e582e1b128419bf10c8a5b83cf8de346ced0`

Current combined runtime has now passed:

- static/materialization/installer-transform GitHub Actions validation,
- healthy real-hardware Safe Home/G28,
- healthy real-hardware QGL,
- multiple direct rapid scans,
- multiple full `BED_MESH_CALIBRATE` flows,
- and, importantly, **one naturally occurring raw34 (`I2C_BUS_NACK|I2C_BUS_BUSY`) real-hardware fault during QGL that was automatically recovered end-to-end by GR1 without firmware restart, manual recovery, or Klipper shutdown.**

Do **not** treat RC5 as released/stable yet. Long-term natural fault soak and broader hardware confidence remain pending.

---

## 1. Fundamental project boundary — never violate silently

The project intent is **NO MCU firmware modification or recompilation, ever**, unless the user explicitly changes this fundamental intent.

MCU C/source may be audited only to understand Sovol's design, root cause, lower-layer limitations, and to guide host-side trust/containment.

Out of scope by default:

- MCU firmware modification,
- MCU rebuild/recompile,
- bootloader work,
- firmware flashing,
- `extra_mcu` replacement,
- low-level STM32 I2C source patch,
- activating new physical I2C bus-recovery behavior through MCU changes.

Allowed:

- Klipper host Python `extras`,
- `printer.cfg`, `Macro.cfg`, related config macros,
- shell/installer/release tooling,
- diagnostics and host-side safety/recovery logic.

If a defect is only correctly repairable in MCU source, document it as a lower-layer limitation and use the smallest safe host-side detection/containment/recovery possible.

---

## 2. Release / branch / installer rules

### Branching

RC5 development uses one branch only:

`rc5-dev`

Do not create a firmware branch.

### Public/dev lineage separation

The development intermediate SHA `dcb78d...` is a **dev-only migration source**, not public release lineage.

Validation artifact hashes are not release compatibility lineage.

### Installer requirements

Installer goals are strict:

- curl/wget one-click capable,
- dry-run by default,
- explicit `--apply` for writes,
- idempotent,
- rollback/full restore support,
- exact hash gating for backend whole-file replacements,
- unknown backend hashes fail closed,
- unknown macro lineage fails closed,
- marker-managed config edits,
- no silent editing of `SAVE_CONFIG` tail,
- temp transaction scratch cleaned after success or successful auto-rollback,
- preserve failed rollback scratch and report it,
- central backend backup directory:
  `/home/sovol/klipper/klippy/extras/mb_bak`,
- backup is original pre-M_Bamboo state, created once and never overwritten,
- legacy `.mb_baseline` is migration input only, not ongoing backup architecture.

Feature ownership must remain independent.

At minimum historical project feature areas include:

1. hardware cooling / bed-fan config (requires physical hardware mod, explicit feature only),
2. printer.cfg / Macro.cfg optimization,
3. M_Bamboo Safe Home,
4. PLR,
5. Eddy Safety / Z-offset / H2-related work,
6. diagnostics.

Current candidate manifest intentionally does **not** make hardware cooling part of `all`.

PLR is deferred/not installable in the current candidate and must not be mixed into RC5 I2C/recovery validation.

Dual GitHub + Gitee release parity is a project requirement for actual releases.

---

## 3. Current installer manifest identities

Current development manifest reports:

- release: `1.0.0-rc5-dev`
- status: `development-candidate`
- runtime safety: `ES-R4-EC2-FS1.1`

Backend targets:

- `ldc1612.py`
  `aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04`
- `probe_eddy_current.py`
  `5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29`
- `probe.py`
  `227d0c6b8527ece1793caf969d5292646ec185f65ca1c679ccf4195515dd529a`
- `M_Bamboo_Safe_Homing.py`
  `5f85a1a397413a7ab5da28d2b19b586a6d371b49a4793b80bc685d5adb0f9038`
- `z_offset_calibration.py`
  `1089df132131010f774d40b331fef4ff6ba02252f4b55c107846c6cc0a7a75ce`

Reference-only stock `homing.py` identity:

`e4a069d0fd4c91a150788b325af9c87d7d0c804ecf16f536e19e7e6b5a3bfedb`

Historical important identities:

- RC4 `ldc1612.py`:
  `aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04`
- RC4 `probe_eddy_current.py`:
  `6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e`
- R3F/HF1 probe:
  `b42ed23e5844b671b9d2de95774830a0054ad3893a6793ee1ea02a8546b07f0b`
- HF2.1 probe:
  `72a43e419bf996b004425280acd9bc4f13f4411e1a68d7a8f094eb4118faedbb`
- HF2.1 ZIP:
  `2ab02b807888f9f4a698c8d723aac431ecb9f2b11914f2b207227a9982e13245`
- old blocked RC5 development package:
  `/mnt/data/M_Bamboo_SV08Max_Mods_RC5_dev_offline_candidate.zip`
  SHA256 `dd5dae4273f025c2dff0cddae1e6108d2f91a680d82fb6d1fc487216f71a7998`
  This package is **blocked** due to rapid-scan shutdown behavior and must not be treated as daily-use.

---

## 4. Sovol MCU/I2C source archaeology — frozen technical conclusion

Sovol source archive previously inspected:

`/mnt/data/sovol-home-current.tar.gz`

Sovol Klipper branch observed:

`klipper-eddy_contact_probe`

HEAD observed:

`d4031b31daa4c896365f5c688a472086f6e43f49`

Date: 2025-10-18.

Relevant history:

- `ad90d60` — add Eddy,
- `93b121b` — optimize LDC ID reads/recover/re-read, add error reporting,
- `060eada` / `738006c` — disable `i2c_shutdown_on_err` on STM32F1, comment equivalent to “needs optimization”,
- `79c9992` — add I2C bus error codes,
- `ee6f394` — modify `i2c_busy_errata`, `i2c_wait`, error exits,
- `265b3f7` — add delays,
- `d436c9f` — cast in `container_of`; warning suppression only,
- `fe4df8b` — LDC I2C error classification.

No later low-level repair was found in that lineage.

### I2C bitmask semantics

Enum values are bit positions, not scalar enum results:

- NACK position 1 → `2`
- TIMEOUT position 2 → `4`
- BUSY position 5 → `32`
- BERR position 7 → `128`

Therefore:

- raw34 = `2 + 32` = `NACK|BUSY`
- raw36 = `4 + 32` = `TIMEOUT|BUSY`

Do not claim the BUSY definition itself is wrong. The architecture intentionally returns combinable bit flags. A real bug class is scalar consuming code such as `ret == I2C_BUS_BUSY` instead of a bit test.

### `i2c_busy_errata` metadata bug

Source shape:

```c
struct i2c_info {
    I2C_TypeDef *i2c;
    uint8_t scl_pin, sda_pin;
};
```

For I2C2 the intended pins are PB10/PB11.

The expression:

```c
container_of((I2C_TypeDef * const *)i2c, struct i2c_info, i2c)
```

is semantically invalid because the function has the *value of the member*, not the address of the member storage inside an `i2c_info` object. Since member offset is 0, the peripheral register base is interpreted as an `i2c_info` struct. After CR2 is cleared, decoded `scl_pin` / `sda_pin` can become 0, resulting in GPIO 0 / PA0 manipulation rather than PB10/PB11.

Peripheral SWRST/re-init still happens and likely explains why recovery sometimes works.

**Do not repair this in M_Bamboo.** Correcting it at host level is impossible; patching MCU source would cross the project boundary and could newly activate physical PB10/PB11 bus manipulation.

### Failed transaction boundary weakness

Observed lower-layer weakness:

- I2C write/read loops may overwrite an earlier error result,
- F1 generic read handler may emit `i2c_read_response` despite a read error,
- LDC helper may ignore return status and continue into status/data/check-home processing.

Therefore the important missing semantic boundary is:

> failed transaction data is not consistently invalidated before downstream LDC use.

### Architectural interpretation

Sovol intentionally chose recoverable I2C rather than fatal MCU shutdown, which is reasonable for high-rate Eddy use. The architecture is incomplete rather than conceptually wrong.

Sovol provides roughly:

- detection,
- logging,
- peripheral reset/re-init.

Missing pieces include:

- strict transaction invalidation,
- host trust reconstruction,
- Z trust semantics,
- bounded workflow recovery,
- safe operation replay.

M_Bamboo's goal is to complete that recoverable-I2C intent at host layer without changing MCU firmware.

Desired fault semantics:

```text
raw34/raw36
→ current action invalidated
→ stream/client cleaned
→ transport revalidated
→ rebuild Z trust if needed
→ replay entire atomic stage/operation
→ continue only if safely recovered
```

Recovery budget exhausted or recovery failure → hard stop/fail closed.

---

## 5. Safety invariants / PREARM

User explicitly considers PREARM an important safety feature that prevented Z crashes.

**Do not remove or simplify PREARM unless equal or stronger fail-closed behavior is proven.**

Current key safety facts:

- `stepper_z position_min=-1` currently; stock was approximately `-10`.
- Eddy Z endstop is `probe:z_virtual_endstop`.
- Safe Home unknown-Z behavior:
  - physical +5 mm positive hop,
  - mark Z unhomed,
  - raw XY home,
  - move to Z-home XY around `(271,251)`,
  - real Eddy Z home,
  - post-home Z=10.
- confirmed transport fault during a bed-facing operation:
  - abort current transaction,
  - invalidate Z if required,
  - quarantine LDC stream,
  - no-motion recovery identity check 3× expected IDs `0x5449/0x3055`,
  - after transport recovery, Z remains untrusted until one armed fresh Safe Home G28 succeeds,
  - never retry the failed transaction in place.

PREARM current settle/read windows historically include `.025/.075/.125`.

Acceptance requires a clean status and unchanged fault sequence; transient→clean may recover before motion; persistent prearm failure aborts before motion.

PREARM is used around:

- Safe Home Z,
- probe/QGL sessions,
- rapid mesh,
- contact probe,
- non-contact calibration.

QGL uses session-level PREARM, not one PREARM per point.

`transport_fault_seq` alone is not enough for automatic recovery eligibility because a PREARM can exhaust without an async transport report. Coordinator/supervisor logic therefore also uses `preflight_failed_count`.

Stage/local marker concept:

`(transport_fault_seq, preflight_failed_count)`

A recovery is eligible only when the marker advances relative to the current owner invocation. This prevents stale historical faults and ordinary macro errors from being misclassified as recoverable Eddy transport faults.

---

## 6. EAR / HF evidence before RC5 combined candidate

R3E summary:

- 41 attempts,
- 35 pass,
- 5 faults,
- one interrupted/unclassified.

Zero dwell:

- 25 attempts,
- 20 pass,
- 5 faults.

Completed dwell >=100 ms:

- 15 completed, all pass,
- but HF2.1 later disproved a clean dwell threshold.

HF2.1:

- 32 attempts,
- 30 PASS,
- 2 faults,
- one true 10 ms contact raw34,
- one initial Safe Home homing fault before a 25 ms cell.

Observed STOP_ACK→next ADD_CLIENT was around 1.42 s even at nominal 0 ms due to macro/motion overhead.

Therefore there is no evidence-backed 50/100 ms magic dwell threshold.

Do not add arbitrary sleep/dwell as a “fix”. If a barrier is ever justified, prefer state-driven lifecycle quiescence.

Likely-cause ranking after HF2.1:

- host lifecycle: LOW,
- MCU-side occasional LDC I2C failure: HIGH,
- repeated workload: HIGH,
- F1/LDC peripheral state: HIGH,
- electrical: MEDIUM,
- host bookkeeping: LOW.

Historical RC4-like MESH soak `11 attempts / 10 pass / 1 fault` did **not** prove that active rapid scan itself faulted. Historical fault contexts were often HOMING and RUN_PROBE_VIR_CONTACT; many actual rapid scans completed normally.

---

## 7. P0 lifecycle bug that triggered RC5 work

The production RC4-like probe implementation had terminalization/cleanup gaps.

### Normal probe

`_run_logged_probe()` protected only `phoming.probing_move()` with try/except. If motion stopped and a later `_gather.pull_probed()` / await failed, `_active_transaction` could remain stale.

### Rapid scan

Analogous cleanup weakness existed.

### Eddy calibration

Bulk client removal happened only on normal path; transport/motion error could leak client state.

Required RC5 lifecycle behavior:

- late probe failure terminalizes transaction as ABORTED,
- result is recorded,
- active transaction is released in `finally`,
- rapid scan does equivalent cleanup,
- scan teardown detaches/retire session state safely,
- `multi_probe_end()` nulls gather before finish,
- Eddy calibration client removal uses `finally`,
- `preflight_failed_count` exposed.

---

## 8. Real rapid-scan shutdown blocker and RS1

A pre-RS1 hardware candidate passed Safe Home, CONTACT, CLEAN, ZCAL, QGL, but full `BED_MESH_CALIBRATE` exposed two failures.

First failure:

- Eddy calibration failed with incomplete sensor data,
- `MBEDDY FAULT HARD_COMM_FAULT reason=I2C_BUS_NACK|I2C_BUS_BUSY raw=34 seq=1`,
- happened before bed-facing motion,
- Z trust preserved,
- manual `M_BAMBOO_EDDY_RECOVERY_CHECK` succeeded 3× identity reads without firmware restart.

Second failure:

- full preconditions and calibration passed,
- rapid mesh started,
- scan transaction invalidated by transport fault,
- then Klipper shutdown via `Exception in flush_handler`.

Root call chain:

```text
toolhead flush
→ _process_moves()
→ EddyScanningProbe._rapid_lookahead_cb()
→ self._gather.note_probe_and_position(...)
→ AttributeError: 'NoneType' object has no attribute 'note_probe_and_position'
→ Exception in flush_handler
→ printer.invoke_shutdown
```

This was not MCU shutdown/CAN loss. MCU stats were clean before the host-side shutdown.

Safety correctly invalidated the scan; the unsafe part was an asynchronous lifecycle race: a queued lookahead callback ran after teardown had cleared `_gather`.

### RS1 design

Name: **RC5-RS1 Rapid Scan Compatibility / Safety Restoration**

Rule: preserve RC4/stock healthy measurement behavior; safety wraps around, not inside, the measurement algorithm.

RS1 intentionally does **not** change:

- `SAMPLE_TIME`,
- rapid scan speed,
- scan height/path,
- lookahead timestamp,
- sample window,
- `note_probe_and_position()` healthy measurement semantics,
- mesh interpolation,
- LDC sample/query rate.

RS1 session-lifetime guard:

- `self._ended = False` at session creation,
- callback returns if ended,
- callback copies `gather = self._gather`, returns if None,
- healthy callback keeps the same start-time math and measurement call,
- teardown sets `_ended=True` before detach,
- detach gather locally, set `_gather=None`, then `gather.finish()`.

A queued stale callback therefore becomes a no-op instead of throwing from toolhead flush context.

Patch file:

`patches/10_rc5_rs1_rapid_scan_lifecycle_guard.patch`

Original blob SHA recorded for the patch chain:

`e05b25b15e3a27ea74ab698271f195f975bf17ca`

---

## 9. START_PRINT coordinator — SR1

Do not casually simplify or reorder START_PRINT. User explicitly asked on 2026-09-08 to leave the current structure alone because it is already considered sufficiently simple.

Current intended core sequence:

```text
CLEAN
→ PRE_ZCAL
→ QGL
→ G28 Z
→ BED_MESH
→ POST_ZCAL
```

The current managed `release/config/start_print_core.block` is version:

`RC5-SR1-GR1`

When `M_Bamboo_Start_Sequence` is ready, the macro calls:

`M_BAMBOO_START_SEQUENCE`

Otherwise it falls back to an exact RC4-compatible legacy sequence.

Current fallback details include:

- `CLEAN_NOZZLE`
- `SET_GCODE_OFFSET Z=0`
- velocity limit setup,
- PRE Z-offset calibration using current bed target and `USE_CURRENT_Z=1`,
- set `_global_var.has_z_offset_calibrated=True`,
- `M400`,
- `QUAD_GANTRY_LEVEL`,
- `G28 Z`,
- `BED_MESH_CALIBRATE`,
- POST Z-offset calibration with `USE_CURRENT_Z=1 USE_CURRENT_Z_ALLOWANCE=1.25 REHOME_XY=1`,
- reset `has_z_offset_calibrated=False`.

Important historical failure modes the coordinator addresses:

1. `has_z_offset_calibrated=True` could persist after mid-start error.
2. BED_MESH wrapper SCV=1 restore happened only on normal exit.
3. POST ZCAL temporary coordinate relabel/allowance could interact with errors before actual motion.
4. Coordinator must use actual heater target.
5. Recovery only on new stage-local safety evidence.

Stage replay policy:

- CLEAN: rerun whole stage.
- PRE_ZCAL: failed stage invalid; flag true only after success.
- QGL: rerun whole QGL; PRE_ZCAL stays completed.
- Z_HOME: successful recovery Safe Home can satisfy stage.
- MESH: coordinator is sole owner and calls base adaptive rapid scan as designed; wrapper remains for manual/compat usage.
- POST_ZCAL: preserve QGL/mesh, recover Z if required, rerun whole POST_ZCAL.

START budget:

- maximum 3 independent recovery episodes total,
- one recovery per stage invocation,
- recovery failure is terminal,
- same stage faults again before clean completion → terminal,
- clean stage completion resets independent-episode semantics,
- non-Eddy errors propagate,
- fourth independent episode stops.

---

## 10. Global bounded automatic recovery — GR1

User explicitly rejected a simplistic “manual command vs START_PRINT” distinction as a reason to disable automatic recovery.

Correct architecture:

- Recovery decision is global/safety-based.
- Operation type determines **replay contract**, not whether recovery is automatic.
- One outermost synchronous owner performs recovery.
- Async callbacks never perform recovery.

Current implementation object:

`M_Bamboo_Recovery_Supervisor`

Version:

`RC5-GR1`

Public commands currently wrapped:

- `G28`
- `RUN_PROBE_VIR_CONTACT`
- `CLEAN_NOZZLE`
- `Z_OFFSET_CALIBRATION`
- `QUAD_GANTRY_LEVEL`
- `BED_MESH_CALIBRATE`

Status command:

`M_BAMBOO_RECOVERY_STATUS`

Core GR1 behavior:

1. On outermost supported public command, snapshot `(transport_fault_seq, preflight_failed_count)`.
2. Run original command.
3. If success → no recovery.
4. If command error and marker did not advance → ordinary/non-Eddy error; propagate unchanged.
5. If marker advanced → one recovery episode is allowed.
6. Run no-motion transport identity recovery.
7. Require transport state `HEALTHY` or `TRANSPORT_RECOVERED`, no restart requirement.
8. If Z recovery required or Z unhomed → perform fresh Safe Home Z trust reconstruction.
9. Replay the entire original public operation once.
10. If replay produces another new Eddy/PREARM marker → stop automatic recovery and fail terminally.
11. If replay succeeds → increment recovered-total and report `RECOVERED_SUCCESS`.

Nested ownership:

- if GR1 already active, nested supported commands pass through original handler,
- if START coordinator active, GR1 direct wrappers pass through and START remains owner.

The supervisor never executes recovery from sensor callback, bulk callback, rapid lookahead callback, or toolhead flush context.

### Recovery tiers concept

Tier A:

- new transport evidence,
- safe operation terminalization,
- motion quiescent,
- transport revalidation,
- known replay contract,
- budget available.

→ automatic recovery + whole-operation replay.

Tier B:

- transport recovery possible,
- but workflow replay is not safe/atomic/idempotent.

→ recover transport but do not invent a workflow replay.

Tier C:

- identity recovery fails,
- recovery itself faults,
- repeated fault before clean checkpoint,
- restart required,
- physical state uncertain.

→ fail closed.

---

## 11. Deterministic RC5 materialization / CI status

Build chain:

`RC4 exact -> patch 09 hardware-candidate alignment -> patch 10 RS1 -> deterministic GR1 transform`

RC4 exact commit used in chain:

`98c0ff8b710c2d809ced8810b4c670e3ed91385a`

Current combined runtime SHA:

`5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29`

Current dev identity doc:

`docs/RC5_DEV_COMBINED_RUNTIME_IDENTITY.md`

Important workflows/tools:

- `.github/workflows/rc5-materialize-combined-runtime.yml`
- `.github/workflows/rc5-finalize-dev-candidate.yml`
- `.github/workflows/rc5-combined-validation.yml`
- `tools/rc5_finalize_dev_candidate.py`
- `tools/test_rc5_combined_runtime.py`

Materialization workflow run `34202420916` succeeded.

Finalize workflow run `34203411788` succeeded.

Combined validation run:

- run `34204058321`
- commit `83a5babd313a459384aa8cc50d54e8ac1b75b2aa`
- SUCCESS.

Validated steps included:

1. exact identities,
2. compile,
3. RS1 + GR1 implementation mock regression,
4. installer parser regression,
5. START_PRINT RC4→RC5 transform and idempotence,
6. public/dev lineage separation,
7. package development candidate,
8. upload development candidate.

Implementation-level mock tests include:

- healthy RS1 callback records once with same timing,
- ended callback no-op,
- `_gather=None` callback no-op,
- GR1 happy path no recovery,
- non-Eddy error propagated/no recovery,
- first transport fault → recovery → replay → success,
- second fault on replay stops,
- nested active owner pass-through,
- START owner pass-through,
- recovery failure terminal.

An early test failure was only exact binary float equality in a mock (`9.95,10.05,10.0`); changed to tolerance `1e-12`. Runtime was unchanged.

Actions artifact:

- name `RC5-RS1-GR1-dev-candidate`
- artifact id `10046984647`
- wrapper size observed: 384883 bytes
- artifact digest:
  `sha256:1dda8e586d6558680e4fe60d6eea546cbe6b57045a0a770c07fb3be866cf5cea`
- expiration noted: 2026-12-07.

Previously downloaded wrapper path:

`/mnt/data/M_Bamboo_SV08Max_Mods_RC5_RS1_GR1_dev_candidate.zip`

Important: the downloaded GitHub Actions artifact is a wrapper ZIP containing the actual candidate ZIP generated by the packaging workflow. Prior local extraction/inner-hash verification could not be completed because local code/container tools repeatedly returned `ClientError`. Do not claim local inner ZIP verification unless rerun successfully in a new environment.

---

## 12. Historical full-package validation gap — preserve this caveat

An earlier offline candidate had a 14-gate validation concept:

1. installer transaction/idempotence/rollback,
2. legacy baseline→centralized `mb_bak`,
3. PREARM state machine,
4. START recovery coordinator,
5. Eddy terminal lifecycle cleanup,
6. EN/CN public interface registry,
7. backend safety invariants,
8. Python 3.9 grammar/compile,
9. docs/installer contract,
10. FS1.1 status regression,
11. first-takeover + factory mirror provenance,
12. Hardware Cooling ownership,
13. RC5 cross-feature fallback/restore,
14. cfg comment vs real unknown-key parser regression.

For the **current exact combined RS1+GR1 candidate**, the new GitHub Actions static/mock/installer-transform gates passed, but the full real `sovol-home-current.tar.gz` simulation:

`dry-run → apply → second apply 0 writes → Full Restore → exact compare`

was **not rerun locally on the exact combined candidate** because local code tools failed with `ClientError`.

This gap must remain explicit. Do not falsely mark all 14 historical gates as rerun on the combined candidate.

---

## 13. Installation on the real machine — 2026-09-08

User installed from directory similar to:

`~/rc5_candidate_clean`

Initial dry run:

```text
M_Bamboo_SV08Max_Mods 1.0.0-rc5-dev INSTALL feature=all
Persistent cfg backups: NONE
Backend original backup: /home/sovol/klipper/klippy/extras/mb_bak (one directory, never overwritten)
Planned writes: 2; deletes: 0
DRY RUN ONLY.
```

Raw diff showed exactly two writes:

1. `Macro.cfg`
   - managed START_PRINT core version marker changed `RC5-SR1` → `RC5-SR1-GR1`,
   - execution body otherwise unchanged.

2. `probe_eddy_current.py`
   - RS1 rapid-scan callback/session lifetime guard,
   - GR1 `MBambooRecoverySupervisor` class and registration.

No unexpected edits to printer.cfg, buffer stepper config, other backend files, etc.

After apply/runtime restart:

`M_BAMBOO_RECOVERY_STATUS` reported:

- Version RC5-GR1,
- Ready True,
- Active False,
- wrapped commands exactly the six listed above.

`M_BAMBOO_EDDY_STATUS` initially reported:

- Safety `ES-R4-EC2-FS1.1`,
- State HEALTHY,
- transport state HEALTHY,
- fault seq 0/0,
- Z recovery required No,
- restart required No.

---

## 14. Real-hardware healthy-path evidence after RS1+GR1 install

### G28 / Safe Home

Passed repeatedly.

Typical slow/final homing triggers around:

- 3.489,
- 3.491,
- 3.493 mm.

The second/slow homing trigger is notably repeatable across many runs, generally within a few microns in the observed session.

### Direct rapid scan baseline

Command used:

`BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=1 METHOD=rapid_scan`

Multiple direct rapid scans completed successfully.

Observed examples:

- ~76.512 s SUCCESS,
- ~77.821 s SUCCESS,
- additional successful direct runs later.

No new fault sequence, no shutdown, no stale callback crash.

### QGL healthy runs

Examples:

One QGL:

- four non-contact points around 3.585/3.585/3.567/3.575,
- probed range `0.018760`, tolerance `0.100000`, retries 0/5.

Later very flat QGL:

- range `0.003610` mm,
- tiny actuator corrections.

Another later QGL:

- range `0.010339` mm.

### Full `BED_MESH_CALIBRATE`

Multiple full flows completed successfully, including:

- Safe Home / homing,
- contact Z verification,
- non-contact Eddy calibration around 1241–1244 queries,
- rapid scan,
- mesh completion.

Observed Eddy calibration stddev examples:

- 620.835 in 1241 queries,
- 632.388 in 1241 queries,
- 640.405 in 1244 queries.

These were in the same broad scale as prior healthy results; no evidence that RS1 itself worsened healthy-path Eddy measurement noise.

Healthy-path conclusion:

There is currently no strong evidence that RS1/GR1 degrades rapid-scan accuracy or healthy-path stability.

---

## 15. Real-hardware GR1 natural raw34 automatic recovery — major PASS

Date/session: 2026-09-08 around 17:39 local test time.

Command owner:

`QUAD_GANTRY_LEVEL`

First QGL attempt:

- points 1–3 passed,
- fourth point transaction `#0050` started at `(490,30,15)` targeting bounded Z=1.5,
- after only ~0.001 mm descent, a natural transport fault occurred:

`I2C_BUS_NACK|I2C_BUS_BUSY raw=34 seq=1`

Safety behavior:

- active trsync sensor-error stop requested,
- transaction failed and was invalidated,
- Z homing state invalidated (`xyz -> xy`),
- transport state moved to TRANSPORT_FAULT,
- current QGL attempt was not allowed to continue with a partial point set.

GR1 then automatically performed:

1. no-motion transport recovery check,
2. three LDC identity reads, all:
   `5449/3055`,
3. recovery result:
   transport recovered, fault seq remained 1,
4. Z remained explicitly UNTRUSTED,
5. armed fresh Safe Home Z recovery,
6. homing transaction `#0051` succeeded,
7. `ARMED RECOVERY SUCCESS` reported:
   transport HEALTHY and Z trust re-established,
8. GR1 reported:
   `recovered transport for QUAD_GANTRY_LEVEL; replaying the whole operation once.`,
9. **whole QGL replayed from point 1**, not just failed point 4,
10. replay points `#0053`–`#0056` all succeeded,
11. final QGL completed with range `0.036137`, retries 0/5,
12. GR1 reported:
   `QUAD_GANTRY_LEVEL completed successfully after one automatic recovery.`

No firmware restart.

No manual `M_BAMBOO_EDDY_RECOVERY_CHECK`.

No Klipper shutdown.

Post-event status later confirmed:

- State HEALTHY,
- fault latched No,
- first fault recorded as `HARD_COMM_FAULT (I2C_BUS_NACK|I2C_BUS_BUSY raw=34 seq=1)`,
- handled/current fault seq `1/1`,
- transport trust watermark/current `1/1`,
- transport state HEALTHY,
- Z recovery required No,
- transport faults this session 1,
- forced LDC stream quarantines 1,
- context `QUAD_GANTRY_LEVEL_BASE=1`,
- recovery checks `1/1 passed`,
- armed recovery successes 1,
- restart required No,
- recovered operations this Klipper session 1.

This is currently the strongest real-hardware validation of GR1.

Official engineering verdict for this event:

- natural raw34 capture: PASS,
- fault detection: PASS,
- active operation abort: PASS,
- partial QGL rejection: PASS,
- Z invalidation: PASS,
- no-motion identity recovery: PASS,
- 3× identity verification: PASS,
- fresh Safe Home recovery: PASS,
- Z trust reconstruction: PASS,
- whole-operation replay: PASS,
- replay completion: PASS,
- no second fault: PASS,
- no firmware restart: PASS,
- no Klipper shutdown: PASS,
- no manual intervention: PASS.

### Historical LDC telemetry after recovery

After the event, later successful transactions continued to print fields such as:

`ldc=err_code=34 i2c_report_seen=True ...`

This is historical last-error telemetry, not proof that each later transaction faulted. Current state must be read from transport state/fault-seq/transaction result. Status text already labels this field as historical. Future console wording could be improved (e.g. `historical_ldc_err=34`) to reduce confusion, but this is not a blocker.

---

## 16. Z_OFFSET_CALIBRATION legacy repeatability issue — ZCAL-R1 finding

A separate issue was observed:

`ZoffsetCalibration: Toolhead probe more than ten times.`

This is **not** an RS1/GR1 transport fault in the captured case.

During the failing run:

- all PREARM checks were READY,
- fault seq stayed 0,
- all contact transactions were SUCCESS,
- `err_code=0` for the actual failure period,
- transport state remained HEALTHY.

The failure comes from the Z-offset calibration's own convergence algorithm.

Current logic concept:

```python
diff_z = abs(zendstop_p1[2] - zendstop_p[2])
zendstop_p = zendstop_p1
if diff_z <= 0.02:
    success
```

Reprobe counter begins at 1 and errors when `reprobe_cnt >= 10`, before verification #10. Therefore the actual maximum is:

- 1 initial contact,
- verification #1 through #9,
- total 10 contacts.

The message “more than ten times” is therefore misleading/off-by-one in wording.

### Captured failing contact sequence

Initial:

`-0.141250`

Verification samples:

1. `-0.115000` delta 0.026250
2. `-0.085000` delta 0.030000
3. `-0.145000` delta 0.060000
4. `-0.092500` delta 0.052500
5. `-0.116875` delta 0.024375
6. `-0.139375` delta 0.022500
7. `-0.086875` delta 0.052500
8. `-0.165625` delta 0.078750
9. `-0.075625` delta 0.090000

Closest pairwise delta was 0.0225 mm, only 2.5 µm above the hard 0.0200 mm threshold, but no adjacent pair passed.

Approximate distribution across 10 contacts:

- mean around `-0.1163` mm,
- median around `-0.1159` mm,
- range ~`0.0900` mm,
- MAD on the order of `0.023` mm.

### Engineering interpretation

The legacy criterion asks:

> are any two *consecutive* samples within 20 µm?

It does **not** robustly ask:

> is the sample population repeatable/stable?

This means it can:

- fail a centered but noisy cluster because adjacent values never happen to be close enough,
- or pass two coincident outliers even if the overall series is unstable.

This is statistically fragile.

However, do **not** simply relax `0.02` to `0.03` or `0.10`. The observed 90 µm range is large enough that mechanical/contact repeatability is also a real concern.

Potential future ZCAL-R1 concept, if evidence justifies changing code:

- collect at least 3 samples,
- use median/robust center,
- evaluate inlier count and/or MAD/range,
- maintain a hard instability ceiling,
- do not accept on a lucky pair alone.

But on 2026-09-08 the user explicitly preferred **not** to add compensation/new complexity if an existing `G28` in START_PRINT can solve the practical reference issue. Therefore do not rush a ZCAL algorithm rewrite. Continue evidence collection first.

### Potential physical contributors

Current hypothesis ranking for the contact spread includes:

- nozzle/contact residue,
- Eddy PCB/probe mounting tilt or small mechanical compliance,
- thermal/contact hysteresis,
- virtual-contact threshold behavior,
- gantry/frame compliance,
- transport/I2C for the captured ZCAL failure: very low.

Drive current `reg_drive_current: 15` was repeatedly observed and is not itself suspicious in this session.

### Randomized calibration XY

Current `z_offset_calibration.py` initializes calibration positions using random ±10 mm offsets from configured base XY values. This means different Klipper sessions can calibrate at different nearby XY positions. Therefore cross-session absolute contact-Z comparisons must not be interpreted entirely as sensor drift.

Within one calibration run, repeated verification contacts remain at the same chosen XY, so this randomization does not explain the within-run 90 µm spread.

---

## 17. QGL / BED_MESH / Z-reference drift investigation

User raised an important practical observation:

1. In previous cases where Z-offset appeared wrong, running another G28 after bed mesh made the newly probed Z appear correct.
2. Asked whether QGL may be followed by sag/settling, whether Z motors unlock during bed mesh, and whether direct bed-mesh leveling could cause the Z problem.

### Motor-disable finding

No evidence was found in the tested QGL→mesh flow of Z motors being explicitly disabled via `M18`, `M84`, `SET_STEPPER_ENABLE ... ENABLE=0`, etc.

Therefore the working hypothesis should **not** be “Z motors unlock and the gantry freely falls”.

If there is a mechanical effect, describe it more carefully as possible:

- load redistribution,
- belt/frame/gantry compliance,
- leadscrew/coupler/bearing elasticity,
- large-area XY workload settling,
- micro-scale mechanical reference shift while steppers remain energized.

### Why `G28 Z` remains meaningful

`G28 Z` re-establishes an actual Eddy Z-home trigger and resets the trusted trigger reference. It is a direct physical re-measurement, not a software-estimated compensation.

User's design preference is important:

> if an existing simple `G28` in START_PRINT solves the practical issue, prefer that over adding a new compensation algorithm.

Do not simplify/rewrite START_PRINT right now. The user explicitly said the current START_PRINT is already sufficiently simple.

### Fixed-XY drift experiment — first version

Initial A–E test at X271/Y251 produced:

- A after G28: `-0.182500`
- B after QGL before re-G28: `-0.201088`
- C after QGL + G28 Z: `-0.182500`
- D after rapid mesh before re-G28: `-0.195625`
- E after rapid mesh + G28 Z: `-0.178750`

At first glance:

- QGL shift ~ -18.6 µm,
- G28 appeared to restore exactly,
- mesh shift ~ -13.1 µm,
- final E within +3.75 µm of original A.

However, the first experiment had a methodological flaw: after `BED_MESH_CALIBRATE_BASE`, the new mesh is active and changes the Z coordinate transform. Therefore D−C cannot be interpreted purely as physical sag/drift.

### Corrected experiment with `BED_MESH_CLEAR`

Second test explicitly cleared mesh before baseline and after rapid scan.

Captured fixed XY values:

- A1 — `BED_MESH_CLEAR → G28` then contact:
  `-0.212500`
- B1 — after QGL, no G28:
  `-0.202317`
- C1 — after QGL + `G28 Z`:
  `-0.167500`
- D1 — after rapid mesh, then `BED_MESH_CLEAR`, no G28:
  `-0.184375`
- E1 — after another `G28 Z`:
  `-0.180625`

Differences:

- B1−A1 = +0.010183 mm (~+10.2 µm)
- C1−B1 = +0.034817 mm (~+34.8 µm)
- D1−C1 = -0.016875 mm (~-16.9 µm)
- E1−D1 = +0.003750 mm (~+3.75 µm)
- E1−A1 = +0.031875 mm (~+31.9 µm)

### Updated verdict

The corrected experiment **did not reproduce** the clean “G28 restores exactly to pre-QGL reference” behavior from the first run.

This substantially weakens the claim that QGL/rapid mesh causes a deterministic Z-reference drift that G28 predictably removes.

More importantly, the measurement instrument used for the experiment — `RUN_PROBE_VIR_CONTACT` — has already shown single-run spread up to ~90 µm. Trying to infer 10–20 µm mechanical drift using a contact measurement with tens-of-microns repeatability is methodologically weak.

A stronger observation is that Eddy Z homing itself is much more repeatable in the same session. Examples of final/slow homing results clustered around:

- 3.489,
- 3.489,
- 3.491,
- 3.493 mm.

This suggests:

- Eddy non-contact Z-home reference is currently very repeatable,
- virtual-contact probe is much noisier.

Therefore a better current model is:

```text
Eddy G28 Z reference
→ highly repeatable

virtual-contact / ZCAL
→ noticeably noisier
→ legacy pairwise convergence may accept a lucky pair or fail a centered noisy series
```

The user's historical observation that a new G28 “makes Z correct again” may therefore reflect re-establishing a highly repeatable Eddy reference after a noisier contact-derived operation, rather than deterministic gantry sag.

### Do not overreact

Current evidence ranking:

- Eddy G28 repeatability: VERY GOOD
- QGL-induced local geometric shift: SMALL / PLAUSIBLE (~10 µm scale)
- rapid-mesh mechanical sag: NOT PROVEN
- virtual-contact repeatability: CLEAR CONCERN
- legacy ZCAL convergence criterion: CLEAR DESIGN WEAKNESS

Do not add a new compensation layer now.

Do not remove existing START_PRINT stages now.

Continue using direct physical re-measurement (`G28 Z`) where already designed.

---

## 18. Current START_PRINT policy after latest discussion

User explicitly said:

> “暂时不要简化start_print，就当前这样已经非常简化了我觉得”

Binding engineering consequence:

- **Do not simplify START_PRINT now.**
- Keep current PRE_ZCAL → QGL → G28 Z → BED_MESH → POST_ZCAL structure.
- Do not replace POST_ZCAL with another G28 based only on current hypothesis.
- Do not introduce new compensation logic without stronger evidence.
- Prefer evidence collection over architecture churn.

---

## 19. Current RC5 hardware validation verdict

### Strongly passed

- runtime registration,
- Safe Home/G28 healthy path,
- PREARM healthy path,
- QGL healthy path,
- direct rapid-scan healthy path,
- full BED_MESH healthy path,
- RS1 stale-callback shutdown mechanism no longer reproduced on healthy scans,
- one natural raw34 real-hardware GR1 automatic recovery through full operation replay,
- no manual recovery required for that event,
- no firmware restart required,
- no Klipper shutdown during recovered QGL fault.

### Still pending / not yet proven

- long-duration natural-fault soak,
- multiple independent naturally occurring GR1 recoveries across contexts,
- real active rapid-scan raw34 under RS1 followed by GR1 recovery/replay,
- second-fault-on-replay hardware path,
- recovery-failure hardware path,
- long-term confidence before stable promotion,
- exact combined candidate full 14-gate home-archive simulation in a working local execution environment,
- whether ZCAL legacy convergence should be changed at all,
- whether any measurable QGL/mesh mechanical settling remains once measured with a sufficiently precise non-contact method.

---

## 20. Recommended next test campaign

Do not modify START_PRINT or ZCAL yet.

### A. Continue ordinary healthy soak

Run normal:

- G28,
- QGL,
- direct rapid scan,
- full BED_MESH_CALIBRATE,
- START_PRINT real jobs.

Capture naturally occurring raw34/raw36 rather than electrically inducing faults.

### B. Natural recovery evidence

When a natural fault occurs:

- do not immediately run manual recovery,
- allow current outer owner to handle it,
- capture complete console/log,
- then run:
  - `M_BAMBOO_EDDY_STATUS`
  - `M_BAMBOO_RECOVERY_STATUS`

Important desired future evidence:

1. natural BED_MESH fault → automatic recovery → whole BED_MESH replay,
2. natural START_PRINT stage fault → START remains outer owner,
3. natural rapid-scan active fault under RS1 → no flush-handler shutdown,
4. if replay gets a second new Eddy fault → automatic recovery stops fail-closed.

### C. ZCAL evidence collection

If `Toolhead probe more than ten times` recurs, save the entire contact series.

Useful per-run data:

- calibration XY,
- initial contact Z,
- each verification Z,
- each adjacent delta,
- success probe index or failure,
- temperatures,
- nozzle cleanliness state,
- whether any I2C fault marker advanced.

Do not change the 0.02 threshold yet.

### D. Z-reference mechanics

If investigating QGL/mesh mechanical drift further, do **not** use single `RUN_PROBE_VIR_CONTACT` values as a precision drift meter.

Prefer a non-contact measurement method with repeatability near the Eddy homing trigger scale and one that does not redefine the coordinate system. Any new diagnostic helper should be instrumentation-only, not compensation logic, and should not disturb production START_PRINT.

---

## 21. Commands useful in the new conversation

Status:

```gcode
M_BAMBOO_EDDY_STATUS
M_BAMBOO_RECOVERY_STATUS
```

Healthy direct rapid scan:

```gcode
BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=1 METHOD=rapid_scan
```

Full wrapped mesh:

```gcode
BED_MESH_CALIBRATE
```

QGL:

```gcode
QUAD_GANTRY_LEVEL
```

Z home:

```gcode
G28 Z
```

Contact probe:

```gcode
RUN_PROBE_VIR_CONTACT
```

Clear active mesh when isolating coordinate-transform effects:

```gcode
BED_MESH_CLEAR
```

Manual recovery command exists but should not be reflexively used during a GR1 outer-owner test:

```gcode
M_BAMBOO_EDDY_RECOVERY_CHECK
```

Use manual recovery only when the automatic owner is not expected/eligible or the workflow has already terminated and the engineering goal is specifically manual recovery validation.

---

## 22. Important source/repo files for continuation

Repository: `kuratsunade/M_Bamboo_SV08Max_Mods`

Branch: `rc5-dev`

Critical runtime/source:

- `backend/probe_eddy_current.py`
- `backend/ldc1612.py`
- `backend/probe.py`
- `backend/M_Bamboo_Safe_Homing.py`
- `backend/z_offset_calibration.py`

Critical START/config:

- `release/config/start_print_core.block`
- relevant managed config blocks under `release/config/`

Critical installer/release:

- `install.sh`
- `installer_manifest.json`

Critical RS1/materialization:

- `patches/10_rc5_rs1_rapid_scan_lifecycle_guard.patch`
- patch 09 hardware-candidate alignment file in the same chain,
- `tools/rc5_finalize_dev_candidate.py`
- `tools/test_rc5_combined_runtime.py`
- `.github/workflows/rc5-materialize-combined-runtime.yml`
- `.github/workflows/rc5-finalize-dev-candidate.yml`
- `.github/workflows/rc5-combined-validation.yml`

Identity doc:

- `docs/RC5_DEV_COMBINED_RUNTIME_IDENTITY.md`

This handoff:

- `docs/RC5_ENGINEERING_HANDOFF_2026-09-08.md`

---

## 23. Important local/uploaded artifacts and logs

Known uploaded / project files useful to carry into a new conversation:

- `/mnt/data/home.zip`
- `/mnt/data/sovol-home-current.tar.gz`
- `/mnt/data/M_Bamboo_SV08Max_Mods_RC4_Integration_Handoff(3).md`
- `/mnt/data/klippy_2026_08_14_err_36.log`
- `/mnt/data/M_Bamboo_SV08Max_Mods_RC5_RS1_GR1_dev_candidate.zip`
  (GitHub Actions artifact wrapper; inner candidate not locally verified due tool failure)

Recent 2026-09-08 conversation evidence files, when available in the chat/file system, include pasted-console captures for:

- installer raw diff,
- repeated rapid scans/QGL,
- ZCAL 10-probe failure,
- natural raw34 + GR1 automatic QGL recovery,
- fixed-XY Z-reference experiments.

When starting the new conversation, upload or attach this handoff plus the latest console capture(s) if the new session does not automatically inherit project files.

---

## 24. Communication / engineering style constraints

The user expects:

- Chinese-first engineering discussion,
- English terms retained where code/technical exactness benefits,
- concise but rigorous analysis,
- critical thinking rather than agreement,
- exact hashes/files/commands when available,
- explicit distinction between proven, plausible, and unproven,
- no overclaiming a “fix” before hardware evidence,
- no arbitrary sleeps/timing tweaks without evidence,
- no silent simplification of PREARM or START_PRINT,
- no MCU modification.

When reporting RC5 status, use language such as:

- RS1 removes the exact known stale rapid-callback shutdown mechanism while preserving healthy scan semantics,
- GR1 implements bounded automatic recovery/replay for the currently supported public commands at the outer synchronous owner boundary,
- hardware validation is strong but not yet equivalent to stable-release qualification.

Do **not** claim:

- generic recovery for commands outside the implemented six,
- `dcb78d...` is public release lineage,
- all historical 14 gates reran on the current combined package,
- rapid scan raw34 frequency was proven to increase under RC5,
- QGL/mesh mechanical sag is proven,
- ZCAL failure is an I2C fault when the marker/telemetry says otherwise.

---

## 25. Immediate continuation prompt for a new conversation

Suggested opening prompt:

> Continue the Sovol SV08 Max `M_Bamboo_SV08Max_Mods` RC5 engineering work from `docs/RC5_ENGINEERING_HANDOFF_2026-09-08.md`. Treat the handoff constraints as binding. Current branch is `rc5-dev`; current combined runtime is RS1+GR1 with `probe_eddy_current.py` SHA256 `5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29`. A natural raw34 fault during QGL has already been automatically recovered end-to-end on real hardware without firmware restart or Klipper shutdown. Do not simplify START_PRINT or change ZCAL yet. First review the latest hardware evidence and continue the evidence-driven validation plan.

---

## 26. Bottom-line engineering snapshot

The project has moved from “detect Eddy transport faults and fail closed” toward a complete host-side recoverable transport architecture:

```text
PREARM / detection
→ invalidate failed work
→ quarantine/terminalize lifecycle
→ no-motion transport identity recovery
→ preserve distinction between transport trust and Z trust
→ fresh Safe Home when required
→ replay whole atomic operation at one outer owner
→ continue only after clean completion
→ fail closed on repeated/recovery failure
```

The strongest new evidence from this conversation is that this architecture has now survived a **real natural raw34 QGL fault on hardware** exactly as intended.

The next major engineering question is no longer “does GR1 fundamentally work?” — one real event says yes. The focus should now be:

- broader natural fault coverage,
- long-term field confidence,
- active rapid-scan fault behavior under RS1,
- and careful characterization of virtual-contact/ZCAL repeatability without destabilizing an already functional START_PRINT pipeline.
