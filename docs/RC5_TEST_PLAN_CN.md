# RC5 当前测试计划

更新：2026 年 9 月 9 日。[English](RC5_TEST_PLAN.md) | [证据与发布阻塞](RC5_TEST_EVIDENCE_CN.md)

## 现在需要你测试什么

已经安装组合版且运行正常时，无需为了重复注册或单独健康 G28 验证而重新安装。下次测试开始先记录：

```gcode
M_BAMBOO_EDDY_STATUS
M_BAMBOO_RECOVERY_STATUS
```

同时保留实际后端 SHA256、温度、耗材、任务标识和会话开始时间。GR1 应为 ready，并列出六个包装命令。仅凭 Runtime Safety 标签无法区分 RC4 与当前组合版。

| 优先级 | 实机内容 | 判定与记录 |
| --- | --- | --- |
| 1 | 正常切片 START_PRINT 与真实打印，覆盖自然发生的冷机、热机启动 | 完整启动、首层、END_PRINT、下一次启动；保留日志及首层观察。检查校准 flag、速度设置、Z 信任和重复恢复异常。失败任务同样计入记录。 |
| 2 | 正常准备中的完整 BED_MESH_CALIBRATE | 完整 wrapper 成功。如遇自然故障，区分发生在校准、归零还是 active rapid scan。 |
| 3 | 快速扫描运行期间的自然故障 | 丢弃失败网格，过期回调不造成 flush shutdown；通信验证、必要时重建 Z，完整重跑所属操作一次并成功。此项仍缺实机证据。 |
| 4 | START_PRINT 某阶段自然故障 | MBSTART 保持最外层 owner，嵌套 GR1 不重复恢复。重跑完整阶段；每阶段调用最多一次恢复，每次 START 最多三个独立事件。同阶段未完成前再故障、或恢复失败，应终止。 |
| 5 | ZCAL 不收敛或首层异常 | 保留初始 contact、每次 contact Z、相邻 delta、实际 XY、温度、喷嘴清洁状态、探测次数及通信故障标记。暂不放宽阈值，也不拿单次 contact 当精密漂移测量。 |

以正常任务积累覆盖，没有证据支持某个固定打印次数即可判定稳定。复盘应看累计使用量、所有失败及覆盖场景。一次 QGL raw34 恢复和多次健康网格已证明过，单纯重复这些不能填补扫描、START 故障场景。

## 遇到自然故障时

先让当前最外层 owner 完成恢复或终止，不在自动恢复中插入手动恢复。结束后保存两个状态命令输出、完整 console 和覆盖故障前后到最终结果的 klippy.log。需能看清 raw code、fault sequence、失败事务、owner/stage、quarantine、身份读取、Z 信任、重跑起点与结果。二次故障或恢复失败即结束本次测试，按实际提示处理重启，不连续尝试向床动作。不制造接线故障、不强制撤销 Z、不做撞床实验。

`BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=1 METHOD=rapid_scan` 可用于健康扫描诊断，但 BASE 不属于 GR1 的六个公开 owner，不能期待它单独获得 GR1 自动重跑。验证完整恢复优先使用 `BED_MESH_CALIBRATE`。

RC4 Public Soak 工具仍严格校验 RC4 后端，不绕过 preflight，也不标为 RC5 已验证工具。其手动恢复 wrapper 可能干扰自动 owner 取证。

## 发布前由维护侧完成的离线工作

1. 修复并验证原厂 START_PRINT 安装入口，同时继续拒绝未知改动。修改前机器快照独立验证，不视为当前机器状态。
2. 修复 CONFIG_START_PRINT_CORE 的逆向恢复，确认后端恢复后没有遗留运行依赖；覆盖完整恢复、按功能恢复和 fallback 组合。
3. 对确切组合版重跑 dry run、apply、第二次 apply 零写入、失败回滚、Full Restore，核对后端原始字节、配置语义及 SAVE_CONFIG 保持。不能放宽旧检查来换取 PASS。
4. 保留二次故障、恢复失败、延迟回调与 ownership mock；没有自然实机事件时，实机对应项继续标为待验证。
5. 历史离线 runner 与 RC5 契约对齐后，才能声称全部历史检查通过。发布时再制作并验证 GitHub、Gitee 两套包，核心内容与验证状态一致。

本次文档更新保持运行时代码、PREARM、START_PRINT 顺序、健康快速扫描测量与 ZCAL 阈值不变。
