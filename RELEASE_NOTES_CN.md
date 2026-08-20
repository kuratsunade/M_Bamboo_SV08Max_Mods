# M_Bamboo_SV08Max_Mods — Release Notes / 版本记录

[English](RELEASE_NOTES.md) | [简体中文](RELEASE_NOTES_CN.md)

本文档是 public release 与 engineering candidate 的**追加式版本历史**，专门回答“每一版相对上一版改了什么”。设计原因请看 `docs/TECHNICAL_FAQ_CN.md`；命令和参数用法请看 `docs/COMMAND_REFERENCE_CN.md`。

---

## v1.0.0-rc4 — Release Candidate（2026-08-20）

- First-takeover migration 在已识别 M_Bamboo lineage 的 legacy baseline 缺失或被污染时，可从 Sovol factory mirror 恢复可信原厂 backend；factory mirror 仍必须精确匹配已知原厂 SHA256，不能仅凭路径获得信任。
- 该 fallback 已在真实旧 M_Bamboo 机器迁移中通过：`mb_bak/MANIFEST.json` 从精确匹配 SHA256 的 factory original 建立，`M_Bamboo_Safe_Homing.py` 正确记录为 originally absent。

RC4 冻结当前已经过实机验证的 `ES-R4-EC2-FS1.1` runtime，并把项目从 engineering-only backend package 提升为 whole-project Release Candidate installer。本次 release installer 重构**不改变**已经验证过的 FS1.1 runtime safety Python。

### Installer / Restore Architecture v2

- CFG / macro 不再创建 persistent whole-file backup。RC4 只管理稳定的 `M_Bamboo_SV08MAX_MOD` transformation，并通过明确 inverse operation 恢复。
- 新增 block 在 restore 时删除；被替换的 stock 参数恢复原值；被删除/替换的 stock section 使用 release-owned exact restore template 重建；`SAVE_CONFIG` 自动生成 tail 永不修改。
- Backend Python 只保留一个集中 `/home/sovol/klipper/klippy/extras/mb_bak/` original-state archive 和 `MANIFEST.json`，只创建一次、永不覆盖。
- 旧 `.mb_baseline` 仅作为已有 M_Bamboo 安装迁移到新 backup schema 的输入；RC4 不再创建新的 `.mb_baseline`、`.last_mb_*` 或时间戳备份系列。
- Install / restore 全部通过 installer 自己的 `/tmp/M_Bamboo_SV08MAX.*` transaction scratch 做即时失败回滚，失败时恢复本次操作前 exact bytes。
- Python compile verification 的 bytecode 只写入 transaction scratch，不在 live extras 中主动制造 `__pycache__`。
- RC4 只保留一个 release removal primitive：Full Restore 回到 M_Bamboo 接管前的 original state。RC4 不实现 generic historical downgrade 命令；如需安装旧版，先 Restore，再运行目标历史 release 自己的 installer。
- 在 M_Bamboo 已建立 ownership 后，如果发现未知 backend 内容，installer 会拒绝覆盖，而不是猜测 lineage。

### 实机 Evidence

Healthy path 已覆盖反复 G28/Safe Home、contact、NC-R1 清嘴、Z calibration、QGL、adaptive rapid mesh、final XY re-home、完整 slicer START_PRINT、真实 cube 打印、END_PRINT 中机器既有的 `clear_plr` cleanup hook，以及打印后的 Eddy status。最近一次 healthy session 记录累计 30 次 pre-arm check，transport fault / transient recovery / pre-arm failure / forced quarantine / repeated-fault suppression 全部为 0。随后又自然捕获到一次 raw-34（`I2C_BUS_NACK | I2C_BUS_BUSY`）active contact-probe 故障，并完成安全中止、stream quarantine、recovery check、armed fresh G28、恢复 HEALTHY 与重新进入打印的完整链路，无需 firmware reset。

这些结果强烈支持 pre-arm transport-quiescence gate 确实降低了 observed raw-34 incidence，也支持部分 raw-34 与 I2C/session transition boundary 有关的 working hypothesis。但 RC4 **不宣称 raw-34 已被彻底消灭**。升级 stable 前仍需下一次自然 FS1.1 transport fault 来完成 forced stream quarantine + full recovery 的端到端实机验证。

---

## ES-R4-EC2 — Engineering Candidate

### Fault-storm 安全热修 FS1（2026-08-19）

- 修复真实机器在 `START_PRINT` 的 `CLEAN_NOZZLE` 后出现的故障：Eddy/I2C fault 发生后，contact-probe 命令虽已 abort，但 LDC periodic bulk query 可能仍保持运行，从而无限产生新的 `ldc1612_i2c_report` / transport fault，最终可能只能断电恢复。
- Eddy bulk client 改为确定性注销，不再依赖“下一批成功 sample”才能结束。
- confirmed runtime transport fault 时强制 quarantine LDC periodic stream，并重置 `BatchBulkHelper` 状态，使后续 recovery 能重新启动干净 stream。
- contact probe 增加 `try/finally` cleanup；Eddy calibration client 也主动清理。
- 同一 fault episode 的重复 HARD_COMM_FAULT console 信息会被抑制，但 fault counter 与最后 evidence 仍完整保留。
- `M_BAMBOO_EDDY_STATUS` 新增 forced stream quarantine 与重复信息抑制统计。
- Installer 支持 Transport Hardening R3 直接升级，并验证可精确 rollback 回 R3。

**状态：** 已通过 offline validation；尚未完成真实机器验证。  

### 实机验证前的 Package / README / Installer 更新

- 参照 RC 版本线的 README 组织方式，把 README 恢复为项目级入口：包含项目目标、feature overview、safety model、安装/测试流程、文档地图、当前边界与简短 Overview FAQ。
- 新增严格受限的 `es_r4_ec2` test installer：默认 dry-run，支持 status/raw-diff/apply/rollback，校验 exact base/target hash，使用有上限备份，执行 `py_compile`、写入后 checksum 校验、Klipper host restart/health check，并在 apply 失败时自动尝试 rollback。
- EC2 test installer 故意只接受已识别的 RC4/ES-R3 + ZC-FR1/Safe Home lineage 或已经安装 EC2 target 的状态；未知 backend hash 直接阻止，Engineering Candidate 不提供 `--force`。
- 手工部署保留为 fallback，不再作为首选测试流程。

**基础：** RC4 development baseline + ES-R3 + ZC-FR1；在进入硬件验证前取代 ES-R4-EC1。

### 首次真实 transport-fault 验证与 Recovery UX

#### Transport hardening follow-up（2026-08-19）

- 在 Safe Home Z homing、普通/contact probe session 启动、Eddy calibration、bed-mesh scan session 启动前加入 **pre-arm transport quiescence gate**。该 gate 只进行无运动 LDC identity read，在 bed-facing motion 或 measurement session 真正开始前确认总线状态。
- 健康状态下一次两组 clean read 即通过（host-side nominal settle budget 约 75 ms）。若观察到 transient/failure，motion 保持不动，并在最多三次的 bounded sequence 内要求连续两个 clean window 才放行；不存在无限 retry。
- preflight 内出现 transport fault 时会立即记录并汇报，但由于尚未开始 bed-facing motion，不会把它伪装成一个已经发生的 motion transaction taint。若 bounded gate 自主恢复，现有 Z trust 保持不变，并只把当前 fault sequence 标记为 trusted-through；历史 fault evidence 不会被抹掉。
- 若 preflight 最终仍无法确认稳定，总是先拒绝 motion。之后 `M_BAMBOO_EDDY_RECOVERY_CHECK` 若成功，可直接恢复 transport 而无需 recovery `G28`，因为 pre-arm fault 没有使 Z 失去信任；真正 active-motion fault 仍严格使用 recovery-check -> one-shot armed G28。
- 增加 pending sequence 与延迟 reactor callback 的 sequence 去重，同一 I2C report 不会被 policy 处理两次，也不会在 pre-arm transient 已被吸收后再次迟到 latch。
- `M_BAMBOO_EDDY_STATUS` 新增 session transport statistics（fault count/type/context、pre-arm recovery/failure、recovery-check、armed-recovery success），并明确分离 **current transport health** 与 Sovol `err_code/i2c_report_seen` 的历史 telemetry。
- 仍不加入双 G28 抑制、自动 G28，也不会 retry 已经开始的 downward transaction。

- Installer partial-upgrade rollback 修正：任何 EC2 apply 只要有一个 managed file 变化，就先同步刷新全部五个 backend 的 rollback snapshot，确保 rollback 回到 coherent pre-apply state。
- Installer 现在把首次上机安装的旧 EC2 target hashes 作为合法 upgrade lineage；无需先 rollback，可直接从旧 EC2 升级到当前 recovery revision。
- 真实 SV08 Max 在 back-to-back `G28` 场景捕获 `err_code=34`，已确认解码为 `I2C_BUS_NACK | I2C_BUS_BUSY`；当前 action 被立即 taint/abort，active trsync `SENSOR_ERROR` stop request 实机触发成功。
- 修正用户侧语义：当 `SENSOR_ERROR` reason 是 ES-R4 为 transport fault 主动请求的 stop channel 时，不再显示成“Eddy current sensor error”，而明确显示为 transport fault / action aborted。
- 新增 transport state：`HEALTHY`、`TRANSPORT_FAULT`、`TRANSPORT_RECOVERED`、`HARD_COMM_FAULT`。Bus recovery 与 transaction validity / Z trust 明确分离。
- 新增 `M_BAMBOO_EDDY_RECOVERY_CHECK`：无运动、三次 LDC identity read + per-read reactor settle + fault-sequence guard。成功只表示 transport recovered，Z 仍保持 untrusted。
- recovery check PASS 后只 armed **一次** Safe Home Z recovery；普通 PROBE/QGL/contact/mesh 不能消费 token。fresh Z home 成功才回到 `HEALTHY`；armed recovery 再次失败则要求 `FIRMWARE_RESTART`。
- transport fault 发生后会立即给出可执行 guidance，而不是把 `BUSY/NACK/TIMEOUT` 直接等同于永久 sensor hardware failure。
- 暂不加入双 `G28` debounce/抑制，也不自动运行 recovery scan / G28。

### Transport fault integrity 加固

- 新增 pending / unhandled transport-fault gate，关闭 serial thread 收到 I2C fault 到 reactor safety callback 实际执行之间的调度窗口。
- 保留单调递增的 `transport_fault_seq` transaction-integrity 模型，并增加 Eddy Safety Core 已处理 sequence 的确认状态。
- fault classification 改为 severity 只能单向升级：如果先看到 `PROBE_NO_TRIGGER`，随后收到更强的直接 I2C evidence，可以升级为 `HARD_COMM_FAULT`。
- 将 first fault 与 strongest/current fault 分开保存，避免诊断丢失最初症状或更强证据。
- active trsync-backed downward probe 继续可以请求 `SENSOR_ERROR` stop；scan/rapid-scan 只做 transaction taint/reject，不伪装成拥有 Z trsync。

### Transaction lifecycle 与 event tracing

- 失败 transaction 一旦进入 `ABORTED` 就是 terminal state；后续 halt-position reconstruction 只作为 evidence 记录，不能把 transaction“复活”。
- 对 homing 与普通 probing 都记录真实 halt-position reconstruction。
- 普通 probe 在完整 transport-integrity 与 probe-result 流程结束前，不把 trigger 直接视为最终 SUCCESS。
- `M_BAMBOO_EDDY_STATUS` 新增有长度上限的 per-transaction fault evidence timeline。
- transport fault 记录 host receive time、reactor handle time 与 reactor scheduling delay，方便后续分析 active-stop latency。

### Persistent calibration safety

- `PROBE_EDDY_CURRENT_CALIBRATE` 在 calibration motion 前以及 pending calibration 写入前都进入统一 Eddy safety preflight。
- 在通用 `probe.py` 加入一个非常小的 persistent-config validation hook；Eddy backend 在 `PROBE_CALIBRATE` / `Z_OFFSET_APPLY_PROBE` 写 pending config 前使用它。
- `LDC_CALIBRATE_DRIVE_CURRENT` 继续使用 transaction guard，transport-tainted result 不允许成为持久配置。
- drive-current calibration 不再恢复一个可能来自失败 I2C read 的 `old_config`，改为恢复这版 Sovol 已知的 measurement-mode CONFIG。
- 继续删除 Sovol runtime `SENSOR_ERROR -> reg_drive_current=0` 的配置修改行为。

### Z calibration 与 coordinate trust safety

- ZC-FR1 增加 guarded Z-sensor call：即使 safety preflight 在 `HomingMove` 创建前就拒绝操作，也会明确撤销 Z trust。
- 避免 current-Z allowance 使用的临时 logical Z rebase 在 fault 后仍被保留为可信 Z。
- 继续保留 EC1 引入的 atomic Safe Home real-Z-reference orchestration。

### 文档与 package hygiene

- 继续扩展 project-wide Command Reference，并补入此前漏掉的 `Z_OFFSET_APPLY_PROBE`。
- 新增机器可验证的中英文 Command Reference coverage gate。
- 恢复并扩展这份 append-only Release Notes，并把 Release Notes 存在性/版本覆盖纳入 package validation。
- 新增 package-level `README.md` / `README_CN.md` 入口页。
- 增加 deployment/rollback 与 hardware-validation guide。
- 从 distribution package 移除 `__pycache__` / `.pyc`。
- 重新生成 patch/checksum，并验证 exact-base → apply patch → packaged backend 的 round-trip 一致性。

### 相比 EC1 的 patch surface 变化

EC2 有意新增 `probe.py` 为 deployable backend file，用于 generic persistent-config validation hook。

仍然不修改：

- MCU firmware
- `bed_mesh.py`
- `mcu.py`
- `homing.py` 继续保持 exact ES-R3 reference payload

---

## ES-R4-EC1 — Engineering Candidate

**状态：** 在进入真实机器验证前已被 ES-R4-EC2 取代。

### Eddy transport safety

- 对 Sovol STM32 I2C error bitmask 做完整解析，不再只把 `err_code=36` 当作特例。
- 新增单调 transport-fault sequence 与 transaction-local fault snapshot。
- 在 Eddy Safety Core 中引入结构化 transport evidence 与 session fault latch。
- 任何 transaction 只要期间出现 transport fault，后续都不能被接受为成功。
- 对已经 arm 的 downward Eddy homing/probing 加入 active trsync `SENSOR_ERROR` stop path，不修改 MCU firmware 或 `mcu.py`。
- scan/rapid-scan session 进入同一个 fault authorization；scan fault 会 taint/reject transaction。
- selective-backport command-error scan cleanup 语义，但不替换 `bed_mesh.py`。

### Safe Home recovery orchestration

- 将 Safe Home 重构为 atomic real-Z-reference sequence：Z 不可信时先建立正向 clearance，再允许 XY motion。
- 修复 `HOME_Z` recovery gap：X/Y 仍 homed、Z 已 invalidated 且 nozzle 处于低位时，不再先横向移动。
- ZC-FR1 HOME-FIRST 改为调用 atomic Safe Home API，不再使用 `prepare_xy_for_calibration() + cmd_HOME_Z()` 两段式流程。
- 避免 double-hop，同时保持现有 touchscreen/public G-code 名称不变。
- `prepare_xy_for_calibration()` 标记为 Internal / Deprecated，新代码不再调用。

### Calibration safety

- drive-current calibration 纳入 transport-sequence guard。
- 删除 Sovol runtime sensor error 后把 pending `reg_drive_current` 改成 0 的行为。

### 文档

- 建立中英文 project-wide Command Reference / Public Interface Registry。
- 扩展 Technical FAQ，记录已经确认的 Sovol I2C / error-propagation 设计错误。
- 增加初版 deployment、rollback 与 hardware-validation 文档。

---

## v1.0.0-rc3

RC3 是在 RC2 已完成真实机器 regression 后，对 package completeness 与 installer UX 的补全版本。

### Config Optimization 补全

- 正式补入 RC2 package 遗漏的 `[buffer_stepper filament_buffer]` 调优：
  - `velocity 150 -> 80`
  - `accel 5000 -> 1900`
  - `push_length 25 -> 27`
- 使用稳定的 `CONFIG_BUFFER_STEPPER` managed block。
- 纳入 feature-scoped backup、幂等检查、raw diff、validation 与 rollback。

### Installer UX

- apply 成功后明确说明已经请求 Klipper restart，并显示 service 返回 `active`。
- 如果没有观察到正常 restart cycle 或机器状态异常，明确提示手动执行 **Firmware Restart**。

### 文档

- Gitee bootstrap 示例统一到仓库实际使用的 `master` branch。

### 延续 RC2 实机 regression

RC2 已验证 fresh/repeated G28、X/Y/Z 独立 homing、touchscreen-style homing、raw X/Y `dZ=0`、HOME-FIRST Eddy recalibration、contact verification、正常 runtime 无 `Z~520 / Z~500` path、SAVE_CONFIG restart，以及重复 installer apply 幂等性。

---

## v1.0.0-rc2

RC2 将最初只包含 Safe Home 的 production package 扩展为两个 feature-aware 模块。

### Safe Home

- 保留需要时先进行 genuine HOME_Z、再做 normal Eddy recalibration 的路径。
- 保留 factory-bootstrap boundary：缺失 Eddy calibration 时直接 abort，不回退到 `Zmax + 15` / 约 `Z520`。
- 正式把 `[stepper_z] position_min: -1` 纳入 Safe Home ownership，作为 Z safety dependency。
- 继续保持原厂触摸屏 G28 compatibility。

### Config Optimization

新增 `config_optimization` feature：

- `max_velocity 700 -> 400`
- `max_accel 40000 -> 15000`
- X/Y TMC5160 `run_current 3.0 -> 2.3`
- QGL `speed 400 -> 200`
- QGL `retries 15 -> 5`
- QGL `max_adjust 20 -> 5`
- Adaptive Mesh `PGP=0 -> PGP=1`
- randomized / cross-hatch `CLEAN_NOZZLE`
- START_PRINT acceleration 与两阶段 current-Z Z-offset verification

Config Optimization 依赖 Safe Home，因为 START_PRINT calibration 调用依赖 Safe Home 的 current-Z 语义。

### Installer

- 支持 `safe_home`、`config_optimization` 与 `all` feature selection。
- `all` 按依赖顺序安装。
- 多 feature 共享配置文件时使用数量受控的 feature-scoped previous-version snapshot。
- `.mb_baseline` 继续作为 first-seen baseline。
- Bootstrap 校验 `SHA256SUMS` 并清理 installer 自己创建的临时文件。

### 文档

- README 与 Release Notes 分拆为英文/简体中文页面。
- 增加 Config Optimization 文档与 AI-assisted development disclosure。

---

## v1.0.0-rc1

Safe Home feature 的第一个 Release Candidate。

### Safe Home

- 新增 `M_Bamboo_Safe_Homing.py`。
- 使用已验证的 M_Bamboo runtime implementation 替换 active Sovol `z_offset_calibration.py`。
- 移除 active `[homing_override]` 并保留明确 managed tombstone。
- 通过 managed macro 保持 touchscreen G28 ABI。
- Z unknown 时，在正常 Eddy recalibration 前先建立真实 Z homing reference。
- 对已有可信 Z reference 的 caller 保留显式 `USE_CURRENT_Z=1` refinement 语义。
- 从 M_Bamboo runtime path 移除 Sovol `Zmax + 15` / 约 `Z520` bootstrap path。
- Eddy calibration 缺失时视为明确 install/runtime boundary，要求先完成 Sovol stock bootstrap。
- 不修改 MCU firmware。

### Installer

- 默认 dry-run。
- Safe Home install 前验证 Eddy calibration。
- 使用数量受控的 baseline / previous-version backup。
- 安装前后运行 Python compile validation。
- 默认 restart Klipper 并检查 service state。
- validation/restart 失败时自动恢复 apply 前的精确 bytes。
- 支持 rollback、baseline restore、raw diff 与 no-restart 选项。

### ES-R4-EC2-FS1.1 — 诊断命令关机 Hotfix
- 修复 FS1 新诊断字段导致的 `M_BAMBOO_EDDY_STATUS` NameError（`raw` 未初始化即使用）。
- Status 现在先执行 `raw = self._raw_diag()` 再格式化 quarantine 计数。
- 新增 AST 离线回归门，防止该未定义局部变量问题再次出现。
- Fault-storm stream quarantine 安全逻辑保持不变。

## ES-R4-EC2-FS1.1 — 文档 / 实机证据更新（2026-08-20）

- Backend behavior 不变，safety label 继续为 `ES-R4-EC2-FS1.1`。
- 正式记录促成 pre-arm transport quiescence gate 的原始 active-motion raw-34（`NACK | BUSY`）问题、为什么 ACTIVE motion 仍禁止 retry，以及 FS1 fault-storm containment 与 pre-arm prevention 的不同职责。
- 固化真实机器 healthy-path 证据：反复 homing/contact/nozzle-clean/Z-calibration、QGL、adaptive rapid mesh、完整 slicer START_PRINT、真实 cube 打印、END_PRINT including the stock `clear_plr` cleanup hook 和 post-print diagnostics。
- 最新 post-print session：30 次 pre-arm checks，0 transport faults，0 transient recoveries，0 pre-arm failures，0 forced quarantines，0 repeated-fault suppressions。
- 当前结论是“observed raw-34 incidence 明显下降，并支持 I2C/session transition boundary 工作假设”，**不是**“error 34 已被彻底消除”。
- FS1.1 继续保持 Engineering Candidate，但此前缺失的自然 fault-path gate 已经完成一次实机闭环：一次自然 raw-34 active contact-probe 故障触发安全中止、Z trust 撤销与 forced LDC stream quarantine；主机保持响应，无运动 recovery check 通过，armed fresh G28 成功恢复 transport 与 Z trust，随后无需 firmware reset 即继续完成打印准备并进入打印。后续仍需更多自然故障 soak，不能把一次成功事件解读为所有时序与故障组合都已完全证明。
