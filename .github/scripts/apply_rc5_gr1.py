#!/usr/bin/env python3
"""Deterministically materialize RC5-GR1 into the exact RS1 runtime.

Development build helper only.  It intentionally uses two exact anchors instead
of applying the human-review patch file, because the latter uses abbreviated
context for readability.  Any unexpected source shape fails closed.
"""
from pathlib import Path

PATH = Path("backend/probe_eddy_current.py")
text = PATH.read_text(encoding="utf-8")

if "class MBambooRecoverySupervisor:" in text:
    raise SystemExit("GR1 already present; refusing double materialization")

class_anchor = '\n# Main "printer object"\nclass PrinterEddyProbe:'
if text.count(class_anchor) != 1:
    raise SystemExit(
        "GR1 class anchor must occur exactly once; found %d" % text.count(class_anchor))

SUPERVISOR = r'''
class MBambooRecoverySupervisor:
    """Outer-owner bounded recovery for supported public Eddy operations.

    Recovery is deliberately started only from a synchronous public G-code
    owner.  Sensor, bulk, lookahead and toolhead-flush callbacks remain outside
    this workflow layer.
    """
    VERSION = 'RC5-GR1'
    COMMANDS = (
        'G28',
        'RUN_PROBE_VIR_CONTACT',
        'CLEAN_NOZZLE',
        'Z_OFFSET_CALIBRATION',
        'QUAD_GANTRY_LEVEL',
        'BED_MESH_CALIBRATE',
    )

    def __init__(self, printer, probe_obj):
        self.printer = printer
        self.reactor = printer.get_reactor()
        self.gcode = printer.lookup_object('gcode')
        self._probe_obj = probe_obj
        self._original = {}
        self.ready = False
        self.active = False
        self.owner = 'IDLE'
        self.last_owner = 'NONE'
        self.last_result = 'IDLE'
        self.recovery_count = 0
        self.recovered_total = 0
        self.gcode.register_command(
            'M_BAMBOO_RECOVERY_STATUS', self.cmd_RECOVERY_STATUS,
            desc='Report M_Bamboo generic recovery supervisor state')
        printer.register_event_handler('klippy:ready', self._handle_ready)

    def get_status(self, eventtime):
        return {
            'ready': self.ready,
            'active': self.active,
            'owner': self.owner,
            'last_owner': self.last_owner,
            'last_result': self.last_result,
            'recovery_count': self.recovery_count,
            'recovered_total': self.recovered_total,
            'version': self.VERSION,
            'wrapped_commands': tuple(sorted(self._original)),
        }

    def cmd_RECOVERY_STATUS(self, gcmd):
        st = self.get_status(self.reactor.monotonic())
        gcmd.respond_info(
            '=== M_Bamboo Recovery Supervisor ===\n'
            'Version: %s\n'
            'Ready: %s\n'
            'Active: %s\n'
            'Owner: %s\n'
            'Last owner: %s\n'
            'Last result: %s\n'
            'Recoveries this invocation: %d\n'
            'Recovered operations this Klipper session: %d\n'
            'Wrapped commands: %s'
            % (st['version'], st['ready'], st['active'], st['owner'],
               st['last_owner'], st['last_result'], st['recovery_count'],
               st['recovered_total'], ', '.join(st['wrapped_commands'])))

    def _handle_ready(self):
        # Config-defined macros and native commands have registered before this
        # ready callback. register_command(command, None) returns the exact
        # existing ready handler; retain it and install one outer wrapper.
        if self._original:
            self.ready = True
            return
        installed = {}
        try:
            for command in self.COMMANDS:
                old = self.gcode.register_command(command, None)
                if old is None:
                    continue
                installed[command] = old
                self._original[command] = old
                self.gcode.register_command(
                    command, self._make_handler(command),
                    desc='M_Bamboo bounded-recovery wrapper for %s' % command)
        except Exception:
            self.ready = False
            raise
        self.ready = bool(installed)

    def _make_handler(self, command):
        def _handler(gcmd):
            return self._dispatch(command, gcmd)
        return _handler

    def _safety_status(self):
        return self._probe_obj.get_status(self.reactor.monotonic())

    @staticmethod
    def _marker(st):
        return (int(st.get('transport_fault_seq', 0)),
                int(st.get('preflight_failed_count', 0)))

    @staticmethod
    def _new_evidence(before, after):
        return after[0] > before[0] or after[1] > before[1]

    def _start_owner_active(self):
        start = self.printer.lookup_object('M_Bamboo_Start_Sequence', None)
        return bool(start is not None and getattr(start, 'active', False))

    def _z_homed(self):
        st = self.printer.lookup_object('toolhead').get_status(
            self.reactor.monotonic())
        return 'z' in st.get('homed_axes', '')

    def _safe_home(self):
        obj = self.printer.lookup_object('M_Bamboo_Safe_Homing', None)
        if obj is None:
            raise self.printer.command_error(
                'M_Bamboo recovery: Safe Home unavailable')
        return obj

    def _recover(self, gcmd):
        # One episode receives one recovery attempt.  Failure of identity
        # verification or the fresh Safe Home is terminal for this invocation.
        self._probe_obj.mcu_probe.run_transport_recovery_check(gcmd)
        st = self._safety_status()
        if st.get('restart_required'):
            raise gcmd.error(
                'M_Bamboo recovery: Safety Core requires FIRMWARE_RESTART')
        if st.get('transport_state') not in ('HEALTHY', 'TRANSPORT_RECOVERED'):
            raise gcmd.error(
                'M_Bamboo recovery: transport did not recover cleanly')
        if st.get('z_recovery_required') or not self._z_homed():
            self._safe_home().establish_real_z_reference(
                gcmd, home_xy_if_needed=True)
            st = self._safety_status()
            if (st.get('transport_state') not in
                    ('HEALTHY', 'TRANSPORT_RECOVERED') or not self._z_homed()):
                raise gcmd.error(
                    'M_Bamboo recovery: fresh Safe Home did not restore trust')

    def _dispatch(self, command, gcmd):
        original = self._original.get(command)
        if original is None:
            raise gcmd.error(
                'M_Bamboo recovery: original handler missing for %s' % command)

        # Only the outermost supported public command may own recovery.  The
        # existing START coordinator remains the owner while it is active.
        if self.active or self._start_owner_active():
            return original(gcmd)

        self.active = True
        self.owner = command
        self.last_owner = command
        self.last_result = 'RUNNING'
        self.recovery_count = 0
        try:
            before = self._marker(self._safety_status())
            try:
                result = original(gcmd)
                self.last_result = 'SUCCESS'
                return result
            except self.printer.command_error:
                after = self._marker(self._safety_status())
                if not self._new_evidence(before, after):
                    self.last_result = 'NON_EDDY_ERROR'
                    raise

            self._recover(gcmd)
            self.recovery_count = 1
            gcmd.respond_info(
                'MBRECOVERY: recovered transport for %s; replaying the whole '
                'operation once.' % command)

            retry_before = self._marker(self._safety_status())
            try:
                result = original(gcmd)
            except self.printer.command_error:
                retry_after = self._marker(self._safety_status())
                if self._new_evidence(retry_before, retry_after):
                    self.last_result = 'SECOND_EDDY_FAULT'
                    raise gcmd.error(
                        'M_Bamboo recovery: second Eddy/PREARM fault before '
                        '%s completed; automatic recovery stopped' % command)
                self.last_result = 'REPLAY_ERROR'
                raise

            self.recovered_total += 1
            self.last_result = 'RECOVERED_SUCCESS'
            gcmd.respond_info(
                'MBRECOVERY: %s completed successfully after one automatic '
                'recovery.' % command)
            return result
        finally:
            self.active = False
            self.owner = 'IDLE'
'''

text = text.replace(class_anchor, "\n" + SUPERVISOR.rstrip() + "\n" + class_anchor, 1)

object_anchor = (
    "        self.start_sequence = MBambooStartSequence(self.printer, self)\n"
    "        self.printer.add_object('M_Bamboo_Start_Sequence', self.start_sequence)\n"
)
if text.count(object_anchor) != 1:
    raise SystemExit(
        "GR1 object anchor must occur exactly once; found %d" % text.count(object_anchor))

object_replacement = object_anchor + (
    "        self.recovery_supervisor = MBambooRecoverySupervisor(\n"
    "            self.printer, self)\n"
    "        self.printer.add_object(\n"
    "            'M_Bamboo_Recovery_Supervisor', self.recovery_supervisor)\n"
)
text = text.replace(object_anchor, object_replacement, 1)

# Fail if materialization produced duplicates or omitted the public status hook.
required = (
    "class MBambooRecoverySupervisor:",
    "M_BAMBOO_RECOVERY_STATUS",
    "M_Bamboo_Recovery_Supervisor",
)
for token in required:
    if text.count(token) != 1:
        raise SystemExit("GR1 token %r expected once, found %d" %
                         (token, text.count(token)))

PATH.write_text(text, encoding="utf-8")
