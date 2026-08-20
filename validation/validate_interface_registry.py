#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
DOCS = [ROOT / 'docs' / 'COMMAND_REFERENCE.md',
        ROOT / 'docs' / 'COMMAND_REFERENCE_CN.md']

# Project-owned or materially changed macro/config interfaces that are not
# discoverable from this engineering package's Python source alone.
REQUIRED_PROJECT_INTERFACES = {
    'G28', 'M9928', 'CLEAN_NOZZLE', 'QUAD_GANTRY_LEVEL',
    'QUAD_GANTRY_LEVEL_BASE', 'BED_MESH_CALIBRATE',
    'BED_MESH_CALIBRATE_BASE', 'START_PRINT',
    'Z_OFFSET_CALIBRATION', 'RUN_PROBE_VIR_CONTACT',
    'XY_STRESS_BASELINE', 'XY_STRESS_RUN', 'XY_STRESS_CHECK',
}


def discover_backend_commands():
    commands = set()
    pattern = re.compile(r"register_(?:mux_)?command\(\s*['\"]([^'\"]+)")
    for path in BACKEND.glob('*.py'):
        text = path.read_text(errors='replace')
        commands.update(pattern.findall(text))
    return commands


def main():
    required = discover_backend_commands() | REQUIRED_PROJECT_INTERFACES
    failed = False
    for doc in DOCS:
        text = doc.read_text(errors='replace')
        missing = sorted(cmd for cmd in required if cmd not in text)
        if missing:
            failed = True
            print(f'{doc.name}: missing {len(missing)} interface(s):')
            for cmd in missing:
                print(f'  - {cmd}')
        else:
            print(f'{doc.name}: PASS ({len(required)} required interfaces found)')
    if failed:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
