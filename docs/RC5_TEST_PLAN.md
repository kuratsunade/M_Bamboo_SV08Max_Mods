# RC5 test plan

Updated 2026-09-09. [中文](RC5_TEST_PLAN_CN.md) | [Evidence and release blockers](RC5_TEST_EVIDENCE.md)

## What needs testing now

Do not reinstall a working combined candidate merely to repeat registration or isolated healthy G28 tests. At the beginning of the next session capture:

```gcode
M_BAMBOO_EDDY_STATUS
M_BAMBOO_RECOVERY_STATUS
```

Record the installed backend SHA256, temperatures, filament, job identifier and session start time. GR1 should be ready and list its six wrapped commands. A runtime safety label alone cannot distinguish RC4 from the combined candidate.

| Priority | Printer work | Acceptance / evidence |
| --- | --- | --- |
| 1 | Normal slicer START_PRINT and real prints, including naturally occurring cold and warm starts | Complete start, first layer, END_PRINT and a subsequent start. Capture full logs and first layer observations. Check no stale calibration flag, unexpected velocity setting, lost Z trust or repeated recovery. Record all failures, not only completed jobs. |
| 2 | Full BED_MESH_CALIBRATE during normal preparation | Entire wrapper completes. If a natural fault occurs, record its actual stage: calibration, homing and active rapid scan are different contexts. |
| 3 | Natural fault during active rapid scan | Failed/partial mesh rejected, queued callback causes no flush shutdown, transport validated, fresh Safe Home if needed, whole owned operation replayed once and clean completion. This gate is still open. |
| 4 | Natural START_PRINT stage fault | MBSTART remains outer owner; nested GR1 does not run duplicate recovery. Whole failed stage restarts. At most one recovery for a stage invocation and three independent episodes per START. Another fault before stage completion or recovery failure terminates. |
| 5 | ZCAL convergence failure or inconsistent first layer | Save every contact Z and adjacent delta, initial contact, chosen XY, temperatures, nozzle condition, probe count and fault markers. Do not merely widen the tolerance or substitute a single contact as a precision drift meter. |

Use normal jobs for coverage. There is no evidence based fixed print count that proves stability; review accumulated exposure, failures and represented contexts. Already demonstrated: one QGL raw34 recovery and multiple healthy mesh flows. Do not repeat those alone as a substitute for the missing scan/START fault contexts.

## When a natural fault occurs

Let the current outer owner finish or terminate. Do not insert manual recovery while automatic recovery is active. After completion or terminal failure, capture both status commands and the complete console plus klippy.log covering before the fault through the final outcome. Capture raw code, fault sequence, failed transaction, owner/stage, quarantine, identity reads, Z trust, replay start and final result. A terminal/repeated fault or recovery failure ends that test; follow the reported restart requirement rather than issuing repeated bed facing commands. No intentional wiring faults, forced Z invalidation or bed contact experiments.

Direct `BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=1 METHOD=rapid_scan` is a healthy scan diagnostic. The BASE command is not one of GR1's six public owners, so do not expect standalone GR1 replay for it. Prefer public `BED_MESH_CALIBRATE` to test whole operation recovery.

The RC4 public Soak toolkit remains RC4 hash gated. Do not bypass its preflight or call it RC5 qualified. Manual recovery wrappers can interfere with automatic owner evidence.

## Maintainer offline work before release

1. Fix and verify recognized stock START_PRINT installation while preserving refusal of unknown edits. Recheck the earlier machine snapshot separately; it is not the present machine state.
2. Fix and verify inverse restoration of CONFIG_START_PRINT_CORE, including removal of runtime dependencies after backend restore. Cover full and feature scoped restore and fallback combinations.
3. Rerun dry run, apply, second apply zero writes, failure rollback, Full Restore and exact backend / semantic config / SAVE_CONFIG preservation checks on the combined candidate. Do not weaken an old gate to obtain PASS.
4. Retain mocks for second fault on replay, failed recovery, delayed callbacks and ownership. Hardware counterparts remain pending unless naturally observed.
5. Reconcile the historical offline runner with RC5 contracts before claiming all historical gates passed. Validate separate GitHub and Gitee packages only at release, with identical core payload and validation state.

Runtime, PREARM, START_PRINT sequence, healthy rapid scan measurement and ZCAL threshold remain unchanged by this documentation update.
