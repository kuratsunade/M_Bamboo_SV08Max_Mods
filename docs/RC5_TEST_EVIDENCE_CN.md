# RC5 Eddy 通讯测试证据

[2026-09-09 offline reproduction and input hashes](RC5_OFFLINE_INSTALLER_FINDINGS.md)


## RC5 验证状态，2026 年 9 月 9 日

候选分支 `rc5-dev`，本次核对提交 `b2eb2bf3b1539e36a414ee6559404395a96b70a3`。公开基线仍是 RC4；组合实现包含 SR1、RS1、GR1。确切身份见 [版本表](../VERSION_MAP.md)。

| 证据 | 结果与边界 |
| --- | --- |
| 9 月 8 日实机记录 | 注册、Safe Home、QGL、多次直接快速扫描及完整 BED_MESH 已通过。这是交接中已有记录，不是 9 月 9 日新执行的实机测试。 |
| QGL 自然 raw34 | 一次 GR1 自动恢复通过：丢弃部分 QGL，撤销 Z 信任，隔离数据流，三次身份读取，重新 Safe Home，从第一个点重跑 QGL 并成功。无需手动恢复、固件重启或 Klipper shutdown。 |
| 快速扫描运行期间故障 | 健康扫描已通过；确切组合版在自然 active scan fault 后不 shutdown 并恢复重跑的实机证据仍待补。健康扫描不能代替该项。 |
| 完整打印 | RC4 的完整打印结果是历史证据。确切组合版仍需继续完整 START_PRINT 与真实打印观察。 |
| ZCAL | 已见接触事务成功、没有新通信故障，但相邻采样 0.020 mm 收敛规则失败；作为独立重复性问题调查。 |
| 组合运行时 mock | 9 月 9 日本地重跑通过，覆盖过期回调、普通错误、首次恢复、二次故障、嵌套 ownership 和恢复失败。不能代替实机故障证据。 |
| 原厂直接安装 | 阻塞：安装器要求 RC4 PRE/POST 或 RC5 core，拒绝原厂 START_PRINT；修改前机器快照也在此处被拒绝。没有强制迁移。 |
| RC4 升 RC5 离线模拟 | 通过：原厂配置先用提供的 RC4 包安装，再升级 RC5，两处写入；第二次 apply 零写入。没有操作打印机服务或实机。 |
| 升级后 Full Restore | 失败：虽报告成功，四个原始后端逐字节恢复、原本不存在的 Safe Home 后端被移除，但 Macro.cfg 仍残留 CONFIG_START_PRINT_CORE 及 RC5 fallback。配置恢复不完整。 |

过去的完整归档模拟缺口现已部分调查，不能标为通过。原厂安装与配置完整恢复属于发布阻塞。在修复并验证前，不应依赖该候选版 Full Restore 完成卸载或降级。配置格式逐字节相等不是恢复契约；残留运行宏才是实质问题。

证据范围：原厂配置取自用户提供的 Sovol 源码 ZIP；后端原始字节与已有 stock fixtures 一致；修改前机器导出另行执行 dry run。全部写入只发生在隔离的本地测试副本。私人归档和日志不提交仓库。

### 保留的决定

保留 PREARM 与 CLEAN、PRE_ZCAL、QGL、G28 Z、BED_MESH、POST_ZCAL 顺序。暂不改变 ZCAL 算法及 0.020 mm 阈值，不增加任意等待、推测性漂移补偿或 MCU 修改。不能宣称 raw34/raw36 已消除。

### 下一步与分工

见[当前测试计划](RC5_TEST_PLAN_CN.md)。安装恢复问题由维护侧离线验证处理；打印机侧继续正常使用及自然故障取证，不人为制造电气故障。

## Historical evidence / 历史证据

The following sections preserve earlier experiments and design stages. Current status above takes precedence.

> 分支：`rc5-dev`  
> 用途：集中记录 RC5 communication-safety 设计所依据的实机测试、故障形态、recovery 结果和被后续证据修正过的假设。  
> 边界：本文只讨论 Klipper host / Eddy Safety 行为，**不宣称已经消灭 STM32F1 / LDC1612 的底层物理根因**。

底层源码审计与 M_Bamboo 明确 cut tie 的位置见 [Sovol STM32F1 I2C / Eddy 根因审计](I2C_ROOT_CAUSE_AND_HOST_BOUNDARY_CN.md)。

## 为什么需要单独保存 Test Evidence

RC5 应该由证据推动，而不是只展示一个漂亮的 pass rate。

这份文档主要回答：

- 实际做过哪些 test；
- fault 在什么 context 发生；
- recovery 到底有没有真的走通；
- 哪些 safety mechanism 是在真实 failure 中证明有价值的；
- 哪些早期 hypothesis 后来被新 trace 推翻；
- 当前数据明确**不能证明什么**。

## 核心结论

- 反复 Eddy contact / homing churn 可以在其他行为正常时复现 intermittent transport fault。
- 已确认的 Sovol transport code 包括 `raw34 = NACK | BUSY` 与 `raw36 = TIMEOUT | BUSY`。
- HF2.1 完成完整六组 matrix：**32 attempts / 30 PASS / 2 transport faults**。
- 两个 HF2.1 fault 中，一个发生在 10 ms nominal dwell 的 active contact churn；另一个发生在 25 ms cell 真正 churn 开始之前的 initial Safe Home Z homing，因此不能归因给 25 ms dwell。
- 后续 timing instrumentation 证明 nominal dwell 并不等于真实 LDC STOP_ACK -> next START 间隔。即使 nominal 0 ms，wall-clock gap 也大约在 ~1.4 s 量级，因为中间还包含 5 mm Z lift、motion completion 和 macro overhead。
- Deterministic client removal、synchronous STOP_ACK、transport fault sequence、active-stream quarantine、PREARM 和 one-shot armed Safe Home recovery 都在 fault/recovery trace 中证明有实际价值。
- PREARM 在 RC5 中必须保留，因为它直接阻断了“transport 已经不健康却仍开始 bed-facing Z motion”这条在 PREARM 之前实际造成过 bed/nozzle strike 的 failure path。

## 历史测试

### EAR-R3E

累计记录：

- 总 attempts：**41**
- PASS：**35**
- Fault：**5**
- 另有 1 次中断 / 未归类。

Zero-dwell subset：

- **25 attempts**
- **20 PASS**
- **5 faults**

Nominal dwell >=100 ms 且完整完成的 subset：

- **15 attempts**
- **15 PASS**
- 相当于完成 **75 次成功 contact transaction**。

Cell 记录：

| Cell | 结果 |
| --- | --- |
| B3 / 0 ms | 6 attempts，5 PASS，1 fault |
| B5 / 0 ms | 5/5 PASS |
| B8 / 0 ms | 7 attempts，5 PASS，2 faults |
| B10 / 0 ms | 7 attempts，5 PASS，2 faults |
| B5 / 100 ms | 5/5 PASS |
| B5 / 250 ms | 5/5 PASS |
| B5 / 500 ms | 5/5 PASS |
| B5 / 1000 ms | 在前面 cell 完成后人工停止，不作为 completed proof |

### 对 R3E 的后续修正

当时这些数据一度让我们怀疑 `>=100 ms` 可能是一个 transport quiescence threshold。

HF2.1 的 timing trace 后来证明这个解释不成立：测试参数里的 dwell 只是 **motion 之后额外增加的等待**；真实 STOP_ACK -> next ADD_CLIENT 本来就已经有大约 ~1.4 s 的 wall-clock separation。

所以 R3E 的价值是：

> 证明 fault 可以重复出现，并且不同 workload 下 incidence 有变化。

它不能证明：

> 100 ms 是一个 magic threshold。

## EAR-R3F / HF1 / HF2

R3F 固定 BURST=8，测试 nominal dwell 0/10/25/50/75/100 ms。

早期 R3F 再次复现 transport fault。一次 nominal 10 ms run 里，transaction 约 #125 出现 `raw36`，后续又形成一串 `raw34/raw36`。当时 session 进入 persistent/escalated 状态，后面的 cell 已经失去干净比较价值。

HF1 增加 structured logging，并得到一个很重要的 negative result：

> 有些 fault 发生在 PREARM 阶段，在 measurement lifecycle 还没开始之前。

也就是说，这类 fault 前面根本没有 ADD_CLIENT / START / BATCH / STOP sequence，因此不能全部归咎于 lifecycle start/stop transition。

HF2 修复 logger lifecycle 和 automatic terminal stop，但抓到了一个独立的 host cleanup bug：

```text
真实 transport fault
-> LDC stream 已经成功 STOP
-> 后面 pull_probed() / sample-finalization 才报 sensor outage
-> _active_transaction 仍然残留
```

这会污染后面的 recovery classification。

HF2.1 把 transaction cleanup 扩展到整个 post-motion sample-finalization / acceptance 阶段，解决了这个问题。

RC5 production audit 后来又确认：这个 HF2.1 whole-terminal cleanup **并没有完整进入 RC4 production backend**。因此把这项已验证修复正式带回 production，并把同样原则扩展到 rapid scan，是 RC5 的 P0 correctness item。

## HF2.1 最终 matrix

完整结果：

- **32 attempts**
- **30 PASS**
- **2 faults**
- logger stop reason：`MATRIX_COMPLETE`
- final transport：`HEALTHY`
- recovery checks：**2/2 PASS**
- armed recovery successes：**2**
- final homed axes：`xyz`

Nominal cell：

| Nominal dwell | 结果 | 正确解释 |
| ---: | --- | --- |
| 0 ms | 5/5 PASS | 没有 confirmed churn fault |
| 10 ms | 6 attempts，5 PASS，1 fault | confirmed active-contact transport fault |
| 25 ms | 6 attempts，5 PASS，1 logged fault | fault 发生在 initial Safe Home Z homing，churn 尚未开始，不能归因给 25 ms |
| 50 ms | 5/5 PASS | clean |
| 75 ms | 5/5 PASS | clean |
| 100 ms | 5/5 PASS | clean |

如果只统计真正 churn-associated fault：

- 0 ms：0
- 10 ms：1
- 25 ms：0 confirmed churn fault
- 50 ms：0
- 75 ms：0
- 100 ms：0

这组数据**不足以证明 50 ms 是 hard threshold**。

## HF2.1 Fault #1 — Active contact churn

- nominal cell：10 ms
- attempt：4
- transaction：#84
- caller：`RUN_PROBE_VIR_CONTACT`
- fault 前 stream：active（`bulk_started=True`, `client_count=1`）
- preceding batch：没有记录 batch error / overflow
- fault：`raw34 = NACK | BUSY`
- containment：stream quarantine；client 1 -> 0；看到 STOP_ACK；bulk stopped
- recovery：no-motion identity check 多次读到 `5449/3055`，期间 fault sequence 不再增长
- 随后 one armed Safe Home G28 成功，Z trust 恢复

这个 trace 强烈支持：

> fault 是 active transport 期间真实发生的 transient transport failure，而不是 host client leak 自己制造出来的假象。

## HF2.1 Fault #2 — Safe Home Z homing

- nominal matrix cell：25 ms
- timing：8-contact churn sequence 真正开始之前
- context：`HOMING`

因此这次 event 不能作为“25 ms churn dwell 有问题”的证据。

## Timing correction

Churn sequence 是：

```text
RUN_PROBE_VIR_CONTACT
G91
G1 Z5 F300
G90
M400
G4 P{dwell}
RUN_PROBE_VIR_CONTACT
```

所以 `DWELL_MS` 只是 5 mm Z lift 和 completed motion **之后**额外加的一段时间。

Lifecycle trace 显示，即使 nominal dwell 很低，LDC STOP acknowledgement 到下一次 measurement client/start 之间的 median wall-clock separation 也大约在 ~1.4 s。

因此 matrix 可以用来复现 fault、观察 recovery，但不是一个真正控制 STOP_ACK -> START gap 的实验。

## 测试支持哪些 safety behavior

### PREARM

PREARM 必须保留。

在 PREARM 之前，实机确实发生过 unhealthy Eddy/transport state 后继续 bed-facing Z motion，最终造成 nozzle/bed contact。加入 PREARM 后，transport 还没有被证明 stable 时，危险 Z transaction 不会开始。

PREARM 不保证 transaction ACTIVE 后不会出现新 fault。它解决的是更窄但非常重要的问题：

> transport 已经不健康时，不允许直接开始危险下探。

### Fault sequence + identity reads

一次正确的 LDC identity read 不能单独作为 health proof。

Recovery 要求：

- repeated expected ID：`0x5449 / 0x3055`；
- 同时 monotonic transport fault sequence 不增长；
- 每次 read 后给 reactor 足够机会接收 Sovol asynchronous I2C fault report。

### Active stream quarantine

HF2.1 trace 证明 fault containment 能把 periodic stream 拉回：

```text
client_count=0
bulk stopped
STOP_ACK observed
```

这明显降低了“后续 fault storm 只是 host client leak”这个解释的可信度。

### Failed transaction 永不 retry

发生 bed-facing fault 的 transaction 直接 abort。

允许 recovery 时，做的是：

```text
fresh transport health check
+
fresh Safe Home（如果 Z 需要重建）
```

不是 replay 刚才失败的 Probe / Homing transaction。

## RC5 `START_PRINT` 自动恢复目标

RC5 区分“一个 fault episode”和“整个 session / print start”。

当前设计目标：

```text
MAX_START_AUTO_RECOVERIES = 3
MAX_RECOVERY_ATTEMPTS_PER_EPISODE = 1
```

真正重要的是 episode semantics：

1. 同一个 fault episode，如果需要 rebuild Z，只允许 **1 次** armed Z recovery；
2. 这一次 recovery 失败，立刻停止；剩余 total budget 不能拿来给同一个 episode 再 blind G28；
3. recovery 成功以后，刚才失败的 **atomic startup stage 必须完整成功**，这个 episode 才算真正结束；
4. 如果 stage 还没完成又发生第二次 transport fault，说明当前 stage 仍然 unstable，应停止，而不是继续进入 recovery loop；
5. 只有 stage 已经 clean complete 以后，后面真正新的 fault 才能建立新的 independent episode，并消耗下一格 total budget；
6. total start budget 负责阻止一连串“每次都看似能恢复”的 fault 无限持续。

这比单纯数新的 fault-seq 更严格，因为它要求两次自动 recovery 之间必须出现明确的 workflow progress checkpoint。

总 budget 的最终数字仍要由 RC5 自然故障实机覆盖 验证后冻结。

## 这些 statistics 不能证明什么

当前数据不能证明：

- 某一个具体 dwell threshold 可以消灭问题；
- PREARM 能消灭 motion ACTIVE 后才发生的新 fault；
- 第一笔 I2C anomaly 的 STM32F1 / LDC1612 / electrical 物理根因已经完全确定；
- recovery 必须 power cycle；
- fault 一定纯软件或一定纯硬件；
- `3` 就一定是最终最优 `START_PRINT` recovery budget。

当前 evidence **足以支持**：继续保留 fail-closed bed-facing safety gate、deterministic lifecycle cleanup、failed-transaction strict invalidation，以及 bounded checkpoint-based auto recovery；而 MCU 以下的 low-level behavior 继续保持在 M_Bamboo 修改边界之外。
