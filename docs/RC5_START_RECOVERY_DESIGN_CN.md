# RC5 `START_PRINT` 自动恢复设计

> 状态：**`rc5-dev` 工程设计 / 审计文档**  
> 当前公开基线仍是 RC4；RC5 实现和实机 fault-injection 尚未完成。

## 目标

RC5 要做到：打印启动阶段发生**可以安全恢复**的 Eddy / PREARM transport fault 时，由系统自动接管 fault containment 和恢复，而不是让用户因为一次可恢复通讯异常重新启动整套 `START_PRINT`。

这个功能刻意保持小范围：只负责 `START_PRINT` 中与 Eddy 有直接依赖的核心流程，不修改 MCU firmware，不加入 daemon，不做通用 workflow framework，也不混入 PLR。

## 为什么普通 Macro 无法直接完成 recovery

Klipper 的普通 G-code macro 不是 exception-resumable workflow。Nested command 抛出 `command_error` 后，当前 macro chain 会 unwind。如果异常继续穿透到 `virtual_sdcard`，打印文件会停止，并被标记为 error。

所以自动恢复不能设计成：

```text
START_PRINT macro fault
-> macro 已经结束
-> 之后再运行一个 recovery macro
-> 希望原来的 START_PRINT 自动接着跑
```

RC5 必须在异常离开 top-level `START_PRINT` 之前，只接住 Safety Core 明确判定为 eligible 的 Eddy transport fault。

Nested command 仍然可以产生正常的 `gcode:command_error` event / `!!` 输出。这些 event 对 ProbeSession、scan session 和 gcode_move cleanup 有价值。Moonraker 只负责转发这类 response；真正让 virtual SD print 停止的是 exception 最终是否穿透到 `virtual_sdcard`。

## 最小接管范围

RC5 不把整个 `START_PRINT` 搬进 Python。

建议结构：

```text
START_PRINT
  -> 现有 non-Eddy setup
  -> M_BAMBOO_START_SEQUENCE
       CLEAN
       PRE_ZCAL
       QGL
       Z_HOME
       MESH
       POST_ZCAL
  -> 现有 MANUAL_FEED / LED / M400 / NOZZLE_CLOG_CHECK / final prep
  -> print body
```

Coordinator 只调用现有 Macro / G-code command，不重新实现 Safe Home、QGL、bed mesh、擦嘴或 Z calibration 的运动算法。

## 当前 dependency chain

现有 managed core 可以概括为：

```text
CLEAN_NOZZLE
-> SET_GCODE_OFFSET Z=0
-> QGL 前 Z_OFFSET_CALIBRATION
-> has_z_offset_calibrated=True
-> QUAD_GANTRY_LEVEL
-> G28 Z
-> BED_MESH_CALIBRATE
-> mesh 后 Z_OFFSET_CALIBRATION
-> has_z_offset_calibrated=False
```

`BED_MESH_CALIBRATE` 本身还有 dependency behavior，例如确认 calibration state、必要时要求 QGL 已经 applied。

因此 recovery 不能只记“执行到第几行”，必须同时维护物理完成状态与 software dependency state。

## Atomic stage

Coordinator 把 managed core 分成：

```text
S0 CLEAN
S1 PRE_ZCAL
S2 QGL
S3 Z_HOME
S4 MESH
S5 POST_ZCAL
DONE
```

只有 command 正常返回，并且对应 completion state 被接受后，stage 才算完整成功。

## 每个 stage 发生 fault 后怎么办

### S0 CLEAN

当前擦嘴流程先做 Eddy contact，再进入真正 wiping motion。因此 contact fault 时擦拭动作还没有开始。

Recovery 后：

- 当前 contact transaction 作废；
- 必要时恢复 transport / Z；
- 从 `CLEAN_NOZZLE` 开头完整重跑。

不需要记录“擦到第几下”。

### S1 PRE_ZCAL

QGL 前 Z calibration 任何中途 fault 都让本轮 calibration 整体无效。

Recovery 后：

- 必要时重新建立 Z；
- 整段 calibration 从头重跑；
- 只有完整成功以后才设置 `has_z_offset_calibrated=True`。

绝不从 contact、verification 或 Eddy calibration 中间续跑。

### S2 QGL

QGL 中途 fault：

- 当前 QGL 视为 incomplete；
- recovery 后整个 QGL 重跑；
- 之前已经成功的 PRE_ZCAL 不因为 QGL partial 就强制重跑。

Klipper 的 QGL `applied` 只有完整 result 被接受后才为 true。新一轮 QGL 会 reset 这个状态；普通 G28 不会自动清掉已经成功的 QGL，Z motor off 会。

### S3 Z_HOME

如果 QGL 后面的显式 Z Home fault，而 bounded recovery 本身已经通过 fresh Safe Home 成功建立新的 Z reference，那么这个 recovery G28 **本身就满足 S3**。

不能紧接着再重复一次 `G28 Z`。

### S4 MESH

Mesh fault：

- 整张 mesh 从头重新扫描；
- partial scan 不接受；
- 如果之前成功的 QGL 仍然显示 `applied`，不因为 mesh fault 无意义地重复 QGL。

Upstream `BED_MESH_CALIBRATE` 在开始 calibration 时会先清掉 active mesh，只有完整 dataset finalize 后才安装新 mesh。因此 half scan 不会成为一张有效新 mesh。

另外，现有 mesh wrapper 会临时把 `square_corner_velocity` 改成 `1.0`。如果 scan 中途 fault，旧流程可能根本走不到 restore。RC5 必须在 stage 开始时保存真正的原始值，并在 success、recoverable failure、hard failure 三条出口都恢复。

### S5 POST_ZCAL

Mesh 后 Z calibration fault：

- 已经成功的 QGL / mesh 默认保留，除非另有条件明确使它们失效；
- 恢复 transport 和 Z trust；
- 整段 post-ZCAL（包括 final XY reseat）从头重跑。

这个 stage 会使用 temporary logical-Z search allowance。即使 PREARM 在下探前拦住 fault，Z calibration 自己也可能为了防止 temporary coordinate state 泄漏而主动把 Z 标成 unhomed。

因此 fresh Z 判断必须同时看两层：

```text
need_fresh_z_home =
    Safety Core 认为 Z recovery required
    OR
    当前 homed_axes 已经不包含 Z
```

## Fault classification

Coordinator 不能因为 Safety Core 里历史上曾经出现过 `HARD_COMM_FAULT`，就把后来任何一个 `command_error` 都自动吞掉。

每个 atomic stage 开始前记录当前 `transport_fault_seq`。只有同时满足：

- Safety Core 认为这次 fault 可以进入 recovery；
- 当前 stage 执行期间 transport fault sequence 确实增加（或提供等价 transaction-local evidence）；

才走 Eddy auto-recovery。

这样普通 QGL 参数错误、Macro 错误或其他 non-Eddy failure 不会被误判为通讯恢复。

## Recovery episode 与次数限制

当前 RC5 设计目标：

```text
MAX_START_AUTO_RECOVERIES = 3
MAX_RECOVERY_ATTEMPTS_PER_EPISODE = 1
```

这里的重点不是数字，而是 episode 定义：

1. eligible fault 先做无运动 transport health check；
2. 需要恢复 Z 时，同一个 episode 只允许一次 fresh armed Safe Home；
3. 这一次 recovery 失败，立即终止；剩余 total budget 不能拿来给同一个 episode 再试 G28；
4. recovery 成功后，刚才失败的 atomic stage 必须完整成功，才算真正离开该 episode；
5. 如果 stage 还没完成又再次 transport fault，视为同一不稳定阶段，不继续自动 recovery loop；
6. 只有 stage 已完整成功后，后面新的 fault 才能算新的独立 episode；
7. 超过整个 `START_PRINT` recovery budget 后停止启动，要求人工检查。

最终数字仍需要 RC5 实机 fault-injection 后冻结。

## PREARM fault 的特殊处理

PREARM 是 no-motion gate，本身不会启动 bed-facing Z descent。

因此单纯 PREARM fault 不自动等于 Z reference 已经失效。Transport 恢复以后，只有同时满足以下条件，才允许不额外 G28 就直接重试同一 stage：

- Safety Core 明确表示不需要 Z recovery；
- 当前 kinematics 仍显示 Z homed；
- owning stage 自己没有因为 temporary coordinate state 而撤销 Z trust。

Z calibration 正是第三种情况的典型例子。

## Ownership

### Eddy Safety Core 继续负责

- transport fault detection / monotonic fault sequence；
- PREARM fail-closed；
- transaction taint / abort；
- stream quarantine；
- Z trust invalidation；
- no-motion transport health check；
- one-shot Safe Home recovery authorization；
- hard-fault / restart-required decision。

### START coordinator 只负责

- 当前 atomic startup stage；
- stage entry / completion state；
- `START_PRINT` recovery budget；
- 判断这次 stage error 是否真的是新的 eligible transport episode；
- stage-local temporary state cleanup；
- successful recovery 后应该完整重跑哪个 stage；
- 只有整个 managed core 成功后才把控制权交回 outer `START_PRINT`。

Eddy backend 绝不应该知道类似“QGL fault 后下一步应该跑 mesh”这样的 workflow knowledge。

## State hygiene

每次新的 managed start sequence 都必须：

- 初始化 stage / budget；
- 先规范化 `has_z_offset_calibrated=False`；
- 保存需要 restoration 的 stage-local state；
- 不相信上一轮失败留下的 checkpoint。

PRE_ZCAL 完整成功后：

- `has_z_offset_calibrated=True`。

POST_ZCAL 完整成功、整个 managed core 成功、或者任何 terminal failure：

- `has_z_offset_calibrated=False`。

Mesh SCV、Eddy transaction/session/client 等也必须保证 terminal cleanup。

## Feature / installer ownership

RC5 不为 coordinator 单独新增 installer feature。

建议在 `config_optimization` 管理的 START_PRINT core 使用 dual-path：

```jinja
{% if 'M_Bamboo_Start_Sequence' in printer %}
    M_BAMBOO_START_SEQUENCE
{% else %}
    # RC4 legacy managed start core
{% endif %}
```

这样：

- 只装 `config_optimization`：继续走 RC4 core；
- Eddy Safety 可以拥有 coordinator backend/config，但单独安装时不强行接管 START_PRINT；
- 两者同时安装：启用 bounded auto recovery；
- 单独 restore Eddy Safety：coordinator object 消失，START_PRINT 自动 fallback，不留下 broken dependency。

START_PRINT takeover 继续使用 provenance / lineage gate。只转换明确识别的 stock / RC4 / RC5 lineage；未知 custom sequence 一律 fail closed，交给人工 review。

## RC5 发布前实机验证要求

至少需要覆盖：

1. PREARM fault：Z 不下探；auto recovery；同 stage 重跑；只有 safety 与 kinematics 都同意时才保留旧 Z trust。
2. CLEAN contact fault：wipe 不开始；recovery 后完整 CLEAN rerun。
3. PRE_ZCAL fault：完整 calibration rerun；flag 只在成功后变 true。
4. QGL partial fault：partial QGL 不接受；完整 QGL rerun。
5. Z_HOME fault：recovery G28 成功后直接满足 stage，不能 double-home。
6. MESH mid-scan fault：完整 rescan；已完成 QGL 保留；SCV 正确恢复。
7. POST_ZCAL fault：mesh 保留；Z trust cross-layer reconciliation；完整 post-ZCAL rerun。
8. Recovery G28 自己 fault：立即 terminal，不允许 same-episode 第二次 armed G28。
9. recovery 后同 stage 尚未成功又再次 fault：停止，不进入连续 recovery loop。
10. stage 成功后出现新的独立 fault：允许继续使用剩余 start budget。
11. non-Eddy error：正常向上抛，不自动恢复。
12. terminal failure / 下一次打印：不存在 stale flag、SCV、checkpoint、token、active tx、client 或 budget。
13. Moonraker / UI：被 coordinator 成功接管的内部 `!!` 只作为诊断输出，不应在支持的 SV08 Max UI 路径里引发独立 cancel。

## Release gate

Mock 可以证明 state machine 没写反，但不能代替实机。以上 fault-injection matrix 完成之前，coordinator 只能保持 engineering/development 状态，不能当作已验证 RC5 release behavior。
