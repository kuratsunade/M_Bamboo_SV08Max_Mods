# RC4 Deployment, Restore, and Transaction Rollback

This document describes the **current v1.0.0-rc4 installer contract**. It does not document historical EC2 test-installer behavior.

## 1. Dry run first

```bash
./install.sh all
./install.sh all --status
./install.sh all --raw-diff
```

No machine file is changed without `--apply`.

## 2. Apply

Canonical software install:

```bash
./install.sh all --apply
```

Feature-scoped install is available for:

```bash
./install.sh safe_home --apply
./install.sh config_optimization --apply
./install.sh eddy_safety --apply
./install.sh diagnostics --apply
```

`diagnostics` is included by `all`; installing it does not automatically execute XY stress tests.

Hardware Cooling is intentionally excluded from `all` because it requires the corresponding physical modification:

```bash
./install.sh hardware_cooling --apply
```

PLR is not included in RC4.

## 3. Persistent-state policy

### Configuration files

`printer.cfg`, `Macro.cfg`, and other managed cfg files have **no persistent whole-file backup copy**. Every release-managed mutation must be reversibly owned by a stable M_Bamboo marker or a deterministic stock-value/template transformation.

Restore rules:

```text
added M_Bamboo block      -> remove that block
replaced recognized value -> restore the exact recognized original/stock value
removed stock section     -> reconstruct from the owned restore template
user content outside M_Bamboo regions -> preserve
SAVE_CONFIG generated tail -> preserve byte-for-byte
```

A cfg mutation that cannot be deterministically reversed is not eligible for the RC4 installer.

### Backend Python

The only persistent original-state archive is:

```text
/home/sovol/klipper/klippy/extras/mb_bak/
```

`MANIFEST.json` records the original present/absent state and SHA256 for each owned backend file. The archive is created only from recognized provenance, is created once, and is never overwritten by install, upgrade, repair, or restore.

Legacy `.mb_baseline` files may be consumed only as validated migration input. RC4 creates no new `.mb_baseline`, `.last_mb_*`, per-version rollback slots, or timestamp backup series.

## 4. First-takeover provenance gate

RC4 refuses to invent an original state. First takeover is accepted only when the current backend is classified by exact SHA256 as a supported Sovol stock file, a recognized M_Bamboo lineage with a trustworthy original source, or a file that is known to have been originally absent.

For a recognized M_Bamboo backend, the preferred migration source is a legacy `.mb_baseline` only when its full SHA256 matches known Sovol stock. If that baseline is missing or fails provenance, RC4 may recover the original from Sovol's factory mirror under `~/zhongchuang/MKSDEB/...` only when the mirror file independently matches an exact known stock SHA256. The mirror path alone never grants trust.

Unknown third-party current content is refused before persistent `mb_bak` state is created, even if a valid factory mirror exists. An unknown pre-existing file at an originally-absent M_Bamboo pathname is also refused rather than overwritten.

## 5. Transaction rollback

Before the first write, touched files are snapshotted into a private:

```text
/tmp/M_Bamboo_SV08MAX.*
```

transaction directory. If apply/compile/hash/restart validation fails, the installer restores the exact immediate pre-transaction bytes **before** cleanup. This scratch tree is an atomicity mechanism, not a second persistent backup history.

Current RC4 policy is to clean installer-owned transaction scratch after success and after a **confirmed successful automatic rollback**. If automatic rollback itself fails, the transaction snapshot is deliberately retained and its exact path is reported so manual byte recovery remains possible. The durable normal-state recovery source remains the original-state `mb_bak` plus deterministic cfg inverse transformations.

## 6. Full Restore

Dry-run:

```bash
./install.sh all --restore
```

Apply:

```bash
./install.sh all --restore --apply
```

Full Restore means **return M_Bamboo-owned surfaces to the pre-M_Bamboo/original machine state**:

- M_Bamboo cfg blocks are removed;
- recognized replaced values are restored;
- removed stock sections/macros are reconstructed from release-owned templates;
- original backend Python is copied back from `mb_bak/`;
- files recorded as originally absent are deleted;
- unrelated user changes outside M_Bamboo-owned regions are preserved.

The `mb_bak/` archive itself is retained as the single durable original-state record.

## 7. No generic downgrade command in RC4

RC4 deliberately does **not** implement `--version`, `--release`, or another generic historical-downgrade engine.

To install an older M_Bamboo release:

```text
current M_Bamboo release
-> full Restore to pre-M_Bamboo/original state
-> obtain the desired historical release artifact
-> run that release's own installer
```

This keeps Restore simple and authoritative, prevents local version-backup chains, and avoids duplicating historical release-selection logic inside every installer.

## 8. Conflict policy

The installer refuses unknown managed cfg values or untrusted backend origins instead of guessing. A recognized M_Bamboo target with no trustworthy original source is also refused on first takeover; RC4 never fabricates `mb_bak` from a modified target.

## 9. RC4 release validation contract

The release matrix must cover at least:

- clean recognized-stock install;
- idempotent reinstall;
- recognized older M_Bamboo migration;
- validated legacy-baseline migration;
- unknown-source refusal with byte-identical filesystem;
- originally-absent same-name collision refusal;
- simulated mid-transaction failure with byte-exact rollback;
- feature-scoped restore and full restore;
- `SAVE_CONFIG` tail byte preservation;
- unrelated user cfg preservation;
- Python 3.9 syntax/compile validation;
- target checksum verification;
- no installer-created cfg backup litter or live `__pycache__`;
- EN/CN public-interface registry synchronization;
- feature ownership completeness.

Historical downgrade testing is not an RC4 gate because generic downgrade is not an RC4 feature.
