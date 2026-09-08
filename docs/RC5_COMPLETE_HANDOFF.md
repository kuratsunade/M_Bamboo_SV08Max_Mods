# M_Bamboo_SV08Max_Mods — RC5 Complete Development Handoff

Date: 2026-09-08  
Branch: `rc5-dev`  
Status: **DEVELOPMENT CANDIDATE — NOT PUBLIC RELEASE**

## Frozen baseline

- Public baseline remains `v1.0.0-rc4`.
- Runtime Safety remains `ES-R4-EC2-FS1.1`.
- RC5 remains one development branch: `rc5-dev`.
- No MCU firmware modification, recompilation, bootloader work, flashing, or extra-MCU replacement is in scope.

## Runtime identities

- RC4 `ldc1612.py` SHA256: `aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04`
- RC4 `probe_eddy_current.py` SHA256: `6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e`
- Hardware-tested pre-RS1/GR1 candidate `probe_eddy_current.py`: `dcb78d4d7d5108236eca23a225e6e582e1b128419bf10c8a5b83cf8de346ced0`
- Current RS1+GR1 combined runtime `probe_eddy_current.py`: `5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29`

## RC5-RS1 — Rapid Scan Compatibility / Safety Restoration

Healthy rapid-scan measurement semantics remain intentionally unchanged:

- no `SAMPLE_TIME` changes;
- no rapid-scan speed changes;
- no scan height/path changes;
- no lookahead timestamp changes;
- no sample-window changes;
- no mesh interpolation changes;
- no LDC sample/query-rate changes.

The stale queued rapid-scan lookahead callback fault is contained by explicit session lifetime handling. A retired session causes a queued callback to no-op instead of dereferencing a released gather object from toolhead flush context. Faulted/partial mesh is never accepted.

## RC5-GR1 — Generic bounded recovery

Supported public commands:

- `G28`
- `RUN_PROBE_VIR_CONTACT`
- `CLEAN_NOZZLE`
- `Z_OFFSET_CALIBRATION`
- `QUAD_GANTRY_LEVEL`
- `BED_MESH_CALIBRATE`

Recovery policy:

- synchronous outer owner only;
- START_PRINT remains the recovery owner while its coordinator is active;
- new recovery evidence uses `transport_fault_seq` and `preflight_failed_count`;
- recovery starts only after the failed operation has terminalized and motion is quiescent;
- perform a no-motion LDC identity recovery check;
- rebuild Z trust with a fresh Safe Home when required;
- replay the entire failed atomic operation once;
- a second Eddy/PREARM fault before clean completion is terminal;
- never launch workflow recovery from async I2C, lookahead, bulk, or toolhead-flush callbacks.

## Real-hardware validation — 2026-09-08

### Healthy path

- Runtime registration: PASS.
- G28 / Safe Home: PASS.
- QGL: PASS.
- Multiple consecutive direct rapid scans: PASS.
- Full `BED_MESH_CALIBRATE` heavy chain: PASS.
- No evidence that RS1 degrades healthy rapid-scan behavior.

### Natural raw34 recovery

A real `I2C_BUS_NACK|I2C_BUS_BUSY raw=34` occurred during `QUAD_GANTRY_LEVEL_BASE`.

Observed sequence:

1. active probe transaction aborted;
2. partial QGL result rejected;
3. Z trust invalidated;
4. LDC no-motion identity recovery passed 3/3 reads (`5449/3055`);
5. fresh Safe Home rebuilt Z trust;
6. the entire QGL was replayed from the beginning;
7. replayed QGL completed successfully;
8. no manual recovery was required;
9. no firmware restart was required;
10. no Klipper shutdown occurred;
11. `Recovered operations this Klipper session` incremented to 1.

**Verdict: GR1 natural raw34 hardware recovery = PASS.**

## Z offset / virtual-contact finding

Observed error:

`ZoffsetCalibration: Toolhead probe more than ten times.`

This was not an I2C transport failure:

- PREARM remained READY;
- `fault_seq` did not advance;
- contact transactions themselves returned SUCCESS.

Current legacy convergence logic:

- initial contact + up to 9 verification contacts;
- every new trigger is compared only with the immediately previous trigger;
- success if `abs(delta_z) <= 0.020 mm`;
- abort when `reprobe_cnt >= 10`.

The pairwise rule is statistically fragile and the wording is effectively off-by-one. No RC5 algorithm change is approved yet. Do not simply widen the `0.020 mm` threshold without evidence.

## START_PRINT — intentionally unchanged

Current structure remains:

```text
PRE_ZCAL
→ QGL
→ G28 Z
→ BED_MESH
→ POST_ZCAL
```

Do not simplify or replace this structure based on the current exploratory Z-reference tests.

## Z-reference investigation

Current evidence:

- Eddy Z homing repeatability appears very good.
- `RUN_PROBE_VIR_CONTACT` has significantly larger single-sample spread.
- QGL may alter local geometry/reference by tens of microns, but current contact-probe noise is of the same order.
- Rapid-mesh mechanical sag has not been established.
- Re-G28 is physically meaningful and repeatable, but no extra drift-compensation code is justified by current evidence.

Current engineering policy: if an existing, physically meaningful `G28 Z` solves a reference problem, prefer that over adding inferred compensation logic. However, START_PRINT is not being simplified at this time.

## Lower-layer I2C conclusions

- `raw34 = NACK|BUSY`.
- `raw36 = TIMEOUT|BUSY`.
- Sovol intentionally chose recoverable I2C behavior rather than fatal MCU shutdown.
- MCU-side handling remains incomplete with respect to strict failed-transaction invalidation and host trust reconstruction.
- M_Bamboo completes containment/recovery at the host layer only.
- No MCU firmware changes are part of this project.

## Critical remaining validation gap

The exact combined RS1+GR1 candidate has passed GitHub Actions static/mock/installer validation and the staged real-hardware tests above.

However, the historical full local simulation:

```text
stock/current tar.gz dry-run
→ apply
→ second apply = 0 writes
→ Full Restore
→ exact compare
```

has **not** been rerun end-to-end on the exact combined candidate because the local execution environment repeatedly returned `ClientError`.

Do **not** claim this gap as passed.

## External evidence not embedded in the repository handoff

The following user-supplied/private artifacts were used during development but are not committed into the repository handoff ZIP:

- `home.zip`
- `sovol-home-current.tar.gz`
- `klippy_2026_08_14_err_36.log`
- prior RC4 integration handoff markdown uploaded in chat
- console/log captures supplied during the 2026-09-08 hardware validation session

They remain external evidence and should not be silently represented as included repository files.

## Next work

1. Preserve current START_PRINT.
2. Continue BED_MESH / START_PRINT soak.
3. Capture naturally occurring raw34/raw36 without artificially inducing bus faults.
4. Continue bounded recovery validation on supported public owners as naturally exercised.
5. Investigate virtual-contact/ZCAL repeatability separately; do not merely widen the legacy 20 µm threshold.
6. Before RC5 release, rerun full install/idempotence/restore/exact-compare simulation.
7. At publish time, generate separate GitHub and Gitee release artifacts with the same core payload/version/validation state.
