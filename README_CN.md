# M_Bamboo_SV08Max_Mods

一个面向 **Sovol SV08 Max（500 × 500）** 的模块化 Klipper 改进项目，重点覆盖 Z 轴安全、Eddy 可靠性、校准流程、配置优化、诊断能力和可回滚发布。

> Maintainer：**Master_Bamboo / 竹子**  
> 当前公开基线：**v1.0.0-rc4**  
> RC5：**开发与验证准备中**  
> Runtime Safety 基线：**ES-R4-EC2-FS1.1**  
> [English README](README.md)

## 项目状态

RC4 仍然是当前公开 Release Candidate。RC5 不是另起一套固件架构，而是在 RC4 基础上继续收口已经发现并验证过的问题。

RC5 当前主要工作包括：

- 把 HF2.1 已证明有效的 Probe / Scan 后半段 transaction cleanup 正式带回 production；
- 保留 **PREARM**，继续作为危险 Eddy Z 动作开始前的 fail-closed 安全门；
- 在 `START_PRINT` 的核心流程中加入针对可恢复 PREARM / Eddy transport fault 的**有次数限制自动恢复**；
- QGL、网格和 Z 校准发生中断后，从完整 checkpoint 重跑对应 atomic stage，而不是从失败的传感器 transaction 中间继续；
- 清理启动过程中产生的临时状态，避免一次 failed start 污染下一次打印；
- 完成 Sovol STM32F1 I2C 源码审计，并明确 MCU / Host 的信任边界；
- 把我们做过的实机测试、fault context、recovery 结果和被修正过的假设整理进正式文档。

RC5 的实机 fault-injection 和最终 release validation 还没有完成。在 RC5 正式发布之前，下面的一键安装命令仍对应 `main` 上的公开版本。

## 项目边界

M_Bamboo **不修改、不重新编译、不刷写，也不替换 Sovol MCU 固件**。这不是 RC5 的临时选择，而是整个项目的固定原则。

源码审计已经确认 Sovol STM32F1 I2C / LDC 底层存在会让失败 transaction 边界变得模糊的实现问题。M_Bamboo 会在 MCU 与 Klipper 主机层的交界处明确停止继续向下接管：MCU 已经提供的 fault telemetry 作为底层故障证据，而 transaction isolation、PREARM、stream quarantine、Z 坐标可信度、lifecycle cleanup 和 bounded workflow recovery 全部在 Klipper host/config 层完成。

详细 high-level / low-level 分析见 [Sovol STM32F1 I2C / Eddy 根因审计](docs/I2C_ROOT_CAUSE_AND_HOST_BOUNDARY_CN.md)。

## 功能概览

| 功能 | 主要用途 | 当前状态 |
|---|---|---|
| **Safe Home** | Z 未知或不可信时先建立安全间隙，再通过真实 Eddy Z Home 建立可信参考 | 已完成实机验证 |
| **Config Optimization** | 调整运动、QGL、电流、自适应网格、buffer stepper 等 SV08 Max 参数 | 已有实机验证 lineage |
| **Eddy Safety / Calibration** | 负责 transport fault、PREARM、transaction taint、quarantine、Z trust、bounded recovery 与校准完整性 | RC4 已验证；RC5 继续 hardening |
| **Z Calibration Refinement** | 两阶段 Z 校准、contact verification、最终 XY reseat | 已完成实机验证 |
| **Nozzle Cleaner** | 使用真实 contact datum 建立擦嘴平面，避开旧流程的 below-limit plunge | 已完成实机验证 |
| **Diagnostics** | Eddy 状态、recovery check 及显式压力测试 / 诊断接口 | 默认软件功能集包含 |
| **Hardware Cooling** | 为对应物理散热改装提供配套配置 | 可选；`all` 不安装 |
| **Full Restore** | 移除 M_Bamboo 自己管理的修改，恢复可信 pre-M_Bamboo backend | Installer 功能 |

PLR 重构和实验性的 Gantry Safe Leveler **不属于当前 RC5 scope**。

## Eddy recovery 模型

RC5 会保留 PREARM，并在此基础上增加打印启动阶段的 bounded auto recovery。

可恢复 fault 出现在 Eddy 相关的 `START_PRINT` 核心流程时，高层策略是：

```text
transport / PREARM fault
-> 当前 atomic stage 保持或中止，不继续危险动作
-> 清理 / quarantine Eddy lifecycle
-> 不进行 Z 运动，先确认 transport 是否恢复
-> 如果 Z 已不可信，只允许一次 fresh armed Safe Home 重建 Z
-> 恢复该 stage 自己留下的临时状态
-> 从完整 checkpoint 重跑失败阶段
-> 只有该阶段完整成功后才继续 START_PRINT
```

这不是 blind retry：

- 同一个 fault episode 最多一次 armed Z recovery；
- 这一次 recovery 如果失败，该 episode 立即终止；
- 只有恢复后的 stage 已经完整成功，后续新 fault 才能视为新的独立 episode；
- 整个 `START_PRINT` 还有总 recovery budget，反复故障最终必须停下来检查；
- 非 Eddy error 不会被 recovery coordinator 吞掉。

当前设计目标是一次 `START_PRINT` 最多允许 **3 个已经成功恢复的独立 fault episode**，最终默认值仍需通过 RC5 实机 fault-injection 后冻结。

## 如何安装

### GitHub 一键入口

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh all
```

Installer 默认只做 dry-run。先看结果，确认无误后再执行：

```bash
sh M_Bamboo_bootstrap.sh all --apply
```

Bootstrap 会先校验仓库根目录 `SHA256SUMS`，之后才调用正式 installer。

### 本地 package / 高级使用

查看当前状态：

```bash
./install.sh all --status
```

预览：

```bash
./install.sh all
./install.sh all --raw-diff
```

确认后应用：

```bash
./install.sh all --apply
```

`all` 只安装当前 release 定义的默认软件功能。**Hardware Cooling 不包含在 `all` 中**，因为它依赖对应的物理改装。

也可以单独预览 / 安装 feature：

```bash
./install.sh safe_home
./install.sh config_optimization
./install.sh eddy_safety
./install.sh diagnostics
```

确认 dry-run 后再加 `--apply`。

### Full Restore

先预览：

```bash
./install.sh all --restore
```

确认后执行：

```bash
./install.sh all --restore --apply
```

Full Restore 只撤销 M_Bamboo 自己拥有的配置变换，并从可信 original-state archive 恢复由项目接管的 Python backend。

如果要安装历史版本，支持的路径是：

```text
当前 release
-> Full Restore
-> 回到 pre-M_Bamboo / original state
-> 使用目标历史 release 自己的 installer
```

## Installer 原则

- 默认 dry-run；
- Python backend 使用精确 SHA / provenance gate；
- 未知 backend lineage 一律 fail closed；
- `printer.cfg` / `Macro.cfg` 使用稳定、feature-owned marker；
- `klippy/extras/mb_bak/` 只保存一份可信 pre-M_Bamboo backend archive；
- 实际写入使用 transaction snapshot 和自动 rollback；
- 成功或安全回滚后清理临时 installer / download / extraction 文件；
- 不提供通用 force-overwrite 去接管未知 Python backend。

## 常见问题

### 这是一套替代 Sovol 的第三方固件吗？

不是。M_Bamboo 不修改或刷写 MCU firmware。项目主要工作在 Klipper host Python、配置、宏和 installer lifecycle，同时保留 SV08 Max 依赖的 Sovol 硬件 / G-code ABI。

### 为什么不直接升级到最新版 Official Klipper？

SV08 Max 包含 Sovol 自己的 Eddy contact、MCU command、Z calibration、触摸屏调用方式以及其他硬件集成。M_Bamboo 会有选择地采用更清晰的 upstream 语义，但不会为了“更新”而直接替换这些机器实际依赖的接口。

### PREARM 能保证以后绝对不会再发生 I2C fault 吗？

不能。PREARM 的作用是：transport 已经不健康，或者刚刚观察到不稳定时，不允许直接进入危险的 bed-facing Z action。若新的 fault 在 motion 开始后才发生，则由 runtime transaction guard 中止 / taint 当前事务，并按上下文撤销 Z trust。

### RC5 会在 `START_PRINT` 中自动恢复 PREARM / transport fault 吗？

会，但只针对 Safety Core 判定为可以安全恢复的 fault，并且有明确次数上限和 checkpoint 规则。Recovery 本身失败时不会继续 blind retry。

### transport recovery 成功后，刚才失败的 Probe / QGL / mesh transaction 会重新变有效吗？

不会。失败 transaction 永远无效。RC5 会从 clean checkpoint 重跑它所属的完整 atomic stage。

### 当前 RC5 包含 PLR 吗？

不包含。PLR 仍是独立 feature，因为它自己的 checkpoint identity 和 coordinate-trust model 需要单独处理。

### `all` 会安装 Hardware Cooling 吗？

不会。Hardware Cooling 明确 opt-in，因为它依赖真实硬件改装。

### 可以完整恢复吗？

可以。Full Restore 是当前支持的完整移除 / 恢复路径。

## 文档

- **[版本记录](RELEASE_NOTES_CN.md)** — release 历史、范围与已知限制。
- **[技术 FAQ](docs/TECHNICAL_FAQ_CN.md)** — 当前有效的安全 / recovery 设计依据与 fault 解释。
- **[Sovol I2C / Eddy 根因审计](docs/I2C_ROOT_CAUSE_AND_HOST_BOUNDARY_CN.md)** — 源码历史、bitmask、BUSY pin lookup、失败数据边界，以及 M_Bamboo 明确 cut tie 的位置。
- **[RC5 START Recovery Design](docs/RC5_START_RECOVERY_DESIGN.md)** — atomic stage、recovery ownership、dependency handling 与 validation requirements。
- **[RC5 Test Evidence](docs/RC5_TEST_EVIDENCE.md)** — 完整测试统计、fault context、recovery 结果、被修正的假设与证据边界。
- **[Eddy Safety Engineering Design](docs/ES_R4_ENGINEERING_CANDIDATE.md)** — transport-fault architecture 与 transaction safety model。
- **[实机验证指南](docs/HARDWARE_VALIDATION.md)** — 实机验证顺序和 pass/fail criteria。
- **[部署与恢复](docs/DEPLOYMENT_AND_ROLLBACK.md)** — installer transaction、provenance 与 restore 机制。
- **[命令参考](docs/COMMAND_REFERENCE_CN.md)** — G-code、Macro、installer CLI 与 public interface。
- **[Offline Validation](VALIDATION.md)** — package / static release gate。
- **[Version Map](VERSION_MAP.md)** / **[Manifest](MANIFEST.md)** — exact artifact、ownership 与 lineage。

## 免责声明

本项目会修改大型 CoreXY 打印机上的 Klipper 行为，包括归零、Probe、Z 校准、运动参数和 recovery logic。安装前请检查 dry-run；完成大版本升级后，应先完成基础实机验证，再恢复无人值守打印。

本项目由社区维护，与 Sovol 无官方隶属或背书关系。开发与技术文档可能包含 AI-assisted analysis；安全结论最终应以源码审查、可复现测试、maintainer review 和明确实机证据为依据。
