# M_Bamboo SV08 Max — 命令与公共接口参考

> **维护者：** Master_Bamboo / 竹子  
> **范围：** 整个 `M_Bamboo_SV08Max_Mods` 项目，而不仅限于 ES-R4。  
> **发布规则：** 本文档是项目的 **authoritative public-interface registry（公共接口权威清单）**。每当 command、macro、参数、兼容别名、诊断接口或 installer-facing interface 新增、修改、弃用或删除时，都必须同步维护。

本文只记录 **M_Bamboo 新增、替换、包装、实质修改，或因为我们替换 backend 而需要明确继承责任的接口**。它不是完整的 Klipper/Sovol G-code 手册复制品。

---

## 0. 状态图例

| 标记 | 含义 |
|---|---|
| **Public / Stable** | 面向普通用户，接口预期长期兼容。 |
| **Public / Soak-test** | 用户可调用，但仍处于实机验证阶段。 |
| **Compatibility ABI** | 触摸屏、Sovol macro、切片器或兼容流程可能依赖，名称/基本行为不可随意修改。 |
| **Advanced / Diagnostic** | 主要用于测试、诊断、校准或高级用户。 |
| **Internal** | 实现细节，不应从用户 macro 直接调用。 |
| **Deprecated** | 暂留一版兼容；新代码不得继续依赖。 |
| **Planned** | 已有设计，但当前 candidate 尚未实现。 |

---

# 1. 总览目录

## 1.1 Public Interface 总览

| 接口 | 类型 | Feature / 归属 | 状态 | 是否运动 | 主要用途 |
|---|---|---|---|---|---|
| [`G28`](#2-g28--安全回零兼容入口) | 替换标准名称的 macro | Safe Home | Compatibility ABI | 是 | 保留触摸屏 `G28`，路由到 Safe Home。 |
| [`M_BAMBOO_HOME_X`](#3-m_bamboo_home_x) | 新增 G-code | Safe Home | Compatibility ABI | 是 | 先建立 clearance，再回零 X。 |
| [`M_BAMBOO_HOME_Y`](#4-m_bamboo_home_y) | 新增 G-code | Safe Home | Compatibility ABI | 是 | 先建立 clearance，再回零 Y。 |
| [`M_BAMBOO_HOME_XY`](#5-m_bamboo_home_xy) | 新增 G-code | Safe Home | Compatibility ABI | 是 | clearance 一次，然后 raw X/Y home。 |
| [`M_BAMBOO_HOME_Z`](#6-m_bamboo_home_z) | 新增 G-code | Safe Home | Compatibility ABI | 是 | XY 横移前 clearance，再真实 Eddy Z home。 |
| [`M_BAMBOO_HOME_ALL`](#7-m_bamboo_home_all) | 新增 G-code | Safe Home | Compatibility ABI | 是 | 原子 clearance → XY → 真实 Z 流程。 |
| [`M_BAMBOO_EDDY_STATUS`](#8-m_bamboo_eddy_status) | 新增 G-code | Eddy Safety | Public / Soak-test | 否 | Eddy safety state + event/fault evidence。 |
| [`M_BAMBOO_EDDY_RECOVERY_CHECK`](#8a-m_bamboo_eddy_recovery_check) | 新增 G-code | Eddy Transport Recovery | Public / Soak-test | 否 | 无运动确认 transport 是否恢复，并在成功时 armed recovery。 |
| [`RUN_PROBE_VIR_CONTACT`](#9-run_probe_vir_contact) | Sovol 原有接口，由 M_Bamboo 防护 | Eddy/contact | Compatibility / Advanced | 是 | Virtual-contact probe。 |
| [`PROBE`](#10-受-m_bamboo-safety-语义影响的标准-probe-command) | 标准 Klipper command，行为受修改 | Eddy Safety | Upstream ABI | 是 | 普通 non-contact probe + M_Bamboo envelope。 |
| [`PROBE_ACCURACY`](#10-受-m_bamboo-safety-语义影响的标准-probe-command) | 标准 Klipper command | Eddy Safety | Upstream ABI | 是 | 重复 probe，同样受 safety policy 保护。 |
| [`PROBE_CALIBRATE`](#10-受-m_bamboo-safety-语义影响的标准-probe-command) | 标准 Klipper command | Eddy backend | Upstream ABI | 是 | 标准 Klipper probe calibration。 |
| [`QUERY_PROBE`](#10-受-m_bamboo-safety-语义影响的标准-probe-command) | 标准 Klipper command | Probe backend | Upstream ABI | 否 | 查询 probe 状态。 |
| [`Z_OFFSET_APPLY_PROBE`](#10-standard-probe-commands-with-m_bamboo-safety-semantics) | Klipper 标准命令、由当前 probe backend 继承 | Probe backend | Upstream ABI | 无轴运动 | 将当前 G-code Z offset 计算进 probe `z_offset` 的待保存配置值。 |
| [`Z_OFFSET_CALIBRATION`](#11-z_offset_calibration) | Sovol command，M_Bamboo 实质修改 | Z Calibration | Public / Soak-test | 是 | M_Bamboo 两阶段安全 Z-offset 流程。 |
| [`CLEAN_NOZZLE`](#12-clean_nozzle) | Sovol macro，由 M_Bamboo 管理/替换 | Nozzle Cleaner NC-R1 | Public / Soak-test | 是 | 单次接触 datum + 随机交叉擦嘴。 |
| [`QUAD_GANTRY_LEVEL`](#13-quad_gantry_level) | 包装标准 Klipper command | Config optimization / Eddy Safety | Compatibility ABI | 是 | 需要时先 home，再执行 base QGL。 |
| [`BED_MESH_CALIBRATE`](#14-bed_mesh_calibrate) | 包装标准 Klipper command | Config optimization / Eddy Safety | Compatibility ABI | 是 | 校准/QGL preflight + adaptive rapid scan。 |
| [`START_PRINT`](#15-start_print) | Sovol slicer macro，M_Bamboo 实质修改 | Print orchestration | Compatibility ABI | 是 | Safe Home / clean / Z-cal / QGL / mesh 总流程。 |
| [`LDC_CALIBRATE_DRIVE_CURRENT`](#16-ldc_calibrate_drive_current) | 原有 LDC 接口，加入 integrity guard | LDC1612 | Advanced / Calibration | 无轴运动 | Drive-current calibration。 |
| [`PROBE_EDDY_CURRENT_CALIBRATE`](#17-probe_eddy_current_calibrate) | 原有 Eddy calibration 接口，由修改 backend 继续暴露 | Eddy calibration | Advanced / Calibration | 是 | 手动重建 Eddy frequency-to-height calibration。 |
| [`EDDY_QUERY_LOOP`](#18-eddy_query_loop) | Sovol 低层诊断接口，由修改 backend 继续暴露 | LDC1612 | Advanced / Diagnostic | 否 | 控制 LDC query loop。 |
| [`XY_STRESS_BASELINE`](#19-xy_stress_baseline) | M_Bamboo diagnostic macro | Diagnostics | RC / Diagnostic | 是 | 记录压力测试前 XY/TMC baseline。 |
| [`XY_STRESS_RUN`](#20-xy_stress_run) | M_Bamboo diagnostic macro | Diagnostics | RC / Diagnostic | 是 | CoreXY 400/15000 压力测试。 |
| [`XY_STRESS_CHECK`](#21-xy_stress_check) | M_Bamboo diagnostic macro | Diagnostics | RC / Diagnostic | 是 | 回零并记录压力测试后 XY/TMC。 |
| [`M_BAMBOO_Z_RELIEF`](#22-m_bamboo_z_relief--计划中) | 计划中的 G-code | Recovery | Planned | 计划仅 +Z | Fault 后机械卸载；当前未实现。 |
| [`./install.sh <feature>`](#23-rc4-release-installer-cli) | Shell installer interface | Installer / Release tooling | RC / Public | N/A | dry-run/apply/status/diff/restore + transaction rollback。 |

## 1.2 Compatibility / Base Alias（通常不要直接调用）

| Alias / base command | 来源 | 用途 |
|---|---|---|
| `M9928` | `G28 rename_existing` | 被 `G28` wrapper 保留的 underlying/raw homing target。 |
| `QUAD_GANTRY_LEVEL_BASE` | `QUAD_GANTRY_LEVEL rename_existing` | wrapper 后面的原始 Klipper QGL。 |
| `BED_MESH_CALIBRATE_BASE` | `BED_MESH_CALIBRATE rename_existing` | wrapper 后面的原始 bed mesh command。 |

> 这些是 **implementation / compatibility target**，不是推荐的普通用户入口。

## 1.3 M_Bamboo 新增或实质修改的参数

| Command / Config | 参数 | 默认 / 范围 | M_Bamboo 语义 |
|---|---|---|---|
| `Z_OFFSET_CALIBRATION` | `USE_CURRENT_Z` | `0`; `0/1` | 保留已经可信的 current Z，不进入 legacy 大 fake-Z acquisition。 |
| `Z_OFFSET_CALIBRATION` | `USE_CURRENT_Z_ALLOWANCE` | `0.0`; `0..5 mm` | 仅第一次 contact 的临时逻辑搜索余量；设置时不移动电机。 |
| `Z_OFFSET_CALIBRATION` | `USE_CURRENT_Z_MAX` | `15.0 mm`; `>0` | `USE_CURRENT_Z` 的 Z 合理性上限。 |
| `Z_OFFSET_CALIBRATION` | `REHOME_XY` | `0`; `0/1` | Post-mesh final calibration 前显式重新定位 XY 机械状态。 |
| `Z_OFFSET_CALIBRATION` | `REHOME_XY_Z_TOLERANCE` | `0.02 mm`; `0..0.25` | raw X/Y rehome 时允许的最大绝对 dZ。 |
| `Z_OFFSET_CALIBRATION` | `ZDBG` | `0`; `0/1` | 精简 Z calibration tracing，不用于改变运动策略。 |
| Eddy probe config | `probe_below_trigger_allowance` | 当前 soak-test 值 `2.0 mm` | lowest trusted Eddy trigger 以下允许的动态 non-contact descent margin。 |
| Eddy probe config | `eddy_diagnostic_level` | soak-test 通常 `2` | M_Bamboo Eddy 诊断详细度。 |

---

# 2. `G28` — 安全回零兼容入口

> **类型：** 标准名称被 macro 接管  
> **归属：** M_Bamboo Safe Home  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是  
> **推荐普通入口：** 是

### 用途

继续保留 SV08 Max 触摸屏和原厂 macro 预期的 `G28`，但已校准状态下将实际回零路由给 `M_BAMBOO_HOME_*`。

### 用法

```gcode
G28
G28 X
G28 Y
G28 Z
G28 X Y
```

### M_Bamboo 行为

已有 Eddy calibration 时，带轴参数的调用进入对应 Safe Home command；裸 `G28` 进入 `M_BAMBOO_HOME_ALL`。

底层被 rename 的 command 是 `M9928`。**普通用户不要把 `M9928` 当正常回零入口。**

### Safety

- unknown/untrusted Z 必须先建立正 Z clearance，之后才允许 XY 横移；
- `G28` 不会清除已经 latch 的 Eddy fault；
- Eddy probe / Z home 失败时，generic homing safety layer 会撤销 Z trust。

---

# 3. `M_BAMBOO_HOME_X`

> **归属：** Safe Home  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是

需要时先建立 Z clearance，再 raw-home X；不会建立 Z datum。

```gcode
M_BAMBOO_HOME_X
```

---

# 4. `M_BAMBOO_HOME_Y`

> **归属：** Safe Home  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是

与 `M_BAMBOO_HOME_X` 相同的 safety 语义，用于 Y。

```gcode
M_BAMBOO_HOME_Y
```

---

# 5. `M_BAMBOO_HOME_XY`

> **归属：** Safe Home  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是

Z clearance **只建立一次**，随后 raw-home X/Y。

```gcode
M_BAMBOO_HOME_XY
```

---

# 6. `M_BAMBOO_HOME_Z`

> **归属：** Safe Home  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是

### 顺序

1. 在任何 XY 横移前先建立 positive-only Z clearance；
2. 要求 X/Y 已回零；
3. 移动到配置的 Z-home XY；
4. 执行真实 Eddy-backed raw Z home；
5. 移动到配置的 post-home Z。

```gcode
M_BAMBOO_HOME_Z
```

### Fault 行为

不会自动清除 Eddy fault。当前 session 已 latch 时，probe 仍会被阻止，必须 `FIRMWARE_RESTART` 开启新 session。

---

# 7. `M_BAMBOO_HOME_ALL`

> **归属：** Safe Home  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是

原子流程：

```text
positive Z clearance 一次
→ raw X
→ raw Y
→ Z-home XY
→ 真实 Z home
→ post-home Z
```

```gcode
M_BAMBOO_HOME_ALL
```

---

# 8. `M_BAMBOO_EDDY_STATUS`

> **归属：** Eddy Safety Core  
> **稳定性：** **Public / Soak-test**  
> **是否运动：** 否  
> **Fault latch 后允许：** 是

查询 authoritative Eddy safety state 与最近一次 transaction/fault evidence。

```gcode
M_BAMBOO_EDDY_STATUS
```

### ES-R4-EC2 可显示的重点 evidence

EC2 额外区分 **first fault** 与当前最强 fault，并显示 transport fault sequence 的 `handled/current` 状态；如果 serial callback 已经记录 fault、但 reactor safety callback 尚未消费，该 pending fault 本身就会阻止新的 Eddy operation。


- session fault state；
- transaction ID / caller / mode / state；
- start / target / final；
- `transport_fault_seq`、trusted-through watermark 与 transaction taint；
- current transport state 与 historical last-error telemetry 的分离显示；
- session transport fault count/type/context statistics；
- pre-arm check / transient-recovery / failure 计数，以及当前是否要求 Z recovery；
- decoded raw I2C fault evidence；
- active stop / `trsync_active`；
- halt-position reconstruction state；
- bounded last-transaction event timeline（相对时间），例如 `TRANSPORT_FAULT → STOP_REQUESTED → ABORTED → HALT_RECONSTRUCTED`；
- trusted trigger / dynamic floor（适用时）。

### 不会做

- 清 fault；
- 自动重试 probe；
- 回零；
- 移动 toolhead。

Eddy abort 后，建议先运行本命令保存 evidence。若属于 transport fault，按 `Recovery guidance` 运行 `M_BAMBOO_EDDY_RECOVERY_CHECK`；只有 recovery check 失败/不稳定或 armed recovery 再次失败时才要求 `FIRMWARE_RESTART`。

---

# 8A. `M_BAMBOO_EDDY_RECOVERY_CHECK`

> **归属：** Eddy Transport Recovery  
> **稳定性：** **Public / Soak-test**  
> **是否运动：** 否  
> **Fault latch 后允许：** 是

用于 transport fault 后进行**显式、无运动**的 LDC1612 recovery health check。它不会清除失败 transaction，也不会恢复 Z trust。 如果 fault 是由 pre-arm gate 在任何 bed-facing Z motion 开始前捕获，则 Z trust 从未被撤销；这种情况下 PASS 会直接把 transport 恢复到 `HEALTHY`，无需 recovery G28 即可继续正常操作。

```gcode
M_BAMBOO_EDDY_RECOVERY_CHECK
```

### 工作方式

- 先留出短暂 settle window；
- 连续读取 LDC1612 manufacturer/device ID 三次；
- 每次读取后留出 reactor settle window，让 Sovol 的 async `ldc1612_i2c_report` 有机会到达；
- 要求整个检查期间 `transport_fault_seq` 不增加；
- 只有 ID 全部正确且 fault sequence 不变，才报告 `TRANSPORT_RECOVERED`。

### 成功后

如果 fault 发生在 HOMING/PROBE motion 已经 ACTIVE 之后：

```text
Transport state = TRANSPORT_RECOVERED
Z trust         = UNTRUSTED
Recovery armed  = YES
```

此时用户应运行**一次** `G28`。Safe Home 会先建立正向 Z clearance、完成 XY home，然后只为随后的 fresh Z home 消费 one-shot recovery authorization。只有 fresh Z home 成功后，transport state 才恢复 `HEALTHY`。

如果 fault 被 pre-arm gate 在 bed-facing Z motion 开始前捕获：

```text
Transport state = HEALTHY
Z trust         = unchanged
Recovery armed  = NO
```

此时可直接继续正常操作，不需要 recovery G28。

### 失败后

不会执行任何 Z motion。用户可以等待后再次运行本 command，或执行 `FIRMWARE_RESTART`。如果 fault 反复出现，应检查 Eddy cable/connector 与 `extra_mcu` I2C path。

### 明确不会做

- 不继续刚才失败的 probe；
- 不自动 `G28`；
- 不自动 `FIRMWARE_RESTART`；
- 不把 recovered transport 误当成 recovered Z coordinate；
- 不允许 QGL/contact/mesh 等普通 Eddy operation 消费 recovery authorization。

---

# 9. `RUN_PROBE_VIR_CONTACT`

> **归属：** Sovol virtual-contact path，由 M_Bamboo Eddy Safety 防护  
> **稳定性：** **Compatibility / Advanced**  
> **是否运动：** 是

用于 `CLEAN_NOZZLE` 和 Z-offset calibration 的 virtual-contact probe。

```gcode
RUN_PROBE_VIR_CONTACT
```

### M_Bamboo safety 语义

- Contact 与 ordinary non-contact dynamic envelope 明确分离；
- transaction 期间出现 transport fault 后，不允许将结果判定为成功；
- 直接调用该 command 也不能绕过已经 latch 的 Eddy fault。

普通用户应优先使用拥有该 contact 操作的上层流程，而不是单独调用。

---

# 10. 受 M_Bamboo Safety 语义影响的标准 Probe Command

> **接口：** `PROBE`、`PROBE_ACCURACY`、`PROBE_CALIBRATE`、`QUERY_PROBE`、`Z_OFFSET_APPLY_PROBE`  
> **归属：** 标准 Klipper Probe API；项目携带修改版 `probe.py`  
> **稳定性：** **Upstream ABI**

M_Bamboo 保留这些标准名称。项目修改的是 ordinary **non-contact** Eddy probing 的安全语义，而不是重新发明一套命令名。

### `PROBE`

```gcode
PROBE
```

适用时，其下降 endpoint 会受到 M_Bamboo trusted-trigger dynamic envelope 限制。

### `PROBE_ACCURACY`

```gcode
PROBE_ACCURACY
```

重复 probing 复用同一 probe backend/safety policy。

### `PROBE_CALIBRATE`

标准 Klipper probe calibration；它与 Sovol/M_Bamboo 的 `Z_OFFSET_CALIBRATION` 不是同一流程。Eddy backend 在把结果写入 pending config 前会通过 ES-R4-EC2 的统一 fault authority 验证；已经 latch 或尚未被 reactor 消费的 transport fault 都会阻止持久化。

### `QUERY_PROBE`

仅查询状态，不产生轴运动。

> 此章节只记录 M_Bamboo **实质影响的行为**，不代替 Official Klipper G-code manual。


### `Z_OFFSET_APPLY_PROBE`

**稳定性：** Upstream ABI / 高级配置命令。它读取当前 G-code Z homing-origin offset，从已配置的 probe `z_offset` 中减去该值，并把结果写入 Klipper 的 pending config，之后需要用户明确执行 `SAVE_CONFIG` 才会持久化。该命令本身不执行轴运动。

它**不是**本项目 `Z_OFFSET_CALIBRATION` 流程的替代品；只有在明确希望把已经建立好的 G-code Z offset 合并进 probe 配置时才应使用。Eddy backend 会在写入 pending 值前调用同一个 persistent-config safety validator，因此 faulted / pending-fault session 会被拒绝。

---

# 11. `Z_OFFSET_CALIBRATION`

> **归属：** Z Calibration / 修改后的 Sovol backend  
> **稳定性：** **Public / Soak-test**  
> **是否运动：** 是

这是 SV08 Max Eddy/contact Z-offset 的主要 workflow。M_Bamboo 保留 command 名，但实质修改了安全策略与 sequence。

### 典型用法

第一次 refinement：

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay USE_CURRENT_Z=1 ZDBG=1
```

Post-mesh final pass：

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay USE_CURRENT_Z=1 USE_CURRENT_Z_ALLOWANCE=1.25 REHOME_XY=1 ZDBG=1
```

### 参数

| 参数 | 默认 / 范围 | 用途 |
|---|---|---|
| `METHOD` | 默认 `default`；项目流程常用 `force_overlay` | 选择 calibration 行为；已有 Eddy data 时 `default` 可能直接返回。 |
| `USE_CURRENT_Z` | `0`; `0/1` | 保留已经可信的当前 Z；**不会**把 unknown Z 变可信。 |
| `USE_CURRENT_Z_ALLOWANCE` | `0.0`; `0..5 mm` | 仅给第一次 contact 临时增加**逻辑**搜索空间；应用时不移动电机，也不降低全局 `position_min`。 |
| `USE_CURRENT_Z_MAX` | `15.0 mm`; `>0` | `USE_CURRENT_Z=1` 时拒绝明显异常过高的 Z。 |
| `REHOME_XY` | `0`; `0/1` | Final calibration 前显式重新 home/reseat XY；不会 `G28 Z`。 |
| `REHOME_XY_Z_TOLERANCE` | `0.02 mm`; `0..0.25` | raw X/Y reseat 过程中允许的最大绝对 dZ，超出则 abort。 |
| `ZDBG` | `0`; `0/1` | 输出精简 `ZDBG:` tracing；设计上不改变运动策略。 |
| `BED_TEMP` | Sovol backend 默认 `65` °C，除非 caller 指定 | calibration bed target。 |
| `EXTRUDER_TEMP` | Sovol backend 默认 `130` °C，除非 caller 指定 | calibration nozzle target。 |

### 关键 Safety 语义

- `USE_CURRENT_Z=1` 要求 trusted/homed Z，不执行旧 runtime `Zmax+15` 大范围 fake coordinate；
- `position_min` 是 safety endpoint，不是合法 contact result；
- post-mesh allowance 只是临时 coordinate headroom，不属于最终 datum；
- `REHOME_XY=1` 只 raw-home X/Y，并通过 dZ guard 确认没有破坏 Z；
- ES-R4 candidate 的 HOME-FIRST 通过 Safe Home atomic real-Z-reference API，避免旧式 split preparation / double-hop。
- Contact / non-contact sensor call 均加入 guard：如果 safety preflight 在 `HomingMove` 尚未开始前就 abort，会显式撤销 Z trust，避免临时逻辑 allowance/rebase 仍被错误标记为 homed。

---

# 12. `CLEAN_NOZZLE`

> **归属：** Nozzle Cleaner NC-R1  
> **稳定性：** **Public / Soak-test**  
> **是否运动：** 是  
> **依赖：** Safe Home + 可工作的 `RUN_PROBE_VIR_CONTACT`

M_Bamboo 管理/替换 Sovol 清嘴 macro，使所有擦拭动作围绕一个已验证 contact datum，消除 legacy secondary plunge 低于 Z safety boundary 的问题。

```gcode
CLEAN_NOZZLE
```

### 主要行为

- 清除 bed mesh；
- 需要时执行安全回零；
- 加热喷嘴；
- 在已知 pad 区域内随机 contact point；
- 只执行 **一次** `RUN_PROBE_VIR_CONTACT`；
- 多行水平 + cross-hatch 重复擦拭；
- secondary wipe 保持在验证过的 contact-relative plane；
- 最后回到可预期 Z，交给后续 `USE_CURRENT_Z=1` calibration。

不会为了“更干净”再增加第二次 contact probe。

---

# 13. `QUAD_GANTRY_LEVEL`

> **类型：** 包装标准 Klipper command  
> **归属：** Config optimization / print orchestration  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是

```gcode
QUAD_GANTRY_LEVEL
```

Wrapper：

```text
如果 XYZ 未全部 homed → G28
→ QUAD_GANTRY_LEVEL_BASE
```

`QUAD_GANTRY_LEVEL_BASE` 是 underlying renamed command，不是推荐的普通入口。

### 当前项目 policy

正常配置使用降低后的 QGL speed / retries / max_adjust。未来 GSL recovery 是独立 feature；普通调用本 wrapper 并不会自动获得未来的放宽 recovery 权限。

---

# 14. `BED_MESH_CALIBRATE`

> **类型：** 包装标准 Klipper command  
> **归属：** Config optimization / print orchestration  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是

```gcode
BED_MESH_CALIBRATE
```

当前 wrapper sequence：

1. 如果尚未建立本次需要的 Z calibration state，则先完成；
2. QGL 未 applied 时执行 QGL；
3. 临时降低 square-corner velocity；
4. 调用：

```gcode
BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=1 METHOD=rapid_scan
```

5. 恢复 square-corner velocity。

### ES-R4

scan / rapid_scan 入口也必须经过同一个 Eddy fault authority；transport-tainted scan 不允许生成被接受的有效 mesh。

---

# 15. `START_PRINT`

> **归属：** Print orchestration / 修改后的 Sovol macro  
> **稳定性：** **Compatibility ABI**  
> **是否运动：** 是  
> **通常由：** slicer start G-code 调用

`START_PRINT` 已由项目实质管理 Z-calibration / QGL / mesh 顺序，不应视为原厂 passthrough。

当前概念流程：

```text
CLEAN_NOZZLE
→ reset G-code Z offset
→ first current-Z Z_OFFSET_CALIBRATION
→ QUAD_GANTRY_LEVEL
→ real G28 Z / Safe Home path
→ BED_MESH_CALIBRATE
→ final post-mesh Z_OFFSET_CALIBRATION
→ remaining Sovol print-start flow
```

典型 managed calibration：

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay BED_TEMP=<target> USE_CURRENT_Z=1 ZDBG=1
```

final pass：

```gcode
Z_OFFSET_CALIBRATION METHOD=force_overlay BED_TEMP=<target> USE_CURRENT_Z=1 USE_CURRENT_Z_ALLOWANCE=1.25 REHOME_XY=1 ZDBG=1
```

> Release 会管理 exact macro body；普通用户应调用 `START_PRINT`，而不是自行复制整条内部 chain。

---

# 16. `LDC_CALIBRATE_DRIVE_CURRENT`

> **归属：** LDC1612 backend  
> **稳定性：** **Advanced / Calibration**  
> **轴运动：** command 本身无预期轴运动  
> **是否改变 calibration：** 是

典型形式：

```gcode
LDC_CALIBRATE_DRIVE_CURRENT CHIP=<chip_name>
```

### ES-R4-EC2 integrity guard

新的、尚未 recovery 的 LDC I2C transport fault 会阻止本命令。只有 `M_BAMBOO_EDDY_RECOVERY_CHECK` 成功、随后 armed fresh Safe Home `G28` 也成功后，Eddy Safety Core 才会把当前 transport fault sequence 标记为 trusted-through；这个 watermark 及之前的历史 fault 不再阻止 drive-current calibration，但任何更新的 fault 都会立即再次 block。校准过程中不再读取并回写一个可能被坏 I2C transaction 污染的 `old_config`；恢复使用这版 Sovol 已知的 measurement-mode CONFIG 值，且只有 transaction-wide fault sequence 保持干净时才允许产生待 `SAVE_CONFIG` 的结果。

Candidate 在 transaction 开始时记录 transport-fault sequence；期间发生 I2C transport fault 时，计算结果直接作废，不允许将 tainted register data 变成持久 `reg_drive_current`。

仅建议在 Eddy/LDC 校准或诊断时使用。

---

# 17. `PROBE_EDDY_CURRENT_CALIBRATE`

> **归属：** Eddy calibration backend  
> **稳定性：** **Advanced / Calibration**  
> **是否运动：** 是  
> **是否修改 calibration data：** 是

这是修改后的 Eddy backend 继续保留的 mux command，用于手动建立/重建 Eddy frequency-to-height calibration。

```gcode
PROBE_EDDY_CURRENT_CALIBRATE CHIP=<chip_name>
PROBE_EDDY_CURRENT_CALIBRATE CHIP=<chip_name> PROBE_SPEED=5
```

| 参数 | 默认 | 含义 |
|---|---:|---|
| `CHIP` | 必填 mux selector | 选择配置中的 Eddy probe instance。 |
| `PROBE_SPEED` | `5 mm/s` | 手动 Eddy calibration 运动速度。 |

它是 sensor calibration interface，不是日常打印使用的 `Z_OFFSET_CALIBRATION`。只有明确需要重建 Eddy calibration data 时才使用。

**EC2 safety behavior：** command 在 manual calibration 开始前检查 Eddy Safety Core；manual-probe 阶段结束、真正 calibration motion 开始前再次检查；生成 calibration table 后、写入 pending config 前再检查一次。任何已经 latch 或尚未 handled 的 transport fault 都会拒绝结果，transport-tainted data 不允许成为持久 calibration。

---

# 18. `EDDY_QUERY_LOOP`

> **归属：** 项目修改 backend 继续暴露的 Sovol LDC1612 interface  
> **稳定性：** **Advanced / Diagnostic**  
> **是否运动：** 否

低层 query-loop 控制：

```gcode
EDDY_QUERY_LOOP SWITCH=ON
EDDY_QUERY_LOOP SWITCH=OFF
```

不属于正常打印、也不是正常 Eddy fault recovery 流程。之所以列入，是因为项目替换/修改了暴露该 command 的 backend，因此文档需要明确继承责任。

---

# 19. `XY_STRESS_BASELINE`

> **归属：** M_Bamboo Diagnostics  
> **稳定性：** **Optional / Diagnostic**  
> **是否运动：** 是

先回零，然后记录 GET_POSITION 与 X/Y TMC baseline。

```gcode
XY_STRESS_BASELINE
```

保存 console output；在最后 `XY_STRESS_CHECK` 前不要重启 Klipper/MCU。

---

# 20. `XY_STRESS_RUN`

> **归属：** M_Bamboo Diagnostics  
> **稳定性：** **Optional / Diagnostic**  
> **是否运动：** 是 — 高速 XY stress motion

使用当前验证测试 envelope：

```text
velocity = 400 mm/s
acceleration = 15000 mm/s²
```

```gcode
XY_STRESS_RUN
```

确保 build volume clear，并且先执行 baseline。

---

# 21. `XY_STRESS_CHECK`

> **归属：** M_Bamboo Diagnostics  
> **稳定性：** **Optional / Diagnostic**  
> **是否运动：** 是

压力测试后重新回零并记录 position/TMC state，用于和 baseline 对比。

```gcode
XY_STRESS_CHECK
```

推荐 sequence：

```text
XY_STRESS_BASELINE
→ 保存输出
→ XY_STRESS_RUN
→ XY_STRESS_CHECK
→ 对比 baseline / check
```

---

# 22. `M_BAMBOO_Z_RELIEF` — 计划中

> **归属：** Recovery / Safe Home  
> **稳定性：** **Planned — ES-R4-EC2 尚未实现**  
> **计划运动：** 仅 positive Z

设计目标：eligible downward-probe fault 后，在不清除 Eddy safety latch 的前提下卸载 nozzle/bed 机械压力。

如果未来实现，预计必须满足：

- fault 已 latch；
- last transaction 被明确标记为 relief-eligible；
- 只能 +Z；
- 不允许 XY；
- 不允许 Eddy probing；
- Z 仍保持 untrusted/unhomed；
- fault 仍保持 latch；
- 仍需 `FIRMWARE_RESTART` 建立新 session。

**当前不要调用或依赖这个 command。**

---

# 23. RC4 Release Installer CLI

> **归属：** Installer / release tooling  
> **稳定性：** **RC / public release interface**  
> **是否修改机器：** 只有 `--apply` 才会写入  
> **默认模式：** dry-run

### 标准安装

```bash
./install.sh all
./install.sh all --apply
```

### Feature scoped install

```bash
./install.sh safe_home --apply
./install.sh config_optimization --apply
./install.sh eddy_safety --apply
./install.sh diagnostics --apply
./install.sh hardware_cooling --apply
```

### Status / diff

```bash
./install.sh all --status
./install.sh all --raw-diff
```

### Restore

```bash
./install.sh all --restore
./install.sh all --restore --apply
```

`restore` 的语义是把 M_Bamboo 管理的 surface 恢复到 M_Bamboo 接管前状态，不等于“回到上一个 M_Bamboo release”。

### Persistent backup contract

```text
CFG / macro：不保留 persistent backup
Backend Python：只使用 /home/sovol/klipper/klippy/extras/mb_bak/
Transaction scratch：仅 installer 运行期间存在 /tmp/M_Bamboo_SV08MAX.*
```

CFG restore 执行 managed transformation 的逆操作：删除新增 block、恢复被替换的 stock 参数、从 release template 重建被删除 section，并且绝不修改 `SAVE_CONFIG` 自动生成 tail。

Backend backup manifest 只建立一次并永不覆盖。升级已有 engineering/RC3 机器时可以把 legacy `.mb_baseline` 当作迁移输入，但 RC4 不再新建 `.mb_baseline` 或 `.last_mb_*`。

### `--no-restart`

```bash
./install.sh all --apply --no-restart
./install.sh all --restore --apply --no-restart
```

仅用于开发/测试。Klipper host process 未重启前，新 Python 不会生效。

first-takeover provenance、atomic failure rollback、migration、Restore，以及 RC4 **不实现 generic downgrade** 的当前策略见 `docs/DEPLOYMENT_AND_ROLLBACK.md`。

---

# 24. Project Configuration Interface

这里记录虽然不是单独 G-code，但已经构成 M_Bamboo project contract 的配置项与 managed value。

## 24.1 Safe Home config — `[M_Bamboo_Safe_Homing]`

| Key | Candidate / 默认 | 含义 |
|---|---:|---|
| `home_xy_position` | 项目值 `271, 251` | 真实 Z home 前使用的 XY 点。 |
| `xy_speed` | `150 mm/s` | 前往 Z-home XY 的速度。 |
| `z_hop` | `5 mm` | unknown/untrusted-Z clearance 距离。 |
| `z_hop_speed` | `10 mm/s` | clearance / recovery lift 速度。 |
| `post_home_z` | `10 mm` | 真实 Z home 后的 clearance Z。 |

## 24.2 Eddy Safety config

| Key | Project policy | 含义 |
|---|---|---|
| `probe_below_trigger_allowance` | 当前 soak-test `2.0 mm` | non-contact safety floor = lowest trusted trigger − allowance。 |
| `eddy_diagnostic_level` | `0..2`，soak-test 通常 `2` | `0=ERROR`、`1=NORMAL`、`2=VERBOSE`。 |

## 24.3 Config Optimization / 全局 managed values

以下属于**配置 policy**，不是新增 G-code 参数：

| Area | Stock / previous | M_Bamboo managed policy |
|---|---:|---:|
| `[printer] max_velocity` | `700` | `400` |
| `[printer] max_accel` | `40000` | `15000` |
| X/Y `run_current` | `3.0 A` | `2.3 A` |
| QGL `speed` | `400` | `200` |
| QGL `retries` | `15` | `5` |
| QGL `max_adjust` | `20` | `5` |
| Adaptive mesh `PGP` | `0` | `1` |
| Buffer stepper `velocity` | `150` | `80` |
| Buffer stepper `accel` | `5000` | `1900` |
| Buffer stepper `push_length` | `25` | `27` |
| `[stepper_z] position_min` | stock 约 `-10` | `-1` |

某个 config-optimization feature 是否实际安装，最终仍以对应 release manifest / managed block 为准。

## 24.4 Hardware Cooling config

Hardware Cooling 是正式但依赖物理改装的可选 feature。它**不包含在 `all` 中**，只有确认完成对应散热硬件改装后才应显式安装。

当前 RC4 ownership：

```ini
[heater_fan bed_fan]
fan_speed: 0.6
```

Installer 对无法识别的现有值直接拒绝，不通过猜测接管 ownership。

---

# 25. Internal / Deprecated Backend Interface

## `establish_real_z_reference(...)`

**Internal Python API。** Safe Home 拥有 HOME-FIRST 所需的 atomic real-Z-reference sequence。用户 macro 应使用 public Safe Home / Z calibration command。

## `prepare_xy_for_calibration(...)`

**Internal / Deprecated。** 只为一版 compatibility 暂留。新代码不得再把“prepare XY”和“home Z”拆成两个外部调用。

## `_safe_z_hop(...)`

**Internal / Deprecated alias。** Recovery refactor 后真正的语义 owner 是“establish Z clearance”。

---

# 26. Interface Audit 说明

## `G80`

本次对当前可恢复的 RC4 / ES-R4-EC2 source artifacts 做了 audit，**没有发现 active `G80` macro、Python registration 或 override**。因此本 reference 不会凭记忆虚构 `G80` 的行为。

如果旧版 M_Bamboo/Sovol package 里确实存在真实 `G80` override，应先找回 exact source，再在下一次 release 前把它加入本 registry。

## 为什么没有把所有 stock Sovol macro 全部抄进来？

SV08 Max `Macro.cfg` 里还有 `PAUSE`、`RESUME`、`M109`、`M190`、`M106`、`M107`、耗材相关 macro 等大量原厂接口。它们**不会因为存在于机器里就自动成为 M_Bamboo public interface**。

只有项目开始 owning、替换或实质改变其行为时，才必须进入本 registry。

---

# 27. Publish / Release 文档 Gate

每次 publish 必须检查：

- [ ] 所有新增 command / macro 已进入本 registry；
- [ ] 所有新增 public 参数/变量都有默认值、范围、用途；
- [ ] 所有替换 stock/Klipper/Sovol command 都记录 compatibility alias/base command；
- [ ] deprecated / removed interface 明确标记；
- [ ] fault / recovery 行为与当前 backend 一致；
- [ ] example 与当前代码一致；
- [ ] touchscreen / slicer ABI 没有被意外改名；
- [ ] 中英文 reference 同步；
- [ ] README 有本 reference 的入口；
- [ ] release notes 记录 public-interface 的新增/修改/删除；
- [ ] 后续自动 validation 应比较实际注册的 `M_BAMBOO_*`、managed macros 与 documented registry。

