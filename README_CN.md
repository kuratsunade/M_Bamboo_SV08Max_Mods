# M_Bamboo_SV08Max_Mods

一个面向 **Sovol SV08 Max（500 × 500）** 的模块化 Klipper 改进项目，重点覆盖安全、校准、配置维护、诊断与可回滚发布流程。

> Maintainer：**Master_Bamboo / 竹子**  
> 当前 Release Candidate：**v1.0.0-rc4**  
> Runtime Safety：**ES-R4-EC2-FS1.1**  
> 状态：**RC；healthy path 已完成实机验证，并已完成一次自然 raw-34 故障到恢复再回到打印的完整实机验证；长期 soak 继续进行**  
> [English README](README.md)

## 项目概览

`M_Bamboo_SV08Max_Mods` 是针对 Sovol SV08 Max 原厂 Klipper 软件栈的一组模块化改进。项目不替换整套 Sovol 固件，也不要求重新编译或刷写 MCU firmware，而是在保留触摸屏、Eddy contact probe、原厂硬件接口与既有调用方式的前提下，对关键流程进行有边界的修正、加固和优化。

项目重点不是追求“最新版 Klipper”本身，而是解决 SV08 Max 在实际使用中暴露出的几个核心问题：

- 归零、Probe 与 Z 坐标可信状态之间的边界不够严格；
- Eddy 通讯异常、探测失败与后续 Z 运动之间缺少足够强的安全约束；
- 部分 Z 校准与擦嘴流程存在可重复性或运动边界问题；
- 原厂部分运动、QGL、电流与网格参数偏激进，维护与调试成本较高；
- 定制 Eddy 栈发生异常时，可观察性不足；
- 修改过的配置和 Python 后端缺少统一、可验证、可恢复的发布生命周期。

M_Bamboo 的目标是让这些行为更安全、更确定、更容易诊断，并确保项目自己的修改能够明确识别、升级和完整恢复。

详细的故障模型、实现细节、证据边界和仍在验证的项目不会全部放在 README 中，请参阅后面的技术文档入口。

## 功能概览

| 功能 | 主要用途 | 当前状态 | 默认随 `all` 安装 |
|---|---|---|---:|
| **Safe Home** | 在 Z 不可信时先建立安全间隙，再进行 XY 归零，并最终通过真实 Eddy Z Home 建立可信坐标 | 已完成实机验证 | 是 |
| **Config Optimization** | 调整运动、QGL、电流、自适应网格、buffer stepper 与相关参数，使默认行为更适合 SV08 Max | 已有实机验证 | 是 |
| **Eddy Safety / Calibration** | 加固 Eddy 通讯、Probe、Z trust、校准事务与故障阻断，并提供恢复检查与状态诊断 | healthy path 已验证；一次自然 raw-34 的中止、quarantine、恢复、fresh G28 与重新进入打印路径也已实机通过 | 是 |
| **Z Calibration Refinement** | 改善两阶段 Z 校准、contact verification 与最终 XY reseat 的机械一致性 | 已集成并实机验证 | 随 Eddy Safety 安装 |
| **Nozzle Cleaner** | 使用一次真实 contact datum 建立擦嘴平面，避免旧流程中的确定性 Z 越界路径 | 已集成并实机验证 | 随 Config Optimization 安装 |
| **Diagnostics** | 提供 Eddy 状态、恢复检查以及 XY stress 等诊断接口，不会因安装而自动执行压力测试 | 已正式纳入 release ownership | 是 |
| **Hardware Cooling** | 为已经完成对应物理散热改装的机器提供配套配置 | 可选，需要硬件改装 | **否** |
| **Full Restore** | 移除 M_Bamboo 管理的配置修改，并恢复安装前的可信后端原始状态 | Installer lifecycle core | 通过 installer 提供 |

当前 RC 不包含 PLR 重构和实验性的 Gantry Safe Leveler。它们不属于默认安装，也不是当前 RC 的运行依赖。具体某个版本新增、删除或调整了什么，请查看 [Release Notes](RELEASE_NOTES_CN.md)。

## 如何安装


### GitHub 一键安装入口

GitHub 镜像使用 `main` 分支。SSH 登录打印机后可执行：

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh all
```

先检查预演结果，确认无误后再应用：

```bash
sh M_Bamboo_bootstrap.sh all --apply
```

Bootstrap 会先下载 GitHub 仓库快照并校验仓库根目录 `SHA256SUMS`，校验通过后才调用 `install.sh`。

### 3.1 安装前准备

安装前建议先确认：

1. 打印机处于空闲状态，没有正在打印或执行校准。
2. 可以通过 SSH 登录 Sovol 主机。
3. 当前 Klipper 能够正常启动。
4. 如果机器安装过其他会修改 `printer.cfg`、`Macro.cfg` 或 `klippy/extras/*.py` 的第三方 mod，先确认其修改范围。
5. 不要在不了解冲突原因的情况下手工绕过 installer 的来源检查或配置冲突检查。

将 release 包下载或复制到打印机后解压，并进入项目目录。

安装程序默认是**预演模式**。不加 `--apply` 时不会真正修改文件。

### 3.2 推荐的完整安装

先查看当前机器状态：

```bash
./install.sh all --status
```

预览计划修改：

```bash
./install.sh all
```

如果希望查看更具体的文件差异：

```bash
./install.sh all --raw-diff
```

确认结果正确后执行：

```bash
./install.sh all --apply
```

`all` 会安装正常的软件功能，包括 Diagnostics，但**不会安装 Hardware Cooling**。

安装完成并确认 Klipper 正常重启后，在第一次运动前建议执行：

```text
M_BAMBOO_EDDY_STATUS
```

确认没有异常 fault 后，再执行一次普通：

```text
G28
```

首次安装或大版本升级后，建议按照 [实机验证指南](docs/HARDWARE_VALIDATION.md) 完成基础运动、Probe、QGL、Z calibration 与小型打印验证，再恢复无人值守打印。

### 3.3 只安装某个功能

可以按 feature 单独预览或安装：

```bash
./install.sh safe_home
./install.sh safe_home --apply

./install.sh config_optimization
./install.sh config_optimization --apply

./install.sh eddy_safety
./install.sh eddy_safety --apply

./install.sh diagnostics
./install.sh diagnostics --apply
```

部分功能存在依赖关系，installer 会按照 manifest 中定义的 ownership 和依赖进行处理。不要通过手工复制单个 backend 文件来代替正常安装流程。

#### Hardware Cooling

Hardware Cooling 是**显式可选功能**，永远不会由 `all` 自动安装：

```bash
./install.sh hardware_cooling
./install.sh hardware_cooling --apply
```

只有机器已经完成对应物理散热改装时才应启用该功能。

### 3.4 如何升级已有 M_Bamboo 安装

使用**新 release 包自带的 installer**。

先检查当前状态和 lineage：

```bash
./install.sh all --status
```

再进行预演：

```bash
./install.sh all
./install.sh all --raw-diff
```

确认识别到的文件来源与计划修改均符合预期后：

```bash
./install.sh all --apply
```

Installer 使用精确 SHA256 和已知 lineage 判断可接管的后端文件。对于无法确认来源的文件，它会 fail closed，而不是猜测“这大概是原厂文件”。

### 3.5 安装被拒绝时如何处理

Installer 的 refusal 通常是保护机制。遇到拒绝时，优先确认原因，不建议为了继续安装而直接修改 installer 或手工覆盖文件。

#### Unknown backend / provenance refusal

如果提示后端文件未知、来源无法识别或 first takeover 被拒绝：

1. 保存 installer 的完整输出。
2. 执行：

```bash
./install.sh all --status
./install.sh all --raw-diff
```

3. 确认相关文件是否来自：
   - 不同版本的 Sovol 固件；
   - 其他第三方 mod；
   - 手工修改过的 Klipper backend；
   - 旧 M_Bamboo engineering package。
4. 在来源明确之前不要强行覆盖。

当前 installer 故意不提供通用 `--force` 来接管未知 Python backend。

#### 配置冲突

如果 installer 报告现有配置无法安全转换：

1. 查看报告的 section / managed block。
2. 使用 `--raw-diff` 确认将要发生的修改。
3. 判断冲突内容属于用户自己的配置、其他 mod，还是旧版 M_Bamboo block。
4. 只有在 ownership 明确后再手工处理冲突，并重新运行预演。

M_Bamboo 不应为了“安装成功”而静默覆盖与项目无关的用户配置。

#### 写入过程中失败

所有实际写入都使用事务机制。

正常情况下：

```text
write failure
→ automatic rollback
→ restore immediate pre-transaction state
```

如果自动 rollback 本身也无法完成，installer 会保留恢复快照，并在错误信息中显示类似：

```text
/tmp/M_Bamboo_SV08MAX.*
```

在完成机器恢复或把该目录复制到安全位置之前，不要删除它。

#### Klipper 安装后无法正常启动

不要立即执行 `G28`、Probe、QGL 或其他运动。

优先保留：

- installer 完整输出；
- `klippy.log`；
- `./install.sh all --status` 输出；
- installer 报告的 transaction snapshot 路径，如果存在。

如果无法快速确定问题来源，可以使用 Full Restore 回到 M_Bamboo 安装前的状态。

### 3.6 完整恢复

先预览恢复：

```bash
./install.sh all --restore
```

确认后执行：

```bash
./install.sh all --restore --apply
```

Full Restore 是当前支持的完整项目移除方式。它只撤销 M_Bamboo 拥有的配置变换，并从可信的原始状态归档恢复由项目接管的 Klipper Python backend。

如果想安装更旧的 M_Bamboo 版本，不需要当前 installer 内置复杂的 downgrade engine：

```text
当前版本
→ Full Restore
→ 回到 pre-M_Bamboo / original state
→ 下载目标历史 release
→ 使用该 release 自己的 installer
```

## 总览 FAQ

### 这是不是一套替代 Sovol 的第三方固件？

不是。项目当前不重新编译或刷写 Sovol MCU firmware，也不是一套完整替换系统。它主要修改 Klipper 用户空间 Python、配置、宏和 installer lifecycle，同时保留 SV08 Max 依赖的 Sovol 硬件接口与调用习惯。

### 为什么不直接把 SV08 Max 升级到最新版 Official Klipper？

因为 Sovol 在 SV08 Max 上存在定制 Eddy contact、Z calibration、触摸屏调用方式和其他硬件相关实现。直接整体替换上游 Klipper 可能破坏这些接口。M_Bamboo 的做法是有选择地采用更合理的 upstream 语义，同时保留机器实际需要的 Sovol ABI 和硬件行为。

### 这个项目最主要改善的是什么？

核心不是单纯“调快”或“调参数”，而是重新收紧 Z trust、Probe failure、Eddy transport fault、校准事务和恢复行为之间的边界，同时改善归零、Z calibration、nozzle cleaning、QGL、运动参数和诊断能力。

### `all` 会修改机器上的所有东西吗？

不会。`all` 只代表当前 release 定义的默认软件 feature 集合。Hardware Cooling 因为依赖物理改装，明确不在 `all` 中。Installer 也只应修改它明确拥有的 backend 和配置 transformation。

### 安装 Diagnostics 会自动运行 XY stress test 吗？

不会。Diagnostics 只是安装公开诊断接口。XY stress 等动作需要用户显式调用。

### 当前版本包含断电续打 PLR 吗？

不包含。原厂 PLR 的恢复点身份和坐标可信模型存在需要单独解决的问题，因此 PLR 重构被保留为独立后续 feature，而不是为了赶当前 RC 直接带入。

### 如果安装后不满意，能恢复原厂或安装前状态吗？

可以。Full Restore 会逆转 M_Bamboo 拥有的配置修改，并恢复集中保存的可信原始 backend。它不会依赖一条无限增长的历史版本备份链。

### 能直接从新版本 downgrade 到任意旧版本吗？

当前不提供 generic downgrade engine。推荐的确定性流程是 Full Restore，然后使用目标历史 release 自己的 installer。

### 这个 RC 是否已经证明所有 Eddy fault 都完全解决？

没有。当前 healthy path 已完成较充分的实机验证，而且已经自然捕获过一次 raw-34 `I2C_BUS_NACK | I2C_BUS_BUSY`：当前动作安全中止、LDC stream 被 quarantine、无运动 recovery check 通过、fresh armed G28 重建 Z trust，随后无需 firmware reset 即重新完成打印准备并开始打印。这个结果证明了该 fault/recovery 路径至少在一次真实事件中成立，但仍需要更多长期自然故障 soak 才适合提升为 stable。详细证据边界请查看 Technical FAQ、Hardware Validation 和 Release Notes。

## 文件 Ownership、备份与项目原则

### 文件 Ownership

项目尽量让每项修改都有明确 owner，而不是把所有逻辑塞入一个宏或整份配置文件。

| 文件 / 范围 | 主要职责 |
|---|---|
| `M_Bamboo_Safe_Homing.py` | Safe Home 与 coordinate trust orchestration |
| `probe.py` | 普通 non-contact probe 的安全 endpoint policy |
| `probe_eddy_current.py` | Eddy operation state、fault handling、diagnostics 与 transaction trace |
| `ldc1612.py` | LDC1612 transport / telemetry 与相关底层状态 |
| `z_offset_calibration.py` | Z calibration、contact verification 与 final XY reseat |
| `printer.cfg` | 只通过明确、可逆的 feature transformation 管理项目拥有的配置 |
| `Macro.cfg` | 通过稳定的 M_Bamboo managed block 管理宏与流程编排 |
| `installer.py` | provenance、feature ownership、transaction、restore 与 release lifecycle |

具体 public command、参数、兼容接口和 feature ownership 以 [命令与公开接口参考](docs/COMMAND_REFERENCE_CN.md) 为准。

### 配置文件原则

`printer.cfg`、`Macro.cfg` 等用户配置不使用持久化整文件备份作为正常 restore 机制。

M_Bamboo 优先使用稳定、机器可识别的 marker：

```text
# >>> M_Bamboo_SV08MAX_MOD:<FEATURE> BEGIN >>>
...
# <<< M_Bamboo_SV08MAX_MOD:<FEATURE> END <<<
```

Restore 只逆转 M_Bamboo 拥有的变换，尽量保留与项目无关的用户内容和 `SAVE_CONFIG` 生成内容。

### Python backend 备份原则

由 M_Bamboo 接管的 Klipper backend 只保留一份经过 provenance 验证的 pre-M_Bamboo 原始状态：

```text
/home/sovol/klipper/klippy/extras/mb_bak/
```

它建立后不会在普通升级时被覆盖。

Legacy `.mb_baseline` 只有在完整 SHA256 能证明其为原厂内容时才可作为迁移输入。对于已识别的 M_Bamboo lineage，如果 legacy baseline 缺失或已被污染，安装程序可以检查 Sovol 自带的 factory mirror，但同样必须精确匹配已知原厂 SHA256；任何文件都不会仅凭路径或文件名获得信任。

### Transaction 临时快照

每次实际写入都会建立临时 transaction snapshot。

- 安装成功：清理；
- 安装失败且 automatic rollback 成功：清理；
- rollback 本身失败：保留并报告路径，用于人工恢复。

### 项目原则

- 不要求重新编译或刷写 Sovol MCU firmware；
- 尽量保持触摸屏与 Sovol 现有 G-code / hardware ABI 兼容；
- 在兼容硬件接口的前提下，让行为向更清晰的 Klipper 语义靠拢；
- feature 必须有明确 ownership，尽量支持独立安装、升级和恢复；
- 配置修改优先采用局部、可逆 transformation，不整文件接管用户配置；
- 未知 backend provenance 一律 fail closed；
- 安装写入必须可 transaction rollback；
- 安全结论必须区分 code-proven、hardware-observed、engineering inference 与 pending validation；
- 不为了完成 release checklist 而把未经验证的功能塞入默认安装。

## 文档入口

README 负责项目总览、功能定位和安装使用。更深入的技术内容与 release-specific 信息分别维护在下面的文档中：

- **[Release Notes](RELEASE_NOTES_CN.md)**：每个 release 的确切变化、范围与已知限制。
- **[命令与公开接口参考](docs/COMMAND_REFERENCE_CN.md)**：G-code、宏、installer CLI、参数、兼容别名和 public interface contract。
- **[Technical FAQ](docs/TECHNICAL_FAQ_CN.md)**：Sovol 已确认问题、设计理由、安全模型、错误解释、证据边界与剩余不确定性。
- **[Eddy Safety 工程设计](docs/ES_R4_ENGINEERING_CANDIDATE.md)**：更深入的 Eddy Safety 架构、transport fault 与 transaction 模型。
- **[实机验证指南](docs/HARDWARE_VALIDATION.md)**：实机验证顺序、pass/fail 标准和当前 evidence。
- **[部署与恢复](docs/DEPLOYMENT_AND_ROLLBACK.md)**：installer transaction、恢复机制和故障恢复细节。
- **[离线验证](VALIDATION.md)**：package、代码与静态 release gate。
- **[Version Map](VERSION_MAP.md)** / **[Manifest](MANIFEST.md)**：exact artifact、lineage、ownership 和 release package 信息。

## 免责声明

本项目会修改大型 CoreXY 3D 打印机上的 Klipper 行为，包括归零、Probe、Z calibration、运动参数和相关安全流程。安装前请阅读预演结果，并在真实机器上完成基础运动和打印验证后再进行无人值守使用。

本项目为社区维护项目，与 Sovol 官方无隶属或授权关系。使用者应自行评估机器状态、硬件改装和第三方修改的兼容性。

项目开发和技术文档可能包含 AI 辅助工作。硬件行为与安全相关结论最终应以源码检查、维护者审核、可复现测试和明确的实机证据为准。
