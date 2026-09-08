# RC5 通用 Recovery Supervisor 设计

> 状态：仅用于 `rc5-dev` 开发验证，尚未发布。
>
> 当前公开基线仍是 RC4。本文取代旧 `RC5_START_RECOVERY_DESIGN_CN.md` 中“只有 START_PRINT 才拥有自动恢复”的边界，但保留其中已经确定的 START stage / replay 规则。

## 目标

RC5 的默认策略应当是：只要某次 Eddy / PREARM transport fault 能够被**证明可以安全收敛和重放**，就优先自动恢复。用户是从 START_PRINT、BED_MESH、QGL 还是 Z calibration 进入，不应决定“自动还是手动”；真正决定恢复策略的是当前 transport / Z trust / 物理状态，以及我们是否有明确的 replay contract。

核心规则：

> **Recovery policy 全局统一；replay policy 按 operation 定义。**

支持的 operation 应按以下流程处理：

```text
出现新的 transport evidence
-> 当前 atomic operation 作废
-> 回到安全的同步 owner boundary
-> no-motion transport identity recovery
-> 仅在必要时重建 Z trust
-> 整段 operation 重跑一次
-> 成功，或 fail closed
```

## 为什么 recovery 不能进入 rapid-scan callback

2026-09-08 的实机故障已经证明：rapid scan 的 lookahead callback 可能在 scan owner 已经进入 teardown 之后，仍从 Klipper motion flush context 被执行。如果 callback 此时继续访问已经释放的 scan state，异常会逃进 `flush_handler` 并导致 Klipper shutdown。

因此：

- I2C / bulk / timing / lookahead callback 可以 latch、taint、quarantine、request abort，或者在 session 结束后直接 no-op；
- callback 内不能执行 G28、不能 retry workflow、也不能抛出 workflow recovery exception；
- recovery 只能在失败 operation 回到普通同步 G-code owner 之后启动。

RS1 负责 callback/session lifetime；GR1 负责后续 recovery / replay。

## GR1 首批支持的 direct operation

```text
G28
RUN_PROBE_VIR_CONTACT
CLEAN_NOZZLE
Z_OFFSET_CALIBRATION
QUAD_GANTRY_LEVEL
BED_MESH_CALIBRATE
```

全部采用“整段 operation 重跑”，绝不从 partial point / partial mesh / partial calibration 中间续接。

### G28

Homing 中途发生 transport fault 后，本轮 homing 作废。Transport recovery 后，如果 Safety Core 要求 fresh Z trust，则只允许一次直接 Safe Home reconstruction；成功后重新执行本次 G28。

### RUN_PROBE_VIR_CONTACT

失败 contact transaction 直接丢弃；transport / Z 恢复后重新发起一次新的 contact transaction。

### CLEAN_NOZZLE

NC-R1 当前设计在真正 wipe motion 之前先完成 Eddy contact，因此 contact fault 时整段 CLEAN 可以安全从头重跑。

### Z_OFFSET_CALIBRATION

Contact、verification、Eddy calibration 统一视为一个 atomic calibration operation。中间任何 transport fault 都使本轮结果整体无效，恢复后整段重跑。

### QUAD_GANTRY_LEVEL

Partial QGL 不从“剩余探点”继续。恢复后在当前真实 gantry 状态上重新执行完整 public QGL。

### BED_MESH_CALIBRATE

Partial mesh 永远无效。恢复后完整重跑 public BED_MESH wrapper，不接受任何 partial rapid-scan dataset。

## Outermost owner 规则

同一调用树中只能有一个 recovery owner。

例如用户直接执行：

```text
BED_MESH_CALIBRATE          <-- owner
  G28                       pass-through
  Z_OFFSET_CALIBRATION      pass-through
  QUAD_GANTRY_LEVEL         pass-through
  BED_MESH_CALIBRATE_BASE   native
```

如果内部任一命令 fault，异常一路返回 BED_MESH owner，由 BED_MESH 做一次 recovery，再把完整 BED_MESH 从头重跑。

START_PRINT 则继续由已经存在的 coordinator 做 outer ownership：

```text
START_PRINT
  M_BAMBOO_START_SEQUENCE   <-- owner
    CLEAN
    PRE_ZCAL
    QGL
    Z_HOME
    MESH
    POST_ZCAL
```

当 `M_Bamboo_Start_Sequence.active=True` 时，generic wrappers 只透传，不独立 recovery。这样不会出现“nested QGL 自己恢复一次，START 又对同一个 episode 再恢复一次”的 double-retry。

现阶段保留已经通过 healthy-path 真机验证的 START coordinator，等 combined candidate 完成硬件验证后，再考虑内部 API 层面的进一步统一，而不是现在为了代码形式漂亮而重写。

## Recovery eligibility

只有 command-local monotonic marker 增长时才允许进入 auto recovery：

```text
(transport_fault_seq, preflight_failed_count)
```

这样既能识别 active transport fault，也能识别 PREARM exhausted、但还没产生新 async fault-seq 的情况。

普通 macro / config / motion error 如果没有新的 Eddy evidence，原样向上抛出。

## Recovery action

每个 eligible episode：

1. 执行已有的 no-motion LDC identity recovery check；
2. 要求 transport state 为 `HEALTHY` 或 `TRANSPORT_RECOVERED`；
3. 如果 `restart_required=True`，立即停止；
4. 如果 Safety Core 标记 `z_recovery_required`，或 kinematics 已不再认为 Z homed，则只允许一次 fresh M_Bamboo Safe Home reconstruction；
5. 从头 replay owning operation 一次。

## Budget

Direct public command：

```text
MAX_AUTO_RECOVERIES_PER_INVOCATION = 1
```

Replay 还没完成就再次出现新的 Eddy/PREARM fault，立即停止。

START_PRINT 保留：

```text
MAX_START_AUTO_RECOVERIES = 3 个独立 episode
MAX_RECOVERY_ATTEMPTS_PER_EPISODE = 1
```

START stage recovery 后必须先 clean complete，之后的新 fault 才能算新的独立 episode。

## Fail-closed 条件

以下情况不允许自动继续：

- 当前 command 没有新的 Eddy/PREARM evidence；
- transport identity recovery 失败；
- Safety Core 要求 firmware restart；
- fresh Safe Home recovery 失败；
- replay 完成前再次出现新的 Eddy/PREARM fault；
- 初次执行或 replay 中出现 non-Eddy error。

## Rapid-scan compatibility 硬约束

GR1 不允许修改：

- `SAMPLE_TIME`；
- rapid-scan speed / path / scan height；
- lookahead timestamp；
- sample window；
- `note_probe_and_position()` 语义；
- mesh interpolation；
- LDC query/sample rate。

RS1 只增加 session lifetime guard，让旧 queued callback 在 session 已结束时变成 harmless no-op。

## 实机验证

### 1. Load / status

Restart 后执行：

```gcode
M_BAMBOO_EDDY_STATUS
M_BAMBOO_RECOVERY_STATUS
```

Supervisor 必须 ready，并列出预期 wrapped commands。

### 2. Healthy rapid baseline

重复 RC4-like rapid scan。Healthy scan 不应触发 recovery，准确度、时序、scan motion 不应因 GR1 改变。

### 3. Full BED_MESH wrapper

执行 public `BED_MESH_CALIBRATE`。如果 prerequisite 或 active rapid scan 自然出现 raw34/raw36，预期为：

```text
本轮 BED_MESH 作废
-> Klipper 不 shutdown
-> 自动 transport recovery
-> 必要时 fresh Safe Home
-> 完整 BED_MESH replay 一次
```

### 4. Direct command recovery

验证 CONTACT、ZCAL、QGL 等 direct command 的一次自动恢复，以及 replay 前再次 fault 时必须 fail closed。

### 5. START nested ownership

运行 START_PRINT，确认 `M_Bamboo_Start_Sequence` active 时 generic wrappers 不会独立消费 recovery。

## Release gate

GR1 只有在 combined RS1 + GR1 candidate 通过 healthy rapid regression 和真实硬件 recovery 验证以后，才可以成为 RC5 release behavior。
