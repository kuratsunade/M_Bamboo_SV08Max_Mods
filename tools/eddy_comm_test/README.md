# M_Bamboo EAR Public Test Toolkit v0.1.0

Public, backend-neutral Eddy communication test toolkit for **M_Bamboo_SV08Max_Mods v1.0.0-rc4**.

## Scope

This package reproduces the useful parts of the EAR/R3E/R3F field-testing workflow without installing engineering Python backends.

It provides:

- RC4 backend SHA256 preflight
- repeatable contact-probe churn matrix runner
- configurable burst / dwell / pass counts
- pre/post `M_BAMBOO_EDDY_STATUS` capture
- timestamped `klippy.log` evidence export
- optional manual recovery helper
- clean uninstall of the tester itself

## Hard boundary

**This toolkit never installs, replaces, patches, or removes any file under `/home/sovol/klipper/klippy/extras/`.**

In particular it does not ship modified copies of:

- `probe_eddy_current.py`
- `ldc1612.py`
- `probe.py`
- `homing.py`
- `z_offset_calibration.py`
- `M_Bamboo_Safe_Homing.py`

Those files must stay exactly on the user's RC branch.

## Supported baseline

Expected RC4 hashes:

```text
ldc1612.py             aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04
probe_eddy_current.py  6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e
```

The preflight script is fail-closed by default if either hash differs. Use a different branch/release only if you understand that the test result is no longer directly comparable with the RC4 reference data.

## Install

```bash
cd tools/eddy_comm_test
chmod +x *.sh
./install_toolkit.sh
```

Installation only copies this tester to:

```text
/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit
```

No Klipper backend restart is required because no Python backend is changed.

## Preflight

```bash
./preflight.sh
```

Expected result:

```text
RC4 backend check: PASS
```

## Run the reference matrix

Default matrix:

- burst = 8 contact probes per attempt
- dwell cells = 0 / 10 / 25 / 50 / 75 / 100 ms
- target = 5 completed attempts per cell

```bash
./run_matrix.sh
```

Optional overrides:

```bash
BURST=8 PASSES_PER_CELL=5 DWELLS_MS="0 10 25 50 75 100" ./run_matrix.sh
```

### Safety behavior

The runner does **not** bypass RC4 safety logic and does **not** retry a failed contact transaction. If Moonraker reports a command failure, the attempt is marked failed and the matrix stops for manual inspection.

After a communication fault, follow the RC4 Eddy Safety guidance shown by `M_BAMBOO_EDDY_STATUS`. Do not force-clear a fault.

## Export evidence

```bash
./collect_logs.sh
```

Exports a timestamped folder containing:

- RC4 backend hashes
- tester version
- `klippy.log`
- Moonraker log if present
- current M_Bamboo tester result file

The collector does not modify Klipper.

## Manual recovery helper

This helper only sends the existing RC4 command:

```bash
./recovery_check.sh
```

It does not implement its own recovery policy. The RC4 `M_BAMBOO_EDDY_RECOVERY_CHECK` / Safe Home logic remains authoritative.

## Remove tester

```bash
./remove_toolkit.sh
```

Removal deletes only `/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit` and never touches `klippy/extras`.

## Interpretation notes

The dwell value in this field test is an extra post-lift dwell. It is **not** the complete backend `STOP_ACK -> next START` interval. Previous instrumented testing showed physical motion and command overhead can dominate the real gap. Therefore do not interpret this matrix as a precise I2C quiescence-threshold measurement.

The toolkit is intended to reproduce fault occurrence and collect comparable field evidence, not to prove a root cause by itself.

## Reporting

Please include:

- printer / firmware baseline
- `preflight.sh` output
- test parameters
- exported evidence folder
- whether the fault context was HOMING, contact probing, idle/pre-arm, or another operation
- raw error code if available

Maintainer: Master_Bamboo / 竹子
