# Repository content and archive policy

Updated 2026-09-09. 中文说明：内部交接已先归档，再从当前分支移除；运行所需迁移识别、恢复模板及测试证据仍保留，不通过删文件破坏升级或恢复能力。

## Removed from the branch tree

The two conversation handoff exports and their dedicated handoff packaging workflow were saved in `RC5_Engineering_Archive_20260909.zip` before removal. The archive contains exact standalone copies, per-file SHA256, restoration instructions and a verified self-contained Git bundle for rc5-dev at `b2eb2bf3b1539e36a414ee6559404395a96b70a3`.

These exports contain conversation context, local paths and temporary artifact references that are unnecessary for end users. Current operational decisions and test evidence are retained in the test plan, evidence, version map and design documents.

This removes files from the current tree only. Existing commits and previously uploaded Actions artifacts may still expose earlier copies. It is not a history purge or a promise of retrospective privacy. No force push or history rewrite was performed.

## Kept because other components depend on them

| Files | Reason |
| --- | --- |
| installer.py provenance/hash tables and installer_manifest.json development_lineage | Required to recognize real installed development bytes without accepting arbitrary mutations. Removing these can break migration. |
| release/restore_templates and managed config blocks | Required for installation and inverse restoration. A restore bug must be fixed, not hidden by deleting its inputs. |
| validation fixtures and migration/provenance tests | Reproducible original-state and upgrade safety checks. |
| patches 09/10/11, deterministic GR1 script, materialization/finalization tools and workflows | Referenced by the combined candidate build chain. Removal requires a separately validated replacement build contract. |
| Design, root-cause and lineage documentation | Technical rationale and reproducibility, with private conversation exports removed. |
| RC4 public Soak toolkit | Existing public tool with strict RC4 compatibility; not relabeled as RC5 qualified. |

At final release, review a separate distribution file list. Public user packages need installer runtime, required config/restore payload, exact checksums, license and user docs; build-only material need not be bundled merely because it remains in source control. Keep GitHub/Gitee core payload and validation state aligned. Do not invent a release export gate before both package variants are verified.

## Recovery of archived material

Use the saved bundle for an isolated checkout, or retrieve the exact paths from source commit b2eb2bf3b1539e36a414ee6559404395a96b70a3 in existing history. Runtime migration does not load the removed handoff documents or packaging workflow.
