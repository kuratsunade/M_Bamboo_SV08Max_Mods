# M_Bamboo_SV08Max_Mods — v1.0.0-rc3

[English](RELEASE_NOTES.md) | [简体中文](RELEASE_NOTES_CN.md)

RC3 是在 RC2 已完成真实机器 regression 的基础上，对 package completeness 与 installer UX 的修正版。

## Config Optimization 补全

RC2 漏掉了此前已经确认过的 `buffer_stepper.cfg` 优化。RC3 正式把 `[buffer_stepper filament_buffer]` 纳入 Feature 2：

- `velocity 150 → 80`
- `accel 5000 → 1900`
- `push_length 25 → 27`

这些参数使用稳定的 `CONFIG_BUFFER_STEPPER` managed block，并参与 feature-scoped baseline / previous-version backup、幂等检查、raw diff、安装后 validation 与 rollback。

## Installer UX

安装成功后，installer 现在会明确说明已经请求 Klipper restart、service 当前报告为 `active`。同时，如果用户没有观察到正常的打印机 / Klipper restart cycle，或机器状态与预期不一致，会明确提示手动执行一次 **Firmware Restart**。

## Gitee 文档修正

README 中的 Gitee bootstrap 示例统一改为仓库实际使用的 `master` branch。

## 延续 RC2 的 Safe Home 实机 regression

RC2 已在真实机器上通过 fresh/repeated G28、X/Y/Z 独立 homing、触摸屏风格 homing、raw X/Y `dZ=0`、HOME-FIRST Eddy recalibration、contact verification、无 `Z≈520 / Z≈500` runtime path、SAVE_CONFIG restart，以及 installer 重复 apply 幂等性测试。
