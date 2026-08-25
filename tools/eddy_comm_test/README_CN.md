# M_Bamboo EAR Public Test Toolkit v0.1.1

面向 **M_Bamboo_SV08Max_Mods v1.0.0-rc4** 的公开 Eddy 通信测试工具。

## v0.1.1 修正

v0.1.0 把 tester 过度简化成了 shell 驱动 matrix，误删了原本已经成熟的 `M_Bamboo_Soak` Klipper-side 测试层。v0.1.1 恢复 `M_Bamboo_Soak.cfg` 的 soak / matrix / recovery state machine，同时继续保持 backend-neutral。

## 硬性边界

本工具**不会安装、覆盖、patch 或删除 `/home/sovol/klipper/klippy/extras/` 下任何文件**。

要求 RC4 backend hash：

```text
ldc1612.py             aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04
probe_eddy_current.py  6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e
```

## 恢复的功能

- `M_BAMBOO_SOAK_START`
- `M_BAMBOO_SOAK_STOP`
- `M_BAMBOO_SOAK_STATUS`
- `M_BAMBOO_SOAK_RESET_STATS`
- `M_BAMBOO_CHURN_MATRIX_START`
- `M_BAMBOO_CHURN_MATRIX_STOP`
- soak tester 原有的 RC4 transport evaluation / bounded recovery orchestration
- attempt/cell/stage 统计与 failed-attempt 永久计数

HF1/HF2/HF2.1 的 Python lifecycle logger 不包含在公开版中。旧 `M_BAMBOO_EAR_LOG_*` hook 在 cfg 内以 no-op compatibility macro 保留，实际证据使用 RC4 原生 `klippy.log` / Moonraker log。

## 安装

```bash
chmod +x *.sh
./install_toolkit.sh
```

installer 会：

1. fail-closed 检查 RC4 backend hash；
2. 安装 `M_Bamboo_Soak.cfg` 到 `printer_data/config`；
3. 在 `printer.cfg` 中加入 marker-managed `[include M_Bamboo_Soak.cfg]`；
4. 安装 shell helper 到 `/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit`。

然后执行 Klipper `RESTART`。

## 使用

```gcode
M_BAMBOO_CHURN_MATRIX_START PASSES_PER_CELL=5
```

状态：

```gcode
M_BAMBOO_SOAK_STATUS
M_BAMBOO_EDDY_STATUS
```

停止：

```gcode
M_BAMBOO_CHURN_MATRIX_STOP
```

也可以用 `./run_matrix.sh` 作为启动 wrapper。

失败 transaction 永远不会被 tester retry，最终 safety decision 仍以 RC4 Eddy Safety 为准。

## 导出

```bash
./collect_logs.sh
```

会导出 RC4 `klippy.log`、Moonraker log、backend hash、tester VERSION 与当前 soak cfg。

## 卸载

```bash
./remove_toolkit.sh
```

只删除 public tester 的 marker include、`M_Bamboo_Soak.cfg` 和 tester 目录，不触碰 `klippy/extras`。之后执行 Klipper `RESTART`。

## 解释限制

matrix 的 dwell 仍是 Z lift / `M400` 后的 nominal dwell，不等于精确 `STOP_ACK -> next START`。它适合复现 fault 和收集 field evidence，不适合单独证明精确 I2C timing threshold。

Maintainer: Master_Bamboo / 竹子
