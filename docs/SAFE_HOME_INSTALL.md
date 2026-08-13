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

A production installer should verify at least:

```text
[ ] target machine looks like Sovol SV08 Max
[ ] expected Klipper directories exist
[ ] printer.cfg / Macro.cfg are writable
[ ] probe_eddy_current section exists
[ ] valid Eddy calibration data exists
[ ] active backend version is recognized
[ ] backup slots are writable
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

## 3. Installer commands / 安装命令

From the extracted `M_Bamboo_SV08Max_Mods` release directory:

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

## 4. Dry-run / 预览

Before applying changes, always run the installer in dry-run mode.

正式修改前应先运行 dry-run。

Expected dry-run categories:

```text
+ install new managed feature
~ modify / migrate existing managed feature
! remove or disable risky stock behavior
```

The preview should show:

- files to be changed
- managed blocks to be inserted / replaced
- backend files to be replaced
- backup targets
- detected source version
- expected target version
- warnings / install blockers

---

## 5. Safe Home runtime behavior / 运行逻辑

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

## 6. Expected files / 相关文件

Backend:

```text
/home/sovol/klipper/klippy/extras/M_Bamboo_Safe_Homing.py
/home/sovol/klipper/klippy/extras/z_offset_calibration.py
```

Configuration:

```text
printer.cfg
Macro.cfg
```

Configuration edits should be contained in stable managed blocks such as:

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

## 7. Backup & rollback / 备份与回滚

Before modifying any active file:

```text
<file>.mb_baseline
<file>.last_mb_ver
```

Rules:

- `.mb_baseline` is created once from the first-seen pre-install state.
- `.mb_baseline` is never overwritten.
- `.last_mb_ver` is refreshed before each M_Bamboo upgrade.
- temporary installer payloads are not backups and should be cleaned after install.

Rollback should restore the appropriate saved state and then restart Klipper.

回滚时应恢复对应备份，然后重启 Klipper。

---

## 8. Post-install regression / 安装后回归测试

Recommended minimum regression:

### Test A — Fresh boot, Home All

```text
restart Klipper
→ G28
```

Expected:

- safe Z clearance before XY movement when Z is unknown
- raw X/Y homing does not alter physical Z
- Z homes at the configured safe XY location
- final state reports `xyz` homed

### Test B — Screen Home controls

Test:

- Home X
- Home Y
- Home Z
- Home All

Expected: no crash, no unexpected Z descent, touchscreen commands remain compatible.

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

## 9. Factory reset / 恢复出厂后的处理

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

## 10. Known non-blocking behavior / 已知但不阻塞发布的问题

On a fresh boot, the Sovol touchscreen may issue independent:

```text
G28 X
G28 Y
```

Because Z remains intentionally unhomed between those commands, the Safe Home backend may perform the unknown-Z safe clearance twice.

This is safe but redundant and is not considered a blocker for Safe Home v1.0.

在 fresh boot 下，触摸屏可能分开发送 `G28 X` 与 `G28 Y`，因此 unknown-Z safe clearance 可能执行两次。该行为安全但略显冗余，目前不作为 v1.0 阻塞项。

---

## 11. Release policy / 发布策略

`safe_home` should be released as an independent feature of `M_Bamboo_SV08Max_Mods`.

Recommended first public feature version:

```text
Safe Home v1.0.0
```

Development labels such as H2 / H3A / H3B-1 / H3B-2 should remain internal history and should not appear as user-facing release versions.

H2 / H3A / H3B-1 / H3B-2 等开发阶段命名应仅保留在开发历史中，不作为最终用户版本号。
