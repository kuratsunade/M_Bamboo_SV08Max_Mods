#!/usr/bin/env python3
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'installer.py'
MANIFEST = ROOT / 'installer_manifest.json'
TARGET_SHA = '5e108f1d1d7259d40dab03c967c1e3ffef33c31da1a0c15932b8a958b869cf29'
DEV_SOURCE_SHA = 'dcb78d4d7d5108236eca23a225e6e582e1b128419bf10c8a5b83cf8de346ced0'


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one anchor, found {count}')
    return text.replace(old, new, 1)


def main():
    text = INSTALLER.read_text(encoding='utf-8')

    text = replace_once(text,
        '"""M_Bamboo SV08 Max RC4 release installer.',
        '"""M_Bamboo SV08 Max RC5 development installer.',
        'installer title')
    text = replace_once(text,
        'PROJECT_RELEASE = "1.0.0-rc4"',
        'PROJECT_RELEASE = "1.0.0-rc5-dev"',
        'project release')
    text = replace_once(text,
        '"probe_eddy_current.py": "6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e",',
        f'"probe_eddy_current.py": "{TARGET_SHA}",',
        'backend target')

    lineage_anchor = '        "6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e",\n'
    lineage_new = lineage_anchor + f'        # DEV_ONLY_MIGRATION_SOURCE: 2026-09-08 hardware-tested RC5 candidate\n        "{DEV_SOURCE_SHA}",\n'
    text = replace_once(text, lineage_anchor, lineage_new, 'dev migration lineage')

    old_parser = "        unmanaged=[ln for ln in between.splitlines() if ':' in ln and not any(re.match(rf'^\\s*{re.escape(k)}\\s*:',ln) for k in keys)]"
    new_parser = "        unmanaged=[ln for ln in between.splitlines() if ln.strip() and not ln.lstrip().startswith('#') and ':' in ln and not any(re.match(rf'^\\s*{re.escape(k)}\\s*:',ln) for k in keys)]"
    text = replace_once(text, old_parser, new_parser, 'comment-aware parser')

    # Replace the legacy PRE/POST START_PRINT transformer with a single RC5 managed core.
    start = text.index("        # START_PRINT: replace the stock first calibration pair / managed block; insert final after BED_MESH_CALIBRATE.\n")
    end = text.index("        text=text[:a]+sec+text[b:]\n", start) + len("        text=text[:a]+sec+text[b:]\n")
    new_block = '''        # START_PRINT: one managed dual-path core.  Existing RC5 core is replaced\n        # directly; recognized RC4 PRE/POST lineage is collapsed into the core.\n        ssp=section_span(text,'gcode_macro START_PRINT')\n        if not ssp: raise RuntimeError('Missing [gcode_macro START_PRINT]')\n        a,b=ssp; sec=text[a:b]\n        core=managed_span(sec,'CONFIG_START_PRINT_CORE')\n        if core:\n            sec=replace_span(sec,core,load('release/config/start_print_core.block'))\n        else:\n            pre=managed_span(sec,'CONFIG_START_PRINT_PRE_QGL') or managed_span(sec,'START_PRINT_PRE_QGL')\n            post=managed_span(sec,'CONFIG_START_PRINT_POST_MESH') or managed_span(sec,'START_PRINT_POST_MESH_Z_OFFSET')\n            if not pre or not post:\n                raise RuntimeError('Refusing unknown START_PRINT lineage; expected recognized RC4 PRE/POST blocks or RC5 core')\n            # The recognized RC4 core begins at CLEAN_NOZZLE and ends after the\n            # has_z_offset_calibrated=False line following POST_ZCAL.\n            clean=re.search(r'(?m)^\\s*CLEAN_NOZZLE\\s*$',sec[:pre[0]])\n            if not clean:\n                raise RuntimeError('Could not locate recognized START_PRINT CLEAN_NOZZLE entry')\n            false_m=re.search(r'(?m)^\\s*SET_GCODE_VARIABLE MACRO=_global_var VARIABLE=has_z_offset_calibrated VALUE=False\\s*$',sec[post[1]:])\n            if not false_m:\n                raise RuntimeError('Could not locate recognized START_PRINT final calibration flag')\n            rs=clean.start()\n            re_=post[1]+false_m.end()\n            sec=sec[:rs]+load('release/config/start_print_core.block').rstrip()+sec[re_:]\n        text=text[:a]+sec+text[b:]\n'''
    text = text[:start] + new_block + text[end:]
    INSTALLER.write_text(text, encoding='utf-8')

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    manifest['release'] = '1.0.0-rc5-dev'
    manifest['status'] = 'development-candidate'
    manifest['backend_targets']['probe_eddy_current.py'] = TARGET_SHA
    manifest['development_lineage'] = {
        'public_release_contract': False,
        'dev_only_migration_sources': {'probe_eddy_current.py': [DEV_SOURCE_SHA]},
        'validation_artifact_hashes_are_not_release_lineage': True,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
