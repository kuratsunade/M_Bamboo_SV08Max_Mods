#!/usr/bin/env python3
"""M_Bamboo_SV08Max_Mods feature installer (v1.0.0-rc3).

Features:
  safe_home
  config_optimization
  all

Default is dry-run. --apply writes changes. Backups are bounded and feature-aware.
"""
import argparse, difflib, hashlib, json, py_compile, re, shutil, subprocess, sys, tempfile
from pathlib import Path

PROJECT = "M_Bamboo_SV08Max_Mods"
PROJECT_RELEASE = "1.0.0-rc3"
NS = "M_Bamboo_SV08MAX_MOD"
SAVE_MARKER = "#*# <---------------------- SAVE_CONFIG ---------------------->"

KNOWN_ZOFFSET_HASHES = {
    "77944d34a555542886020417afd4a005da1c027e98c5c68cd3c6116d26824db7": "Sovol stock snapshot",
    "e4c06027feb1ac51d6ace1a47cceee08169d0b82d500f422bf61c3be4156ce87": "M_Bamboo H3A development",
    "58f6acf7e49d4096b4003ceac0f07079959d7b21dd11d0b028d5ffa6bce1854b": "M_Bamboo H3B-1 development",
    "9771a42b854c293ccd770fe769b630fc961dcbd4fbc025ad37853801a9cc0ed3": "M_Bamboo H3B-2 development",
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def color(code, text):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def cyan(s): return color("1;36", s)
def green(s): return color("1;32", s)
def yellow(s): return color("1;33", s)
def red(s): return color("1;31", s)
def dim(s): return color("2", s)


def split_save_config(text):
    i = text.find(SAVE_MARKER)
    return (text, "") if i < 0 else (text[:i], text[i:])


def section_span(text, name):
    m = re.search(r"(?m)^\[" + re.escape(name) + r"\]\s*(?:#.*)?$", text)
    if not m: return None
    n = re.search(r"(?m)^\[[^\]\n]+\]", text[m.end():])
    end = m.end() + (n.start() if n else len(text[m.end():]))
    return m.start(), end


def managed_span(text, tag):
    m = re.search(
        rf"(?ms)^# >>> {re.escape(NS)}:{re.escape(tag)} BEGIN >>>\n.*?^# <<< {re.escape(NS)}:{re.escape(tag)} END <<<\n?",
        text)
    return (m.start(), m.end()) if m else None


def indented_managed_span(text, tag):
    m = re.search(
        rf"(?ms)^\s*# >>> {re.escape(NS)}:{re.escape(tag)} BEGIN >>>\n.*?^\s*# <<< {re.escape(NS)}:{re.escape(tag)} END <<<\n?",
        text)
    return (m.start(), m.end()) if m else None


def replace_span(text, span, replacement):
    a, b = span
    return text[:a] + replacement.rstrip() + "\n" + text[b:].lstrip("\n")


def load(root, rel):
    return (root / rel).read_text(encoding="utf-8").rstrip() + "\n"


def replace_key_block(sec, keys, block, tag, legacy_tags=()):
    sp = managed_span(sec, tag)
    if sp:
        return sec
    for oldtag in tuple(legacy_tags):
        sp = managed_span(sec, oldtag)
        if sp:
            return replace_span(sec, sp, block)
    lines = []
    for k in keys:
        lines.append(r"^" + re.escape(k) + r"\s*:\s*[^\n]+\n?")
    pat = re.compile(r"(?m)" + "".join(lines))
    m = pat.search(sec)
    if not m:
        # tolerate target values already surrounded by comments by locating first key through last key
        first = re.search(r"(?m)^" + re.escape(keys[0]) + r"\s*:\s*[^\n]+$", sec)
        last = re.search(r"(?m)^" + re.escape(keys[-1]) + r"\s*:\s*[^\n]+$", sec[first.end():] if first else "")
        if first and last:
            a = first.start(); b = first.end() + last.end()
            return sec[:a] + block.rstrip() + "\n" + sec[b:].lstrip("\n")
        raise RuntimeError("Could not locate keys: " + ", ".join(keys))
    return sec[:m.start()] + block.rstrip() + "\n" + sec[m.end():]


def patch_section(text, section, fn):
    sp = section_span(text, section)
    if not sp: raise RuntimeError(f"Missing [{section}]")
    a, b = sp
    return text[:a] + fn(text[a:b]) + text[b:]


def extract_eddy_calibrate_value(text):
    head, tail = split_save_config(text)
    sp = section_span(head, "probe_eddy_current eddy")
    if sp:
        sec = head[sp[0]:sp[1]]
        m = re.search(r"(?ms)^calibrate\s*:\s*(.*?)(?=^\S[^:\n]*\s*:|^\[|\Z)", sec)
        if m: return m.group(1).strip()
    m = re.search(
        r"(?ms)^#\*# \[probe_eddy_current eddy\]\s*$.*?^#\*# calibrate\s*=\s*(.*?)(?=^#\*# [A-Za-z_][A-Za-z0-9_ -]*\s*=|^#\*# \[|\Z)", tail)
    if m: return re.sub(r"(?m)^#\*#\s?", "", m.group(1)).strip()
    return None


def eddy_calibrated(text):
    raw = extract_eddy_calibrate_value(text)
    pts = re.findall(r"[-+]?\d+(?:\.\d+)?\s*:\s*[-+]?\d+(?:\.\d+)?", raw or "")
    return len(pts) > 2, len(pts)


def verify_feature_manifest(root, feature):
    p = root / "features" / feature / "manifest.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    checked = 0
    for item in data.get("files", []):
        target = root / item["path"]
        if not target.is_file() or sha256(target) != item["sha256"]:
            raise RuntimeError("Release payload checksum mismatch: " + item["path"])
        checked += 1
    return checked


def baseline_backup(path):
    b = path.with_name(path.name + ".mb_baseline")
    if path.exists() and not b.exists(): shutil.copy2(path, b)


def feature_backup(path, feature):
    if not path.exists(): return
    baseline_backup(path)
    slot = path.with_name(path.name + ".last_mb_" + feature)
    shutil.copy2(path, slot)


def restore_feature(paths, feature):
    restored = []
    for p in paths:
        slot = p.with_name(p.name + ".last_mb_" + feature)
        if slot.exists():
            atomic_write(p, slot.read_bytes()); restored.append(str(p))
    return restored


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".M_Bamboo.tmp")
    tmp.write_bytes(data); tmp.replace(path)


def unified(path, old, new):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(path), tofile=str(path)+" (M_Bamboo)"))


def restart_klipper():
    subprocess.run(["sudo", "systemctl", "restart", "klipper"], check=True)
    chk = subprocess.run(["systemctl", "is-active", "klipper"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if chk.returncode or chk.stdout.strip() != "active": raise RuntimeError("Klipper service did not return active")

# ---------- Safe Home ----------
def patch_safe_printer(root, text):
    head, tail = split_save_config(text)
    safe = load(root, "features/safe_home/config/printer_safe_home.block")
    tomb = load(root, "features/safe_home/config/printer_legacy_homing_override_tombstone.block")
    zmin = load(root, "features/safe_home/config/printer_z_min_safety.block")

    done = False
    sp = managed_span(head, "SAFE_HOME")
    if sp:
        done = True
    else:
        sp = managed_span(head, "SAFE_HOMING_CONFIG")
        if sp: head = replace_span(head, sp, safe); done = True
    if not done:
        for sec in ("M_Bamboo_Safe_Homing", "h2_homing_debug_v3"):
            sp = section_span(head, sec)
            if sp: head = replace_span(head, sp, safe); done = True; break
    if not done:
        zsp = section_span(head, "z_offset_calibration")
        if not zsp: raise RuntimeError("Missing [z_offset_calibration]")
        head = head[:zsp[1]] + "\n" + safe + "\n" + head[zsp[1]:].lstrip("\n")

    done = False
    sp = managed_span(head, "SAFE_HOME_LEGACY_HOMING_OVERRIDE")
    if sp:
        done = True
    else:
        sp = managed_span(head, "LEGACY_HOMING_OVERRIDE_REMOVED")
        if sp: head = replace_span(head, sp, tomb); done = True
    if not done:
        sp = section_span(head, "homing_override")
        if sp: head = replace_span(head, sp, tomb)
        else: head = tomb + "\n" + head

    def zfn(sec): return replace_key_block(sec, ["position_min"], zmin, "SAFE_HOME_Z_MIN", ("Z_MIN_SAFETY",))
    head = patch_section(head, "stepper_z", zfn)
    if section_span(head, "homing_override"): raise RuntimeError("Active [homing_override] remains")
    return head.rstrip()+"\n\n"+tail.lstrip("\n") if tail else head.rstrip()+"\n"


def patch_safe_macro(root, text):
    block = load(root, "features/safe_home/config/macro_g28.block")
    sp = managed_span(text, "SAFE_HOME_G28")
    if sp: return text
    sp = managed_span(text, "HOMING_G28")
    if sp: return replace_span(text, sp, block)
    sp = section_span(text, "gcode_macro G28")
    if not sp: raise RuntimeError("Missing [gcode_macro G28]")
    return replace_span(text, sp, block)

# ---------- Config Optimization ----------
def patch_config_printer(root, text):
    head, tail = split_save_config(text)
    specs = [
        ("printer", ["max_velocity","max_accel"], "printer_motion_limits.block", "CONFIG_MOTION_LIMITS", ("MOTION_LIMITS",)),
        ("tmc5160 stepper_x", ["run_current"], "printer_xy_current_x.block", "CONFIG_XY_CURRENT_X", ("XY_MOTOR_CURRENT_X",)),
        ("tmc5160 stepper_y", ["run_current"], "printer_xy_current_y.block", "CONFIG_XY_CURRENT_Y", ("XY_MOTOR_CURRENT_Y",)),
        ("quad_gantry_level", ["speed"], "printer_qgl_speed.block", "CONFIG_QGL_SPEED", ("QGL_SPEED",)),
        ("quad_gantry_level", ["retries","max_adjust"], "printer_qgl_limits.block", "CONFIG_QGL_LIMITS", ("QGL_RETRY_LIMITS",)),
    ]
    for section, keys, fname, tag, legacy in specs:
        block = load(root, "features/config_optimization/config/"+fname)
        head = patch_section(head, section, lambda sec, k=keys,b=block,t=tag,l=legacy: replace_key_block(sec,k,b,t,l))
    return head.rstrip()+"\n\n"+tail.lstrip("\n") if tail else head.rstrip()+"\n"


def patch_config_buffer(root, text):
    block = load(root, "features/config_optimization/config/buffer_stepper_filament_buffer.block")
    return patch_section(
        text, "buffer_stepper filament_buffer",
        lambda sec: replace_key_block(
            sec, ["velocity", "accel", "push_length"], block,
            "CONFIG_BUFFER_STEPPER", ("BUFFER_STEPPER",)))


def patch_config_macro(root, text):
    # CLEAN_NOZZLE whole-section ownership.
    clean = load(root, "features/config_optimization/config/macro_clean_nozzle.block")
    sp = managed_span(text, "CONFIG_CLEAN_NOZZLE")
    if sp:
        pass
    else:
        sp = managed_span(text, "CLEAN_NOZZLE")
        if sp: text = replace_span(text, sp, clean)
        else:
            sp = section_span(text, "gcode_macro CLEAN_NOZZLE")
            if not sp: raise RuntimeError("Missing [gcode_macro CLEAN_NOZZLE]")
            text = replace_span(text, sp, clean)

    # Adaptive mesh line.
    mesh = load(root, "features/config_optimization/config/macro_bed_mesh_adaptive.block")
    sp = indented_managed_span(text, "CONFIG_BED_MESH_ADAPTIVE")
    if sp:
        pass
    else:
        sp = indented_managed_span(text, "BED_MESH_ADAPTIVE")
        if sp: text = replace_span(text, sp, mesh)
        else:
            m = re.search(r"(?m)^\s*BED_MESH_CALIBRATE_BASE\s+ADAPTIVE=1\s+PGP=[01]\s+METHOD=rapid_scan\s*$", text)
            if not m: raise RuntimeError("Could not locate adaptive bed mesh command")
            text = text[:m.start()] + mesh.rstrip() + text[m.end():]

    # START_PRINT block.
    ssp = section_span(text, "gcode_macro START_PRINT")
    if not ssp: raise RuntimeError("Missing [gcode_macro START_PRINT]")
    a,b = ssp; sec=text[a:b]
    pre = load(root, "features/config_optimization/config/macro_start_print_pre_qgl.block")
    sp = indented_managed_span(sec, "CONFIG_START_PRINT_PRE_QGL")
    if sp:
        pass
    else:
        sp = indented_managed_span(sec, "START_PRINT_PRE_QGL")
        if sp: sec = replace_span(sec, sp, pre)
        else:
            pat = re.compile(r"(?m)^\s*SET_VELOCITY_LIMIT ACCEL=(?:40000|15000) ACCEL_TO_DECEL=(?:10000|7500)\s*$\n^\s*Z_OFFSET_CALIBRATION METHOD=force_overlay BED_TEMP=\{printer\.heater_bed\.target\}(?: USE_CURRENT_Z=1 ZDBG=1)?\s*$")
            m=pat.search(sec)
            if not m: raise RuntimeError("Could not locate START_PRINT pre-QGL tuning lines")
            sec=sec[:m.start()]+pre.rstrip()+sec[m.end():]

    post = load(root, "features/config_optimization/config/macro_start_print_post_mesh.block")
    sp = indented_managed_span(sec, "CONFIG_START_PRINT_POST_MESH")
    if sp:
        pass
    else:
        sp = indented_managed_span(sec, "START_PRINT_POST_MESH_Z_OFFSET")
        if sp: sec = replace_span(sec, sp, post)
        elif "USE_CURRENT_Z_ALLOWANCE=1.25" in sec:
            m=re.search(r"(?m)^\s*Z_OFFSET_CALIBRATION .*USE_CURRENT_Z_ALLOWANCE=1\.25.*$", sec)
            sec=sec[:m.start()]+post.rstrip()+sec[m.end():]
        else:
            m=re.search(r"(?m)^\s*BED_MESH_CALIBRATE\s*$", sec)
            if not m: raise RuntimeError("Could not locate BED_MESH_CALIBRATE in START_PRINT")
            sec=sec[:m.end()]+"\n"+post.rstrip()+sec[m.end():]
    text=text[:a]+sec+text[b:]
    return text.rstrip()+"\n"


def safe_home_ready(printer, ztarget, zpayload):
    head,_=split_save_config(printer)
    if not section_span(head,"M_Bamboo_Safe_Homing"): return False
    zh=sha256(ztarget)
    return zh in KNOWN_ZOFFSET_HASHES or zh == sha256(zpayload)


def print_header(title, subtitle):
    print(); print(cyan("╭─ "+title+" ─╮")); print(cyan("│ "+subtitle)); print(cyan("╰"+"─"*(len(title)+4)+"╯")); print()


def main():
    ap=argparse.ArgumentParser(description=f"{PROJECT} {PROJECT_RELEASE} installer")
    ap.add_argument("feature", nargs="?", default="all", choices=["safe_home","config_optimization","all"])
    ap.add_argument("--config-dir", default="/home/sovol/printer_data/config")
    ap.add_argument("--extras-dir", default="/home/sovol/klipper/klippy/extras")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--restore-baseline", action="store_true")
    ap.add_argument("--raw-diff", action="store_true")
    ap.add_argument("--force-unrecognized", action="store_true")
    ap.add_argument("--no-restart", action="store_true")
    args=ap.parse_args()
    if sum(bool(x) for x in (args.apply,args.rollback,args.restore_baseline))>1: raise SystemExit("Choose one write mode")

    root=Path(__file__).resolve().parent; cfg=Path(args.config_dir); extras=Path(args.extras_dir)
    printer=cfg/"printer.cfg"; macro=cfg/"Macro.cfg"; buffer_cfg=cfg/"buffer_stepper.cfg"; ztarget=extras/"z_offset_calibration.py"; safe_target=extras/"M_Bamboo_Safe_Homing.py"
    zpayload=root/"features/safe_home/payload/z_offset_calibration.py"; safepayload=root/"features/safe_home/payload/M_Bamboo_Safe_Homing.py"
    for p in (printer,macro,buffer_cfg,ztarget):
        if not p.is_file(): raise SystemExit("Missing required file: "+str(p))

    features=["safe_home","config_optimization"] if args.feature=="all" else [args.feature]

    if args.rollback:
        if args.feature=="safe_home" and f"{NS}:CONFIG_START_PRINT_PRE_QGL BEGIN" in macro.read_text(encoding="utf-8"):
            raise SystemExit("Rollback blocked: config_optimization depends on safe_home. Roll back config_optimization first or use 'all --rollback'.")
        order=list(reversed(features)); restored=[]
        for f in order:
            paths=[printer,macro,ztarget,safe_target] if f=="safe_home" else [printer,macro,buffer_cfg]
            restored += restore_feature(paths,f)
            if f=="safe_home":
                slot=safe_target.with_name(safe_target.name+".last_mb_safe_home")
                if not slot.exists() and safe_target.exists() and sha256(safe_target)==sha256(safepayload): safe_target.unlink(); restored.append(str(safe_target)+" (removed)")
        if not args.no_restart: restart_klipper()
        print(green("Rollback complete")); [print("  ✓ "+x) for x in restored]; return

    if args.restore_baseline:
        restored=[]
        for p in (printer,macro,buffer_cfg,ztarget,safe_target):
            b=p.with_name(p.name+".mb_baseline")
            if b.exists(): atomic_write(p,b.read_bytes()); restored.append(str(p))
        if not args.no_restart: restart_klipper()
        print(green("Baseline restore complete")); [print("  ✓ "+x) for x in restored]; return

    oldp=printer.read_text(encoding="utf-8"); oldm=macro.read_text(encoding="utf-8"); oldb=buffer_cfg.read_text(encoding="utf-8")
    safe_p,safe_m=oldp,oldm
    checks=0

    if "safe_home" in features:
        checks += verify_feature_manifest(root,"safe_home")
        has,pts=eddy_calibrated(oldp)
        if not has:
            print(red("INSTALL BLOCKED / 安装已阻止")); print("Complete Sovol factory Eddy calibration and SAVE_CONFIG first."); raise SystemExit(2)
        zh=sha256(ztarget); zsource=KNOWN_ZOFFSET_HASHES.get(zh)
        if zsource is None and zh!=sha256(zpayload) and not args.force_unrecognized: raise SystemExit("Unrecognized z_offset_calibration.py: "+zh)
        with tempfile.TemporaryDirectory(prefix="M_Bamboo_compile_") as td:
            py_compile.compile(str(zpayload),cfile=str(Path(td)/"z.pyc"),doraise=True); py_compile.compile(str(safepayload),cfile=str(Path(td)/"s.pyc"),doraise=True)
        safe_p=patch_safe_printer(root,oldp); safe_m=patch_safe_macro(root,oldm)
    else:
        pts=eddy_calibrated(oldp)[1]; zsource="n/a"

    newp,newm,newb=safe_p,safe_m,oldb
    if "config_optimization" in features:
        checks += verify_feature_manifest(root,"config_optimization")
        probe_printer=safe_p if "safe_home" in features else oldp
        if not safe_home_ready(probe_printer, ztarget, zpayload) and "safe_home" not in features:
            raise SystemExit("config_optimization requires Safe Home because START_PRINT uses its current-Z calibration semantics. Install safe_home first or use 'all'.")
        newp=patch_config_printer(root,newp); newm=patch_config_macro(root,newm); newb=patch_config_buffer(root,newb)

    if args.raw_diff:
        print("===== printer.cfg ====="); print(unified(printer,oldp,newp) or "(no changes)")
        print("===== Macro.cfg ====="); print(unified(macro,oldm,newm) or "(no changes)")
        print("===== buffer_stepper.cfg ====="); print(unified(buffer_cfg,oldb,newb) or "(no changes)")

    if not args.apply:
        print_header(f"{PROJECT} · {PROJECT_RELEASE} · DRY RUN", "Feature-aware production preview / 模块化安装预览")
        print(cyan("Selected features")); [print("  "+green("✓")+" "+f) for f in features]
        print(f"  {green('✓')} payload checksums       {checks} files verified")
        if "safe_home" in features:
            print(f"  {green('✓')} Eddy calibration        valid ({pts} points)")
            print("  ~ safe_home               genuine HOME_Z + Z position_min -1 + G28 routing")
        if "config_optimization" in features:
            print("  ~ config_optimization     motion/QGL/current + CLEAN_NOZZLE + adaptive mesh + START_PRINT")
            print("      motion                max_velocity 700→400; max_accel 40000→15000")
            print("      XY current            3.0→2.3 A")
            print("      QGL                   speed 400→200; retries 15→5; max_adjust 20→5")
            print("      adaptive mesh         PGP 0→1")
            print("      START_PRINT           ACCEL 15000/7500 + two Safe Home Z-offset checks")
            print("      CLEAN_NOZZLE          randomized contact + cross-hatch wiping")
            print("      buffer_stepper        velocity 150→80; accel 5000→1900; push_length 25→27")
        print(); print(yellow("DRY RUN — nothing written / 未写入文件")); return

    # Feature-scoped bounded snapshots. Do not refresh a rollback slot for a no-op apply.
    safe_backend_changed = ("safe_home" in features and
        (not safe_target.exists() or sha256(safe_target) != sha256(safepayload) or sha256(ztarget) != sha256(zpayload)))
    safe_config_changed = ("safe_home" in features and (safe_p != oldp or safe_m != oldm))
    safe_changed = safe_backend_changed or safe_config_changed
    config_base_p, config_base_m = safe_p, safe_m
    config_changed = ("config_optimization" in features and (newp != config_base_p or newm != config_base_m or newb != oldb))
    if not safe_changed and not config_changed:
        print(green("Already at requested target state / 已是目标状态"))
        return

    originals={p:p.read_bytes() for p in (printer,macro,buffer_cfg,ztarget,safe_target) if p.exists()}; safe_existed=safe_target.exists()
    try:
        if safe_changed:
            for p in (printer,macro,ztarget): feature_backup(p,"safe_home")
            if safe_target.exists(): feature_backup(safe_target,"safe_home")
            atomic_write(safe_target,safepayload.read_bytes()); atomic_write(ztarget,zpayload.read_bytes())
            atomic_write(printer,safe_p.encode()); atomic_write(macro,safe_m.encode())
        if config_changed:
            for p in (printer,macro,buffer_cfg): feature_backup(p,"config_optimization")
            # The config snapshot is taken after Safe Home, preserving the dependency boundary.
            atomic_write(printer,newp.encode()); atomic_write(macro,newm.encode()); atomic_write(buffer_cfg,newb.encode())

        if safe_target.exists(): py_compile.compile(str(safe_target),doraise=True)
        if "safe_home" in features: py_compile.compile(str(ztarget),doraise=True)
        fp=printer.read_text(encoding="utf-8"); fm=macro.read_text(encoding="utf-8")
        if "safe_home" in features:
            if section_span(split_save_config(fp)[0],"homing_override"): raise RuntimeError("[homing_override] remains")
            if "position_min: -1" not in section_span_text(fp,"stepper_z"): raise RuntimeError("Safe Home Z minimum missing")
        if "config_optimization" in features:
            for token in ("CONFIG_MOTION_LIMITS BEGIN","CONFIG_QGL_SPEED BEGIN","CONFIG_CLEAN_NOZZLE BEGIN","CONFIG_START_PRINT_PRE_QGL BEGIN"):
                if token not in fp+fm: raise RuntimeError("Config optimization marker missing: "+token)
            fb=buffer_cfg.read_text(encoding="utf-8")
            if "CONFIG_BUFFER_STEPPER BEGIN" not in fb: raise RuntimeError("Config optimization marker missing: CONFIG_BUFFER_STEPPER")
        if not args.no_restart: restart_klipper()
    except Exception as exc:
        for p,data in originals.items(): atomic_write(p,data)
        if not safe_existed and safe_target.exists(): safe_target.unlink()
        if not args.no_restart:
            try: restart_klipper()
            except Exception: pass
        raise SystemExit("Install failed; automatic rollback completed: "+str(exc))

    print(green("Installed successfully / 安装成功: "+", ".join(features)))
    if not args.no_restart:
        print(green("Klipper restart requested; service currently reports: active"))
        print()
        print(yellow("IMPORTANT / 注意:"))
        print("If you did not observe a normal printer/Klipper restart cycle, or the printer state")
        print("appears inconsistent, please perform a manual Firmware Restart before continuing.")
        print("如果没有观察到正常的打印机 / Klipper 重启过程，或机器状态与预期不一致，")
        print("请在继续使用前手动执行一次 Firmware Restart。")
    else:
        print(yellow("Klipper restart skipped (--no-restart). Perform a Firmware Restart before normal use."))


def section_span_text(text,name):
    head,_=split_save_config(text); sp=section_span(head,name); return head[sp[0]:sp[1]] if sp else ""

if __name__=="__main__": main()
