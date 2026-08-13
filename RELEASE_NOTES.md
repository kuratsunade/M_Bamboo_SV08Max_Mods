# M_Bamboo_SV08Max_Mods — v1.0.0-rc3

[English](RELEASE_NOTES.md) | [简体中文](RELEASE_NOTES_CN.md)

RC3 is a packaging/completeness update based on the successful RC2 real-machine regression.

## Config Optimization completeness fix

RC2 omitted a previously validated `buffer_stepper.cfg` tuning set. RC3 formally adds feature ownership of `[buffer_stepper filament_buffer]`:

- `velocity 150 → 80`
- `accel 5000 → 1900`
- `push_length 25 → 27`

The values use a stable `CONFIG_BUFFER_STEPPER` managed block and participate in feature-scoped baseline/previous-version backup, idempotency, raw diff, validation, and rollback.

## Installer UX

After a successful apply, the installer now states that a Klipper restart was requested and the service reports `active`. It also explicitly asks the user to perform a manual **Firmware Restart** if no normal printer/Klipper restart cycle was observed or machine state appears inconsistent.

## Gitee documentation fix

Gitee README bootstrap examples are normalized to the repository's `master` branch.

## Safe Home regression carried forward

RC2 real-machine testing passed fresh/repeated G28, individual X/Y/Z homing, touchscreen-style homing, raw X/Y `dZ=0`, HOME-FIRST Eddy recalibration, contact verification, absence of the `Z≈520 / Z≈500` runtime path, SAVE_CONFIG restart, and repeated installer apply idempotency.
