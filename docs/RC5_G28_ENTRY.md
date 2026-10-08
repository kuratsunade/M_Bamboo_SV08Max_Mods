> GR1.1 is superseded by [GR1.2](GR1_2_UPGRADE.md), which fixes an AttributeError in the inherited-fault G28 entry. Do not install the old GR1.1 artifact.

# RC5 GR1.1: inherited communication faults at G28 entry

Development candidate, not yet hardware validated. No START_PRINT, Safe Home, G28 macro, MCU or retry-limit changes.

## Behavior

The existing GR1 wrapper now checks inherited transport faults for an outermost `G28` or Z-only `G28 Z`. It consumes pending reports, refuses restart-locked states and uncalibrated probes, and runs one no-motion transport health check. The original G28 handler then executes exactly once. The requested home is the recovery home; GR1 does not separately home and replay G28. Any check, homing or postcondition failure is terminal for that invocation. The inherited-fault path consumes the one recovery allowance. START-owned and nested calls bypass this entry policy, preserving their existing owner.

Healthy commands pass unchanged. XY-only commands receive no added Z recovery. The current macro prioritizes X/Y when Z is also specified. Consequently mixed-axis requests containing Z are refused *only when an inherited transport fault needs handling*. Use `G28` or `G28 Z`; do not reinterpret the existing macro in this patch. No axis-choice change is made on the healthy path.

The requested G28 remains subject to existing Safe Home prerequisites. Z-only homing with unhomed X/Y can fail; this patch does not silently add XY homing. No background recovery, firmware reset, whole-job replay or START_PRINT wrapper is introduced. Each independent G28 retains its own allowance; it does not share a job-wide budget with later START_PRINT. Existing healthy-entry/new-fault recovery behavior remains unchanged.

## Validation

Local source-extracted regression covers all-axis and Z-only entry, unchanged healthy axis combinations, XY-only passthrough, mixed-Z rejection under inherited fault, locked and uncalibrated rejection, failed checks, failed homes with/without new faults, nested/START ownership, postcondition failure and existing fresh-fault recovery. Existing RS1/GR1 mock tests also pass. Mocks do not establish motor behavior, real macro cancellation timing or hardware reliability.

Hardware checks: compare healthy `G28` and `G28 Z` against the current version; check XY-only behavior; on a natural inherited fault confirm one entry check and one requested homing operation, then healthy transport and homed Z. Preserve console and klippy logs. Do not induce electrical failures. Existing installer release blockers remain open.

The historical automatic metadata finalizer is now manual-only and retains its old exact-runtime guard. It must not rewrite a new candidate's metadata. Candidate hashes and accepted previous development hashes are updated together in this commit.

## 中文

本次仅在现有 GR1 中补充遗留通信故障入口，不修改 START_PRINT、G28 宏或 Safe Home，不增加重试次数。`G28` 或仅含 Z 的 `G28 Z` 先执行一次无运动通信检查，再由原 G28 完成本次归零；不额外归零后重跑。检查或归零失败立即结束，不能再获得第二次自动恢复。

纯 X/Y 命令不增加恢复 Z 运动。现有宏对混合轴参数有 X/Y 优先行为，因此只有在遗留故障需要处理时，含 Z 的混合轴请求会被拒绝并要求使用明确的命令。健康路径保持原行为。START 内部及嵌套调用继续由原最外层协调器负责。

此版已通过本地 mock 回归，尚未实机验证。每个独立 G28 与后续 START_PRINT 分别计数，不宣称共享打印任务总预算。Z 状态文案与校准上下文的进一步诊断修正不包含在本次小范围补丁中。
