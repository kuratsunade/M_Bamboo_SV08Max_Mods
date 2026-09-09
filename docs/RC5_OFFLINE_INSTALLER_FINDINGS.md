# RC5 offline installer findings, 2026-09-09

Runtime and installer evaluated from commit b2eb2bf3b1539e36a414ee6559404395a96b70a3. No runtime or installer changes were made for these checks. All operations used isolated local config/extras directories with `--no-restart`.

## Input identity

Stock configuration was extracted from the supplied Sovol source archive. Four backend source files were the repository stock fixtures and match the official source bytes. The RC4 bridge installer came from the supplied RC4 with Toolkit ZIP.

| Stock config | SHA256 |
| --- | --- |
| printer.cfg | `b1ba0926dee0f03efa847fdeca8c2240fb683212516a5cb51a2640e65cda5109` |
| Macro.cfg | `e9bfde339c2b9a554e6976a6be44667c329b481983c06f57320c5043101acd9c` |
| buffer_stepper.cfg | `022b421a4d8a64b9b3572644225379c39fc2e70827f7a10a412d749b21fa1e12` |

## Reproduction sequence and observed result

1. Copy the three stock configs and four stock backend fixtures into isolated directories. Run RC5 `all --config-dir CONFIG --extras-dir EXTRAS --no-restart` without apply: rejected with `Refusing unknown START_PRINT lineage; expected recognized RC4 PRE/POST blocks or RC5 core`.
2. In that isolated input, run the exact RC4 installer with `all --apply --no-restart` and the same directory arguments: eight planned writes, success.
3. Run RC5 dry run: two planned writes. Apply: success. Apply again: zero writes and zero deletes.
4. Run RC5 `all --restore --apply --no-restart` with those directory arguments: seven writes, one delete, reports success.
5. Compare four backend files with initial stock fixtures: exact match. M_Bamboo_Safe_Homing.py is correctly absent. Macro.cfg still contains the entire CONFIG_START_PRINT_CORE, including the RC5 coordinator branch and its fallback Z calibration sequence: complete config restore FAIL.
6. Separately run RC5 dry run on a copy of the earlier machine export's config/extras tree: rejected by the same START_PRINT guard. No apply attempted on that snapshot.

Config files are not byte identical after restoration, which alone is not a failure because the contract uses inverse transformations. The decisive defect is the surviving runtime managed block. This is a local simulation; no firmware service or printer was operated.

## Boundaries

The existing `validation/test_release_installer_v2.sh`, supplied with the stock config directory, also fails at the first stock installation guard. The entire historical offline matrix is therefore not claimed to pass. Focused combined runtime, terminal cleanup, transport preflight and EN/CN interface registry checks pass locally. The internal handoff's hardware evidence is carried forward separately; no new hardware evidence was collected here.
