# M_Bamboo_SV08Max_Mods

A modular collection of configuration, safety, and quality-of-life improvements for the **Sovol SV08 Max (500 × 500)**.

一个面向 **Sovol SV08 Max（500 × 500）** 的模块化改进项目，目标是在尽量保留原厂兼容性的前提下，逐步改善 Klipper 行为、安全性、配置可维护性与后续扩展能力。

> Maintainer: **Master_Bamboo / 竹子**

---

## Project goals / 项目目标

This project is intentionally conservative about firmware changes.

本项目尽量避免修改或重新编译 Sovol MCU firmware。优先使用：

- Klipper configuration
- G-code macros
- user-space Python extras
- shell-based installer / rollback tooling

Where Sovol-specific Klipper behavior differs from upstream Klipper, this project prefers to move behavior back toward **standard Klipper semantics and interfaces** whenever practical, while preserving SV08 Max touchscreen compatibility.

当 Sovol 的定制行为与 Official Klipper 有明显偏离时，本项目优先尽量恢复到标准 Klipper 的行为、接口与语义，同时保持 SV08 Max 原厂触摸屏常用命令链的兼容性。

---

## Features / 功能模块

The project is organized as independent features. Features should be installable, upgradeable, and rollbackable separately.

本项目按 feature 独立组织，后续应支持独立安装、升级与回滚。

| Feature | Status | Description |
|---|---|---|
| `safe_home` | v1.0.0-rc1 | Safer homing and Z-offset calibration behavior / 更安全的归零与 Z-offset 校准 |
| `config_optimization` | Planned | `printer.cfg` / `Macro.cfg` parameter tuning / 参数优化 |
| `hardware_cooling` | Planned | Electrical enclosure / bed cooling config for modified hardware / 硬件改装后的散热配置 |
| `plr` | Planned | Power-loss recovery redesign / 断电续打重构 |
| `restore` | Planned | Restore / rollback helpers / 恢复与回滚 |

---

# Safe Home

`Safe Home` is the first productionized feature in this project.

它主要解决 SV08 Max 原厂 homing / Z-offset calibration 中几个比较危险或不清晰的行为：

- unknown-Z 状态下的安全抬升
- raw X/Y homing 不应造成 Z 漂移
- Z homing 必须在安全 XY 位置执行
- 正常 Eddy recalibration 不再使用 `Zmax + 15` / `Z≈520` 的大范围 fake coordinate
- 正常 recalibration 先建立真实 Z reference，再进行 contact verify / Eddy recalibration
- Eddy calibration data 缺失时直接停止，而不是回退到长距离 blind probing

### Normal runtime policy / 正常运行策略

```text
valid Eddy calibration
        ↓
Z unknown?
        ↓
M_Bamboo genuine HOME_Z
        ↓
trusted Z reference
        ↓
contact verify
        ↓
Eddy recalibration
```

### Factory bootstrap boundary / 原厂初始化边界

`M_Bamboo_SV08Max_Mods` does **not** replace the Sovol first-time Eddy bootstrap procedure.

本项目**不接管**完全没有 Eddy calibration data 的首次初始化流程。

If Eddy calibration data is missing, the Safe Home feature should refuse to continue and instruct the user to complete the standard Sovol Eddy calibration first.

如果检测不到有效 Eddy calibration data，Safe Home 应直接拒绝继续，并提示用户先在原厂环境完成 Sovol Eddy Current Sensor Calibration 与 `SAVE_CONFIG`。

This is deliberate: the stock Sovol bootstrap path may use a large temporary Z frame (`Zmax + 15`, approximately `Z≈520`). That behavior is allowed to exist on the **factory/setup side**, but is not retained inside the M_Bamboo maintained runtime backend.

这是有意设计的边界：原厂首次 bootstrap 可以继续使用 Sovol 自己的 `Zmax + 15`（约 `Z≈520`）逻辑，但该逻辑不会保留在 M_Bamboo 维护的运行时 backend 中。

---

## Before installing / 安装前必须完成

Before installing `safe_home`:

1. Complete the normal Sovol initial setup.
2. Complete **Eddy Current Sensor Calibration** using the stock Sovol workflow.
3. Confirm `SAVE_CONFIG` completes successfully.
4. Make sure the printer can restart normally.
5. Only then install the M_Bamboo Safe Home feature.

安装 `safe_home` 之前：

1. 先完成 Sovol 原厂初始化。
2. 使用原厂流程完成 **Eddy Current Sensor Calibration**。
3. 确认 `SAVE_CONFIG` 成功。
4. 确认 Klipper 可以正常重启。
5. 再安装 M_Bamboo Safe Home。

> If you have just performed a factory reset, repeat the Sovol Eddy calibration first before reinstalling M_Bamboo.
>
> 如果刚刚执行过 factory reset，请先重新完成原厂 Eddy 校准，再重新安装 M_Bamboo。

---

## File ownership / 文件管理方式

Backend Python files are whole-file managed by M_Bamboo when the installed version is recognized and compatible.

Backend Python 文件采用整文件管理，但安装前必须备份并进行版本 / checksum 检查。

Typical backend files:

```text
klippy/extras/M_Bamboo_Safe_Homing.py
klippy/extras/z_offset_calibration.py
```

Configuration files are **not** wholesale overwritten. Managed blocks use stable markers:

配置文件不会整文件覆盖，而使用稳定的 BEGIN / END managed block：

```ini
# >>> M_Bamboo_SV08MAX_MOD:SAFE_HOME BEGIN >>>
# Version: 1
# Maintainer: Master_Bamboo / 竹子
...
# <<< M_Bamboo_SV08MAX_MOD:SAFE_HOME END <<<
```

---

## Backup policy / 备份策略

Every modified active file must be backed up before overwrite.

每个被修改的 active file 在覆盖前必须备份。

```text
<file>.mb_baseline   first-seen pre-install baseline; never overwritten
<file>.last_mb_ver   latest pre-M_Bamboo modification state; overwritten on upgrade
```

The backup count is intentionally bounded. The installer should not create unlimited timestamp backup directories.

备份数量必须有上限，不采用无限累积的时间戳备份目录。

---

## Installation model / 安装模型

The repository installer now provides:

- machine / version detection
- feature-aware install / upgrade / rollback
- pretty dry-run preview
- checksum verification
- backup before write
- Python `py_compile` validation
- Klipper restart and health check
- automatic rollback on failed validation
- cleanup of installer-owned temporary files

当前 installer 已提供 Safe Home 的 preflight、dry-run、版本识别、备份、`py_compile`、重启检查与失败自动 rollback。未来其它 feature 会复用同一架构。

---


### Safe Home installer commands / 安装命令

From an extracted release directory on the printer:

```bash
./install.sh safe_home
```

The default is **dry-run**. Review the preview first.

```bash
./install.sh safe_home --apply
```

Audit full config changes:

```bash
./install.sh safe_home --raw-diff
```

Rollback to the immediately previous version:

```bash
./install.sh safe_home --rollback
```

Restore first-seen baseline:

```bash
./install.sh safe_home --restore-baseline
```

## Current status / 当前状态

`safe_home` has completed the main behavior validation on an SV08 Max, including:

- fresh boot `G28`
- individual X / Y / Z homing
- touchscreen Home X / Y / Z / All
- genuine Z home before normal Eddy recalibration
- contact verify after real Z reference
- removal of `Z≈520 / Z≈500` from the normal M_Bamboo recalibration path

The missing-Eddy fail-safe branch should also be regression-tested before tagging the first public release.

在首个公开 release tag 之前，仍建议补做一次可恢复的“Eddy calibration data missing”异常分支 regression test。

---

## Disclaimer / 免责声明

This project modifies Klipper-side behavior on a large-format CoreXY printer. Always review the dry-run output and keep a recoverable backup before applying changes.

本项目会修改大尺寸 CoreXY 3D 打印机上的 Klipper 行为。安装前请仔细检查 dry-run，并确保存在可恢复备份。

This project is community-maintained and is not an official Sovol product.

本项目为社区维护项目，并非 Sovol 官方产品。
