# M_Bamboo_SV08Max_Mods

[English](README.md) | [简体中文](README_CN.md)

一个面向 **Sovol SV08 Max（500 × 500）** 的模块化改进项目，重点改善安全性、Klipper 配置行为、可维护性以及日常使用体验。

> Maintainer: **Master_Bamboo / 竹子**

## 项目目标

本项目在可行的情况下避免重新编译 MCU firmware，优先使用 Klipper 配置、G-code macro、用户空间 Python extras，以及可回滚的安装工具。对于与 Official Klipper 明显偏离的 Sovol 定制行为，本项目倾向于恢复到更标准的 Klipper 语义，同时保持 SV08 Max 原厂触摸屏常用命令 ABI 的兼容性。

## AI 辅助开发声明

本项目在开发过程中大量使用 **OpenAI ChatGPT** 辅助进行代码草拟、代码 review、架构讨论、文档编写、测试规划，以及 Klipper / Sovol 行为分析。AI 给出的建议**不会被未经验证地直接采用**：涉及安全的逻辑会由维护者审阅，并在真实 SV08 Max 硬件上验证后，才会进入 production release。最终的项目决策、发布文件以及 release approval 仍由维护者负责。

由于本项目的软件能够控制真实的运动机构与加热部件，即使安装器提供 dry-run、备份和 rollback，用户仍应检查变更内容，并将 release-candidate 版本视为测试软件。

## 功能模块

| Feature | 状态 | 说明 |
|---|---|---|
| `safe_home` | v1.0.0 RC | 更安全的归零、Z-offset 与 Eddy recalibration |
| `config_optimization` | v1.0.0 RC | 已验证的 `printer.cfg` / `Macro.cfg` 参数与流程优化 |
| `hardware_cooling` | 计划中 | 针对硬件改装的电控仓 / 热床散热配置 |
| `plr` | 计划中 | 断电续打重构 |
| `restore` | 计划中 | 恢复与回滚辅助功能 |

## Safe Home

Safe Home 负责 unknown-Z 安全抬升、受控 XY/Z homing、正常 Eddy recalibration 前建立真实 Z reference，以及明确的 factory bootstrap boundary。`[stepper_z] position_min: -1` 现在也正式归 Safe Home 管理，因为它属于 Z 安全依赖。

**安装前置条件：**先使用 Sovol 原厂流程完成 Eddy Current Sensor Calibration，并确认 `SAVE_CONFIG` 成功。M_Bamboo active runtime 不保留原厂 `Zmax + 15` / 约 `Z520` bootstrap fallback。

## Config Optimization

`config_optimization` 是独立 feature，但依赖 Safe Home，因为其中 `START_PRINT` 使用了已经验证的 `USE_CURRENT_Z` calibration 语义。

本 RC 包含：

- `[printer]` `max_velocity: 700 → 400`
- `[printer]` `max_accel: 40000 → 15000`
- X/Y TMC5160 `run_current: 3.0 → 2.3`
- QGL `speed: 400 → 200`
- QGL `retries: 15 → 5`
- QGL `max_adjust: 20 → 5`
- Adaptive Mesh `PGP=0 → PGP=1`
- 随机 contact point + cross-hatch 的 `CLEAN_NOZZLE`
- `START_PRINT` acceleration limit `15000 / 7500`
- QGL 前 current-Z Z-offset verification，以及 mesh 后再次 verification

该 feature 不接管 Safe Home 的 G28 routing 或 Z backend。

## 快速安装

### 推荐方式：下载 bootstrap，先 dry-run，再安装

同时预览当前两个 feature：

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh all
```

确认无误后：

```bash
sh M_Bamboo_bootstrap.sh all --apply
```

也可以单独使用：

```bash
sh M_Bamboo_bootstrap.sh safe_home
sh M_Bamboo_bootstrap.sh config_optimization
```

`config_optimization` 要求 Safe Home 已经安装；或者直接使用 `all`，安装器会按依赖顺序处理。

### 一行命令

```bash
wget -qO- https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh \
  | sh -s -- all
```

确认 dry-run 后再加 `--apply`。

Bootstrap 会把完整仓库 snapshot 下载到 installer 自己创建的 `/tmp/M_Bamboo_SV08MAX.XXXXXX`，校验 `SHA256SUMS`，再调用正式 installer；无论成功还是失败都会清理自己的临时文件。

## 已解压目录中的命令

```bash
./install.sh all                    # 两个 feature dry-run
./install.sh all --apply            # 安装两个 feature
./install.sh safe_home
./install.sh config_optimization
./install.sh all --raw-diff
```

Rollback 是 feature-aware 的。如果同时安装了两个 feature，因为 Config Optimization 依赖 Safe Home，应先 rollback `config_optimization`，再 rollback `safe_home`。

## 备份策略

每个被修改文件保留一个 first-seen baseline：

```text
<file>.mb_baseline
```

多个 feature 共享的配置文件使用数量受控的 feature-scoped previous-version slot，例如：

```text
printer.cfg.last_mb_safe_home
printer.cfg.last_mb_config_optimization
```

这样一个 feature 的 rollback 不会无意恢复掉另一个 feature 的配置状态。

## 文档

- [Safe Home 安装与恢复](docs/SAFE_HOME_INSTALL.md)
- [Config Optimization](docs/CONFIG_OPTIMIZATION.md)
- [Safe Home Regression Checklist](docs/SAFE_HOME_REGRESSION.md)
- [English Release Notes](RELEASE_NOTES.md)
- [中文 Release Notes](RELEASE_NOTES_CN.md)

## 当前版本状态

`v1.0.0-rc2` 将已经 productionized 的 Safe Home 与 Config Optimization 的首个 release-candidate package 合并。建议在任何额外机器上 apply 前都先运行 dry-run 并检查 diff。
