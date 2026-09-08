# RC5 Lineage and Hash Policy

> Status: development policy for `rc5-dev`.

## Purpose

RC5 development uses offline hardware-test packages, exact backend candidates, historical public releases, and factory source hashes. These serve different purposes and must not be mixed into one installer/release contract.

The project therefore distinguishes three lineages.

## 1. Public release lineage

Public release lineage is the only lineage that belongs in the final user-facing release contract.

It may contain:

- exact recognized Sovol/factory source hashes required for first takeover;
- exact hashes from previously published M_Bamboo releases that the new release explicitly supports as upgrade sources;
- exact target hashes shipped by the current release;
- checksums for files/assets actually present in the GitHub/Gitee release.

Final public files such as `VERSION_MAP.md`, `SHA256SUMS`, `installer_manifest.json`, and release notes must not claim support for an artifact that users could never have obtained from a published release.

## 2. Development migration lineage

During RC5 hardware development, a real machine may temporarily contain an exact backend that was never publicly released.

Example from the 2026-09-08 hardware candidate:

```text
probe_eddy_current.py
dcb78d4d7d5108236eca23a225e6e582e1b128419bf10c8a5b83cf8de346ced0
```

That exact file hash may be accepted temporarily on `rc5-dev` so the test machine can upgrade safely to the next development candidate without disabling exact-hash fail-closed migration.

Such hashes must be explicitly classified as development-only migration sources. They are not public-release compatibility claims.

Before final RC5 publication, development-only migration hashes must be removed unless the project intentionally publishes and supports the corresponding development artifact as an upgrade source.

## 3. Validation artifact lineage

Offline ZIPs, fault-injection packages, A/B packages, temporary sidecars and other locally generated validation archives exist only to prove what exact bits were tested.

Examples include historical development ZIP/checksum identities such as:

```text
M_Bamboo_SV08Max_Mods_RC5_dev_offline_candidate.zip
```

Their archive hashes may be recorded in engineering/test evidence, but they must not be treated as installer source lineage merely because they existed during development.

A ZIP checksum and the checksum of a backend file installed from that ZIP are different concepts:

- ZIP/archive hash -> validation evidence only;
- installed backend hash -> may temporarily be a development migration source if a real test machine must upgrade from it.

## Release build gate

Final RC5 release preparation must fail if any development-only artifact hash remains in the public compatibility/target manifest.

Conceptually:

```text
for each hash in public release lineage:
    assert hash belongs to factory source,
           a published supported prior release,
           or the current release payload
```

Validation evidence documents may retain historical development hashes because they describe engineering history; production installer compatibility tables may not.

## Why this matters

Keeping these lineages separate provides all three properties we need:

1. exact-hash fail-closed upgrades remain possible during hardware development;
2. test evidence remains reproducible;
3. final users are not exposed to meaningless offline-candidate identities or unsupported compatibility claims.
