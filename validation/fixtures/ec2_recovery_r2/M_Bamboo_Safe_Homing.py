# M_Bamboo Safe Homing for Sovol SV08 Max.
# Master_Bamboo / 竹子
# Safe Home v1.0.0 backend; G28 ABI remains in Macro.cfg.
# Safe Home v1.0.0 后端；G28 对外接口继续由 Macro.cfg 保持。

M_BAMBOO_SAFE_HOME_VERSION = "1.0.0"

class MBambooSafeHoming:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.homing = self.printer.load_object(config, 'homing')

        x_pos, y_pos = config.getfloatlist(
            'home_xy_position', count=2)
        self.home_xy = [x_pos, y_pos]
        self.xy_speed = config.getfloat('xy_speed', 150., above=0.)
        self.z_hop = config.getfloat('z_hop', 5., minval=0.)
        self.z_hop_speed = config.getfloat('z_hop_speed', 10., above=0.)
        self.post_home_z = config.getfloat('post_home_z', 10., minval=0.)

        self.gcode.register_command(
            'M_BAMBOO_HOME_X', self.cmd_HOME_X)
        self.gcode.register_command(
            'M_BAMBOO_HOME_Y', self.cmd_HOME_Y)
        self.gcode.register_command(
            'M_BAMBOO_HOME_XY', self.cmd_HOME_XY)
        self.gcode.register_command(
            'M_BAMBOO_HOME_Z', self.cmd_HOME_Z)
        self.gcode.register_command(
            'M_BAMBOO_HOME_ALL', self.cmd_HOME_ALL)

    def _toolhead(self):
        return self.printer.lookup_object('toolhead')

    def _status(self):
        toolhead = self._toolhead()
        return toolhead.get_kinematics().get_status(
            self.reactor.monotonic())

    def _respond_state(self, gcmd, label):
        toolhead = self._toolhead()
        pos = toolhead.get_position()
        homed = self._status().get('homed_axes', '')
        gcmd.respond_info(
            "MBSH: %s homed=%s XYZ=(%.3f, %.3f, %.3f)"
            % (label, homed, pos[0], pos[1], pos[2]))

    def _raw_home(self, axes, gcmd):
        toolhead = self._toolhead()
        params = {axis: '0' for axis in axes}
        raw = self.gcode.create_gcode_command('G28', 'G28', params)
        before = toolhead.get_position()
        self.homing.cmd_G28(raw)
        after = toolhead.get_position()
        gcmd.respond_info(
            "MBSH: raw home %s dZ=%.6f XYZ=(%.3f, %.3f, %.3f)"
            % (''.join(axes), after[2] - before[2],
               after[0], after[1], after[2]))

    def _establish_z_clearance(self, gcmd):
        if self.z_hop <= 0.:
            return

        toolhead = self._toolhead()
        kin = toolhead.get_kinematics()
        status = self._status()
        pos = toolhead.get_position()

        if 'z' not in status.get('homed_axes', ''):
            # Follow upstream safe_z_home unknown-Z semantics.
            # 未知 Z 时采用 Official safe_z_home 的临时参考语义。
            pos[2] = 0.
            toolhead.set_position(pos, homing_axes=[2])
            toolhead.manual_move(
                [None, None, self.z_hop], self.z_hop_speed)
            if hasattr(kin, 'note_z_not_homed'):
                kin.note_z_not_homed()
            gcmd.respond_info(
                "MBSH: unknown-Z hop +%.3f complete; Z marked unhomed"
                % (self.z_hop,))
        elif pos[2] < self.z_hop:
            # Known Z uses an explicit clearance move.
            # 可信 Z 使用显式安全间隙移动。
            old_z = pos[2]
            toolhead.manual_move(
                [None, None, self.z_hop], self.z_hop_speed)
            gcmd.respond_info(
                "MBSH: known-Z clearance %.3f -> %.3f"
                % (old_z, self.z_hop))

    def _home_z_after_clearance(self, gcmd):
        toolhead = self._toolhead()
        homed = self._status().get('homed_axes', '')
        if 'x' not in homed or 'y' not in homed:
            raise gcmd.error("M_Bamboo Safe Homing: X and Y must be homed before Z")

        before = toolhead.get_position()
        toolhead.manual_move(self.home_xy, self.xy_speed)
        gcmd.respond_info(
            "MBSH: Z-home XY position (%.3f, %.3f)"
            % (self.home_xy[0], self.home_xy[1]))

        # If Eddy transport previously faulted, only an explicit successful
        # no-motion recovery check may arm this one fresh Z-home attempt.
        probe_obj = self.printer.lookup_object('probe', None)
        if (probe_obj is not None
                and hasattr(probe_obj, 'prepare_safe_home_z_recovery')):
            armed = probe_obj.prepare_safe_home_z_recovery()
            if armed:
                gcmd.respond_info(
                    'MBSH: Eddy transport recovery armed; attempting one '
                    'fresh Z home')

        self._raw_home(['Z'], gcmd)

        pos = toolhead.get_position()
        if pos[2] < self.post_home_z:
            toolhead.manual_move(
                [None, None, self.post_home_z], self.z_hop_speed)

        after = toolhead.get_position()
        gcmd.respond_info(
            "MBSH: Z home complete; post-home Z=%.3f, XY delta=(%.3f, %.3f)"
            % (after[2], after[0] - before[0], after[1] - before[1]))

    def _safe_z_hop(self, gcmd):
        # Deprecated internal alias retained for one compatibility cycle.
        return self._establish_z_clearance(gcmd)

    def establish_real_z_reference(self, gcmd, home_xy_if_needed=False,
                                   force_xy_home=False):
        # Atomic recovery-safe sequence: clearance is established exactly once
        # before any XY motion while Z is untrusted.
        self._establish_z_clearance(gcmd)
        homed = self._status().get('homed_axes', '')
        need_x = force_xy_home or (home_xy_if_needed and 'x' not in homed)
        need_y = force_xy_home or (home_xy_if_needed and 'y' not in homed)
        if need_x:
            self._raw_home(['X'], gcmd)
        if need_y:
            self._raw_home(['Y'], gcmd)
        self._home_z_after_clearance(gcmd)

    def prepare_xy_for_calibration(self, gcmd):
        # One safe-hop transaction, then raw XY homing.
        # 单次安全抬升后执行原始 XY 回零，供 Eddy recalibration 的 HOME-FIRST 路径复用。
        self._establish_z_clearance(gcmd)
        self._raw_home(['X'], gcmd)
        self._raw_home(['Y'], gcmd)

    def cmd_HOME_X(self, gcmd):
        self._respond_state(gcmd, "HOME_X start")
        self._establish_z_clearance(gcmd)
        self._raw_home(['X'], gcmd)
        self._respond_state(gcmd, "HOME_X done")

    def cmd_HOME_Y(self, gcmd):
        self._respond_state(gcmd, "HOME_Y start")
        self._establish_z_clearance(gcmd)
        self._raw_home(['Y'], gcmd)
        self._respond_state(gcmd, "HOME_Y done")

    def cmd_HOME_XY(self, gcmd):
        self._respond_state(gcmd, "HOME_XY start")
        self._establish_z_clearance(gcmd)
        self._raw_home(['X'], gcmd)
        self._raw_home(['Y'], gcmd)
        self._respond_state(gcmd, "HOME_XY done")

    def cmd_HOME_Z(self, gcmd):
        self._respond_state(gcmd, "HOME_Z start")
        self.establish_real_z_reference(gcmd, home_xy_if_needed=False)
        self._respond_state(gcmd, "HOME_Z done")

    def cmd_HOME_ALL(self, gcmd):
        self._respond_state(gcmd, "HOME_ALL start")
        self.establish_real_z_reference(
            gcmd, home_xy_if_needed=True, force_xy_home=True)
        self._respond_state(gcmd, "HOME_ALL done")




def load_config(config):
    return MBambooSafeHoming(config)
