# M_Bamboo_SV08Max_Mods

[English](README.md) | [简体中文](README_CN.md)

一个面向 **Sovol SV08 Max（500 × 500）** 的模块化改进项目，重点改善安全性、Klipper 配置行为、可维护性以及日常使用体验。

> Maintainer: **Master_Bamboo / 竹子**

## 项目目标

本项目在可行的情况下避免重新编译 MCU firmware，优先使用 Klipper 配置、G-code macro、用户空间 Python extras，以及可回滚的安装工具。对于与 Official Klipper 明显偏离的 Sovol 定制行为，本项目倾向于恢复到更标准的 Klipper 语义，同时保持 SV08 Max 原厂触摸屏常用命令 ABI 的兼容性。

## 功能模块

| Feature | 状态 | 说明 |
|---|---|---|
| `safe_home` | v1.0.0-rc1 | 更安全的归零、Z-offset 与 Eddy recalibration |
| `config_optimization` | 计划中 | `printer.cfg` / `Macro.cfg` 参数优化 |
| `hardware_cooling` | 计划中 | 针对硬件改装的电控仓 / 热床散热配置 |
| `plr` | 计划中 | 断电续打重构 |
| `restore` | 计划中 | 恢复与回滚辅助功能 |

## Safe Home

`safe_home` 是本项目第一个进入 production 阶段的 feature。

它提供：

- Z 未归零时，在 X/Y homing 前先做安全抬升；
- raw X/Y homing 不造成物理 Z 漂移；
- Z 只在受控 XY 位置执行 homing；
- 正常 Eddy recalibration 在 Z unknown 时先执行真实 Z home；
- contact verification 使用真实 Z reference；
- M_Bamboo runtime backend 中不再保留 `Zmax + 15` / 约 `Z520` fallback；
- Eddy calibration data 缺失时明确报错，而不是继续盲目下降。

### Factory bootstrap 边界

M_Bamboo **不接管** Sovol 首次 Eddy bootstrap。安装 Safe Home 前，请先使用原厂流程完成 Eddy Current Sensor Calibration，并确认 `SAVE_CONFIG` 成功。

如果机器刚刚 factory reset，请先重新完成 Sovol 初始化和 Eddy calibration，再重新安装 M_Bamboo。

## 快速安装

### 推荐方式：先下载、检查，再执行

先 dry-run：

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh safe_home
```

确认预览无误后安装：

```bash
sh M_Bamboo_bootstrap.sh safe_home --apply
```

Bootstrap 会把完整仓库 snapshot 下载到 installer 自创建的 `/tmp` 目录，校验 `SHA256SUMS`，再调用正式 feature installer；成功或失败后都会自动清理自己创建的临时文件。

### 一行命令（方便测试）

Dry-run：

```bash
wget -qO- https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh \
  | sh -s -- safe_home
```

正式安装：

```bash
wget -qO- https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh \
  | sh -s -- safe_home --apply
```

正式 public release 后，建议通过 `M_BAMBOO_REF` 固定到 release tag，而不是长期追踪 `main`。

## 已解压目录中的直接命令

```bash
./install.sh safe_home              # dry-run
./install.sh safe_home --apply      # 安装
./install.sh safe_home --raw-diff   # 完整配置 diff
./install.sh safe_home --rollback
./install.sh safe_home --restore-baseline
```

## 备份策略

每个被修改的 active file 在覆盖前都必须备份：

```text
<file>.mb_baseline   第一次安装前看到的 baseline；永不覆盖
<file>.last_mb_ver   最近一次 M_Bamboo 修改之前的状态
```

配置文件使用稳定 managed block 做局部管理，不进行整文件覆盖；backend Python 文件在 source/version 检查通过后可以整文件管理。

## Safe Home runtime policy

```text
有效 Eddy calibration
        ↓
Z unknown?
        ↓
真实 M_Bamboo HOME_Z
        ↓
可信 Z reference
        ↓
contact verify
        ↓
Eddy recalibration
```

如果 Eddy calibration 缺失，Safe Home 会直接停止并提示用户先完成 Sovol 原厂 calibration，不会回退到 `Zmax + 15` 的长距离 probing。

## 文档

- [Safe Home 安装与恢复说明](docs/SAFE_HOME_INSTALL.md)
- [Safe Home Regression Checklist](docs/SAFE_HOME_REGRESSION.md)
- [English Release Notes](RELEASE_NOTES.md)
- [中文 Release Notes](RELEASE_NOTES_CN.md)

## 当前版本状态

`safe_home` v1.0.0-rc1 在开发阶段已经通过主要的 Home All、触摸屏 homing、HOME-FIRST Eddy recalibration、contact verification、`SAVE_CONFIG` 与 restart 测试。正式 v1.0.0 前仍需要完成 controlled missing-Eddy fail-safe regression。
