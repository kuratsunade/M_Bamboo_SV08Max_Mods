# 技术 FAQ — Eddy Safety、PREARM、I2C 故障与 RC5 自动恢复

> 状态：**RC5 工程技术参考。** RC4 仍然是当前公开基线；RC5 正在完成 transaction cleanup 与 `START_PRINT` bounded recovery，之后进入实机验证。

## M_Bamboo 会修改或重刷 MCU 固件吗？

不会。这是整个项目的固定边界，不是 RC5 的临时选择。

M_Bamboo 不修改、不重新编译、不刷写，也不替换 Sovol MCU 固件。我们会审计 MCU 源码，用来判断 host 层哪些信息可以信、哪些结果必须保守处理，但所有正式 mitigation 都发生在 Klipper host Python、配置、Macro 与 installer-managed orchestration 中。

完整源码历史和 pin lookup 分析见 [Sovol STM32F1 I2C / Eddy 根因审计](I2C_ROOT_CAUSE_AND_HOST_BOUNDARY_CN.md)。

## `raw34` 到底表示什么？

Sovol 的 STM32F1 I2C telemetry 使用 bitmask。当前最相关的 bit 是：

- bit 1 -> NACK -> `2`
- bit 2 -> TIMEOUT -> `4`
- bit 5 -> BUSY -> `32`
- bit 7 -> bus error / BERR -> `128`

因此：

```text
raw34 = 34 = NACK | BUSY
raw36 = 36 = TIMEOUT | BUSY
```

Bitmask 本身是有价值的，因为它可以同时保留 transaction symptom 和当时的 bus-state evidence。M_Bamboo 会解析完整 bitmask，不会只 special-case 某一个数字。

## Sovol 的 I2C error definition 本身写错了吗？

不能简单这么说。`I2C_BUS_*` enum 更合理的理解是 **bit position**。真正的问题是：error model 已经迁移成 bitmask，但部分 MCU consumer 仍然使用旧的 scalar comparison，例如概念上的：

```c
if (ret == I2C_BUS_BUSY)
```

BUSY 在 bitmask 中对应 bit 5，也就是 `32`，并不是 scalar `5`。因此我们把这个问题定义为：

> **scalar -> bitmask migration 没有完全收口。**

## `i2c_busy_errata()` 的 pin lookup 问题是什么？

Sovol 的 BUSY recovery helper 手里只有 I2C peripheral pointer，于是尝试用 `container_of` 反查当前 bus 的 SCL/SDA metadata。

但它拿到的是结构体成员**里面存放的 peripheral address**，并不是这个成员本身的地址。结果是代码把 STM32 I2C peripheral register block 当成了 `struct i2c_info`。

恢复函数又在读取所谓 `scl_pin / sda_pin` 之前先清空 `CR2`，因此最终得到的 pin value 为 0，也就是 Klipper STM32 pin 编码里的 `PA0`。

而 SV08 Max `extra_mcu` 的 I2C2 实际使用 PB10/PB11。也就是说，当前 firmware 中本来想对真实 SCL/SDA 做的 GPIO bus-unlock 动作并没有作用到真正的 I2C2 引脚；仍然有效的是 I2C peripheral 自身的 reset / re-init。

M_Bamboo 会记录这个 finding，但不会修 firmware，也不会接管 physical bus recovery。

## 为什么 I2C fault 会变成 Eddy safety 问题？

真正关键的不是“不 shutdown”，而是 **failed transaction 有没有被严格判死**。

在审计到的 STM32F1 路径里，I2C fault 可以被上报，但失败结果并没有在所有 LDC path 上形成严格的 sample/transaction invalid contract。后续代码仍可能继续产生或消费数据。

所以 M_Bamboo 的规则非常简单：

> 一旦出现确认的 transport fault，当前 Eddy transaction 永远 tainted，绝不允许再回到 SUCCESS。

后面即使又收到看起来正常的 response，也不能把刚才失败的那一笔“救活”。

## `NACK | BUSY` 是否说明 Eddy sensor 已经坏了？

不说明。它足以证明**当前 transaction 不可信**，但不能单凭一次 `NACK | BUSY` 判定 sensor、线材或 PCB 已经永久损坏。

因此 recovery 要拆成两个问题：

1. transport 是否已经恢复健康？
2. 当前 Z reference 是否仍然可信？

Transport recovered 只能回答第一个问题。

## 为什么 `i2c_err_flag` 不能直接当实时 bus health？

Sovol 会异步上报 fault，但后续成功 transaction 不一定发送对应的 `0` 去清除旧值。因此它更像“最后一次观察到的 error evidence”，不是实时 health flag。

M_Bamboo 使用 monotonic `transport_fault_seq`，并在每个 transaction 内比较 sequence 是否发生变化。

## 为什么同时还要记录 handled sequence？

Raw serial callback 可能已经让 `transport_fault_seq` 增加，但 reactor callback 还没来得及完整 latch Safety Core state。如果没有 handled watermark，新 operation 有机会卡在这个 scheduling gap 里启动，并把已经发生的 fault 当成自己的“旧历史”。

所以只要 raw sequence 领先 handled sequence，新的 Eddy operation 就直接拒绝启动。

## 为什么 fault 可能从 `PROBE_NO_TRIGGER` 升级成 `HARD_COMM_FAULT`？

因为 evidence severity 只能单向增强。No-trigger 既可能来自几何问题，也可能来自 sensor / transport fault；如果稍后又收到明确的 I2C transport evidence，就必须升级成更强的 fault classification，同时保留最早 symptom 作为 trace。

## PREARM 是什么？

PREARM 是危险 Eddy operation 开始之前的 no-motion readiness gate。

它的目的不是“预测以后绝对不会出错”，而是：

> **Transport 已经不健康、或者刚刚暴露出不稳定时，不允许直接开始 bed-facing Z action。**

PREARM 会在 motion 前做 bounded readiness / health check；无法证明 transport stable 时，Z motion 保持不动，operation fail closed。

## PREARM 能保证 motion 开始后绝对不会再发生 transport fault 吗？

不能。PREARM 是 prevention，不是 prediction。

新的 fault 仍可能在 transaction ACTIVE 后发生，所以 runtime 仍需要：

- transaction taint；
- 必要时 trsync abort；
- stream quarantine；
- Z trust invalidation；
- terminal transaction/session cleanup；
- bounded recovery。

## 既然 runtime 可以 abort，为什么 PREARM 还必须保留？

因为两者保护的是不同阶段。

PREARM 防止“transport 已经有问题，却还进入危险 Z 下探”；runtime guard 处理的是 motion/session 已经启动后才新发生的 fault。我们的实机历史里，在 PREARM 加入之前确实出现过 Z 触底；PREARM 加入后，这条“已知 unhealthy state -> 继续下探”的路径才被真正拦住。

因此 RC5 把 PREARM 当作 safety invariant，不进入默认 simplification candidate。

## RC5 会在 `START_PRINT` 里自动恢复 PREARM / Eddy transport fault 吗？

会，但只针对 Safety Core 判定为**可以安全恢复**的 fault。

RC5 会在现有 Eddy Safety Core 上方增加一个很小的 startup coordinator。可恢复 fault 在异常穿透到 virtual-SD print executor 之前被接住，然后：

1. 清理 / quarantine failed Eddy lifecycle；
2. 不做 Z motion，先重新验证 transport health；
3. 如果 Z trust 需要重建，则执行一次 fresh Safe Home：active bed-facing fault 必须使用 Safety Core 的 one-shot armed token；如果 PREARM 在 motion 前拦住 fault、transport 已恢复 HEALTHY，但 owning stage 自己撤销了 Z homing，则走普通 PREARM-protected Safe Home，不强行要求 armed token；
4. 恢复当前 startup stage 自己留下的 temporary state；
5. 从头重跑完整 failed atomic stage；
6. 只有 stage 完整成功后，`START_PRINT` 才继续往下走。

## 这不就是 automatic retry 吗？

不是 blind retry。Recovery 有明确边界：

- **active-fault episode 同一个 Z recovery 最多只 armed 一次**；
- 这一次 armed recovery 失败，立即 terminal，不会自动继续第二次 / 第三次 G28；
- 只有恢复后的 atomic stage 已经完整成功，后续新 fault 才有资格成为新的 episode；
- 整个 `START_PRINT` 还有总 recovery budget，反复故障最终必须停下来检查；
- 非 Eddy error 不会被 coordinator 当成通讯故障吞掉。

当前设计目标是一次 `START_PRINT` 最多允许 **3 个已经成功恢复的独立 fault episode**，最终默认值仍要经过 RC5 实机 fault-injection 才冻结。

## Coordinator 怎么知道 fault 是当前 stage 新发生的，而不是旧状态？

不能只看 error message，也不能因为 Safety Core 历史上曾经 latch 过 `HARD_COMM_FAULT` 就自动进入 recovery。

每个 atomic stage 开始前会同时 snapshot 两个 monotonic marker：

- `transport_fault_seq`：收到新的 asynchronous I2C transport evidence 时增加；
- `preflight_failed_count`：PREARM 的 bounded readiness window 全部耗尽时增加，包括“identity/readiness 一直失败，但没有新的 async I2C report”这种情况。

一个 caught stage error 只有在 Safety Core 认为当前 fault 可以 recovery，并且这两个 marker 至少有一个在**当前 stage 内**发生增长时，才允许自动进入 Eddy recovery。

这样既能接住真实 raw transport fault，也不会漏掉 `PREARM_NOT_READY`；同时不需要解析 error string，也不会把普通 QGL / Macro / configuration error 或 stale historical state 错吞掉。

## 为什么 recovery 后要重跑完整 stage，而不是只 retry 刚才失败的 Probe？

因为 transport 恢复成功，并不会让刚才失败的 transaction 重新变有效；而且 QGL、mesh、Z calibration 在报错之前可能已经改变了一部分机械或 software state。

RC5 会把 Eddy-sensitive startup core 看成几个 atomic stage：

- CLEAN / contact datum；
- QGL 前 Z calibration；
- QGL；
- 显式 Z Home；
- bed mesh；
- mesh 后 Z calibration。

QGL fault 就整段 QGL 重跑；mesh fault 就从头重新扫网格；Z calibration fault 就重新开始 calibration transaction。

显式 Z Home 是特殊情况：如果 recovery 本身已经成功完成 fresh Safe Home，那么 recovery G28 已经满足这个 stage，不能紧接着再额外 home 一次。

## 为什么需要 coordinator，普通 Macro 不行吗？

普通 Klipper macro 不是 exception-resumable workflow。Nested command 抛 `command_error` 后，当前 macro chain 会 unwind；如果异常继续穿透到 `virtual_sdcard`，打印文件会停止并进入 error state。

所以 coordinator 只负责 Eddy-sensitive startup checkpoint，并在 eligible transport / PREARM fault 穿透 top-level `START_PRINT` 之前接住。它不会重新实现 QGL、mesh、Safe Home 或 Z calibration。

## 为什么 managed START sequence 的 MESH stage 直接调用 `BED_MESH_CALIBRATE_BASE`？

现有 `BED_MESH_CALIBRATE` wrapper 自己也在做 dependency orchestration：`has_z_offset_calibrated` 为 false 时会补做 homing / Z calibration，QGL 未 applied 时会补跑 QGL，而且它还会临时改 `square_corner_velocity`。

在 RC5 managed start core 里，这些 dependency 已经由 coordinator 负责。如果再调用 wrapper，就会出现两个 workflow owner。

因此 RC5 的 MESH stage 会自己确认前置 checkpoint，保存 / 恢复真实 SCV，然后用相同 adaptive rapid-scan 参数直接调用现有 renamed mesh implementation。原来的 wrapper 不删除，用户单独手动执行 `BED_MESH_CALIBRATE` 时仍按原行为工作。

## START recovery 需要清理哪些状态？

审计已经发现两类 state：workflow completion state 和 temporary execution state。

目前至少包括：

- `has_z_offset_calibrated`；
- mesh scan 临时修改的 `square_corner_velocity`；
- 当前 Z homing / trust state；
- active Eddy transaction / scan session pointer；
- sensor client / bulk stream lifecycle；
- Z calibration 自己的 temporary logical-Z state。

RC5 要求 success、recoverable failure 和 hard failure 三条出口都执行 terminal cleanup。

## 为什么有时 PREARM fault 发生在 Z motion 之前，最后还是必须 fresh G28？

因为 Z calibration 自己可能已经临时 relabel logical Z。它的 guarded sensor call 如果随后 abort，会主动把 Z 标成 unhomed，避免 temporary coordinate state 被错误保留为可信 Z。

所以 coordinator 的判断必须同时看两层：

```text
需要 fresh Z home，如果：
    Eddy Safety 认为 Z recovery required
    OR
    当前 homed_axes 已经不包含 Z
```

这里又分两种安全路径：

- active bed-facing fault -> transport 进入 `TRANSPORT_RECOVERED`，必须消费 one-shot armed Safe Home token；
- PREARM 在 motion 前拦住 fault，但 ZCAL 自己撤销了 homing -> transport 已经可以回到 `HEALTHY`，此时走一次普通的 PREARM-protected fresh Safe Home 即可，不应该因为没有 armed token 而锁死。

## 为什么 transport fault 后要 quarantine LDC stream？

Graceful `finish()` 可能依赖后续一个 successful batch callback 才真正 unregister client。如果 bus 已经坏到没有下一次 good batch，periodic LDC query 可能在上层 G-code 已经 abort 后继续产生新的 I2C fault。

Quarantine 强制停止 active stream，给 recovery 建立一个 clean lifecycle boundary。

## 为什么 late sample exception 一定要释放 `_active_transaction`？

HF2 实机测试抓到过这种情况：motion 已经停止，LDC stream/client 也已经清掉，但 `pull_probed()` 在后面等待 sample 时才抛 `sensor outage`。RC4 production 在这个路径上可能留下 stale `_active_transaction`，导致后续 recovery 被软件状态挡住。

RC5 会把 HF2.1 的 whole-terminal-lifecycle cleanup 正式带回 production，把同一原则补到 rapid scan，并保证 Eddy calibration movement 异常退出时也 deterministic remove client。

## QGL 已经成功后，如果后面的 mesh fault 导致 fresh G28，需要重新 QGL 吗？

通常不需要。Klipper 的 QGL `applied` state 会在新 QGL 开始或 Z motors off 时 reset；普通 G28 并不会自动清掉一个已经成功完成的 QGL。

因此 mesh stage fault 可以 recovery 后直接重扫 mesh，只要 QGL status 仍然是 applied。

但如果 fault 本身发生在 QGL 过程中，那一轮 QGL 是 incomplete，必须整段重跑。

## mesh 中途 fault 会不会留下半张“有效网格”？

Upstream bed-mesh command 在 calibration 开始时先 clear active mesh，只有完整 dataset finalize 成功后才安装新 mesh。因此 partial scan 不会被当作完整新 mesh 使用。

RC5 仍然会明确从头重跑整个 mesh stage。

## 为什么 M_Bamboo 还会动到通用 `probe.py`？

改动非常窄：通用 probe code 在某些 probe-derived persistence path 写入 pending configuration 之前，允许 active probe object 提供 optional validator。普通非 Eddy probe 没有这个 hook 时行为不变；具体 Eddy safety policy 仍留在 Eddy backend。

## RC5 是否已经证明第一次 I2C anomaly 的物理根因？

没有。

源码审计证明了很多 implementation boundary 和不一致，但不能证明为什么第一笔 NACK / TIMEOUT / BUSY 会发生。仍然可能涉及 STM32F1 peripheral state/timing、LDC1612/device interaction、signal integrity、以及 workload/timing interaction。

由于 MCU firmware 明确 out-of-scope，RC5 的目标是把这些 lower-layer fault 在 host 边界变得安全、可诊断、可有界恢复，而不是宣称消灭它们的物理来源。

## Churn / HF 测试最终推翻了什么？

最重要的是推翻了“加 50 / 100 ms quiet time 就能解决问题”的简单解释。HF2.1 trace 显示，即使 nominal dwell=0，真实 STOP-ACK 到下一次 start 的 wall-clock gap 本身也已经大约在 1.4 s 量级，因为 motion / macro overhead 占了主要部分。

这轮测试真正留下的价值是：

- 确认 active contact / homing context 中会出现真实 transport fault；
- 找到 deterministic lifecycle cleanup 的必要性；
- 验证 bounded recovery；
- 强化 PREARM 的价值；
- 证明 transport recovery、failed transaction validity 和 Z trust 必须分开。

完整统计和 experiment chronology 放在 [RC5 测试证据](RC5_TEST_EVIDENCE_CN.md)，FAQ 不重复整张 matrix。

## PLR 属于 RC5 吗？

不属于。PLR 继续作为独立 feature，它自己的 checkpoint identity 与 coordinate-trust 问题不会混进 RC5 Eddy / START recovery。

## 建议继续阅读

- [Sovol STM32F1 I2C / Eddy 根因审计](I2C_ROOT_CAUSE_AND_HOST_BOUNDARY_CN.md) — low-level source findings 与项目 cut line。
- [RC5 START 自动恢复设计](RC5_START_RECOVERY_DESIGN_CN.md) — checkpoint / recovery architecture。
- [RC5 测试证据](RC5_TEST_EVIDENCE_CN.md) — 完整 statistics 与 evidence limits。
- [Eddy Safety Engineering Design](ES_R4_ENGINEERING_CANDIDATE.md) — transaction / transport safety internals。
