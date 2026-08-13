# Support for reading frequency samples from ldc1612
#
# Copyright (C) 2024-2025 Sovol3d <info@sovol3d.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
# M_Bamboo Safe Home v1.0.0 runtime safety integration.
# Master_Bamboo / 竹子

M_BAMBOO_SAFE_HOME_VERSION = "1.0.0"
import random
from . import probe, probe_eddy_current, manual_probe
import math
import configparser

class ZoffsetCalibration:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.config = config
        base_endstop_x, base_endstop_y = config.getfloatlist("endstop_xy_position", count=2)
        base_center_x, base_center_y = config.getfloatlist("center_xy_position", count=2)      
        self.endstop_x_pos = base_endstop_x + random.uniform(-10, 10)
        self.endstop_y_pos = base_endstop_y + random.uniform(-10, 10)
        self.center_x_pos = base_center_x + random.uniform(-10, 10)
        self.center_y_pos = base_center_y + random.uniform(-10, 10)
        self.z_hop = config.getfloat("z_hop", default=2.0)
        self.z_hop_speed = config.getfloat('z_hop_speed', 5., above=0.)
        self.zconfig = config.getsection('stepper_z')
        self.endstop_pin = self.zconfig.get('endstop_pin')
        self.speed = config.getfloat('speed', 180.0, above=0.)
        self.internal_endstop_offset = config.getfloat('internal_endstop_offset', default=0.)
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_move = self.printer.lookup_object('gcode_move')
        self.gcode.register_command("Z_OFFSET_CALIBRATION", self.cmd_Z_OFFSET_CALIBRATION, desc=self.cmd_Z_OFFSET_CALIBRATION_help)
        self.last_toolhead_pos = self.last_kinematics_pos = None
        self.non_contact_probe_name = config.get('non_contact_probe', None)
        self.contact_probe_name = config.get('contact_probe', None)
        contact_probe = self.printer.lookup_object(self.contact_probe_name)
        self.x_offset, self.y_offset, self.z_offset = contact_probe.get_offsets()       
        if self.x_offset == 0 and self.y_offset == 0:
            raise config.error("ZoffsetCalibration: Check the x and y offset from [%s] - "
                               "it seems both are 0 and the Probe can't be at the same position as the nozzle :-)" 
                               % self.contact_probe_name)
    def _call_macro(self, macro):
        self.gcode.run_script_from_command(macro)
    def cmd_Z_OFFSET_CALIBRATION(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')

        # Optional safe-refinement mode for callers that already have a valid Z
        # reference (for example, START_PRINT after CLEAN_NOZZLE or after G28 Z).
        #
        # IMPORTANT: USE_CURRENT_Z=1 does NOT home Z and does not make an unknown
        # Z position trustworthy.  It only tells this calibration routine to keep
        # the toolhead's current Z coordinate instead of Sovol's legacy behavior
        # of relabelling the current position to position_max + 15.
        #
        # When omitted, M_Bamboo uses HOME-FIRST whenever calibration work is
        # actually required. The Sovol ~Zmax+15 bootstrap is intentionally not
        # part of the maintained runtime backend; factory bootstrap remains a
        # prerequisite handled by the stock Sovol setup flow.
        requested_use_current_z = gcmd.get_int(
            "USE_CURRENT_Z", 0, minval=0, maxval=1)
        use_current_z = bool(requested_use_current_z)

        # Extra logical search room for the post-mesh contact pass.
        # 后置校准的临时逻辑搜索余量。
        # set_position() changes coordinates only; motors do NOT move.
        # 仅修改逻辑坐标，不产生电机运动，也不降低全局 position_min。
        # Recommended: first pass=0.0, post-mesh pass=1.0 mm.
        # 建议：首次校准=0.0，热床网格后再次校准=1.0 mm。
        use_current_z_allowance = gcmd.get_float(
            "USE_CURRENT_Z_ALLOWANCE", 0.0, minval=0., maxval=5.0)

        # Sanity ceiling for USE_CURRENT_Z; rejects obviously wrong Z state.
        # USE_CURRENT_Z 安全上限：发现明显异常的 Z 状态时直接拒绝执行。
        use_current_z_max = gcmd.get_float("USE_CURRENT_Z_MAX", 15.0, above=0.)

        # position_min is a safety endpoint, never a valid touch result.
        # position_min 仅作为安全边界，不能被当作有效接触结果。
        contact_endpoint_margin = 0.05

        # ZDBG=1: concise runtime diagnostics; no effect on motion.
        # ZDBG=1：输出精简运行诊断，不改变任何运动逻辑。
        zdbg = gcmd.get_int("ZDBG", 0, minval=0, maxval=1)

        def dbg(msg):
            # One switch for all added diagnostics. / 所有新增诊断统一开关。
            if zdbg:
                gcmd.respond_info("ZDBG: " + msg)
        try:
            _non_contact_probe = self.printer.lookup_object(self.non_contact_probe_name)
            _contact_probe = self.printer.lookup_object(self.contact_probe_name)
        except:
            raise gcmd.error('ZoffsetCalibration: Failed to get object.')
        if hasattr(_non_contact_probe, 'run_non_contact_calibrate') is False:
            raise gcmd.error('ZoffsetCalibration: The [run_non_contact_calibrate] in the [non_contact_probe] object is not defined.')
        if hasattr(_contact_probe, 'run_contact_probe') is False:
            raise gcmd.error('ZoffsetCalibration: The [run_contact_probe] in the [contact_probe] object is not defined.')
        eddy_calibrated = _non_contact_probe.calibration.is_calibrated() == True
        method = gcmd.get("METHOD", "default")
        if not eddy_calibrated:
            raise gcmd.error(
                'ZoffsetCalibration: Eddy calibration data is missing. '
                'Complete the Sovol factory Eddy Current Sensor Calibration '
                'and SAVE_CONFIG before using M_Bamboo Z calibration.')
        if method == 'default':
            gcmd.respond_info("ZoffsetCalibration: Eddy data already exists")
            return

        # M_Bamboo production path: once a valid Eddy curve exists, establish a
        # genuine Z reference before recalibration. Explicit USE_CURRENT_Z=1 keeps
        # the caller-controlled current-Z refinement path unchanged.
        # M_Bamboo 正式路径：已有有效 Eddy 曲线时先建立真实 Z 参考；显式
        # USE_CURRENT_Z=1 继续保留调用方控制的 current-Z 精调路径。
        home_first = not requested_use_current_z
        drive_cur = self.config.getint("reg_drive_current", 0, minval=0, maxval=31)
        if drive_cur == 0:
            gcmd_LDC = self.gcode.create_gcode_command("cmd_LDC_CALIBRATE", "cmd_LDC_CALIBRATE", {})
            _contact_probe.sensor_helper.dccal.cmd_LDC_CALIBRATE(gcmd_LDC)
            toolhead.dwell(0.1)
        raw_homing = self.printer.lookup_object('homing')
        try:
            safe_homing = self.printer.lookup_object('M_Bamboo_Safe_Homing')
        except:
            safe_homing = None
        self.toolhead = self.printer.lookup_object('toolhead')
        pheater_bed = self.printer.lookup_object('heater_bed')
        pheater_extruder = self.printer.lookup_object('extruder')
        z_max_position = self.zconfig.getfloat('position_max')
        z_min_position = self.zconfig.getfloat(
            'position_min', 0., note_valid=False)
        bed_temp = gcmd.get_float('BED_TEMP', default=65.0)
        extruder_temp = gcmd.get_float('EXTRUDER_TEMP', default=130.0)
        # Heat up
        pheaters = self.printer.lookup_object('heaters')
        ## set temp
        pheaters.set_temperature(pheater_bed.heater, bed_temp, wait=False)
        pheaters.set_temperature(pheater_extruder.heater, extruder_temp, wait=False)
        ## wait for heating
        pheaters.set_temperature(pheater_bed.heater, bed_temp, wait=True)
        pheaters.set_temperature(pheater_extruder.heater, extruder_temp, wait=True)
        # Home xy
        curtime = self.printer.get_reactor().monotonic()
        # Read homing state once here so the mode checks and the existing XY-home
        # decision are based on the same snapshot of toolhead status.
        status = self.toolhead.get_status(curtime)
        current_pos = self.toolhead.get_position()
        dbg("START requested=%s home_first=%s eddy_calibrated=%s homed=%s "
            "XYZ=(%.3f, %.3f, %.3f)"
            % ("USE_CURRENT_Z" if requested_use_current_z else "AUTO",
               home_first, eddy_calibrated, status['homed_axes'],
               current_pos[0], current_pos[1], current_pos[2]))

        if home_first:
            if safe_homing is None or not hasattr(
                    safe_homing, 'prepare_xy_for_calibration'):
                raise gcmd.error(
                    'ZoffsetCalibration: M_Bamboo Safe Homing backend unavailable.')
            # Home XY only when needed, then establish a real Z reference using
            # the already-calibrated Eddy virtual endstop.
            # 仅在需要时回零 XY，然后利用已有 Eddy 曲线建立真实 Z 参考。
            if ('x' not in status['homed_axes'] or
                    'y' not in status['homed_axes']):
                dbg("HOME-FIRST XY preparation start")
                safe_homing.prepare_xy_for_calibration(gcmd)
                dbg("HOME-FIRST XY preparation done")
            dbg("HOME-FIRST real Z home start")
            safe_homing.cmd_HOME_Z(gcmd)
            dbg("HOME-FIRST real Z home done")
            # Continue through the verified current-Z calibration path.
            # 后续进入已验证的 current-Z 校准路径。
            use_current_z = True
            curtime = self.printer.get_reactor().monotonic()
            status = self.toolhead.get_status(curtime)
            current_pos = self.toolhead.get_position()

        if use_current_z:
            # USE_CURRENT_Z requires an already-established Z reference.
            # USE_CURRENT_Z 必须建立在已有可靠 Z 参考的基础上。
            if 'z' not in status['homed_axes']:
                raise gcmd.error(
                    'ZoffsetCalibration: USE_CURRENT_Z requires Z to be homed.')
            # Reject an implausibly high Z even if Klipper reports Z homed.
            # 即使已回零，Z 数值异常过高时仍拒绝执行。
            if current_pos[2] > use_current_z_max:
                raise gcmd.error(
                    'ZoffsetCalibration: current Z %.3f exceeds '
                    'USE_CURRENT_Z_MAX %.3f.'
                    % (current_pos[2], use_current_z_max))
        if use_current_z:
            # Explicit Z clearance; avoid Sovol override Z side effects.
            # 显式建立 Z 安全间隙，避免 Sovol override 隐式改动 Z。
            if current_pos[2] < 5:
                dbg("Z clearance %.3f -> 5.000"
                    % (current_pos[2],))
                self.toolhead.manual_move([None, None, 5.0], 5.0)
                dbg("Z clearance done Z=%.3f"
                    % (self.toolhead.get_position()[2],))

            # Use upstream Klipper homing semantics for XY only.
            # XY 仅使用 Klipper 原始 homing 语义。
            if ('x' not in status['homed_axes'] or
                    'y' not in status['homed_axes']):
                before = self.toolhead.get_position()
                dbg("raw XY home start XYZ=(%.3f, %.3f, %.3f)"
                    % (before[0], before[1], before[2]))
                gcmd_G28 = self.gcode.create_gcode_command(
                    "G28", "G28", {'X': 0, 'Y': 0})
                raw_homing.cmd_G28(gcmd_G28)
                after = self.toolhead.get_position()
                dbg("raw XY home done XYZ=(%.3f, %.3f, %.3f) dZ=%.6f"
                    % (after[0], after[1], after[2],
                       after[2] - before[2]))
        pos = self.toolhead.get_position()
        # Every active M_Bamboo calibration path now has a trustworthy Z reference.
        # 所有 M_Bamboo 活跃校准路径到此都必须已经具备可信 Z 参考。
        dbg("PREP current Z=%.3f (USE_CURRENT_Z_MAX=%.3f)"
            % (pos[2], use_current_z_max))
        self.set_z_offset(offset=0.)
        # Move to probe position
        gcmd.respond_info("ZoffsetCalibration: Toolhead move ...")
        self.toolhead.manual_move([self.endstop_x_pos, self.endstop_y_pos], self.speed)

        if use_current_z and use_current_z_allowance > 0.:
            # Temporary search room for this first contact only; no motor move.
            # 仅为本次首次接触增加临时搜索余量，不产生电机运动。
            pos = self.toolhead.get_position()
            old_z = pos[2]
            pos[2] = old_z + use_current_z_allowance
            dbg("SEARCH allowance +%.3f mm: logical Z %.6f -> %.6f; floor=%.3f"
                % (use_current_z_allowance, old_z, pos[2], z_min_position))
            self.toolhead.set_position(pos, homing_axes=(0, 1, 2))

        # Contact probe calibration
        gcmd.respond_info("ZoffsetCalibration: Toolhead probing ...")
        dbg("CONTACT start logical_Z=%.6f" % (self.toolhead.get_position()[2],))
        zendstop_p = _contact_probe.run_contact_probe(gcmd)
        dbg("CONTACT trigger raw_Z=%.6f current_Z=%.6f"
            % (zendstop_p[2], self.toolhead.get_position()[2]))

        # Reaching position_min means "no touch detected", never success.
        # 到达 position_min 表示“未检测到接触”，绝不能判定为成功。
        if use_current_z and \
                zendstop_p[2] <= z_min_position + contact_endpoint_margin:
            raise gcmd.error(
                'ZoffsetCalibration: contact probe reached position_min safety '
                'endpoint without a valid virtual-contact trigger.')

        # A temporary search allowance uses contact as a fresh Z=0 verification datum.
        # 使用临时搜索余量时，将有效接触点作为后续验证的 Z=0 基准。
        contact_z0 = use_current_z_allowance > 0.
        if contact_z0:
            pos = self.toolhead.get_position()
            raw_contact_z = pos[2]
            pos[2] = 0.0
            self.toolhead.set_position(pos, homing_axes=(0, 1, 2))
            zendstop_p = list(zendstop_p)
            zendstop_p[2] = 0.0
            dbg("CONTACT datum set: raw_Z=%.6f -> Z=0.000000 (no motor move)"
                % (raw_contact_z,))

        pos = self.toolhead.get_position()
        if contact_z0:
            dbg("VERIFY reference=CONTACT_Z0")
        else:
            # First USE_CURRENT_Z pass has no artificial allowance; keep its native datum.
            # 首次 USE_CURRENT_Z 校准无临时余量，保持原始接触坐标。
            dbg("VERIFY reference=native_contact_Z")
        reprobe_cnt = 1
        while True:
            if(reprobe_cnt >= 10):
                self.gcode.run_script_from_command('M117 Tip code: 109')
                raise gcmd.error('ZoffsetCalibration: Toolhead probe more than ten times.')
            ## perform z hop
            if self.z_hop:
                pos[2] = self.toolhead.get_position()[2] + self.z_hop
                if pos[2] > z_max_position:
                    pos[2] = z_max_position
                self.toolhead.manual_move([None, None, pos[2]], 5)
            gcmd.respond_info("ZoffsetCalibration: Toolhead verifying the difference between before and after %d/10." % (reprobe_cnt))
            dbg("VERIFY #%d start_Z=%.6f"
                % (reprobe_cnt, self.toolhead.get_position()[2]))
            zendstop_p1 = _contact_probe.run_contact_probe(gcmd)
            if use_current_z and \
                    zendstop_p1[2] <= z_min_position + contact_endpoint_margin:
                raise gcmd.error(
                    'ZoffsetCalibration: verification probe reached position_min '
                    'safety endpoint without a valid virtual-contact trigger.')
            diff_z = abs(zendstop_p1[2] - zendstop_p[2])
            dbg("VERIFY #%d trigger_Z=%.6f delta=%.6f"
                % (reprobe_cnt, zendstop_p1[2], diff_z))
            zendstop_p = zendstop_p1
            if diff_z <= 0.02:
                gcmd.respond_info("ZoffsetCalibration: Toolhead check success.")
                break
            reprobe_cnt += 1
        # Rejoin Sovol's original eddy non-contact calibration flow.
        # 从这里重新进入 Sovol 原始 Eddy 非接触校准流程。
        dbg("EDDY calibration start after verified contact")
        _non_contact_probe.run_non_contact_calibrate(gcmd, self.internal_endstop_offset, self.z_hop_speed)
        dbg("DONE post_calibration_toolhead_Z=%.6f (NOT contact height)"
            % (self.toolhead.get_position()[2],))
    def set_z_offset(self, offset):
        # Reset existing Z offset. / 清零现有 Z offset。
        gcmd_offset = self.gcode.create_gcode_command("SET_GCODE_OFFSET",
                                                      "SET_GCODE_OFFSET",
                                                      {'Z': 0})
        self.gcode_move.cmd_SET_GCODE_OFFSET(gcmd_offset)
        # Apply requested Z offset. / 应用目标 Z offset。
        gcmd_offset = self.gcode.create_gcode_command("SET_GCODE_OFFSET",
                                                      "SET_GCODE_OFFSET",
                                                      {'Z': offset})
        self.gcode_move.cmd_SET_GCODE_OFFSET(gcmd_offset)
    cmd_Z_OFFSET_CALIBRATION_help = "Test endstop and bed surface to calculate g-code offset for Z"
    
def load_config(config):
    return ZoffsetCalibration(config)
