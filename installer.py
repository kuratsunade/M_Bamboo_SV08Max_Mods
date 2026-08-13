#!/usr/bin/env python3
"""M_Bamboo_SV08Max_Mods feature installer.

Safe Home v1.0.0 is the first supported feature.
Default mode is dry-run. Use --apply to write, --rollback to restore the
immediately previous version, or --restore-baseline to restore first-seen files.
"""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

PROJECT = "M_Bamboo_SV08Max_Mods"
PROJECT_VERSION = "1.0.0"
FEATURE = "safe_home"
FEATURE_VERSION = "1.0.0"
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
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def cyan(s): return color("1;36", s)
def green(s): return color("1;32", s)
def yellow(s): return color("1;33", s)
def red(s): return color("1;31", s)
def dim(s): return color("2", s)


def split_save_config(text):
    idx = text.find(SAVE_MARKER)
    if idx < 0:
        return text, ""
    return text[:idx], text[idx:]


def section_span(text, section_name):
    pat = re.compile(r"(?m)^\[" + re.escape(section_name) + r"\]\s*$")
    m = pat.search(text)
    if not m:
        return None
    nxt = re.search(r"(?m)^\[[^\]\n]+\]\s*$", text[m.end():])
    end = m.end() + (nxt.start() if nxt else len(text[m.end():]))
    return m.start(), end


def managed_span(text, name):
    pat = re.compile(
        rf"(?ms)^# >>> {re.escape(NS)}:{re.escape(name)} BEGIN >>>\n.*?"
        rf"^# <<< {re.escape(NS)}:{re.escape(name)} END <<<\n?"
    )
    m = pat.search(text)
    return (m.start(), m.end()) if m else None


def load_block(path):
    return path.read_text(encoding="utf-8").rstrip() + "\n"


def replace_span(text, span, replacement):
    a, b = span
    return text[:a] + replacement + "\n" + text[b:].lstrip("\n")


def patch_printer(text, safe_block, tombstone):
    head, tail = split_save_config(text)

    # Migrate development marker, replace production marker, or install section.
    done = False
    for tag in ("SAFE_HOME", "SAFE_HOMING_CONFIG"):
        sp = managed_span(head, tag)
        if sp:
            head = replace_span(head, sp, safe_block)
            done = True
            break
    if not done:
        for secname in ("M_Bamboo_Safe_Homing", "h2_homing_debug_v3"):
            sp = section_span(head, secname)
            if sp:
                head = replace_span(head, sp, safe_block)
                done = True
                break
    if not done:
        zsp = section_span(head, "z_offset_calibration")
        if not zsp:
            raise RuntimeError("Missing [z_offset_calibration] in printer.cfg")
        pos = zsp[1]
        head = head[:pos] + "\n" + safe_block + "\n" + head[pos:].lstrip("\n")

    # Remove/migrate the stock homing_override and leave an explicit tombstone.
    done = False
    for tag in ("SAFE_HOME_LEGACY_HOMING_OVERRIDE", "LEGACY_HOMING_OVERRIDE_REMOVED"):
        sp = managed_span(head, tag)
        if sp:
            head = replace_span(head, sp, tombstone)
            done = True
            break
    if not done:
        sp = section_span(head, "homing_override")
        if sp:
            head = replace_span(head, sp, tombstone)
        else:
            sx = section_span(head, "stepper_x")
            if sx:
                head = head[:sx[0]] + tombstone + "\n" + head[sx[0]:]
            else:
                head = tombstone + "\n" + head

    # No active legacy sections or development backend section may remain.
    if section_span(head, "homing_override"):
        raise RuntimeError("Active [homing_override] remains after patch")
    if section_span(head, "h2_homing_debug_v3"):
        raise RuntimeError("Active [h2_homing_debug_v3] remains after patch")
    if not section_span(head, "M_Bamboo_Safe_Homing"):
        raise RuntimeError("[M_Bamboo_Safe_Homing] missing after patch")
    return head.rstrip() + "\n\n" + tail.lstrip("\n") if tail else head.rstrip() + "\n"


def patch_macro(text, g28_block):
    # Replace production/development managed G28, or the stock G28 section.
    for tag in ("SAFE_HOME_G28", "HOMING_G28"):
        sp = managed_span(text, tag)
        if sp:
            out = replace_span(text, sp, g28_block)
            break
    else:
        sp = section_span(text, "gcode_macro G28")
        if not sp:
            raise RuntimeError("Missing [gcode_macro G28] in Macro.cfg")
        out = replace_span(text, sp, g28_block)
    if "HDBG_HOME_" in out:
        raise RuntimeError("Legacy HDBG_HOME command remains in Macro.cfg")
    return out


def extract_eddy_calibrate_value(text):
    # Direct live section value.
    head, tail = split_save_config(text)
    sp = section_span(head, "probe_eddy_current eddy")
    if sp:
        sec = head[sp[0]:sp[1]]
        m = re.search(r"(?ms)^calibrate\s*:\s*(.*?)(?=^\S[^:\n]*\s*:|^\[|\Z)", sec)
        if m:
            return m.group(1).strip()

    # SAVE_CONFIG representation: '#*# [probe_eddy_current eddy]' and '#*# calibrate ='.
    m = re.search(
        r"(?ms)^#\*# \[probe_eddy_current eddy\]\s*$.*?"
        r"^#\*# calibrate\s*=\s*(.*?)(?=^#\*# [A-Za-z_][A-Za-z0-9_ -]*\s*=|^#\*# \[|\Z)",
        tail,
    )
    if m:
        raw = re.sub(r"(?m)^#\*#\s?", "", m.group(1)).strip()
        return raw
    return None


def eddy_calibrated(text):
    raw = extract_eddy_calibrate_value(text)
    if not raw:
        return False, 0
    points = re.findall(r"[-+]?\d+(?:\.\d+)?\s*:\s*[-+]?\d+(?:\.\d+)?", raw)
    return len(points) > 2, len(points)


def verify_feature_manifest(root, feature_dir):
    manifest_path = feature_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Safe Home manifest.json is missing")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("version") != FEATURE_VERSION:
        raise RuntimeError("Safe Home manifest version mismatch")
    checked = 0
    for item in data.get("files", []):
        rel = item.get("path")
        expected = item.get("sha256")
        if not rel or not expected:
            raise RuntimeError("Invalid Safe Home manifest file entry")
        target = root / rel
        if not target.is_file():
            raise RuntimeError("Release payload missing: %s" % rel)
        actual = sha256(target)
        if actual != expected:
            raise RuntimeError("Release payload checksum mismatch: %s" % rel)
        checked += 1
    if checked < 1:
        raise RuntimeError("Safe Home manifest contains no payload files")
    return checked


def backup_existing(path):
    baseline = path.with_name(path.name + ".mb_baseline")
    last = path.with_name(path.name + ".last_mb_ver")
    if not baseline.exists():
        shutil.copy2(path, baseline)
    shutil.copy2(path, last)


def atomic_write(path, data):
    tmp = path.with_name(path.name + ".M_Bamboo.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def unified(path, old, new):
    return "".join(difflib.unified_diff(
        old.splitlines(True), new.splitlines(True),
        fromfile=str(path), tofile=str(path) + " (M_Bamboo Safe Home v1.0.0)"))


def restart_klipper():
    cmd = ["sudo", "systemctl", "restart", "klipper"]
    subprocess.run(cmd, check=True)
    chk = subprocess.run(["systemctl", "is-active", "klipper"], text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if chk.returncode != 0 or chk.stdout.strip() != "active":
        raise RuntimeError("Klipper service did not return active after restart")


def restore_paths(paths, suffix):
    restored = []
    for p in paths:
        src = p.with_name(p.name + suffix)
        if src.exists():
            atomic_write(p, src.read_bytes())
            restored.append(str(p))
    return restored


def main():
    ap = argparse.ArgumentParser(description=f"{PROJECT} installer")
    ap.add_argument("feature", nargs="?", default=FEATURE, choices=[FEATURE])
    ap.add_argument("--config-dir", default="/home/sovol/printer_data/config")
    ap.add_argument("--extras-dir", default="/home/sovol/klipper/klippy/extras")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", action="store_true", help="restore .last_mb_ver")
    ap.add_argument("--restore-baseline", action="store_true", help="restore .mb_baseline")
    ap.add_argument("--raw-diff", action="store_true")
    ap.add_argument("--force-unrecognized", action="store_true")
    ap.add_argument("--no-restart", action="store_true")
    args = ap.parse_args()

    modes = sum(bool(x) for x in (args.apply, args.rollback, args.restore_baseline))
    if modes > 1:
        raise SystemExit("Choose only one of --apply, --rollback, --restore-baseline")

    root = Path(__file__).resolve().parent
    feature_dir = root / "features" / FEATURE
    config_dir = Path(args.config_dir)
    extras_dir = Path(args.extras_dir)
    printer = config_dir / "printer.cfg"
    macro = config_dir / "Macro.cfg"
    ztarget = extras_dir / "z_offset_calibration.py"
    safe_target = extras_dir / "M_Bamboo_Safe_Homing.py"
    zpayload = feature_dir / "payload" / "z_offset_calibration.py"
    safepayload = feature_dir / "payload" / "M_Bamboo_Safe_Homing.py"
    manifest_files_checked = verify_feature_manifest(root, feature_dir)
    safe_block = load_block(feature_dir / "config" / "printer_safe_home.block")
    tombstone = load_block(feature_dir / "config" / "printer_legacy_homing_override_tombstone.block")
    g28_block = load_block(feature_dir / "config" / "macro_g28.block")

    required = [printer, macro, ztarget, zpayload, safepayload]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise SystemExit("Missing required file(s):\n  " + "\n  ".join(missing))

    touched = [printer, macro, ztarget, safe_target]
    if args.rollback or args.restore_baseline:
        suffix = ".last_mb_ver" if args.rollback else ".mb_baseline"
        # New backend may have no original backup; remove only if it is our exact payload.
        restored = restore_paths(touched, suffix)
        src = safe_target.with_name(safe_target.name + suffix)
        if not src.exists() and safe_target.exists() and sha256(safe_target) == sha256(safepayload):
            safe_target.unlink()
            restored.append(str(safe_target) + " (removed; did not exist before install)")
        if not args.no_restart:
            restart_klipper()
        print(cyan("Rollback complete / 恢复完成"))
        for item in restored:
            print("  " + green("✓") + " " + item)
        return

    old_printer = printer.read_text(encoding="utf-8")
    old_macro = macro.read_text(encoding="utf-8")

    # Hard prerequisite: Safe Home is installed only after Sovol factory Eddy setup.
    has_cal, cal_points = eddy_calibrated(old_printer)
    if not has_cal:
        print(red("INSTALL BLOCKED / 安装已阻止"))
        print("Eddy calibration data was not detected in printer.cfg/SAVE_CONFIG.")
        print("请先使用 Sovol 原厂流程完成 Eddy Current Sensor Calibration，")
        print("确认 SAVE_CONFIG 成功后，再运行 M_Bamboo Safe Home installer。")
        raise SystemExit(2)

    zhash = sha256(ztarget)
    zsource = KNOWN_ZOFFSET_HASHES.get(zhash)
    if zsource is None and zhash != sha256(zpayload) and not args.force_unrecognized:
        print(red("INSTALL BLOCKED / 安装已阻止"))
        print("Unrecognized z_offset_calibration.py:")
        print("  sha256 " + zhash)
        print("Use --force-unrecognized only after reviewing --raw-diff and backups.")
        raise SystemExit(3)
    if zsource is None:
        zsource = "target production" if zhash == sha256(zpayload) else "unrecognized (forced)"

    # Compile payloads before any write.
    with tempfile.TemporaryDirectory(prefix="M_Bamboo_SafeHome_compile_") as td:
        py_compile.compile(str(zpayload), cfile=str(Path(td) / "zoff.pyc"), doraise=True)
        py_compile.compile(str(safepayload), cfile=str(Path(td) / "safe.pyc"), doraise=True)

    new_printer = patch_printer(old_printer, safe_block, tombstone)
    new_macro = patch_macro(old_macro, g28_block)

    if args.raw_diff:
        print("===== printer.cfg =====")
        print(unified(printer, old_printer, new_printer) or "(no changes)")
        print("===== Macro.cfg =====")
        print(unified(macro, old_macro, new_macro) or "(no changes)")

    if not args.apply:
        print()
        print(cyan("╭─ M_Bamboo_SV08Max_Mods · Safe Home v1.0.0 · DRY RUN ─╮"))
        print(cyan("│ Production package preview / 正式版安装预览             │"))
        print(cyan("╰──────────────────────────────────────────────────────────╯"))
        print()
        print(cyan("Preflight / 安装前检查"))
        print(f"  {green('✓')} release checksums      {manifest_files_checked} files verified")
        print(f"  {green('✓')} Eddy calibration       valid ({cal_points} points detected)")
        print(f"  {green('✓')} z_offset source        {zsource}")
        print(f"  {green('✓')} payload py_compile     passed")
        print()
        print(cyan("Safe Home feature"))
        print(f"  {yellow('~')} z_offset_calibration.py   whole-file → v{FEATURE_VERSION}")
        print(f"  {yellow('~')} M_Bamboo_Safe_Homing.py   whole-file → v{FEATURE_VERSION}")
        print(f"  {yellow('~')} printer.cfg               SAFE_HOME managed block")
        print(f"  {red('!')} printer.cfg               remove active [homing_override]")
        print(f"  {yellow('~')} Macro.cfg                 SAFE_HOME_G28 managed block")
        print("      touchscreen ABI          G28 preserved")
        print("      missing Eddy + G28 Z/All explicit error; no factory bootstrap")
        print()
        print(cyan("Runtime policy"))
        print("  calibrated   → genuine HOME_Z → contact verify → Eddy recalibrate")
        print("  uncalibrated → abort; Sovol factory calibration required")
        print("  Zmax+15/≈520 → absent from M_Bamboo runtime backend")
        print()
        print(cyan("Backups on apply"))
        print("  <file>.mb_baseline   create once / never overwrite")
        print("  <file>.last_mb_ver   refresh before this install/upgrade")
        print()
        print(yellow("DRY RUN — nothing written / 未写入文件"))
        print(dim("Use --raw-diff for complete config diffs; --apply to install."))
        return

    # Snapshot rollback data before writes.
    for p in (printer, macro, ztarget):
        backup_existing(p)
    if safe_target.exists():
        backup_existing(safe_target)

    # Keep in-memory rollback copies for automatic failure recovery.
    originals = {p: p.read_bytes() for p in (printer, macro, ztarget) if p.exists()}
    safe_existed = safe_target.exists()
    if safe_existed:
        originals[safe_target] = safe_target.read_bytes()

    try:
        atomic_write(safe_target, safepayload.read_bytes())
        atomic_write(ztarget, zpayload.read_bytes())
        atomic_write(printer, new_printer.encode("utf-8"))
        atomic_write(macro, new_macro.encode("utf-8"))

        # Static post-write validation.
        py_compile.compile(str(safe_target), doraise=True)
        py_compile.compile(str(ztarget), doraise=True)
        final_printer = printer.read_text(encoding="utf-8")
        final_macro = macro.read_text(encoding="utf-8")
        if section_span(split_save_config(final_printer)[0], "homing_override"):
            raise RuntimeError("post-write validation: [homing_override] still active")
        ztext = ztarget.read_text(encoding="utf-8")
        if ("z_max_position + 15" in ztext or
                re.search(r"z_limit_position\s*=", ztext)):
            raise RuntimeError("post-write validation: legacy Zmax+15 logic remains")
        if "M_BAMBOO_HOME_" not in final_macro:
            raise RuntimeError("post-write validation: Safe Home G28 routing missing")

        if not args.no_restart:
            restart_klipper()
    except Exception as exc:
        # Restore exact pre-apply bytes before exiting.
        for p, data in originals.items():
            atomic_write(p, data)
        if not safe_existed and safe_target.exists():
            safe_target.unlink()
        if not args.no_restart:
            try:
                restart_klipper()
            except Exception:
                pass
        raise SystemExit("Install failed; automatic rollback completed: %s" % (exc,))

    print(green("Safe Home v1.0.0 installed successfully / 安装成功"))
    print("Backups: .mb_baseline + .last_mb_ver")
    if args.no_restart:
        print(yellow("Klipper was not restarted (--no-restart)."))
    else:
        print(green("Klipper service: active"))


if __name__ == "__main__":
    main()
