# 技术 FAQ : 已确认的 Sovol Eddy / I2C 安全问题

> 范围：**现有主机层安全架构及 RC5 操作恢复增量。** 下文区分源码事实、实机观察与推断。确切测试状态见[测试证据](RC5_TEST_EVIDENCE_CN.md)，安装验收见[离线验证](../VALIDATION.md)。

## 为什么 Eddy probe 出错后还可能继续产生危险 Z 动作？

Sovol 的 STM32F1 LDC1612 路径可以检测 I2C transaction fault 并上报 host，但没有在 LDC sample API 边界把这次读取明确标记为 invalid。STM32F1 上 `sensor_ldc1612.c` 有意跳过 `i2c_shutdown_on_err(ret)`；同时 `read_reg()` 返回 `void`，caller 无法知道寄存器读取是否成功。因此 sampling path 仍可能继续解析 status/data，甚至在 I2C read 失败后继续调用 `check_home()`。

M_Bamboo 策略：确认的 LDC transport fault 必须成为一等安全证据。后续 Eddy data 视为 tainted；应锁存通信故障，在可安全实现的情况下终止正在进行中的 Eddy probe，撤销 Z trust，并阻止后续 Eddy-dependent Z 操作，直到所需的通信与 Z 信任重新建立。要求重启的故障继续阻断；历史错误本身不会永久禁止已经验证的恢复。

## Sovol 的 `err_code=36` 到底是什么？

Sovol 修改后的 STM32 I2C driver 返回 bitmask，`I2C_BUS_*` enum 值被当作 bit position。于是 `36` 表示：

- bit 2：`I2C_BUS_TIMEOUT`
- bit 5：`I2C_BUS_BUSY`

因此 `36 = 4 + 32 = TIMEOUT | BUSY`。

这和其它 Eddy 文档中显示的 amplitude 数值 `(36)` / `(48)` 不是同一语义。

## 除了 36，还有哪些 I2C err_code 需要关注？

已知相关 bit：

- `1 << 1` (`2`)：NACK
- `1 << 2` (`4`)：TIMEOUT
- `1 << 5` (`32`)：BUSY
- `1 << 7` (`128`)：BERR / bus error

因此可能出现 34、36、38、130、132、134、162、164、166 等组合。M_Bamboo 不应只 special-case 36，而应解析整个 bitmask。未知 non-zero bit 也应明确报告并保守阻断危险操作。

## Sovol 的 error representation 有什么问题？

修改后的 STM32 driver 使用 bitmask (`1 << I2C_BUS_*`)，但后续部分代码仍用 `ret == I2C_BUS_BUSY` 这种 enum 直接比较。`I2C_BUS_BUSY` 的 enum 值是 5，而 bitmask 是 32，因此作者想要的 BUSY retry path 在 representation 上并不自洽。

通用 `i2c_shutdown_on_err()` 的 switch 也按 upstream 的“单一 enum status”设计，直接套在 Sovol bitmask 上可能映射错误。SV08 Max 的 Eddy MCU 是 STM32F1，而 Sovol 又对该 MCU family 直接绕过 shutdown。

## LDC register read 失败后，坏数据还会被当作 sensor data 使用吗？

从代码结构看，会有这种风险。STM32F1 上 `read_reg()` 不向 caller 传播 I2C status；`read_reg_status()` 因而没有 validity signal；`ldc1612_query()` 仍可能继续 DATA0 读取并执行 `check_home()`。结果既可能是 missed trigger，也理论上可能出现 false trigger，如果 stale/invalid bytes 恰好满足 trigger condition。

## Sovol 是否完整保留每一次 I2C error？

不一定。部分 byte-write loop 每次都覆盖 `ret`，而不是第一次失败后停止；因此后一次返回值可能覆盖前面的 error。STOP phase 的 `i2c_wait()` 结果也被直接丢弃。当前 upstream Klipper 的相关路径会保留第一处失败并传播 STOP error。

## `ldc1612_i2c_report` 一定来自 LDC1612 吗？

协议设计层面并不保证。Sovol 是从通用 STM32 hardware-I2C driver 发送这个消息，而且 payload 没有 device address、bus ID 或 transaction owner。当前测试的 SV08 Max 配置里，`extra_mcu:i2c2` 看起来由 Eddy LDC1612 独占，因此对当前机器可以合理归因；future installer/preflight 应验证这个前提，不能永远硬编码。

## 为什么当前 Python `i2c_err_flag` 不是实时 bus-health？

MCU 只有出错时才发送 `ldc1612_i2c_report`，后续正常 transaction 不会发送 `err_code=0` 清状态。因此 `i2c_err_flag` 实际更像 last observed error / historical evidence，不代表 bus 此刻仍然坏。M_Bamboo 应从“fault event”本身锁存 safety state，并保存事件 metadata，而不是轮询该变量判断实时健康度。

## ES-R4 出现后，ES-R3 的哪些保护仍然需要？

- Z invalidation 仍需保留，因为 I2C 健康时也可能发生 geometry/no-trigger。包内 `homing.py` 仅供审计参考，不由 installer 部署，不能从文件存在推断它被安装。
- dynamic non-contact descent envelope 仍需保留，因为它限制非通信原因导致的 blind descent；在不刷 MCU firmware 的条件下尤其重要。
- 已有 trsync communication/sensor-error handling 仍需保留，因为它覆盖的是另一个 transport layer。
- “`ldc1612.py` 只做 telemetry”这条旧结论被新证据推翻：它仍应负责硬件 decode/source，但必须把 transport-fault event 交给 Eddy Safety Core。

## M_Bamboo 是否应该重刷或修改 MCU firmware？

不修改。除非用户明确改变项目边界，否则不修改、编译或刷写 MCU。方案是消费 Sovol 已经提供的 asynchronous I2C error report，在最底层 host-side hardware layer 解析，然后把 structured fault 交给 `probe_eddy_current.py`，并复用 Klipper 原生 trsync/homing machinery 去终止和撤销危险操作。MCU-level defects 会记录在技术文档中，但 release 继续保持 user-space/Klipper 修改边界。

## 与 ES-R4 直接相关、已经确认的 Sovol Eddy/I2C 实现问题

当前 SV08 Max Sovol fork 的 I2C/Eddy error handling 存在多处内部语义不一致。ES-R4 记录这些问题，是因为我们选择在 host/Python 层修复其 safety consequence，而不是要求用户重新编译/刷写 MCU firmware。

- 修改后的 STM32 I2C driver 返回的是 `1 << enum_index` 形式的 **bitmask**，但部分后续代码仍把 enum 数值本身当返回 error code 比较，导致 BUSY retry / error mapping 语义可能失效。
- STM32F1 的 LDC register read 即使已经上报 I2C failure，也可能不把失败结果传播给 LDC caller；runtime sampling 因而缺少可靠的数据有效性 contract。
- `ldc1612_i2c_report` 实际从通用 STM32 I2C driver 发出，却没有携带 device identity，命名具有误导性。
- `i2c_err_flag` 是 last-observed error，而不是实时 bus health；成功事务不会自动清零。ES-R4 因此使用单调递增的 `transport_fault_seq` 作为 transaction-local truth。
- Sovol runtime `SENSOR_ERROR` 路径会把 `reg_drive_current=0` 写入待保存配置。ES-R4 删除这一行为：runtime fault 不应静默修改持久校准状态。
- Drive-current calibration 原本会在没有 transaction-local transport integrity guard 的情况下消费寄存器值。ES-R4 在 calibration transaction 期间只要 fault sequence 变化，就拒绝持久化结果。

## 为什么不直接把整套 Klipper 更新到最新 upstream？

SV08 Max 的 Sovol stack 包含 custom Eddy contact、custom MCU commands、touchscreen-facing G-code ABI、定制 Z calibration 等依赖。M_Bamboo 采用 selective semantic backport：

- 优先借鉴/回移结构化错误传播、transaction taint、session cleanup、abort handling 等低风险正确性语义；
- 如果替换 implementation 会要求 MCU 重刷或破坏已经实机验证的 contact/Z-calibration 流程，则保留现有 Sovol ABI；
- 尽量靠近 Official Klipper 的 ownership boundary 与 safety invariant，但不机械复制当前 fork 并不存在依赖的新架构。

## 为什么 ES-R4 同时记录 sensor fault sequence 和 “handled” sequence？

Sovol 的 I2C error 从 serial receive callback 上报。raw callback 可以先让
`transport_fault_seq` 增加，而 reactor 中真正负责 latch `HARD_COMM_FAULT`
的 callback 还没来得及执行。如果只看 transaction start/end sequence，新
operation 有可能正好在这个调度间隙开始，并把已经增加后的 sequence 当作
自己的健康起点。

ES-R4-EC2 因此规定：只要
`transport_fault_seq > transport_fault_seq_handled`，新的 Eddy operation 就
直接拒绝启动。raw evidence 本身具有 authority，安全性不依赖 callback
调度运气。

## 为什么 fault state 可能从 `PROBE_NO_TRIGGER` 升级成 `HARD_COMM_FAULT`？

Fault severity 只能单向升级。`PROBE_NO_TRIGGER` 的证据较弱，因为严重 gantry
几何问题和 sensor failure 都可能产生它；如果稍后到达明确的 I2C transport
fault，EC2 会把当前分类升级成 `HARD_COMM_FAULT`，同时单独保留 first fault
用于 evidence timeline。更强的后续事实不能被“最先出现的症状”永久遮住。


## 为什么 ES-R4-EC2 现在也会修改通用 `probe.py`？

改动刻意保持很小：`ProbeCommandHelper` 在 `PROBE_CALIBRATE` 或
`Z_OFFSET_APPLY_PROBE` 准备写入 pending `z_offset` 前，查询当前 probe object
是否提供 optional persistent-config validator。普通 probe 没有这个 hook 时
行为完全不变；Eddy backend 则实现该 hook，并复用同一 fault latch / pending
transport fault gate。

这样比重新 unregister/re-register G-code command 更干净，同时也没有把 Eddy
具体 policy 塞进通用 `probe.py`。


## 为什么 Z-offset calibration 在 guarded sensor call 提前 abort 时还要显式撤销 Z trust？

`Z_OFFSET_CALIBRATION` 会为了 `USE_CURRENT_Z_ALLOWANCE` 临时调整逻辑 Z 坐标，而不移动电机。EC2 加强 preflight 后，pending transport fault 可能在 `HomingMove` 尚未开始前就拒绝 contact/non-contact operation；此时通用 `homing.py` 没有机会通过 probe failure 撤销这次临时 Z trust。EC2 因此包装这些 sensor call，任何 command error 都显式把 Z 标记为 unhomed，避免临时逻辑 rebase 被错误保留为可信坐标。

## 哪些 persistent calibration 路径会经过统一 Eddy fault authority？

EC2 覆盖当前项目相关的持久化入口：drive-current calibration、手动 `PROBE_EDDY_CURRENT_CALIBRATE`、标准 `PROBE_CALIBRATE` 与 `Z_OFFSET_APPLY_PROBE`。通用 `probe.py` 只新增一个可选 validation hook；非 Eddy probe 行为保持原样。核心 invariant 是：transport-tainted 或 fault-latched 的 Eddy data 绝不能进入 pending persistent configuration。


---

## `NACK | BUSY` 是否意味着 Eddy sensor 已经坏了？

不意味着。`BUSY` 在这版 Sovol STM32F1 driver 中通常作为 transaction 已经因 NACK/TIMEOUT 失败后观察到的附加 bus-state evidence；一次 `NACK | BUSY` 足以判定**当前 transaction 不可信**，但不能单凭这一点证明 sensor hardware 永久损坏。EC2 因此立即 stop/taint/abort 当前 action，并在 bed-facing Z context 撤销 Z trust；随后允许用户运行无运动 `M_BAMBOO_EDDY_RECOVERY_CHECK`。多次有效 LDC identity read 且没有新的 `transport_fault_seq` 才能恢复通信信任。需要恢复 Z 时，它仍不可信，只允许一次 fresh Safe Home。运动和坐标失效前捕获的 PREARM 故障可能保留 Z 信任。

异步 fault callback 不启动流程恢复。受支持的最外层同步操作可在失败工作结束后恢复，这与继续重试正在进行的传感器事务不同。PREARM 也可在运动前通过有界、无运动检查吸收暂态故障。一旦探测已开始，新故障仍中止原事务。操作恢复范围见后文。


## 为什么 G-code 已经失败后 Eddy fault 仍可能无限重复？

Sovol/Official lineage 的 `BatchBulkHelper` 只有在后续 batch 真正调用 client callback 且 callback 返回 `False` 时，才会注销 client 并调用 stop callback。如果 I2C 已经故障到再也收不到成功 batch，仅设置 `finish()` flag 并不足以真正停掉 stream；MCU periodic LDC query 因此可能在上层 G-code 已 abort 后继续产生新的 I2C error report。FS1 通过确定性 client removal 与 runtime transport fault 后的 immediate LDC stream quarantine 修复该 lifecycle hole；quarantine 会停止 periodic query 并重置 batch helper，使后续显式 recovery 可以重新启动干净 stream。

## 为什么要加入 pre-arm transport quiescence gate？实机测试结果如何？

### 它要解决的问题

在加入 pre-arm hardening 之前，真实 SV08 Max 已经复现过 Eddy Z homing transaction 进入 ACTIVE 后发生 transport fault：`err_code=34`。按 Sovol STM32F1 bitmask 语义，它是 `NACK | BUSY`。一旦 bed-facing transaction 已经 ACTIVE，transport integrity 已经丢失，正确的 safety response 只能是 stop / taint / abort，并在适用时撤销 Z trust；在已经开始向床运动后继续 retry sensor 会削弱安全模型。

结合真实故障发生位置和 Sovol I2C implementation，我们形成了一个更窄的工作假设：至少一部分 raw-34 可能集中发生在 **I2C / measurement-session transition 边界**，也就是新的 Eddy action 在 transport/peripheral 尚未完全 quiescent 时开始。

### M_Bamboo 做了什么

ES-R4 transport hardening 因此在 Safe Home Z、普通/contact probe session、Eddy calibration、rapid bed-mesh scan 等关键入口前加入 **pre-arm transport quiescence gate**。这个 gate 明确是无运动的：先做 bounded settle，再读取已知 LDC manufacturer/device identity，并确认单调递增的 transport fault sequence 没有变化，只有通过后才允许 motion/session arm。

它不是 active-motion retry。若 transient 发生在 Z 仍静止的 pre-arm 阶段，可以 bounded 地重新确认 readiness，并要求后续 clean window；但一旦 HOMING/PROBE 已经 ACTIVE，任何 confirmed transport fault 仍严格执行 stop -> taint -> abort。

它的设计目标是：

`不要在 transport 尚未稳定时启动 safety-critical Eddy transaction`

而不是：

`先开始下降，通信失败后再继续 retry sensor`。

### 历史实机结果，2026 年 8 月

加入 pre-arm gate 后，实机已经覆盖反复 G28 / Safe Home、direct contact probe、反复 `CLEAN_NOZZLE`、反复 Z-offset calibration、QGL、adaptive rapid mesh、final XY re-home，以及一次完整 slicer 驱动的 `START_PRINT`、真实 cube 打印和打印后的 Eddy status 检查。当时记录的 post-print session 的 `M_BAMBOO_EDDY_STATUS` 记录为：**30 次 pre-arm checks，0 transport faults，0 transient recoveries，0 pre-arm failures，0 forced stream quarantines，0 repeated-fault suppressions**。

这是该会话中的健康流程兼容证据，不能单独证明故障发生率因果下降，也不能确定可靠的最短等待时间。后续 churn 证据不支持通用 50/100 ms 阈值。PREARM 的价值在于拒绝不健康状态下启动动作；后续实验和修正后的假设见[测试证据](RC5_TEST_EVIDENCE_CN.md)。

仍需要更长时间 soak，但此前最关键的自然 fault-path gate 已经跨过。2026-08-20，一次自然发生的 raw `34`（`I2C_BUS_NACK | I2C_BUS_BUSY`）出现在 active contact verification 中：当前动作被安全中止，Z trust 被撤销，active LDC stream 被 quarantine；随后无运动 recovery check 以三次正确的 LDC identity read 且 fault sequence 不增长通过，一次 armed Safe Home `G28` 重新建立 transport 与 Z trust，机器无需 firmware reset 即继续完成后续 START_PRINT 准备并开始打印。这是一次真实事件的端到端验证，不代表已经获得足够统计样本证明以后所有 transport fault 都会完全相同。

## Pre-arm prevention 和 FS1 fault-storm containment 有什么区别？

它们处理的是同一 failure chain 的不同阶段：

- **Prevent : pre-arm quiescence gate：** 尽量不让 unsettled transport state 进入 safety-critical motion/session。
- **Detect/Stop : ES-R4 transaction safety：** 如果 motion ACTIVE 后仍发生 transport fault，则 stop / taint / abort，并在需要时撤销 Z trust。
- **Contain : FS1 stream quarantine：** 如果 faulted bulk stream 在 command abort 后仍可能持续产生 I2C report，则确定性注销 client 并强制停止 periodic LDC stream。
- **Recover : recovery check + fresh Safe Home Z：** 将 transport health 与 coordinate trust 分开重新建立；需要时只有 fresh trusted Z home 才恢复 Z。

刻意把这几层分开非常重要：pre-arm 负责降低进入危险状态的概率；FS1 则保证即使 fault 仍然发生，也不能再次演变成无限 fault storm。

## RC5 在现有安全核心之上增加了什么？

SR1 协调既有 CLEAN、PRE_ZCAL、QGL、G28 Z、BED_MESH、POST_ZCAL 阶段。RS1 使快速扫描会话明确结束，避免排队中的 lookahead 回调访问已释放的 gather。GR1 为 G28、RUN_PROBE_VIR_CONTACT、CLEAN_NOZZLE、Z_OFFSET_CALIBRATION、QUAD_GANTRY_LEVEL、BED_MESH_CALIBRATE 提供最外层同步恢复 owner。BASE 及任意校准命令不自动获得这一能力。

Safety 标签保持不变，确切组合身份以[版本表](../VERSION_MAP.md)中的后端 hash 为准。RS1 不修改健康快速扫描速度、高度、路径、采样窗口、时间语义或插值。

## 什么情况下重跑操作，什么情况下必须停止？

恢复资格要求本次 owner 调用中出现新的 `transport_fault_seq` 或 `preflight_failed_count` 证据；普通错误直接抛出。失败工作结束后，先无运动验证通信，必要时通过 fresh Safe Home 重建 Z，再完整重跑操作一次，不单独续跑失败的 QGL 点或部分网格。

START_PRINT 内由 SR1 保持 owner，嵌套 GR1 直接调用原 handler。每阶段调用最多一次恢复，整个 START 最多三个独立事件。完整成功前再次故障、或恢复失败即终止。异步 I2C、bulk、lookahead 和 flush 回调不启动流程恢复。恢复成功也不会使被丢弃的数据重新有效。

实现细节见[恢复管理设计](RC5_RECOVERY_SUPERVISOR_DESIGN_CN.md)及[START 设计](RC5_START_RECOVERY_DESIGN_CN.md)，接口以[命令参考](COMMAND_REFERENCE_CN.md)为准。

## 为什么保留现在的 START_PRINT 顺序和接触阈值？

已观察到 contact verification 的离散程度大于同会话 Eddy Z home trigger。相邻采样 0.020 mm 规则失败、但通信标记不增长，不能视作 I2C 故障。存在较大噪声的 contact 测量也不足以证明更小的机械漂移。快速网格导致下垂及需要推测性补偿都尚未证实。

继续保留两阶段校准、PREARM 和 ZCAL 阈值，等待更强证据。协调器清理启动临时状态、管理 mesh 阶段设置，不替换底层测量算法。应记录的 contact 序列与坐标变换控制见[测试计划](RC5_TEST_PLAN_CN.md)。

## 底层源码审计放在哪里？

[Sovol I2C 源码审计](I2C_ROOT_CAUSE_AND_HOST_BOUNDARY_CN.md)保留驱动历史、BUSY 引脚查找问题及失败事务边界分析，说明主机层能处理的范围和本项目不修改的 MCU 行为。

## PLR 是否属于当前候选？

不属于，PLR 仍为后续独立功能。Sovol stock resume 方案依赖 coordinate fabrication 与 commandline 文本匹配，不满足当前 coordinate-trust 与 checkpoint identity 要求。正常打印不依赖该后续 PLR 功能。

## Installer 是否实现 downgrade？

没有通用降级引擎。预期路径是已验证的 Full Restore，再使用目标历史版本 installer。当前开发候选存在配置恢复缺陷，尚不能依赖这条路径。见[部署与恢复](DEPLOYMENT_AND_ROLLBACK.md)。

## Full Restore 应当保留什么？

契约要求保留无关用户 cfg 内容及 SAVE_CONFIG，移除或逆转项目拥有的 block，从 `extras/mb_bak/` 恢复原始后端，并删除记录为原本不存在的文件。这是必须满足的契约，不是当前候选已满足它的声明。[离线发现](RC5_OFFLINE_INSTALLER_FINDINGS.md)记录了残留 START_PRINT block 的问题。
