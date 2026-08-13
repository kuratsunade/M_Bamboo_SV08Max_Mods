# Safe Home — Installation & Recovery Guide

`safe_home` is one feature of **M_Bamboo_SV08Max_Mods**.

本文档仅描述 `safe_home` feature 的安装、前置条件、验证与恢复边界。

---

## 1. Prerequisite / 前置条件

**Do not install Safe Home on a factory-reset / uninitialized printer before completing the stock Sovol Eddy calibration.**

**如果机器刚 factory reset、尚未完成原厂 Eddy calibration，请不要先安装 Safe Home。**

Recommended order:

```text
Factory reset / new printer
        ↓
Sovol stock setup
        ↓
Sovol Eddy Current Sensor Calibration
        ↓
SAVE_CONFIG
        ↓
confirm normal Klipper restart
        ↓
install M_Bamboo Safe Home
```

Why:

- Sovol stock firmware already contains a first-time Eddy bootstrap path.
- That bootstrap may temporarily use `Zmax + 15` (`Z≈520`) to obtain the initial contact datum.
- M_Bamboo intentionally does not retain this long-range fallback in normal runtime.
- After a valid Eddy curve exists, Safe Home can use a genuine Z home instead.

原因：

- Sovol 原厂已经实现首次 Eddy bootstrap。
- 原厂 bootstrap 可能临时使用 `Zmax + 15`（约 `Z≈520`）。
- M_Bamboo 不在正常 runtime 中保留这条大范围 fallback。
- 一旦 Eddy curve 已经存在，后续应通过真实 Z home 建立 reference。

---

## 2. Installer preflight / 安装前检查

The installer verifies at least:

```text
[ ] expected Klipper directories exist
[ ] printer.cfg / Macro.cfg are available
[ ] valid Eddy calibration data exists
[ ] active z_offset backend version is recognized
[ ] release payload checksums are valid
[ ] Python payloads compile successfully
```

Missing Eddy calibration is a **hard install block** for Safe Home.

如果找不到有效 Eddy calibration data，应直接阻止 Safe Home feature 安装。

Expected message:

```text
Eddy calibration data was not detected.
Complete the Sovol factory Eddy Current Sensor Calibration,
confirm SAVE_CONFIG, then run the installer again.

未检测到有效 Eddy 校准数据。
请先使用 Sovol 原厂流程完成 Eddy Current Sensor Calibration，
确认 SAVE_CONFIG 成功后，再重新运行安装程序。
```

---

## 3. Bootstrap installer / Bootstrap 安装器

Recommended workflow on the printer:

```bash
cd /home/sovol
wget -O M_Bamboo_bootstrap.sh \
  https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh
sh M_Bamboo_bootstrap.sh safe_home
```

The first run is a dry-run. After reviewing the preview:

```bash
sh M_Bamboo_bootstrap.sh safe_home --apply
```

Bootstrap behavior:

```text
create /tmp/M_Bamboo_SV08MAX.XXXXXX
→ download full repository snapshot
→ extract inside installer-owned temp directory
→ verify SHA256SUMS
→ invoke install.sh / installer.py
→ cleanup exact installer-owned temp directory
```

By default, temporary files are cleaned on both success and failure. For debugging only, set:

```bash
M_BAMBOO_KEEP_TEMP=1 sh M_Bamboo_bootstrap.sh safe_home
```

Convenience one-liner for testing:

```bash
wget -qO- https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh \
  | sh -s -- safe_home
```

Apply via one-liner:

```bash
wget -qO- https://raw.githubusercontent.com/kuratsunade/M_Bamboo_SV08Max_Mods/main/bootstrap.sh \
  | sh -s -- safe_home --apply
```

For stable public releases, pin `M_BAMBOO_REF` to a release tag instead of tracking `master`.

---

## 4. Direct installer commands / 直接安装命令

From an extracted `M_Bamboo_SV08Max_Mods` release directory:

```bash
./install.sh safe_home
```

Default behavior is dry-run. To install after review:

```bash
./install.sh safe_home --apply
```

Useful maintenance commands:

```bash
./install.sh safe_home --raw-diff
./install.sh safe_home --rollback
./install.sh safe_home --restore-baseline
```

Use `--no-restart` only for development/debugging; normal production apply restarts Klipper and verifies that the service returns active.

---


### Restart confirmation / 重启确认

After an apply, the installer requests a Klipper service restart and verifies that the service reports `active`. This status check does not prove that the user visibly observed a complete frontend/printer restart cycle. If no normal restart cycle was observed, or the printer state appears inconsistent, perform a manual **Firmware Restart** before continuing.

Apply 后安装器会请求重启 Klipper service，并确认 service 返回 `active`。如果没有观察到正常的打印机 / Klipper 重启过程，或机器状态与预期不一致，请在继续使用前手动执行一次 **Firmware Restart**。

## 5. Dry-run / 预览

Before applying changes, always run the installer in dry-run mode.

正式修改前应先运行 dry-run。

Expected dry-run categories:

```text
+ install new managed feature
~ modify / migrate existing managed feature
! remove or disable risky stock behavior
```

The preview should show files to be changed, managed blocks, backend replacements, backup targets, source version, target version, and blockers.

---

## 6. Safe Home runtime behavior / 运行逻辑

### Valid Eddy calibration + Z unknown

```text
safe clearance
→ home X/Y if needed
→ move to configured Z-home XY
→ genuine Eddy Z home
→ post-home Z clearance
→ normal Z-offset / Eddy recalibration
```

### Valid Eddy calibration + Z already homed

Explicit current-Z calibration paths may reuse the established Z reference without forcing another Z home.

如果调用方明确使用 current-Z path，则在已有可信 Z reference 时不强制重复 home Z。

### Missing Eddy calibration

```text
ABORT
```

Safe Home must not fall back to the stock `Zmax + 15` acquisition path.

Safe Home 不应回退到原厂 `Zmax + 15` acquisition。

---

## 7. Expected files / 相关文件

Backend:

```text
/home/sovol/klipper/klippy/extras/M_Bamboo_Safe_Homing.py
/home/sovol/klipper/klippy/extras/z_offset_calibration.py
```

Safe Home also owns `[stepper_z] position_min: -1` as a negative-Z travel safety dependency.
Safe Home 同时管理 `[stepper_z] position_min: -1`，因为它属于负 Z 行程安全边界。

Configuration:

```text
printer.cfg
Macro.cfg
```

Configuration edits are contained in stable managed blocks such as:

```ini
# >>> M_Bamboo_SV08MAX_MOD:SAFE_HOME BEGIN >>>
# Version: 1
# Maintainer: Master_Bamboo / 竹子
...
# <<< M_Bamboo_SV08MAX_MOD:SAFE_HOME END <<<
```

Do not edit Klipper's `SAVE_CONFIG` generated block manually.

不要手工修改 Klipper 自动维护的 `SAVE_CONFIG` block。

---

## 8. Backup & rollback / 备份与回滚

Before modifying any active file:

```text
<file>.mb_baseline
<file>.last_mb_safe_home
```

Rules:

- `.mb_baseline` is created once from the first-seen pre-install state.
- `.mb_baseline` is never overwritten.
- `.last_mb_safe_home` is the bounded previous-version slot for Safe Home on shared files.
- Feature-scoped slots prevent another feature's config state from being rolled back accidentally.
- temporary installer payloads are not backups and are cleaned after install.

Rollback should restore the appropriate saved state and then restart Klipper.

---

## 9. Post-install regression / 安装后回归测试

Recommended minimum regression:

### Test A — Fresh boot, Home All

```text
restart Klipper
→ G28
```

Expected: safe Z clearance before XY movement when Z is unknown; raw X/Y homing does not alter physical Z; Z homes at the configured safe XY location; final state reports `xyz` homed.

### Test B — Screen Home controls

Test Home X, Home Y, Home Z, and Home All. Expected: no crash, no unexpected Z descent, touchscreen commands remain compatible.

### Test C — Screen Eddy recalibration

From a restarted / Z-unhomed state, start the normal Sovol Eddy calibration from the touchscreen.

Expected flow:

```text
G28 X / Y
→ M_Bamboo genuine HOME_Z
→ contact probe
→ verify
→ Eddy recalibration
→ SAVE_CONFIG
→ FIRMWARE_RESTART
```

The normal M_Bamboo path should not show `Z≈520` or `Z≈500` relabels.

### Test D — Missing Eddy data fail-safe

Before public release, perform a controlled and fully recoverable test where the backend sees Eddy calibration as unavailable.

Expected:

```text
calibration request
→ immediate explicit error
→ no heater action
→ no Z probing movement
```

Do not perform this test without a verified backup / restore path.

---

## 10. Factory reset / 恢复出厂后的处理

After a true Sovol factory reset:

```text
M_Bamboo modifications are no longer assumed valid
        ↓
complete Sovol setup again
        ↓
complete Sovol Eddy calibration
        ↓
SAVE_CONFIG
        ↓
reinstall M_Bamboo features
```

Do not reinstall Safe Home before the stock Eddy calibration is complete.

---

## 11. Known non-blocking behavior / 已知但不阻塞发布的问题

On a fresh boot, the Sovol touchscreen may issue independent `G28 X` and `G28 Y`. Because Z remains intentionally unhomed between those commands, the Safe Home backend may perform the unknown-Z safe clearance twice.

This is safe but redundant and is not considered a blocker for Safe Home v1.0.

---

## 12. Release policy / 发布策略

`safe_home` is released as an independent feature of `M_Bamboo_SV08Max_Mods`.

Development labels such as H2 / H3A / H3B-1 / H3B-2 remain internal history and should not appear as user-facing release versions.
