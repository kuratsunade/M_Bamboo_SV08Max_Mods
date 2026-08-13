# M_Bamboo_SV08Max_Mods — v1.0.0-rc2

[English](RELEASE_NOTES.md) | [简体中文](RELEASE_NOTES_CN.md)

RC2 将最初只包含 Safe Home 的 production package 扩展为两个 feature-aware 模块。

## Safe Home

- 保留已经验证的 genuine HOME_Z recalibration path。
- 保留 factory-bootstrap boundary：缺失 Eddy calibration 时直接报错，不回退到 `Zmax + 15` / 约 `Z520`。
- 正式把 `[stepper_z] position_min: -1` 纳入 Safe Home ownership，因为它属于 Z safety dependency。
- 继续保持原厂触摸屏 G28 ABI 兼容。
- 不修改 `probe_eddy_current.py`，也不修改 MCU firmware。

## Config Optimization

新增 `config_optimization` feature：

- `max_velocity 700 → 400`
- `max_accel 40000 → 15000`
- X/Y TMC5160 `run_current 3.0 → 2.3`
- QGL `speed 400 → 200`
- QGL `retries 15 → 5`
- QGL `max_adjust 20 → 5`
- Adaptive Mesh `PGP=0 → PGP=1`
- 随机 contact + cross-hatch `CLEAN_NOZZLE`
- `START_PRINT` acceleration 与两阶段 current-Z Z-offset verification

由于 START_PRINT 的 calibration 调用依赖 Safe Home 已验证的 current-Z 语义，因此 Config Optimization 明确依赖 Safe Home。

## Installer

- 支持 `safe_home`、`config_optimization` 和 `all`。
- `all` 会按依赖顺序安装。
- 多 feature 共享配置文件时，使用数量受控的 feature-scoped previous-version snapshot。
- `.mb_baseline` 继续作为 first-seen baseline，不覆盖。
- Bootstrap 下载完整 snapshot，校验 `SHA256SUMS`，运行 installer，并自动清理临时目录。

## 文档

- README 拆分为英文和简体中文页面，并可互相切换。
- Release Notes 同样拆分为英文和简体中文页面。
- 新增明确的 AI 辅助开发声明。
- 新增 Config Optimization 文档。
