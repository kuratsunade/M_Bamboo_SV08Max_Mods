# GR1.2 correction for GR1.1 G28 entry exception

GR1.1 is superseded. A pending inherited fault reaches a call to PrinterEddyProbe.is_calibrated(), which does not exist. Calibration belongs to PrinterEddyProbe.calibration. GR1.2 calls calibration.is_calibrated(); no recovery policy, macro, threshold or retry limit changes.

The previous test double incorrectly supplied the nonexistent method. The regression now uses the actual source-extracted PrinterEddyProbe and EddyCalibration classes (without hardware initialization). It reproduces AttributeError on GR1.1 and passes all 10 groups with GR1.2. Combined RS1/GR1 regressions also pass. This is not yet hardware validation; the October 8 console lacks the full traceback needed to independently match the on-printer exception.

## Install on the existing RC5 printer while idle

Use this package instead of the superseded GR1.1 ZIP. From its extracted directory:

```sh
sha256sum -c SHA256SUMS
sh install.sh eddy_safety
sh install.sh eddy_safety --apply
```

Apply restarts Klipper. Existing GR1 and GR1.1 backend identities are accepted with preserved original backups. Unknown files remain refused. Do not bypass refusal or delete mb_bak. This targeted update does not modify configuration or macros. The documented Full Restore defect remains open; do not use it for a downgrade.

After successful installation:

```gcode
M_BAMBOO_RECOVERY_STATUS
M_BAMBOO_EDDY_STATUS
```

Expect RC5-GR1.2 and Ready: True. Preserve the October 8 klippy.log before a restart if possible. A firmware restart alone reloads the defective code and does not fix GR1.1. Continue normal printing only after loading the correction; record the next naturally occurring inherited-fault entry without intentionally inducing a fault.
