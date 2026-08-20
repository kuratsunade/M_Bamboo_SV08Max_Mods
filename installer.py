#!/usr/bin/env python3
"""M_Bamboo SV08 Max RC4 release installer.

Release policy v2:
- config files have NO persistent backup; every managed mutation is reversible;
- backend Python keeps one centralized extras/mb_bak/ original-state backup;
- installer writes are transactional using a private temporary directory;
- restore means pre-M_Bamboo state; older releases are installed only after Full Restore using that release's own installer.
"""
import argparse, difflib, hashlib, json, os, py_compile, re, shutil, subprocess, sys, tempfile
from pathlib import Path

PROJECT = "M_Bamboo_SV08Max_Mods"
PROJECT_RELEASE = "1.0.0-rc4"
SAFETY_VERSION = "ES-R4-EC2-FS1.1"
NS = "M_Bamboo_SV08MAX_MOD"
SAVE_MARKER = "#*# <---------------------- SAVE_CONFIG ---------------------->"
ROOT = Path(__file__).resolve().parent

BACKEND_TARGETS = {
    "ldc1612.py": "aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04",
    "probe_eddy_current.py": "6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e",
    "probe.py": "227d0c6b8527ece1793caf969d5292646ec185f65ca1c679ccf4195515dd529a",
    "M_Bamboo_Safe_Homing.py": "5f85a1a397413a7ab5da28d2b19b586a6d371b49a4793b80bc685d5adb0f9038",
    "z_offset_calibration.py": "1089df132131010f774d40b331fef4ff6ba02252f4b55c107846c6cc0a7a75ce",
}
ORIGINALLY_ABSENT = {"M_Bamboo_Safe_Homing.py"}

# First-takeover provenance tables. These are exact SHA256 values, never prefixes.
# The Sovol stock hashes below were recovered byte-for-byte from the source-machine
# archive and independently matched its zhongchuang/MKSDEB factory mirror.
KNOWN_STOCK_SOURCES = {
    "ldc1612.py": {
        "5992b2189b40bc4ae7a33d804a5584f74620e3db6d75ab3f6151daca2c895547",
    },
    "probe_eddy_current.py": {
        "4a45a563b40ecc2d06eaa37ee1eebbdfe3f4d21827ffe7918316ac480b65e14b",
    },
    "probe.py": {
        "0e83c2dd327b73e70dbea9736eea6c346c5a85e63c40b57213be7bd504453745",
    },
    "z_offset_calibration.py": {
        "77944d34a555542886020417afd4a005da1c027e98c5c68cd3c6116d26824db7",
    },
}

# Historical M_Bamboo artifacts recovered from the canonical handoff packages.
# Exact hashes prevent a short-prefix collision from becoming an ownership grant.
KNOWN_MB_SOURCES = {
    "ldc1612.py": {
        "1ee331668fe792d4b944374f15364bf66c8b06a67fdca1660d1da90dcd2d22c0",
        "7f9bf01a52946b02f1508bd57054e75f0ef4b6f847a3c165f7aa7bb8c558ad0c",
        "92d6e62086a03f352768fbd3c956ad4dfbbf910e6704a03e7b8c8657406d848f",
        "aa25833c27367905c68f27dfa6e4d669ddfe304bdaa23febee8287737f757e04",
    },
    "probe_eddy_current.py": {
        "48cd4f98c2423970b6c49d138b78fb5805fd3e774d15ffb3d8d6575e844a06f9",
        "4b37c2ed58c085d16d842e8edabfaa9ffd8057b12f0d3aa7866f79ef85845f64",
        "1dd933700671d6b80709d9f55279f78630d031a8b440d5a71ddbe8f5de3b26e6",
        "c9626c6233faf4a06dc036569ea892ec5b85788db31eae512ba44d40cbda112c",
        "6b82c2a057746cd83ee46e02835e5b392e1ceba9c731d4984b98c1f75c63295e",
    },
    "probe.py": {
        "498b3b607a39be5988005a5b334872e9e7c14b5cd66b719e07bb61c169991e14",
        "227d0c6b8527ece1793caf969d5292646ec185f65ca1c679ccf4195515dd529a",
    },
    "M_Bamboo_Safe_Homing.py": {
        "dd33f5508977492d70113244563dda4380f8062c8fdbfc0e02b965a7fd619029",
        "5f85a1a397413a7ab5da28d2b19b586a6d371b49a4793b80bc685d5adb0f9038",
    },
    "z_offset_calibration.py": {
        "4954918676c73faadb01dcb685b1b095761575770884e24d45688a59bc6a0b8b",
        "1089df132131010f774d40b331fef4ff6ba02252f4b55c107846c6cc0a7a75ce",
    },
}



def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.M_Bamboo.tmp')
    tmp.write_bytes(data); tmp.replace(path)


def split_save(text):
    i=text.find(SAVE_MARKER)
    return (text,'') if i<0 else (text[:i],text[i:])


def section_span(text, name):
    m=re.search(r'(?m)^\['+re.escape(name)+r'\][^\n]*\n', text)
    if not m: return None
    n=re.search(r'(?m)^\[', text[m.end():])
    e=m.end()+(n.start() if n else len(text[m.end():]))
    return m.start(),e


def managed_span(text, tag, indent=True):
    lead=r'\s*' if indent else ''
    p=re.compile(rf'(?ms)^{lead}# >>> {re.escape(NS)}:{re.escape(tag)} BEGIN >>>\n.*?^{lead}# <<< {re.escape(NS)}:{re.escape(tag)} END <<<\n?')
    m=p.search(text); return (m.start(),m.end()) if m else None


def replace_span(text, sp, repl):
    a,b=sp
    return text[:a]+repl.rstrip()+"\n"+text[b:]


def load(rel): return (ROOT/rel).read_text(encoding='utf-8').rstrip()+"\n"


def replace_section(text, name, replacement):
    sp=section_span(text,name)
    if not sp: raise RuntimeError(f"Missing [{name}]")
    return replace_span(text,sp,replacement)


def replace_key_with_block(text, section, key_pattern, block, tag, accepted_values):
    sp=section_span(text,section)
    if not sp: raise RuntimeError(f"Missing [{section}]")
    a,b=sp; sec=text[a:b]
    ms=managed_span(sec,tag)
    if ms: sec=replace_span(sec,ms,block)
    else:
        m=re.search(rf'(?m)^{re.escape(key_pattern)}\s*:\s*([^#\n]+)',sec)
        if not m: raise RuntimeError(f"Missing {key_pattern} in [{section}]")
        val=m.group(1).strip()
        if val not in accepted_values: raise RuntimeError(f"Refusing unknown [{section}] {key_pattern}={val}")
        line_start=sec.rfind('\n',0,m.start())+1; line_end=sec.find('\n',m.end())
        if line_end<0: line_end=len(sec)
        else: line_end+=1
        sec=sec[:line_start]+block.rstrip()+"\n"+sec[line_end:]
    return text[:a]+sec+text[b:]


def replace_keys_block(text, section, keys, block, tag, accepted):
    sp=section_span(text,section)
    if not sp: raise RuntimeError(f"Missing [{section}]")
    a,b=sp; sec=text[a:b]
    ms=managed_span(sec,tag)
    if ms: sec=replace_span(sec,ms,block)
    else:
        found=[]
        for k in keys:
            m=re.search(rf'(?m)^{re.escape(k)}\s*:\s*([^#\n]+)',sec)
            if not m: raise RuntimeError(f"Missing {k} in [{section}]")
            v=m.group(1).strip()
            if v not in accepted[k]: raise RuntimeError(f"Refusing unknown [{section}] {k}={v}")
            found.append(m)
        start=min(sec.rfind('\n',0,m.start())+1 for m in found)
        ends=[]
        for m in found:
            e=sec.find('\n',m.end()); ends.append(len(sec) if e<0 else e+1)
        end=max(ends)
        # Only permit whitespace/comments between first and last managed keys if keys are adjacent.
        between=sec[start:end]
        unmanaged=[ln for ln in between.splitlines() if ':' in ln and not any(re.match(rf'^\s*{re.escape(k)}\s*:',ln) for k in keys)]
        if unmanaged: raise RuntimeError(f"Managed keys in [{section}] are not safely contiguous")
        sec=sec[:start]+block.rstrip()+"\n"+sec[end:]
    return text[:a]+sec+text[b:]


def target_printer(text, safe=True, optimize=True):
    head,tail=split_save(text)
    if safe:
        # Safe Home config: replace old/new managed block or insert before SAVE_CONFIG.
        for old in ('SAFE_HOME','SAFE_HOMING_CONFIG'):
            sp=managed_span(head,old,False)
            if sp:
                head=replace_span(head,sp,load('release/config/safe_home.block')); break
        else:
            zsp=section_span(head,'z_offset_calibration')
            if not zsp: raise RuntimeError('Missing [z_offset_calibration]')
            head=head[:zsp[1]]+'\n'+load('release/config/safe_home.block')+'\n'+head[zsp[1]:].lstrip('\n')
        # Remove stock homing_override and leave reversible tombstone.
        tsp=None
        for tag in ('SAFE_HOME_LEGACY_HOMING_OVERRIDE','LEGACY_HOMING_OVERRIDE_REMOVED'):
            tsp=managed_span(head,tag,False)
            if tsp:
                head=replace_span(head,tsp,load('release/config/safe_home_tombstone.block')); break
        if not tsp:
            hsp=section_span(head,'homing_override')
            if hsp: head=replace_span(head,hsp,load('release/config/safe_home_tombstone.block'))
            else: head=load('release/config/safe_home_tombstone.block')+'\n'+head
        head=replace_key_with_block(head,'stepper_z','position_min',load('release/config/safe_home_zmin.block'),'SAFE_HOME_Z_MIN',{'-10','-1'})
    if optimize:
        blocks={
          'motion': '# >>> M_Bamboo_SV08MAX_MOD:CONFIG_MOTION_LIMITS BEGIN >>>\n# Version: 2\n# Maintainer: Master_Bamboo / 竹子\n# Stock: max_velocity=700, max_accel=40000\nmax_velocity: 400\nmax_accel: 15000\n# <<< M_Bamboo_SV08MAX_MOD:CONFIG_MOTION_LIMITS END <<<\n',
          'x': '# >>> M_Bamboo_SV08MAX_MOD:CONFIG_XY_CURRENT_X BEGIN >>>\n# Version: 2\n# Maintainer: Master_Bamboo / 竹子\n# Stock: run_current=3.0\nrun_current: 2.3\n# <<< M_Bamboo_SV08MAX_MOD:CONFIG_XY_CURRENT_X END <<<\n',
          'y': '# >>> M_Bamboo_SV08MAX_MOD:CONFIG_XY_CURRENT_Y BEGIN >>>\n# Version: 2\n# Maintainer: Master_Bamboo / 竹子\n# Stock: run_current=3.0\nrun_current: 2.3\n# <<< M_Bamboo_SV08MAX_MOD:CONFIG_XY_CURRENT_Y END <<<\n',
          'qs': '# >>> M_Bamboo_SV08MAX_MOD:CONFIG_QGL_SPEED BEGIN >>>\n# Version: 2\n# Maintainer: Master_Bamboo / 竹子\n# Stock: speed=400\nspeed: 200\n# <<< M_Bamboo_SV08MAX_MOD:CONFIG_QGL_SPEED END <<<\n',
          'ql': '# >>> M_Bamboo_SV08MAX_MOD:CONFIG_QGL_LIMITS BEGIN >>>\n# Version: 2\n# Maintainer: Master_Bamboo / 竹子\n# Stock: retries=15, max_adjust=20\nretries: 5\nmax_adjust: 5\n# <<< M_Bamboo_SV08MAX_MOD:CONFIG_QGL_LIMITS END <<<\n',
        }
        head=replace_keys_block(head,'printer',['max_velocity','max_accel'],blocks['motion'],'CONFIG_MOTION_LIMITS',{'max_velocity':{'700','400'},'max_accel':{'40000','15000'}})
        head=replace_key_with_block(head,'tmc5160 stepper_x','run_current',blocks['x'],'CONFIG_XY_CURRENT_X',{'3.0','2.3'})
        head=replace_key_with_block(head,'tmc5160 stepper_y','run_current',blocks['y'],'CONFIG_XY_CURRENT_Y',{'3.0','2.3'})
        head=replace_key_with_block(head,'quad_gantry_level','speed',blocks['qs'],'CONFIG_QGL_SPEED',{'400','200'})
        head=replace_keys_block(head,'quad_gantry_level',['retries','max_adjust'],blocks['ql'],'CONFIG_QGL_LIMITS',{'retries':{'15','5'},'max_adjust':{'20','5'}})
    return head.rstrip()+('\n\n'+tail.lstrip('\n') if tail else '\n')


def target_macro(text, safe=True, optimize=True):
    if safe:
        # Replace a managed G28 or stock section.
        done=False
        for tag in ('SAFE_HOME_G28','HOMING_G28'):
            sp=managed_span(text,tag,False)
            if sp: text=replace_span(text,sp,load('release/config/g28.block')); done=True; break
        if not done: text=replace_section(text,'gcode_macro G28',load('release/config/g28.block'))
    if optimize:
        # CLEAN_NOZZLE exact release-owned section.
        done=False
        for tag in ('CONFIG_CLEAN_NOZZLE','CLEAN_NOZZLE'):
            sp=managed_span(text,tag,False)
            if sp: text=replace_span(text,sp,load('release/config/clean_nozzle.block')); done=True; break
        if not done: text=replace_section(text,'gcode_macro CLEAN_NOZZLE',load('release/config/clean_nozzle.block'))
        # BED_MESH adaptive line.
        sp=managed_span(text,'CONFIG_BED_MESH_ADAPTIVE') or managed_span(text,'BED_MESH_ADAPTIVE')
        if sp: text=replace_span(text,sp,load('release/config/bed_mesh_adaptive.block'))
        else:
            m=re.search(r'(?m)^\s*BED_MESH_CALIBRATE_BASE\s+ADAPTIVE=1\s+PGP=[01]\s+METHOD=rapid_scan\s*$',text)
            if not m: raise RuntimeError('Could not locate adaptive mesh line')
            text=text[:m.start()]+load('release/config/bed_mesh_adaptive.block').rstrip()+text[m.end():]
        # START_PRINT: replace the stock first calibration pair / managed block; insert final after BED_MESH_CALIBRATE.
        ssp=section_span(text,'gcode_macro START_PRINT')
        if not ssp: raise RuntimeError('Missing [gcode_macro START_PRINT]')
        a,b=ssp; sec=text[a:b]
        sp=managed_span(sec,'CONFIG_START_PRINT_PRE_QGL') or managed_span(sec,'START_PRINT_PRE_QGL')
        if sp: sec=replace_span(sec,sp,load('release/config/start_print_pre.block'))
        else:
            pat=re.compile(r'(?m)^\s*SET_VELOCITY_LIMIT ACCEL=(?:40000|15000) ACCEL_TO_DECEL=(?:10000|7500)\s*$\n^\s*Z_OFFSET_CALIBRATION METHOD=force_overlay BED_TEMP=\{printer\.heater_bed\.target\}(?: USE_CURRENT_Z=1 ZDBG=1)?\s*$')
            m=pat.search(sec)
            if not m: raise RuntimeError('Could not locate START_PRINT pre-QGL lines')
            sec=sec[:m.start()]+load('release/config/start_print_pre.block').rstrip()+sec[m.end():]
        sp=managed_span(sec,'CONFIG_START_PRINT_POST_MESH') or managed_span(sec,'START_PRINT_POST_MESH_Z_OFFSET')
        if sp: sec=replace_span(sec,sp,load('release/config/start_print_post.block'))
        elif 'USE_CURRENT_Z_ALLOWANCE=1.25' not in sec:
            m=re.search(r'(?m)^\s*BED_MESH_CALIBRATE\s*$',sec)
            if not m: raise RuntimeError('Could not locate BED_MESH_CALIBRATE in START_PRINT')
            e=sec.find('\n',m.end()); e=len(sec) if e<0 else e+1
            sec=sec[:e]+load('release/config/start_print_post.block')+sec[e:]
        text=text[:a]+sec+text[b:]
    return text


def target_buffer(text):
    block='# >>> M_Bamboo_SV08MAX_MOD:CONFIG_BUFFER_STEPPER BEGIN >>>\n# Version: 2\n# Maintainer: Master_Bamboo / 竹子\n# Stock: velocity=150, accel=5000, push_length=25\nvelocity: 80\naccel: 1900\npush_length: 27\n# <<< M_Bamboo_SV08MAX_MOD:CONFIG_BUFFER_STEPPER END <<<\n'
    return replace_keys_block(text,'buffer_stepper filament_buffer',['velocity','accel','push_length'],block,'CONFIG_BUFFER_STEPPER',{'velocity':{'150','80'},'accel':{'5000','1900'},'push_length':{'25','27'}})


def target_hardware_cooling(text):
    head,tail=split_save(text)
    sp=section_span(head,'heater_fan bed_fan')
    if not sp: raise RuntimeError('Missing [heater_fan bed_fan]')
    a,b=sp; sec=head[a:b]
    block=load('release/config/hardware_cooling_bed_fan.block')
    ms=managed_span(sec,'HARDWARE_COOLING_BED_FAN')
    if ms:
        sec=replace_span(sec,ms,block)
    else:
        m=re.search(r'(?m)^fan_speed\s*:\s*([^#\n]+)',sec)
        if m:
            value=m.group(1).strip()
            # Bare 0.6 is accepted only as migration from an already-managed MB config.
            if value!='0.6' or '# >>> '+NS+':' not in head:
                raise RuntimeError(
                    f'Refusing unknown pre-existing [heater_fan bed_fan] fan_speed={value}; '
                    'Hardware Cooling owns only stock-absent or recognized legacy M_Bamboo 0.6')
            ls=sec.rfind('\n',0,m.start())+1; le=sec.find('\n',m.end())
            le=len(sec) if le<0 else le+1
            sec=sec[:ls]+block.rstrip()+"\n"+sec[le:]
        else:
            # Sovol stock has no fan_speed key. Insert before its existing blank
            # section separator so removing the managed block restores bytes exactly.
            if sec.endswith('\n\n'):
                pos=len(sec)-1
                sec=sec[:pos]+block+sec[pos:]
            else:
                sec=sec.rstrip('\n')+'\n'+block
    head=head[:a]+sec+head[b:]
    return head.rstrip()+('\n\n'+tail.lstrip('\n') if tail else '\n')


def restore_hardware_cooling(text):
    head,tail=split_save(text)
    sp=section_span(head,'heater_fan bed_fan')
    if not sp: raise RuntimeError('Missing [heater_fan bed_fan]')
    a,b=sp; sec=head[a:b]
    ms=managed_span(sec,'HARDWARE_COOLING_BED_FAN')
    if ms:
        sec=sec[:ms[0]]+sec[ms[1]:]
    head=head[:a]+sec+head[b:]
    return head.rstrip()+('\n\n'+tail.lstrip('\n') if tail else '\n')


def target_diagnostics(text):
    block=load('release/config/diagnostics.block')
    sp=managed_span(text,'DIAGNOSTICS_XY_STRESS',False)
    if sp:
        return replace_span(text,sp,block)

    names=['gcode_macro XY_STRESS_BASELINE','gcode_macro XY_STRESS_RUN','gcode_macro XY_STRESS_CHECK']
    spans=[section_span(text,n) for n in names]
    if any(spans):
        if not all(spans):
            raise RuntimeError('Partial legacy XY_STRESS diagnostics detected; refusing ambiguous ownership takeover')
        if not (spans[0][0] < spans[1][0] < spans[2][0]):
            raise RuntimeError('Legacy XY_STRESS diagnostics are not in recognized order')
        # Preserve only whitespace between the three exact legacy macro sections.
        if text[spans[0][1]:spans[1][0]].strip() or text[spans[1][1]:spans[2][0]].strip():
            raise RuntimeError('Legacy XY_STRESS diagnostics are not safely contiguous')
        return text[:spans[0][0]]+block.rstrip()+"\n"+text[spans[2][1]:].lstrip('\n')

    # Stock Sovol has no XY_STRESS macros. Add one release-owned block.
    return text.rstrip()+"\n\n"+block


def restore_diagnostics(text):
    sp=managed_span(text,'DIAGNOSTICS_XY_STRESS',False)
    if sp:
        return text[:sp[0]]+text[sp[1]:].lstrip('\n')
    return text


def restore_managed_block(text, tag, replacement=''):
    sp=managed_span(text,tag)
    return replace_span(text,sp,replacement) if sp else text


def restore_printer(text, safe=True, optimize=True):
    head,tail=split_save(text)
    if safe:
        # Safe config block is an addition.
        for tag in ('SAFE_HOME','SAFE_HOMING_CONFIG'):
            sp=managed_span(head,tag,False)
            if sp: head=replace_span(head,sp,'')
        # Z min inverse.
        sp=managed_span(head,'SAFE_HOME_Z_MIN') or managed_span(head,'Z_MIN_SAFETY')
        if sp: head=replace_span(head,sp,'position_min: -10')
        # Reconstruct exact stock homing_override where tombstone stands.
        for tag in ('SAFE_HOME_LEGACY_HOMING_OVERRIDE','LEGACY_HOMING_OVERRIDE_REMOVED'):
            sp=managed_span(head,tag,False)
            if sp: head=replace_span(head,sp,load('release/restore_templates/stock_homing_override.cfg')); break
    if optimize:
        repl={
          'CONFIG_MOTION_LIMITS':'max_velocity: 700\nmax_accel: 40000',
          'CONFIG_XY_CURRENT_X':'run_current: 3.0', 'CONFIG_XY_CURRENT_Y':'run_current: 3.0',
          'CONFIG_QGL_SPEED':'speed: 400', 'CONFIG_QGL_LIMITS':'retries: 15\nmax_adjust: 20',
        }
        for tag,val in repl.items():
            sp=managed_span(head,tag)
            if sp: head=replace_span(head,sp,val)
    return head.rstrip()+('\n\n'+tail.lstrip('\n') if tail else '\n')


def restore_macro(text, safe=True, optimize=True):
    if safe:
        for tag in ('SAFE_HOME_G28','HOMING_G28'):
            sp=managed_span(text,tag,False)
            if sp: text=replace_span(text,sp,load('release/restore_templates/stock_g28.cfg')); break
    if optimize:
        for tag in ('CONFIG_CLEAN_NOZZLE','CLEAN_NOZZLE'):
            sp=managed_span(text,tag,False)
            if sp: text=replace_span(text,sp,load('release/restore_templates/stock_clean_nozzle.cfg')); break
        for tag in ('CONFIG_BED_MESH_ADAPTIVE','BED_MESH_ADAPTIVE'):
            sp=managed_span(text,tag)
            if sp: text=replace_span(text,sp,'    BED_MESH_CALIBRATE_BASE ADAPTIVE=1 PGP=0 METHOD=rapid_scan'); break
        ssp=section_span(text,'gcode_macro START_PRINT')
        if ssp:
            a,b=ssp; sec=text[a:b]
            for tag in ('CONFIG_START_PRINT_PRE_QGL','START_PRINT_PRE_QGL'):
                sp=managed_span(sec,tag)
                if sp:
                    sec=replace_span(sec,sp,'    SET_VELOCITY_LIMIT ACCEL=40000 ACCEL_TO_DECEL=10000\n    Z_OFFSET_CALIBRATION METHOD=force_overlay BED_TEMP={printer.heater_bed.target}'); break
            for tag in ('CONFIG_START_PRINT_POST_MESH','START_PRINT_POST_MESH_Z_OFFSET'):
                sp=managed_span(sec,tag)
                if sp: sec=replace_span(sec,sp,'')
            text=text[:a]+sec+text[b:]
    return text


def restore_buffer(text):
    sp=managed_span(text,'CONFIG_BUFFER_STEPPER')
    if sp: text=replace_span(text,sp,'velocity: 150\naccel: 5000\npush_length: 25')
    # remove legacy outer wrapper without deleting section content
    for tag in ('BUFFER_STEPPER_TUNING',):
        sp=managed_span(text,tag,False)
        if sp:
            block=text[sp[0]:sp[1]]
            lines=block.splitlines()
            kept=[ln for ln in lines if not re.match(r'^# (>>>|<<<) '+re.escape(NS)+':'+tag+r' ',ln)]
            text=text[:sp[0]]+'\n'.join(kept).strip()+"\n"+text[sp[1]:].lstrip('\n')
    return text


def _hash_is_known_stock(name, digest):
    return digest in KNOWN_STOCK_SOURCES.get(name, ())


def _hash_is_known_mb(name, digest):
    return digest in KNOWN_MB_SOURCES.get(name, ())


def _factory_mirror_path(extras, name):
    """Return the stock Sovol factory-mirror path for a standard install tree.

    The mirror is recovery evidence only.  It is never trusted by path alone;
    callers must verify its full SHA256 against KNOWN_STOCK_SOURCES.
    """
    extras=Path(extras).resolve()
    expected_tail=Path('klipper/klippy/extras')
    try:
        user_home=extras.parents[2]
    except IndexError:
        return None
    if Path(*extras.parts[-3:]) != expected_tail:
        return None
    return (user_home/'zhongchuang'/'MKSDEB'/'home'/'sovol'/'klipper'/
            'klippy'/'extras'/name)

def _validated_factory_mirror(extras, name):
    mirror=_factory_mirror_path(extras, name)
    if mirror is None or not mirror.is_file():
        return None, None
    digest=sha256(mirror)
    if not _hash_is_known_stock(name, digest):
        return mirror, digest
    return mirror, digest

def _first_takeover_plan(extras):
    """Classify every backend before creating any persistent backup state."""
    files={}
    for name,target_hash in BACKEND_TARGETS.items():
        dest=extras/name
        legacy=dest.with_name(dest.name+'.mb_baseline')
        current_hash=sha256(dest) if dest.is_file() else None
        legacy_hash=sha256(legacy) if legacy.is_file() else None

        if name in ORIGINALLY_ABSENT:
            if legacy.is_file():
                raise RuntimeError(
                    f'Unexpected legacy baseline for originally-absent {name}: {legacy}; '
                    'refusing ambiguous provenance')
            if current_hash is None:
                files[name]={'state':'absent','provenance':'known-originally-absent'}
                continue
            if _hash_is_known_mb(name,current_hash):
                files[name]={'state':'absent','provenance':'known-M_Bamboo-created'}
                continue
            raise RuntimeError(
                f'First-takeover provenance refusal for {name}: current hash {current_hash} '
                'is neither absent nor a recognized M_Bamboo lineage; refusing to overwrite '
                'a possible user/third-party file')

        if current_hash is None:
            raise RuntimeError(f'Missing original backend file: {dest}')

        if _hash_is_known_stock(name,current_hash):
            files[name]={
                'state':'present','source':dest,'sha256':current_hash,
                'provenance':'known-sovol-stock-current',
            }
            continue

        if _hash_is_known_mb(name,current_hash):
            if legacy_hash is not None and _hash_is_known_stock(name,legacy_hash):
                files[name]={
                    'state':'present','source':legacy,'sha256':legacy_hash,
                    'provenance':'validated-legacy-stock-baseline',
                }
                continue

            mirror, mirror_hash = _validated_factory_mirror(extras, name)
            if mirror_hash is not None and _hash_is_known_stock(name, mirror_hash):
                files[name]={
                    'state':'present','source':mirror,'sha256':mirror_hash,
                    'provenance':('validated-sovol-factory-mirror-after-invalid-legacy'
                                  if legacy_hash is not None
                                  else 'validated-sovol-factory-mirror'),
                }
                continue

            if legacy_hash is not None:
                mirror_detail = (
                    f'; factory mirror {mirror} has unrecognized hash {mirror_hash}'
                    if mirror_hash is not None else
                    '; no validated Sovol factory mirror is available')
                raise RuntimeError(
                    f'Legacy baseline provenance refusal for {name}: {legacy_hash} is not a '
                    f'recognized Sovol stock hash{mirror_detail}')
            mirror_detail = (
                f'; factory mirror {mirror} has unrecognized hash {mirror_hash}'
                if mirror_hash is not None else
                '; no validated Sovol factory mirror is available')
            raise RuntimeError(
                f'Cannot establish original backup for {name}: current hash {current_hash} '
                'is recognized M_Bamboo lineage but no trustworthy .mb_baseline exists'
                f'{mirror_detail}')

        raise RuntimeError(
            f'First-takeover provenance refusal for {name}: unrecognized current hash '
            f'{current_hash}; expected known Sovol stock or known M_Bamboo lineage with a '
            'validated stock .mb_baseline')
    return files


def ensure_backup_manifest(extras):
    bdir=extras/'mb_bak'; mf=bdir/'MANIFEST.json'
    if mf.exists():
        data=json.loads(mf.read_text())
        if data.get('format') != 1 or data.get('project') != PROJECT: raise RuntimeError('Invalid mb_bak/MANIFEST.json')
        for name,meta in data['files'].items():
            if meta['state']=='present':
                bp=bdir/meta['backup']
                if not bp.is_file() or sha256(bp)!=meta['sha256']: raise RuntimeError(f'Backup integrity failure: {name}')
        return data
    if bdir.exists() and any(bdir.iterdir()): raise RuntimeError('mb_bak exists without a valid manifest')

    # Critical ordering: classify ALL sources before mkdir/copy/write. A provenance
    # refusal therefore leaves the persistent filesystem byte-identical.
    plan=_first_takeover_plan(extras)
    bdir.mkdir(parents=True,exist_ok=True)
    data={'format':1,'project':PROJECT,'purpose':'original pre-M_Bamboo backend state; never overwritten','files':{}}
    try:
        for name,item in plan.items():
            if item['state']=='absent':
                data['files'][name]={'state':'absent','provenance':item['provenance']}
                continue
            source=item['source']
            shutil.copy2(source,bdir/name)
            data['files'][name]={
                'state':'present','backup':name,'sha256':item['sha256'],
                'provenance':item['provenance'],
            }
        mf.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    except Exception:
        # No half-built original archive is ever allowed to survive.
        shutil.rmtree(bdir,ignore_errors=True)
        raise
    return data


def backend_target(extras):
    # Verify the release payload before persistent backup creation.
    for name,want in BACKEND_TARGETS.items():
        src=ROOT/'backend'/name
        if not src.is_file() or sha256(src)!=want:
            raise RuntimeError(f'Release payload hash mismatch: {name}')

    manifest=ensure_backup_manifest(extras)
    changes={}
    for name,want in BACKEND_TARGETS.items():
        src=ROOT/'backend'/name; dest=extras/name
        if dest.is_file():
            current=sha256(dest)
            if current==want:
                continue
            meta=manifest['files'].get(name, {})
            original=(meta.get('sha256') if meta.get('state')=='present' else None)
            # After ownership is established, accept only exact preserved original
            # or exact recognized M_Bamboo lineage. Unknown content is user-owned.
            if current != original and not _hash_is_known_mb(name,current):
                raise RuntimeError(
                    f'Unrecognized current backend hash for {name}: {current}; '
                    'refusing to overwrite a possible user/third-party modification')
        elif name not in ORIGINALLY_ABSENT:
            raise RuntimeError(f'Missing managed backend file after backup initialization: {dest}')
        changes[dest]=src.read_bytes()
    return changes


def backend_restore(extras):
    bdir=extras/'mb_bak'; mf=bdir/'MANIFEST.json'
    if not mf.is_file(): raise RuntimeError('No mb_bak/MANIFEST.json; refusing guessed backend restore')
    data=json.loads(mf.read_text()); changes={}; deletes=[]
    for name,meta in data['files'].items():
        dest=extras/name
        if meta['state']=='absent': deletes.append(dest)
        else:
            bp=bdir/meta['backup']
            if sha256(bp)!=meta['sha256']: raise RuntimeError(f'Backup integrity failure: {name}')
            changes[dest]=bp.read_bytes()
    return changes,deletes


def restart_klipper():
    subprocess.run(['sudo','systemctl','restart','klipper'],check=True)
    p=subprocess.run(['systemctl','is-active','klipper'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.returncode or p.stdout.strip()!='active': raise RuntimeError('Klipper did not return active')


def transaction_apply(writes,deletes,restart):
    paths=set(writes)|set(deletes)
    # Do not use TemporaryDirectory here. If rollback itself fails, the snapshot
    # is the last byte-exact recovery source and MUST survive for manual repair.
    td=Path(tempfile.mkdtemp(prefix='M_Bamboo_SV08MAX.',dir='/tmp'))
    state={}
    try:
        for i,p in enumerate(sorted(paths,key=str)):
            if p.exists():
                q=td/f'{i}.orig'; shutil.copy2(p,q); state[p]=('present',q)
            else: state[p]=('absent',None)
        for p,data in writes.items(): atomic_write(p,data)
        for p in deletes:
            if p.exists(): p.unlink()
        if os.environ.get('MB_TEST_FAIL_AFTER_WRITE')=='1': raise RuntimeError('Injected transaction failure')
        # compile changed python targets
        for p in writes:
            if p.suffix=='.py': py_compile.compile(str(p), cfile=str(td/(p.name+'.pyc')), doraise=True)
        if restart: restart_klipper()
    except Exception as original_error:
        rollback_errors=[]
        for idx,(p,(kind,q)) in enumerate(state.items()):
            try:
                if os.environ.get('MB_TEST_FAIL_DURING_ROLLBACK')=='1' and idx==0:
                    raise RuntimeError('Injected rollback failure')
                if kind=='present': atomic_write(p,q.read_bytes())
                elif p.exists(): p.unlink()
            except Exception as exc:
                rollback_errors.append(f'{p}: {exc}')
        if rollback_errors:
            # Deliberately retain td. Never destroy the last known-good snapshot
            # when automatic rollback could not prove restoration succeeded.
            raise RuntimeError(
                f'Transaction failed: {original_error}; automatic rollback ALSO failed. '
                f'Recovery snapshot retained at {td}. Rollback errors: '
                + '; '.join(rollback_errors)
            ) from original_error
        shutil.rmtree(td,ignore_errors=True)
        raise
    else:
        shutil.rmtree(td,ignore_errors=True)


def config_changes(config_dir, feature, restore=False):
    safe=feature in ('safe_home','all')
    opt=feature in ('config_optimization','all')
    diagnostics=feature in ('diagnostics','all')
    cooling=feature=='hardware_cooling'
    if feature=='eddy_safety': return {}

    writes={}
    if safe or opt or cooling:
        p=config_dir/'printer.cfg'
        if not p.is_file(): raise RuntimeError(f'Missing config file: {p}')
        old=p.read_text(encoding='utf-8')
        if cooling:
            new=restore_hardware_cooling(old) if restore else target_hardware_cooling(old)
        else:
            new=restore_printer(old,safe,opt) if restore else target_printer(old,safe,opt)
        if new!=old: writes[p]=new.encode()

    if safe or opt or diagnostics:
        p=config_dir/'Macro.cfg'
        if not p.is_file(): raise RuntimeError(f'Missing config file: {p}')
        old=p.read_text(encoding='utf-8')
        if restore:
            new=restore_macro(old,safe,opt)
            if diagnostics: new=restore_diagnostics(new)
        else:
            new=target_macro(old,safe,opt)
            if diagnostics: new=target_diagnostics(new)
        if new!=old: writes[p]=new.encode()

    if opt:
        p=config_dir/'buffer_stepper.cfg'
        if not p.is_file(): raise RuntimeError(f'Missing config file: {p}')
        old=p.read_text(encoding='utf-8')
        new=restore_buffer(old) if restore else target_buffer(old)
        if new!=old: writes[p]=new.encode()
    return writes


def status(config_dir,extras):
    print(f'{PROJECT} {PROJECT_RELEASE} / {SAFETY_VERSION}')
    for p in (config_dir/'printer.cfg',config_dir/'Macro.cfg',config_dir/'buffer_stepper.cfg'):
        if p.is_file(): print(f'{p.name}: managed_markers={p.read_text(errors="replace").count("# >>> "+NS+":")}')
    print('Backend:')
    for name,want in BACKEND_TARGETS.items():
        p=extras/name; got=sha256(p) if p.is_file() else 'MISSING'
        print(f'  {name}: {"RC4" if got==want else got}')
    mf=extras/'mb_bak/MANIFEST.json'; print(f'mb_bak manifest: {"present" if mf.is_file() else "absent"}')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('feature',nargs='?',default='all',choices=['all','safe_home','config_optimization','eddy_safety','diagnostics','hardware_cooling'])
    ap.add_argument('--apply',action='store_true')
    ap.add_argument('--restore',action='store_true',help='Reverse selected M_Bamboo feature(s); all means full pre-MB restore')
    ap.add_argument('--status',action='store_true')
    ap.add_argument('--raw-diff',action='store_true')
    ap.add_argument('--no-restart',action='store_true')
    ap.add_argument('--config-dir',default='/home/sovol/printer_data/config')
    ap.add_argument('--extras-dir',default='/home/sovol/klipper/klippy/extras')
    args=ap.parse_args()
    cfg=Path(args.config_dir); extras=Path(args.extras_dir)
    if args.status: status(cfg,extras); return
    writes={}; deletes=[]
    if args.feature in ('safe_home','config_optimization','diagnostics','hardware_cooling','all'):
        writes.update(config_changes(cfg,args.feature,args.restore))
    if args.feature in ('eddy_safety','all'):
        if args.restore:
            bw,bd=backend_restore(extras); writes.update(bw); deletes.extend(bd)
        else: writes.update(backend_target(extras))
    print(f'{PROJECT} {PROJECT_RELEASE} {"RESTORE" if args.restore else "INSTALL"} feature={args.feature}')
    print('Persistent cfg backups: NONE')
    print(f'Backend original backup: {extras}/mb_bak (one directory, never overwritten)')
    print(f'Planned writes: {len(writes)}; deletes: {len(deletes)}')
    if args.raw_diff:
        for p,data in writes.items():
            if p.suffix in ('.cfg','.py') and p.exists():
                try: old=p.read_text(); new=data.decode()
                except Exception: continue
                print(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(p),tofile=str(p)+' target')))
    if not args.apply:
        print('DRY RUN ONLY. Re-run with --apply to write changes.'); return
    transaction_apply(writes,deletes,not args.no_restart)
    print('Applied successfully. Transaction scratch directory cleaned.')
    if args.restore and args.feature=='all': print('Full restore completed: cfg transformations reversed; backend originals restored; originally-absent MB backend files removed.')

if __name__=='__main__': main()
