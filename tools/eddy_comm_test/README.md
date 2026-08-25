# M_Bamboo EAR Public Test Toolkit v0.1.1

Public RC4-compatible Eddy communication field-test toolkit for **M_Bamboo_SV08Max_Mods v1.0.0-rc4**.

## v0.1.1 correction

v0.1.0 over-simplified the tester into a shell-driven matrix. v0.1.1 restores the established `M_Bamboo_Soak.cfg` Klipper-side soak/matrix/recovery state machine while keeping the public toolkit backend-neutral.

## Hard boundary

This toolkit never installs, replaces, patches, or removes any file under `/home/sovol/klipper/klippy/extras/`.

Expected RC4 hashes:

```text
ldc1612.py             aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04
probe_eddy_current.py  6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e
```

## What is restored

- `M_BAMBOO_SOAK_START`
- `M_BAMBOO_SOAK_STOP`
- `M_BAMBOO_SOAK_STATUS`
- `M_BAMBOO_SOAK_RESET_STATS`
- `M_BAMBOO_CHURN_MATRIX_START`
- `M_BAMBOO_CHURN_MATRIX_STOP`
- existing RC4 transport evaluation / bounded recovery orchestration used by the soak tester
- original soak counters / stage attribution / failed-attempt accounting

HF1/HF2/HF2.1 Python lifecycle logger backends are **not** included. Their old `M_BAMBOO_EAR_LOG_*` hooks are retained as config-only compatibility no-ops; evidence is collected from normal RC4 `klippy.log` and Moonraker logs.

## Install

```bash
chmod +x *.sh
./install_toolkit.sh
```

The installer:

1. fail-closed validates the two RC4 backend hashes;
2. copies `M_Bamboo_Soak.cfg` to `/home/sovol/printer_data/config/`;
3. adds a marker-managed `[include M_Bamboo_Soak.cfg]` block to `printer.cfg`;
4. installs helper scripts to `/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit`.

Then run Klipper `RESTART`.

## Run

From Mainsail:

```gcode
M_BAMBOO_CHURN_MATRIX_START PASSES_PER_CELL=5
```

or:

```bash
./run_matrix.sh
```

Status:

```gcode
M_BAMBOO_SOAK_STATUS
M_BAMBOO_EDDY_STATUS
```

Stop:

```gcode
M_BAMBOO_CHURN_MATRIX_STOP
```

The failed transaction is never retried. RC4 Eddy Safety remains authoritative.

## Evidence

```bash
./collect_logs.sh
```

This exports normal RC4 `klippy.log`, Moonraker log, backend hashes, tester version and the installed soak cfg.

## Remove

```bash
./remove_toolkit.sh
```

Removal only removes the marker-managed include, the public `M_Bamboo_Soak.cfg`, and the tester directory. It never touches `klippy/extras`. Run Klipper `RESTART` afterward.

## Interpretation limitation

The matrix dwell remains a post-lift nominal dwell, not an exact backend `STOP_ACK -> next START` interval. Use the toolkit for fault reproduction and comparable field evidence, not as proof of a precise I2C timing threshold.

Maintainer: Master_Bamboo / 竹子
