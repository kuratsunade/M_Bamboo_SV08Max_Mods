# Sovol STM32F1 I2C / Eddy 根因审计与 M_Bamboo 边界设计

> 状态：**RC5 工程技术文档**  
> 用途：记录 SV08 Max Eddy 通讯问题的源码证据、根因边界，以及 M_Bamboo 明确选择在哪一层停止继续向下修改。  
> 项目原则：**M_Bamboo 不修改、不重新编译、不刷写、也不替换 MCU 固件。** 对 MCU 源码的审计只用于判断上层哪些信息可以信、哪些结果必须保守处理。

## 结论先行

SV08 Max 的 Eddy 通讯问题并不是某一处 Python 代码单独造成的。底层使用的是 Sovol 定制的 STM32F1 I2C / LDC1612 实现。Sovol 当时的目标其实很合理：STM32F1 偶发一次 I2C 抖动，不应该直接把整台打印机带入 shutdown。因此他们没有照搬 Klipper 原本较为强硬的失败策略，而是增加了更细的错误位、I2C 外设恢复以及主机端重读机制。

问题在于，这套从“单一错误码”向“可恢复 + 位图错误信息”的迁移没有完全收口。当前固件能够提供很有价值的 `NACK | BUSY`、`TIMEOUT | BUSY` 等信息，但 MCU 内仍存在按照旧的单值错误语义判断的代码；STM32F1 的 BUSY 恢复函数又通过错误的方式反查 SCL/SDA 引脚；同时，失败的 I2C 读取并没有在所有路径上严格阻止后续 LDC 采样或归零逻辑继续使用数据。

M_Bamboo 在这里明确 **cut tie**：不继续向 MCU 固件和物理总线层接管责任。我们把 MCU 上报的通讯错误视为可靠的“故障证据”，但不因为后面又收到一笔响应，就相信刚才失败的 Eddy 事务重新变得有效。

因此 RC5 的目标不是保证 `raw34` / `raw36` 永远不出现，而是保证底层通讯错误不会静默演变成可信的 Probe 结果、危险的 Z 下探，或者把 `START_PRINT` 的前后依赖关系搞乱。

## 1. 本次审计的 Sovol 源码来源

真机归档中当前使用的 Klipper checkout 为：

- 分支：`klipper-eddy_contact_probe`
- 当前 commit：`d4031b31daa4c896365f5c688a472086f6e43f49`
- 日期：2025-10-18
- 提交信息：`zoffset校准增加前置电流校准动作`

这个仓库并不是保留完整 Official Klipper ancestry 的普通 fork，因此无法简单通过 merge-base 找到某一个上游基准点。不过 Sovol 自己加入 STM32F1 I2C 恢复逻辑的提交历史保留得很完整。

2024 年 12 月的关键提交包括：

- `93b121b...`：发现 I2C 受干扰后可能读到错误的 LDC 身份信息，因此加入重读；
- `060eada...`：STM32F1 禁用 `i2c_shutdown_on_err`，提交说明中直接写有“有待优化”；
- `79c9992...`：增加 I2C bus 错误码；
- `ee6f394...`：修改 `i2c_busy_errata`、`i2c_wait` 及错误退出逻辑；
- `265b3f7...`：给 BUSY 恢复流程增加延时；
- `fe4df8b...`：增加 LDC1612 I2C 错误分类处理。

从这组提交直到当前真机版本，没有后续提交重新修正本文讨论的 `src/stm32/i2c.c` / `src/i2ccmds.c` 低层逻辑。

## 2. Sovol 为什么会选择这条路线

从提交顺序可以看出，他们面对的是一个很实际的产品问题：Eddy 传感器的 I2C 访问频率远高于偶尔读取一次的普通外设。如果每一次瞬时异常都直接触发 MCU shutdown，极小概率的总线抖动也可能被放大成整次打印失败。

Sovol 想实现的大致流程是：

```text
出现一次 I2C 异常
-> STM32F1 不立即 shutdown
-> 记录更具体的错误状态
-> 尝试恢复 / 重置 I2C 外设或总线
-> 主机重新读取 LDC 身份信息
-> 如果恢复正常则继续
```

这个方向本身并没有问题，甚至和 M_Bamboo 希望“可恢复而不是一有异常就整机退出”的目标一致。

真正的分歧在于：**总线恢复成功，并不代表刚才那一笔失败的事务突然变成有效。** M_Bamboo 会严格切断这两件事之间的等号。

## 3. Sovol 的 bitmask 错误模型本身是合理的

`I2C_BUS_*` 的 enum 更合理的理解是“bit 位置”，而不是最终错误值。MCU 使用 `1 << I2C_BUS_*` 构造错误信息，Sovol 主机端代码也按相同方式检查对应 bit。

目前最关键的几位是：

- bit 1：NACK -> `2`
- bit 2：TIMEOUT -> `4`
- bit 5：BUSY -> `32`
- bit 7：总线错误 / BERR -> `128`

因此：

```text
raw34 = 34 = 2 + 32 = NACK | BUSY
raw36 = 36 = 4 + 32 = TIMEOUT | BUSY
```

这种表示法其实比“只能返回一个错误”的方式更有诊断价值，因为它能告诉我们：事务失败时，总线同时还处于 BUSY 状态。

### 真正的问题在哪里

部分 MCU 代码仍然按照旧的“单值错误码”写法判断，例如概念上：

```c
if (ret == I2C_BUS_BUSY)
```

但在 bitmask 模型中，BUSY 实际是 bit 5，也就是 `32`，而不是数值 `5`。所以这里的问题不是 Sovol 把 BUSY 定义错了，而是：

> **错误模型已经改成 bitmask，但部分使用者仍停留在旧的 scalar 语义。**

M_Bamboo 会保留 bitmask 提供的诊断价值，但不会假设 MCU 内部的 BUSY retry 一定正确执行过。

## 4. `i2c_busy_errata()` 的引脚反查问题

Sovol 把原本直接接收 SCL/SDA 引脚的 BUSY 恢复函数，改成只接收一个 `I2C_TypeDef *`，随后尝试通过 `container_of` 反查当前 I2C 对应的元数据。

元数据结构大致是：

```c
struct i2c_info {
    I2C_TypeDef *i2c;
    uint8_t scl_pin, sda_pin;
};
```

正确使用 `container_of` 的前提，是拿到结构体成员本身的地址，也就是 `&ii->i2c`。但这里实际拿到的是 `ii->i2c` 里面存放的**外设地址值**。这两个指针并不是一回事。

因为 `i2c` 恰好是结构体第一个成员，offset 为 0，错误的反查最终会直接把 STM32 的 I2C 寄存器基址当成 `struct i2c_info *`。

按照 STM32F1 的寄存器布局，代码随后读取的“scl_pin / sda_pin”实际上落在 I2C 的 `CR2` 附近。而恢复函数在读取它们之前又先把 `CR2` 清零，于是最终得到：

```text
scl_pin = 0
sda_pin = 0
```

Klipper 的 STM32 GPIO 编码中，0 对应 `PA0`。

而 SV08 Max `extra_mcu` 的 I2C2 实际使用 PB10/PB11。因此当前固件中，这段原本想对真实 SCL/SDA 进行的物理解锁动作，并没有作用到 I2C2 的真实引脚。真正仍然有效的是 I2C 外设本身的 reset / re-init。

### 为什么 M_Bamboo 不“顺手把 pin lookup 修掉”

一旦把引脚反查改正确，这段 GPIO 恢复代码就会第一次真正作用到 PB10/PB11，也就开始直接改变实际 I2C 总线的电气行为。此时必须连 GPIO 模式、开漏行为、电平切换顺序、延时、上拉以及 STM32F1 对应 silicon errata 一起重新审查。

这已经超出本项目边界。因此 M_Bamboo 只记录问题，不接管这部分固件和硬件行为。

## 5. 更关键的问题：失败事务缺少严格的数据有效性边界

“不因为一次 I2C 错误就 shutdown”本身并不是问题。真正危险的是，失败以后并没有在所有路径上明确做到“这笔数据已经无效”。

源码中可以看到几类风险：

- STM32F1 会上报 I2C 错误，但不会进入通用的 fatal shutdown；
- 某些读取路径即使底层已经报错，仍可能继续向主机发送 `i2c_read_response`；
- LDC register helper 没有把读取成功 / 失败状态向采样调用者传播；
- 因此 LDC 采样 / homing 路径仍可能继续解析 status/data，甚至继续走到 `check_home()`；
- 部分循环会被后一次 `ret` 覆盖，第一处错误不一定被完整保留。

现代 upstream Klipper 的 LDC 路径已经更强调一个清晰原则：I2C 读取失败时，这个 sensor sample 本身就应被判定为失败，而不是继续当作正常数据消费。

M_Bamboo 不修改 MCU，但会在 host 边界采用这个原则。

## 6. M_Bamboo 在哪里正式 cut tie

项目边界可以简单画成：

```text
Sovol MCU 固件
    负责产生 / 上报底层 I2C 行为
    可能自行尝试恢复 I2C 外设
                 |
                 |  信任边界
                 v
M_Bamboo Host 层
    不修 MCU
    不相信失败事务会因为后续又有响应而重新有效
```

Host 侧必须坚持：

1. 新的 transport fault 一旦确认，当前 Eddy 事务立即 taint；
2. tainted transaction 永远不能再回到 SUCCESS；
3. 必须停止 / quarantine 当前 measurement stream，避免错误风暴持续；
4. 即使错误发生在 motion 已结束、等待 sample 的后半段，也必须完成 transaction/client/session 的 terminal cleanup；
5. transport health 与 Z 坐标可信度必须分开管理；
6. 任何危险的 Z 下探开始前都必须经过 PREARM；
7. bed-facing 动作已经开始后再发生通讯故障，按上下文撤销 Z trust；
8. recovery 先证明 transport 恢复，再在需要时通过一次 fresh Safe Home 重建 Z；
9. QGL、网格、Z 校准等事务一旦中断，不从中间继续，而是从完整 checkpoint 重跑。

## 7. PREARM 与 RC5 自动恢复

PREARM 的作用不是保证下一笔 I2C 永远不会出错，而是在危险 Z 动作开始之前，拒绝已经存在或刚被观察到的通讯不稳定状态。

RC5 会在这个基础上接管 `START_PRINT` 中与 Eddy 有依赖的核心流程，实现**有次数限制的自动恢复**：

```text
PREARM / 当前阶段发生 transport fault
-> 中止或保持当前阶段，不继续危险动作
-> 清理 / quarantine Eddy 生命周期
-> 无运动检查通讯是否真正恢复
-> 如果 Z 已经不可信，只允许一次 fresh Safe Home 重建 Z
-> 恢复该阶段留下的临时状态
-> 从完整 checkpoint 重跑失败阶段
-> 只有阶段完整成功后才继续 START_PRINT
```

这里的自动恢复不是 blind retry：

- 同一个 fault episode 最多一次 armed Z recovery；
- 这一次 recovery 如果失败，立即终止，不会自动继续第二次、第三次 G28；
- recovery 成功后，当前 atomic stage 必须完整跑通，才允许把后续新 fault 视为新的 episode；
- 当前 RC5 设计目标是一次 `START_PRINT` 最多允许 3 个已成功恢复的独立 episode；最终默认值仍要经过实机 fault-injection 后冻结。

## 8. RC5 能解决什么，不能解决什么

### RC5 能修复 / 规避的部分

- sample 后半段报错导致 host 残留 `_active_transaction`；
- transport-tainted 数据被 host 当作成功事务接受；
- confirmed fault 之后 bulk stream 继续运行并形成 fault storm；
- bed-facing fault 后 Z trust 仍被错误保留；
- transport 已经不健康却仍开始 Z 下探；
- recovery 后 `START_PRINT` 依赖链被破坏；
- `has_z_offset_calibrated`、mesh scan 运动参数等临时状态泄漏；
- 安全恢复后，从完整阶段 checkpoint 有界重跑。

### RC5 无法也不会修改的部分

- STM32F1 为什么第一次产生 NACK / TIMEOUT / BUSY；
- MCU 内编译进去的 BUSY retry 判断；
- MCU 内编译进去的 `i2c_busy_errata()` pin lookup；
- MCU GPIO 的物理 bus recovery sequence；
- MCU 内的 LDC register/sample 传播方式。

这些低层限制会被完整记录，但不会由 M_Bamboo 修改。

## 9. 为什么这不只是“给固件 bug 打补丁”

即使底层 MCU 完全正确，以下策略本来也应该由 host 层决定：

- Probe 失败后 Z trust 是否仍成立；
- QGL / mesh / Z calibration 是否属于 atomic stage；
- 一个阶段被中断后应该从哪里重新执行；
- `START_PRINT` 最多允许多少次自动恢复；
- 什么条件下必须从“可以继续尝试”升级成 hard stop。

MCU 可以告诉我们总线是否出错，但它不可能知道“做了一半的 QGL 是否还能直接进入 mesh”。因此 RC5 所做的 workflow recovery，本来就是 host 的职责。

## 10. 证据边界

目前测试已经自然复现过包括 `raw34 = NACK | BUSY` 在内的 transport fault，并完成过实机的 bounded recovery。Churn / HF 测试同时证明，简单用某一个 nominal dwell 值解释问题并不成立，因为真实 STOP-ACK 到下一次启动之间本身已经包含明显的 host/motion 时间。

现有证据足以支持：

- transport fault 是真实存在的，不是单纯 host client bookkeeping；
- Sovol 固件中确实存在本文记录的实现不一致；
- host lifecycle bug 会放大或阻塞 recovery，因此必须修复；
- PREARM 对阻止“带病 transport 直接进入危险 Z 下探”有明确实机价值；
- transport recovered 不代表 failed transaction suddenly valid，也不代表 Z trust 自动恢复。

但这些证据**不能证明第一笔 I2C anomaly 的物理根因**，也不能证明 host-side containment 会让 raw34/raw36 从此不再发生。

完整测试统计与实验演进请参阅 [RC5 测试证据](RC5_TEST_EVIDENCE.md)。

## 11. 项目最终决定

`M_Bamboo_SV08Max_Mods` 不修改 MCU firmware。这不是 RC5 的临时选择，而是整个项目的固定边界。

因此我们的工程路线是：

> **使用 Sovol 已有 I2C telemetry 作为底层证据，在 MCU / Host 交界处终止信任继续向上蔓延；所有 transaction isolation、Z safety、lifecycle cleanup 与 bounded workflow recovery 都在 Klipper host/config 层完成。**

这样既保持项目可回滚，也不接管固件和电气层责任，同时仍能处理我们真正能观察、验证并控制的危险后果。
