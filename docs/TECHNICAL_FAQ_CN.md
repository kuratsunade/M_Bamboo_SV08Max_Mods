# 技术 FAQ — 已确认的 Sovol Eddy / I2C 安全问题

> 状态：**v1.0.0-rc4 Technical Reference。** Healthy path 已完成实机验证，并已在一次自然发生的 FS1.1 raw-34 事件中完成端到端 fault/recovery 实机验证；长期自然故障 soak 仍继续。本文明确区分 source/code fact、hardware observation、engineering inference 与 remaining uncertainty。

## 为什么 Eddy probe 出错后还可能继续产生危险 Z 动作？

Sovol 的 STM32F1 LDC1612 路径可以检测 I2C transaction fault 并上报 host，但没有在 LDC sample API 边界把这次读取明确标记为 invalid。STM32F1 上 `sensor_ldc1612.c` 有意跳过 `i2c_shutdown_on_err(ret)`；同时 `read_reg()` 返回 `void`，caller 无法知道寄存器读取是否成功。因此 sampling path 仍可能继续解析 status/data，甚至在 I2C read 失败后继续调用 `check_home()`。

M_Bamboo 策略：确认的 LDC transport fault 必须成为一等安全证据。后续 Eddy data 视为 tainted；应锁存通信故障，在可安全实现的情况下终止正在进行中的 Eddy probe，撤销 Z trust，并阻止后续 Eddy-dependent Z 操作直到 restart。

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

从代码结构看，会有这种风险。STM32F1 上 `read_reg()` 不向 caller 传播 I2C status；`read_reg_status()` 因而没有 validity signal；`ldc1612_query()` 仍可能继续 DATA0 读取并执行 `check_home()`。结果既可能是 missed trigger，也理论上可能出现 false trigger——如果 stale/invalid bytes 恰好满足 trigger condition。

## Sovol 是否完整保留每一次 I2C error？

不一定。部分 byte-write loop 每次都覆盖 `ret`，而不是第一次失败后停止；因此后一次返回值可能覆盖前面的 error。STOP phase 的 `i2c_wait()` 结果也被直接丢弃。当前 upstream Klipper 的相关路径会保留第一处失败并传播 STOP error。

## `ldc1612_i2c_report` 一定来自 LDC1612 吗？

协议设计层面并不保证。Sovol 是从通用 STM32 hardware-I2C driver 发送这个消息，而且 payload 没有 device address、bus ID 或 transaction owner。当前测试的 SV08 Max 配置里，`extra_mcu:i2c2` 看起来由 Eddy LDC1612 独占，因此对当前机器可以合理归因；future installer/preflight 应验证这个前提，不能永远硬编码。

## 为什么当前 Python `i2c_err_flag` 不是实时 bus-health？

MCU 只有出错时才发送 `ldc1612_i2c_report`，后续正常 transaction 不会发送 `err_code=0` 清状态。因此 `i2c_err_flag` 实际更像 last observed error / historical evidence，不代表 bus 此刻仍然坏。M_Bamboo 应从“fault event”本身锁存 safety state，并保存事件 metadata，而不是轮询该变量判断实时健康度。

## ES-R4 出现后，ES-R3 的哪些保护仍然需要？

- `homing.py` 的 Z invalidation 仍需保留，因为 I2C 完全健康时也可能发生 geometry/no-trigger。
- dynamic non-contact descent envelope 仍需保留，因为它限制非通信原因导致的 blind descent；在不刷 MCU firmware 的条件下尤其重要。
- 已有 trsync communication/sensor-error handling 仍需保留，因为它覆盖的是另一个 transport layer。
- “`ldc1612.py` 只做 telemetry”这条旧结论被新证据推翻：它仍应负责硬件 decode/source，但必须把 transport-fault event 交给 Eddy Safety Core。

## M_Bamboo 是否应该重刷或修改 MCU firmware？

RC4 不需要。优先方案是消费 Sovol 已经提供的 asynchronous I2C error report，在最底层 host-side hardware layer 解析，然后把 structured fault 交给 `probe_eddy_current.py`，并复用 Klipper 原生 trsync/homing machinery 去终止和撤销危险操作。MCU-level defects 会记录在技术文档中，但 release 继续保持 user-space/Klipper 修改边界。

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

不意味着。`BUSY` 在这版 Sovol STM32F1 driver 中通常作为 transaction 已经因 NACK/TIMEOUT 失败后观察到的附加 bus-state evidence；一次 `NACK | BUSY` 足以判定**当前 transaction 不可信**，但不能单凭这一点证明 sensor hardware 永久损坏。EC2 因此立即 stop/taint/abort 当前 action，并在 bed-facing Z context 撤销 Z trust；随后允许用户运行无运动 `M_BAMBOO_EDDY_RECOVERY_CHECK`。只有多次有效 LDC identity read 且检查期间没有新的 `transport_fault_seq` 才进入 `TRANSPORT_RECOVERED`。该状态仍不恢复 Z，只 armed 一次 fresh Safe Home `G28`。

为什么不在 fault callback 里自动 scan/retry？因为 Sovol ABI 同时存在 synchronous I2C response 与 asynchronous error report，host ordering 尚未完全实测。显式 recovery check 可以在每次 read 后给 reactor 留 settle window，并且不会自动触发任何 Z motion。

EC2 现在只在**运动开始前**做一个更窄的自动例外：pre-arm readiness gate 可以 bounded 地重复无运动 identity read。如果 transient `NACK|BUSY` 在这里被吸收，因为从未发生 Z descent，所以 Z trust 不需要撤销。这和 retry active probe 是两件完全不同的事；一旦 trsync/Z motion 已 ACTIVE，任何 transport fault 仍立即 abort + taint 当前 transaction。


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

### 目前实机结果

加入 pre-arm gate 后，实机已经覆盖反复 G28 / Safe Home、direct contact probe、反复 `CLEAN_NOZZLE`、反复 Z-offset calibration、QGL、adaptive rapid mesh、final XY re-home，以及一次完整 slicer 驱动的 `START_PRINT`、真实 cube 打印和打印后的 Eddy status 检查。最近一次 post-print session 的 `M_BAMBOO_EDDY_STATUS` 记录为：**30 次 pre-arm checks，0 transport faults，0 transient recoveries，0 pre-arm failures，0 forced stream quarantines，0 repeated-fault suppressions**。

这已经是很强的正面证据：pre-arm gate 不只是“没有带来 regression”，而且很可能确实显著降低了 observed fault incidence；同时它也支持、但尚不能证明“部分 raw-34 主要发生在 transition boundary”的工作假设。因此项目文档会表述为 **显著降低目前观察到的 raw-34 发生率**，而不会宣称 error 34 已被彻底消除。

仍需要更长时间 soak，但此前最关键的自然 fault-path gate 已经跨过。2026-08-20，一次自然发生的 raw `34`（`I2C_BUS_NACK | I2C_BUS_BUSY`）出现在 active contact verification 中：当前动作被安全中止，Z trust 被撤销，active LDC stream 被 quarantine；随后无运动 recovery check 以三次正确的 LDC identity read 且 fault sequence 不增长通过，一次 armed Safe Home `G28` 重新建立 transport 与 Z trust，机器无需 firmware reset 即继续完成后续 START_PRINT 准备并开始打印。这是一次真实事件的端到端验证，不代表已经获得足够统计样本证明以后所有 transport fault 都会完全相同。

## Pre-arm prevention 和 FS1 fault-storm containment 有什么区别？

它们处理的是同一 failure chain 的不同阶段：

- **Prevent — pre-arm quiescence gate：** 尽量不让 unsettled transport state 进入 safety-critical motion/session。
- **Detect/Stop — ES-R4 transaction safety：** 如果 motion ACTIVE 后仍发生 transport fault，则 stop / taint / abort，并在需要时撤销 Z trust。
- **Contain — FS1 stream quarantine：** 如果 faulted bulk stream 在 command abort 后仍可能持续产生 I2C report，则确定性注销 client 并强制停止 periodic LDC stream。
- **Recover — recovery check + fresh Safe Home Z：** 将 transport health 与 coordinate trust 分开重新建立；需要时只有 fresh trusted Z home 才恢复 Z。

刻意把这几层分开非常重要：pre-arm 负责降低进入危险状态的概率；FS1 则保证即使 fault 仍然发生，也不能再次演变成无限 fault storm。

## PLR 是否属于 RC4？

不属于。PLR 已明确从 RC4 defer。Sovol stock resume 方案依赖 coordinate fabrication 与 commandline 文本匹配，不满足当前 coordinate-trust 与 checkpoint identity 要求。正常打印和 RC4 safety stack 不依赖 PLR。

## RC4 是否实现 downgrade？

没有。RC4 不提供 generic downgrade 命令。Full Restore 是唯一权威的 release removal path；Restore 完成后，用户可以使用目标历史 release 自己的 exact installer artifact 安装该版本。

## Full Restore 会保留什么？

M_Bamboo-owned region 之外的用户 cfg 修改会被保留。M_Bamboo 增加的 cfg block 会删除或逆变换，backend Python 从集中 `extras/mb_bak/` original archive 恢复；manifest 记录为 originally absent 的 M_Bamboo Python 会被删除。
