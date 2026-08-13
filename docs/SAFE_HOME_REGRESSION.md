# Safe Home v1.0.0 — Final Regression Checklist

Run this checklist after the production installer has been applied.

## A. Fresh boot / Home All

1. Restart Klipper or power-cycle the printer.
2. Do not manually home any axis first.
3. Run `G28`.

Expected:

- unknown-Z safe clearance occurs before XY travel;
- raw X/Y homing reports no physical Z drift;
- Z homes at `271,251`;
- post-home Z is `10`;
- final homed axes are `xyz`.

## B. Individual homing / 单轴回零

Test `G28 X`, `G28 Y`, and `G28 Z` (Z after XY are homed).

Expected: no unsafe downward travel and touchscreen ABI remains compatible.

## C. Touchscreen Home

Test Home X / Y / Z / All from the Sovol screen.

Known v1.0 behavior: on a fresh boot, separate screen `G28 X` then `G28 Y` may perform the unknown-Z +5 mm clearance twice. This is safe but redundant.

## D. Touchscreen Eddy recalibration

From a restarted, Z-unhomed state, start Eddy Current Sensor Calibration from the touchscreen.

Expected sequence:

```text
G28 X / G28 Y
→ M_Bamboo HOME_Z
→ genuine Eddy Z home
→ current-Z contact probe
→ contact verification
→ Eddy non-contact recalibration
→ SAVE_CONFIG
→ FIRMWARE_RESTART
```

Must NOT appear in the active M_Bamboo path:

```text
z_max_position + 15
Z≈520 acquisition
Z≈500 verify relabel
```

## E. Missing-Eddy runtime fail-safe

This is the final destructive/controlled test before removing the RC label.
Only perform it with a verified restore path.

Expected:

- `Z_OFFSET_CALIBRATION` reports missing Eddy calibration immediately;
- no heater action caused by the calibration command;
- no contact-probe Z descent caused by the calibration command;
- `G28 Z` / Home All refuses Z homing while Eddy data is missing;
- X/Y-only homing remains available.

Restore the saved configuration immediately after the test.
