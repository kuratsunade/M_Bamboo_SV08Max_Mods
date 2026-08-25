# M_Bamboo EAR Public Test Toolkit v0.1.0

面向 **M_Bamboo_SV08Max_Mods v1.0.0-rc4** 的公开 Eddy 通信测试工具。

## 范围

这个公开版只保留 EAR / R3E / R3F 调查过程中真正有价值、又不需要 engineering backend 的部分：

- RC4 backend SHA256 预检
- 可重复的 contact-probe churn matrix
- 可配置 burst / dwell / pass 数量
- 测试前后的 `M_BAMBOO_EDDY_STATUS`
- 时间戳化 `klippy.log` / Moonraker log 导出
- 调用 RC4 自带 recovery check 的辅助脚本
- 可安全卸载 tester 本身

## 硬性边界

**本工具不会安装、覆盖、patch 或删除 `/home/sovol/klipper/klippy/extras/` 下任何 Python 文件。**

特别包括：

- `probe_eddy_current.py`
- `ldc1612.py`
- `probe.py`
- `homing.py`
- `z_offset_calibration.py`
- `M_Bamboo_Safe_Homing.py`

这些文件必须保持用户所安装 RC branch 的原样。

## RC4 参考 hash

```text
ldc1612.py             aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04
probe_eddy_current.py  6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e
```

默认 preflight 是 fail-closed：hash 不一致时不会继续运行参考测试。

## 安装

```bash
cd tools/eddy_comm_test
chmod +x *.sh
./install_toolkit.sh
```

仅复制到：

```text
/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit
```

因为不修改 Python backend，所以不需要为安装 tester 重启 Klipper。

## 运行参考 matrix

```bash
./run_matrix.sh
```

默认：

- BURST=8
- dwell = 0 / 10 / 25 / 50 / 75 / 100 ms
- 每个 cell 目标 5 次完整 PASS

可覆盖：

```bash
BURST=8 PASSES_PER_CELL=5 DWELLS_MS="0 10 25 50 75 100" ./run_matrix.sh
```

### Safety 行为

工具不会绕过 RC4 Eddy Safety，也不会 retry 失败的 contact transaction。一旦 Moonraker 返回 command failure，当前 matrix 停止，交给用户检查。

通信 fault 后请以 RC4 `M_BAMBOO_EDDY_STATUS` 给出的 guidance 为准，不提供 force-clear。

## 导出证据

```bash
./collect_logs.sh
```

会生成包含以下内容的 tar.gz：

- backend SHA256
- tester VERSION
- `klippy.log`
- Moonraker log（存在时）
- tester result log

只读收集，不修改 Klipper。

## Recovery helper

```bash
./recovery_check.sh
```

它只调用 RC4 已有的：

```gcode
M_BAMBOO_EDDY_RECOVERY_CHECK
```

不会自行发明新的 recovery policy。

## 卸载

```bash
./remove_toolkit.sh
```

仅删除：

```text
/home/sovol/M_Bamboo_EAR_Public_Test_Toolkit
```

不会触碰 `klippy/extras`。

## 重要解释限制

这里的 `DWELL_MS` 是 Z lift / `M400` 之后额外加入的 nominal dwell，**并不等于完整的 backend `STOP_ACK -> next START` 间隔**。之前 instrumented engineering test 已经证明，实际间隔往往由 Z motion 和命令调度占主导。

因此这个 public matrix 适合：

- 复现通信 fault
- 收集不同机器上的 field evidence
- 比较 fault context / raw error code

不适合单独用于宣称一个精确的 I2C quiescence threshold。

Maintainer: Master_Bamboo / 竹子
