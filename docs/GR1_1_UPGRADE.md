# GR1 to GR1.1 development upgrade

This package targets an existing M_Bamboo RC5 installation. Wait until the printer is idle. It is a development candidate, not a final RC5 release.

From the extracted package directory:

```sh
sha256sum -c SHA256SUMS
sh install.sh eddy_safety
sh install.sh eddy_safety --apply
```

The preview reports planned backend changes. The apply command restarts Klipper. Do not use sudo for the whole installer; it invokes sudo only for the service restart. If the installer refuses an unknown backend hash or invalid original backup, stop and preserve the output; do not force it or delete mb_bak.

For the exact previous combined GR1 candidate with otherwise matching backends, only probe_eddy_current.py changes. The eddy_safety feature does not edit printer.cfg, Macro.cfg, START_PRINT or the G28 macro. Other recognized older backend versions can require additional backend writes; inspect the preview.

After Klipper returns, run in the printer console:

```gcode
M_BAMBOO_RECOVERY_STATUS
M_BAMBOO_EDDY_STATUS
```

Expected supervisor version: RC5-GR1.1, Ready: True. With no intervening fault, Eddy should be healthy. The target probe_eddy_current.py SHA256 is:

```text
119b6bf46f01ea40d2c946ddce7864d29e413b90eb7b7591572d5bed82b41aae
```

GR1.1 adds a bounded no-motion recovery check at qualifying top-level G28 entry when an inherited communication fault exists. The requested G28 supplies the recovery home. It retains the stop on a second fault within a replayed startup stage. Hardware validation of the new entry path remains pending; do not intentionally induce electrical faults.

Installer correction in this package: the previous combined GR1 hash 5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29 is recognized as M_Bamboo lineage, not Sovol stock. Existing original backups remain unchanged. Missing original backups still require validated stock provenance.

Do not use Full Restore as a GR1 downgrade procedure: the previously documented full configuration restore defect remains open. This targeted upgrade does not exercise that path.
