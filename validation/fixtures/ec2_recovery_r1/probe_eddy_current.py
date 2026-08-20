# Support for eddy current based Z probes
#
# Copyright (C) 2021-2024  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, math, bisect
import mcu
from . import ldc1612, probe, manual_probe

OUT_OF_RANGE = 99.9

class _ProbeType:
    TYPE_DEFAULT = 0
    TYPE_VIR_TOUCH = 1

# Tool for calibrating the sensor Z detection and applying that calibration
class EddyCalibration:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.drift_comp = DummyDriftCompensation()
        # Current calibration data
        self.cal_freqs = []
        self.cal_zpos = []
        cal = config.get('calibrate', None)
        if cal is not None:
            cal = [list(map(float, d.strip().split(':', 1)))
                   for d in cal.split(',')]
            self.load_calibration(cal)
        # Probe calibrate state
        self.probe_speed = 0.
        self._safety = None
        # Register commands
        cname = self.name.split()[-1]
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_mux_command("PROBE_EDDY_CURRENT_CALIBRATE", "CHIP",
                                   cname, self.cmd_EDDY_CALIBRATE,
                                   desc=self.cmd_EDDY_CALIBRATE_help)
    def set_safety(self, safety):
        self._safety = safety

    def _check_safety(self):
        if self._safety is not None:
            self._safety._check_fault()

    def is_calibrated(self):
        return len(self.cal_freqs) > 2
    def load_calibration(self, cal):
        cal = sorted([(c[1], c[0]) for c in cal])
        self.cal_freqs = [c[0] for c in cal]
        self.cal_zpos = [c[1] for c in cal]
    def apply_calibration(self, samples):
        cur_temp = self.drift_comp.get_temperature()
        for i, (samp_time, freq, dummy_z) in enumerate(samples):
            adj_freq = self.drift_comp.adjust_freq(freq, cur_temp)
            pos = bisect.bisect(self.cal_freqs, adj_freq)
            if pos >= len(self.cal_zpos):
                zpos = -OUT_OF_RANGE
            elif pos == 0:
                zpos = OUT_OF_RANGE
            else:
                # XXX - could further optimize and avoid div by zero
                this_freq = self.cal_freqs[pos]
                prev_freq = self.cal_freqs[pos - 1]
                this_zpos = self.cal_zpos[pos]
                prev_zpos = self.cal_zpos[pos - 1]
                gain = (this_zpos - prev_zpos) / (this_freq - prev_freq)
                offset = prev_zpos - prev_freq * gain
                zpos = adj_freq * gain + offset
            samples[i] = (samp_time, freq, round(zpos, 6))
    def freq_to_height(self, freq):
        dummy_sample = [(0., freq, 0.)]
        self.apply_calibration(dummy_sample)
        return dummy_sample[0][2]
    def height_to_freq(self, height):
        # XXX - could optimize lookup
        rev_zpos = list(reversed(self.cal_zpos))
        rev_freqs = list(reversed(self.cal_freqs))
        pos = bisect.bisect(rev_zpos, height)
        if pos == 0 or pos >= len(rev_zpos):
            self.gcode.run_script_from_command('M117 Tip code: 115')
            raise self.printer.command_error(
                "Invalid probe_eddy_current height")
        this_freq = rev_freqs[pos]
        prev_freq = rev_freqs[pos - 1]
        this_zpos = rev_zpos[pos]
        prev_zpos = rev_zpos[pos - 1]
        gain = (this_freq - prev_freq) / (this_zpos - prev_zpos)
        offset = prev_freq - prev_zpos * gain
        freq = height * gain + offset
        return self.drift_comp.unadjust_freq(freq)
    def do_calibration_moves(self, move_speed):
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        move = toolhead.manual_move
        # Start data collection
        msgs = []
        is_finished = False
        def handle_batch(msg):
            if is_finished:
                return False
            msgs.append(msg)
            return True
        self.printer.lookup_object(self.name).add_client(handle_batch)
        toolhead.dwell(1.)
        self.drift_comp.note_z_calibration_start()
        # Move to each 40um position
        max_z = 4.0
        samp_dist = 0.040
        req_zpos = [i*samp_dist for i in range(int(max_z / samp_dist) + 1)]
        start_pos = toolhead.get_position()
        times = []
        for zpos in req_zpos:
            # Move to next position (always descending to reduce backlash)
            next_pos = list(start_pos)
            next_pos[2] += zpos
            move(next_pos, move_speed)
            # Note sample timing
            start_query_time = toolhead.get_last_move_time() + 0.050
            end_query_time = start_query_time + 0.050
            toolhead.dwell(0.060)
            # Find Z position based on actual commanded stepper position
            toolhead.flush_step_generation()
            kin_spos = {s.get_name(): s.get_commanded_position()
                        for s in kin.get_steppers()}
            kin_pos = kin.calc_position(kin_spos)
            times.append((start_query_time, end_query_time, kin_pos[2]))
        toolhead.dwell(1.0)
        toolhead.wait_moves()
        self.drift_comp.note_z_calibration_finish()
        # Finish data collection
        is_finished = True
        # Correlate query responses
        cal = {}
        step = 0
        for msg in msgs:
            for query_time, freq, old_z in msg['data']:
                # Add to step tracking
                while step < len(times) and query_time > times[step][1]:
                    step += 1
                if step < len(times) and query_time >= times[step][0]:
                    cal.setdefault(times[step][2], []).append(freq)
        if len(cal) != len(times):
            self.gcode.run_script_from_command('M117 Tip code: 116')
            raise self.printer.command_error(
                "Failed calibration - incomplete sensor data")
        return cal
    def calc_freqs(self, meas):
        total_count = total_variance = 0
        positions = {}
        for pos, freqs in meas.items():
            count = len(freqs)
            freq_avg = float(sum(freqs)) / count
            positions[pos] = freq_avg
            total_count += count
            total_variance += sum([(f - freq_avg)**2 for f in freqs])
        return positions, math.sqrt(total_variance / total_count), total_count
    def post_manual_probe(self, kin_pos):
        if kin_pos is None:
            # Manual Probe was aborted
            return
        # Do not begin calibration motion in a faulted or pending-fault session.
        self._check_safety()
        curpos = list(kin_pos)
        move = self.printer.lookup_object('toolhead').manual_move
        # Move away from the bed
        probe_calibrate_z = curpos[2]
        curpos[2] += 5.
        move(curpos, self.probe_speed)
        # Move sensor over nozzle position
        pprobe = self.printer.lookup_object("probe")
        x_offset, y_offset, z_offset = pprobe.get_offsets()
        curpos[0] -= x_offset
        curpos[1] -= y_offset
        move(curpos, self.probe_speed)
        # Descend back to bed
        curpos[2] -= 5. - 0.050
        move(curpos, self.probe_speed)
        # Perform calibration movement and capture
        cal = self.do_calibration_moves(self.probe_speed)
        # Calculate each sample position average and variance
        positions, std, total = self.calc_freqs(cal)
        last_freq = 0.
        flag_pos = 0.
        for pos, freq in reversed(sorted(positions.items())):
            if flag_pos != 0.:
                positions[flag_pos] += float((freq - last_freq) / 2)
                flag_pos = 0.
                
            if freq < last_freq:
                self.gcode.run_script_from_command('M117 Tip code: 117')
                raise self.printer.command_error(
                    "Failed calibration - frequency not increasing each step")
            elif freq == last_freq:
                flag_pos = pos
            last_freq = freq
        self.gcode.respond_info(
            "probe_eddy_current: stddev=%.3f in %d queries\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "and restart the printer." % (std, total))
        # Save results
        cal_contents = []
        cal_vals = []
        for i, (pos, freq) in enumerate(sorted(positions.items())):
            if not i % 3:
                cal_contents.append('\n')
            cal_contents.append("%.6f:%.3f" % (pos - probe_calibrate_z, freq))
            cal_contents.append(',')
            cal_vals.append([round(pos - probe_calibrate_z, 6), round(freq, 3)]) ##
        cal_contents.pop()
        # The calibration movement includes long sensor-gather dwells, but give
        # the async I2C report path one final reactor opportunity and consume
        # any pending transport fault before accepting persistent calibration.
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.dwell(0.050)
        toolhead.wait_moves()
        self._check_safety()
        configfile = self.printer.lookup_object('configfile')
        configfile.set(self.name, 'calibrate', ''.join(cal_contents))
        self.load_calibration(cal_vals)
    cmd_EDDY_CALIBRATE_help = "Calibrate eddy current probe"
    def cmd_EDDY_CALIBRATE(self, gcmd):
        self._check_safety()
        self.probe_speed = gcmd.get_float("PROBE_SPEED", 5., above=0.)
        # Start manual probe
        return manual_probe.ManualProbeHelper(self.printer, gcmd,
                                       self.post_manual_probe)

    def register_drift_compensation(self, comp):
        self.drift_comp = comp

# Tool to gather samples and convert them to probe positions
class EddyGatherSamples:
    def __init__(self, printer, sensor_helper, calibration, z_offset):
        self._printer = printer
        self._sensor_helper = sensor_helper
        self._calibration = calibration
        self._z_offset = z_offset
        # Results storage
        self._samples = []
        self._probe_times = []
        self._probe_results = []
        self._need_stop = False
        self.gcode = self._printer.lookup_object("gcode")
        # Start samples
        if not self._calibration.is_calibrated():
            self.gcode.respond_info("Must calibrate probe_eddy_current first")
        sensor_helper.add_client(self._add_measurement)
    def _add_measurement(self, msg):
        if self._need_stop:
            del self._samples[:]
            return False
        self._samples.append(msg)
        self._check_samples()
        return True
    def finish(self):
        self._need_stop = True
    def _await_samples(self):
        # Make sure enough samples have been collected
        reactor = self._printer.get_reactor()
        mcu = self._sensor_helper.get_mcu()
        while self._probe_times:
            start_time, end_time, pos_time, toolhead_pos = self._probe_times[0]
            systime = reactor.monotonic()
            est_print_time = mcu.estimated_print_time(systime)
            if est_print_time > end_time + 1.0:
                self.gcode.run_script_from_command('M117 Tip code: 119')
                raise self._printer.command_error(
                    "probe_eddy_current sensor outage")
            reactor.pause(systime + 0.010)
    def _pull_freq(self, start_time, end_time):
        # Find average sensor frequency between time range
        msg_num = discard_msgs = 0
        samp_sum = 0.
        samp_count = 0
        while msg_num < len(self._samples):
            msg = self._samples[msg_num]
            msg_num += 1
            data = msg['data']
            if data[0][0] > end_time:
                break
            if data[-1][0] < start_time:
                discard_msgs = msg_num
                continue
            for time, freq, z in data:
                if time >= start_time and time <= end_time:
                    samp_sum += freq
                    samp_count += 1
        del self._samples[:discard_msgs]
        if not samp_count:
            # No sensor readings - raise error in pull_probed()
            return 0.
        return samp_sum / samp_count
    def _lookup_toolhead_pos(self, pos_time):
        toolhead = self._printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        kin_spos = {s.get_name(): s.mcu_to_commanded_position(
                                      s.get_past_mcu_position(pos_time))
                    for s in kin.get_steppers()}
        return kin.calc_position(kin_spos)
    def _check_samples(self):
        while self._samples and self._probe_times:
            start_time, end_time, pos_time, toolhead_pos = self._probe_times[0]
            if self._samples[-1]['data'][-1][0] < end_time:
                break
            freq = self._pull_freq(start_time, end_time)
            if pos_time is not None:
                toolhead_pos = self._lookup_toolhead_pos(pos_time)
            sensor_z = None
            if freq:
                sensor_z = self._calibration.freq_to_height(freq)
            self._probe_results.append((sensor_z, toolhead_pos))
            self._probe_times.pop(0)
    def pull_probed(self, probe_method=_ProbeType.TYPE_DEFAULT):
        self._await_samples()
        results = []
        for sensor_z, toolhead_pos in self._probe_results:
            if sensor_z is None:
                self.gcode.run_script_from_command('M117 Tip code: 120')
                raise self._printer.command_error(
                    "Unable to obtain probe_eddy_current sensor readings")
            if probe_method == _ProbeType.TYPE_DEFAULT and (sensor_z <= -OUT_OF_RANGE or sensor_z >= OUT_OF_RANGE):
                self.gcode.run_script_from_command('M117 Tip code: 121')
                raise self._printer.command_error(
                    "probe_eddy_current sensor not in valid range")
            elif probe_method == _ProbeType.TYPE_VIR_TOUCH:
                sensor_z = 0.
                self._z_offset = 0.
            # Callers expect position relative to z_offset, so recalculate
            bed_deviation = toolhead_pos[2] - sensor_z
            toolhead_pos[2] = self._z_offset + bed_deviation
            results.append(toolhead_pos)
        del self._probe_results[:]
        return results
    def note_probe(self, start_time, end_time, toolhead_pos):
        self._probe_times.append((start_time, end_time, None, toolhead_pos))
        self._check_samples()
    def note_probe_and_position(self, start_time, end_time, pos_time):
        self._probe_times.append((start_time, end_time, pos_time, None))
        self._check_samples()

# Helper for implementing PROBE style commands (descend until trigger)
class EddyEndstopWrapper:
    _FAULT_RANK = {
        'PROBE_NO_TRIGGER': 1,
        'SENSOR_DATA_FAULT': 2,
        'HARD_FAULT': 3,
        'HARD_COMM_FAULT': 4,
    }
    REASON_SENSOR_ERROR = mcu.MCU_trsync.REASON_COMMS_TIMEOUT + 1
    def __init__(self, config, sensor_helper, calibration):
        self._printer = config.get_printer()
        self._sensor_helper = sensor_helper
        self._mcu = sensor_helper.get_mcu()
        self._calibration = calibration
        self._z_offset = config.getfloat('z_offset', minval=0.)
        self._dispatch = mcu.TriggerDispatch(self._mcu)
        self._trsync_trigger_cmd = None
        self._mcu.register_config_callback(self._build_mb_safety_config)
        self._trigger_time = 0.
        self._gather = None
        self._active_scan_session = None
        self.gcode = self._printer.lookup_object("gcode")
        if hasattr(self._sensor_helper, 'register_transport_fault_handler'):
            self._sensor_helper.register_transport_fault_handler(
                self._handle_transport_fault)
        self._printer.register_event_handler(
            'homing:homing_move_end', self._handle_homing_move_end)
        self._printer.register_event_handler(
            'gcode:command_error', self._handle_command_error)
        # Session-scoped Eddy safety state.  A no-trigger is recoverable in
        # classification (it may be geometry), but normal probing remains
        # blocked until Klipper restarts so a failed probe cannot be retried
        # blindly.
        self._fault_state = None
        self._fault_reason = None
        self._first_fault_state = None
        self._first_fault_reason = None
        # Serial callbacks increment the sensor sequence before their reactor
        # notification runs.  Track the highest sequence consumed by the Eddy
        # Safety Core so a newly-starting operation cannot slip into that gap.
        self._last_handled_transport_fault_seq = 0
        # Transport recovery is deliberately separate from transaction and Z
        # trust.  A recovered bus does not validate the failed transaction or
        # restore Z; it can only arm one explicit Safe Home Z recovery.
        self._transport_state = 'HEALTHY'
        self._recovery_authorized = False
        self._recovery_attempt_used = False
        self._safe_home_recovery_token = False
        self._restart_required = False
        self._last_recovery_check = {}
        self._diagnostic_level = config.getint(
            'eddy_diagnostic_level', 1, minval=0, maxval=2)
        # Non-contact probe safety envelope.  The endpoint is bounded against
        # the lowest trusted Eddy trigger observed since the most recent
        # successful Z homing cycle, not against the current lift height.
        self._probe_below_trigger_allowance = config.getfloat(
            'probe_below_trigger_allowance', None, above=0.)
        self._trusted_trigger_z = None
        self._last_trusted_trigger_z = None
        self._transaction_id = 0
        self._active_transaction = None
        self._next_probe_context = {
            'caller': 'UNKNOWN', 'original_target_z': None,
            'bounded_target_z': None, 'reference_trigger_z': None,
            'probe_below_trigger_allowance': None, 'safety_floor_z': None,
        }
        self._last_probe = {}
        self.homing_method = _ProbeType.TYPE_DEFAULT
        if config.get('homing_method', None) is not None:
            _homing_method = config.get('homing_method', None)
            if _homing_method == 'TOUCH_HOMING':
                self.homing_method = _ProbeType.TYPE_VIR_TOUCH
    def _build_mb_safety_config(self):
        self._trsync_trigger_cmd = self._mcu.lookup_command(
            'trsync_trigger oid=%c reason=%c',
            cq=self._dispatch.get_command_queue())

    def _transport_seq(self):
        getter = getattr(self._sensor_helper, 'get_transport_fault_seq', None)
        return getter() if getter is not None else 0

    def _decode_transport_reason(self, evidence):
        bits = evidence.get('known_bits') or ()
        text = '|'.join(bits) if bits else 'UNKNOWN_I2C_FAULT'
        unknown = evidence.get('unknown_bits', 0)
        if unknown:
            text += '|UNKNOWN_BITS_0x%x' % (unknown,)
        return '%s raw=%s seq=%s' % (
            text, evidence.get('err_code'), evidence.get('seq'))

    def _abort_active_trsync(self, tx, reason='TRANSPORT_FAULT'):
        if (tx is None or tx.get('state') not in ('ARMED', 'ACTIVE')
                or not tx.get('trsync_active')):
            return False
        if self._trsync_trigger_cmd is None:
            return False
        if tx.get('stop_requested'):
            return True
        tx['stop_requested'] = True
        tx['state'] = 'STOP_REQUESTED'
        tx['stop_reason'] = reason
        self._trace_event(tx, 'STOP_REQUESTED', reason)
        self._trsync_trigger_cmd.send(
            [self._dispatch.get_oid(), self.REASON_SENSOR_ERROR])
        self._diag(0, '%s active trsync SENSOR_ERROR stop requested reason=%s'
                   % (self._tx_prefix(tx), reason))
        return True

    def _handle_command_error(self, *args):
        scan = self._active_scan_session
        if scan is not None:
            self._trace_event(scan._tx, 'COMMAND_ERROR_CLEANUP', 'scan session')
            scan.end_probe_session()

    def _handle_transport_fault(self, evidence):
        reason = self._decode_transport_reason(evidence)
        handled_time = self._printer.get_reactor().monotonic()
        evidence = dict(evidence)
        evidence['reactor_handle_time'] = handled_time
        recv_time = evidence.get('host_receive_time')
        if recv_time is not None:
            evidence['reactor_delay_ms'] = max(
                0., (handled_time - recv_time) * 1000.)
        self._last_handled_transport_fault_seq = max(
            self._last_handled_transport_fault_seq, evidence.get('seq', 0))
        tx = self._active_transaction
        recovery_failed = bool(tx is not None and tx.get('recovery_attempt'))
        if recovery_failed:
            self._transport_state = 'HARD_COMM_FAULT'
            self._restart_required = True
        else:
            self._transport_state = 'TRANSPORT_FAULT'
        self._recovery_authorized = False
        self._safe_home_recovery_token = False
        if tx is not None:
            tx['transport_tainted'] = True
            tx['transport_fault'] = dict(evidence)
            tx['fault_seq_end'] = self._transport_seq()
            trace_reason = reason
            if 'reactor_delay_ms' in evidence:
                trace_reason += ' callback_delay_ms=%.3f' % (
                    evidence['reactor_delay_ms'],)
            self._trace_event(tx, 'TRANSPORT_FAULT', trace_reason)
            if tx.get('state') in ('ARMED', 'ACTIVE'):
                self._abort_active_trsync(tx, reason)
        self._set_fault('HARD_COMM_FAULT', reason)

    def _consume_pending_transport_fault(self):
        current = self._transport_seq()
        if current <= self._last_handled_transport_fault_seq:
            return False
        getter = getattr(self._sensor_helper, 'get_diagnostic_status', None)
        evidence = getter() if getter is not None else {
            'seq': current, 'err_code': None, 'known_bits': (),
            'unknown_bits': 0}
        evidence = dict(evidence)
        evidence['seq'] = current
        handled_time = self._printer.get_reactor().monotonic()
        evidence['reactor_handle_time'] = handled_time
        recv_time = evidence.get('host_receive_time')
        if recv_time is not None:
            evidence['reactor_delay_ms'] = max(
                0., (handled_time - recv_time) * 1000.)
        self._last_handled_transport_fault_seq = current
        reason = self._decode_transport_reason(evidence)
        self._transport_state = 'TRANSPORT_FAULT'
        self._recovery_authorized = False
        self._safe_home_recovery_token = False
        tx = self._active_transaction
        if tx is not None:
            tx['transport_tainted'] = True
            tx['transport_fault'] = dict(evidence)
            tx['fault_seq_end'] = current
            trace_reason = reason
            if 'reactor_delay_ms' in evidence:
                trace_reason += ' callback_delay_ms=%.3f' % (
                    evidence['reactor_delay_ms'],)
            self._trace_event(tx, 'PENDING_TRANSPORT_FAULT', trace_reason)
        self._set_fault('HARD_COMM_FAULT',
                        'PENDING_TRANSPORT_FAULT|' + reason)
        return True

    def _recovery_guidance(self):
        if self._restart_required or self._transport_state == 'HARD_COMM_FAULT':
            return ('Recovery is locked after a failed armed attempt. Run '
                    'FIRMWARE_RESTART, verify nozzle clearance, then run G28.')
        if self._transport_state == 'TRANSPORT_FAULT':
            return ('The failed action is aborted and Z is untrusted. This '
                    'communication fault may be transient. After motion has '
                    'stopped, run M_BAMBOO_EDDY_RECOVERY_CHECK. If it reports '
                    'RECOVERED, run one G28; if it still fails, use '
                    'FIRMWARE_RESTART and inspect the Eddy/I2C connection.')
        if self._transport_state == 'TRANSPORT_RECOVERED':
            return ('Eddy transport responded normally, but Z remains '
                    'untrusted. Run one G28 to perform an armed Safe Home '
                    'recovery. Do not run PROBE/QGL/contact/mesh first.')
        return 'No transport recovery action is required.'

    def run_transport_recovery_check(self, gcmd):
        self._consume_pending_transport_fault()
        if self._fault_state is None:
            self._transport_state = 'HEALTHY'
            self._recovery_authorized = False
            gcmd.respond_info(
                'MBEDDY RECOVERY: transport is already HEALTHY; no recovery '
                'check is required.')
            return
        if self._restart_required or self._transport_state == 'HARD_COMM_FAULT':
            raise gcmd.error(
                'M_Bamboo Eddy Recovery: a previous armed recovery failed; '
                'FIRMWARE_RESTART is required before another Z recovery')
        if self._active_transaction is not None:
            raise gcmd.error(
                'M_Bamboo Eddy Recovery: cannot run a transport health check '
                'while an Eddy transaction is active')
        checker = getattr(self._sensor_helper, 'check_transport_health', None)
        if checker is None:
            raise gcmd.error(
                'M_Bamboo Eddy Recovery: sensor backend does not provide a '
                'transport health check')
        before = self._transport_seq()
        gcmd.respond_info(
            'MBEDDY RECOVERY: no-motion transport check starting; current '
            'action remains aborted and Z remains untrusted.')
        result = checker()
        self._last_recovery_check = dict(result)
        after = self._transport_seq()
        if result.get('ok') and after == before:
            self._transport_state = 'TRANSPORT_RECOVERED'
            self._recovery_authorized = True
            self._recovery_attempt_used = False
            reads = result.get('reads', ())
            read_text = ', '.join('%04x/%04x' % pair for pair in reads)
            gcmd.respond_info(
                'MBEDDY RECOVERY: RECOVERED. LDC identity reads=[%s], '
                'fault_seq=%d unchanged. Z is still UNTRUSTED. Run one G28 '
                'to perform the armed Safe Home recovery.' % (read_text, after))
            return
        self._transport_state = 'TRANSPORT_FAULT'
        self._recovery_authorized = False
        reads = result.get('reads', ())
        read_text = ', '.join('%04x/%04x' % pair for pair in reads) or '<none>'
        gcmd.respond_info(
            'MBEDDY RECOVERY: NOT RECOVERED. reads=[%s] fault_seq=%s->%s '
            'error=%s. No Z motion was attempted. You may wait and run '
            'M_BAMBOO_EDDY_RECOVERY_CHECK again, or use FIRMWARE_RESTART. '
            'If the fault repeats, inspect the Eddy cable/connector and '
            'extra_mcu I2C path.' % (
                read_text, result.get('seq_start'), result.get('seq_end'),
                result.get('error') or 'None'))

    def arm_safe_home_recovery(self):
        # Called only by M_Bamboo Safe Home immediately before its raw Z home.
        # It never restores Z trust by itself.
        self._consume_pending_transport_fault()
        if self._fault_state is None:
            self._safe_home_recovery_token = False
            return False
        if (self._restart_required or self._recovery_attempt_used
                or self._transport_state == 'HARD_COMM_FAULT'):
            raise self._printer.command_error(
                'M_Bamboo Eddy Recovery: recovery attempt is no longer '
                'authorized; FIRMWARE_RESTART is required')
        if (self._transport_state != 'TRANSPORT_RECOVERED'
                or not self._recovery_authorized):
            raise self._printer.command_error(
                'M_Bamboo Eddy Recovery: transport has not been confirmed '
                'recovered. Run M_BAMBOO_EDDY_RECOVERY_CHECK first')
        self._safe_home_recovery_token = True
        return True

    def _complete_recovery_success(self, tx):
        self._trace_event(tx, 'RECOVERY_SUCCESS', 'fresh Z home accepted')
        self._fault_state = None
        self._fault_reason = None
        self._transport_state = 'HEALTHY'
        self._recovery_authorized = False
        self._recovery_attempt_used = False
        self._safe_home_recovery_token = False
        self._restart_required = False
        self._diag(0, '%s ARMED RECOVERY SUCCESS: fresh Z home accepted; '
                   'transport=HEALTHY and Z trust re-established'
                   % (self._tx_prefix(tx),))

    def _fail_recovery_attempt(self, tx, reason):
        if tx is None or not tx.get('recovery_attempt'):
            return
        self._transport_state = 'HARD_COMM_FAULT'
        self._recovery_authorized = False
        self._safe_home_recovery_token = False
        self._restart_required = True
        self._trace_event(tx, 'RECOVERY_FAILED', reason)
        self._diag(0, '%s ARMED RECOVERY FAILED: %s; FIRMWARE_RESTART '
                   'required before another recovery attempt'
                   % (self._tx_prefix(tx), reason))

    def _mark_active_aborted(self, result):
        tx = self._active_transaction
        if tx is None:
            return
        tx['state'] = 'ABORTED'
        tx['result'] = result
        tx['fault_seq_end'] = self._transport_seq()
        self._trace_event(tx, 'ABORTED', result)
        self._fail_recovery_attempt(tx, result)
        self._last_probe = self._snapshot_transaction(tx)

    def _transaction_transport_clean(self, tx):
        if tx is None:
            return True
        now = self._transport_seq()
        tx['fault_seq_end'] = now
        if tx.get('transport_tainted') or now != tx.get('fault_seq_start', now):
            tx['transport_tainted'] = True
            return False
        return True

    def _require_transaction_transport_clean(self, tx, context):
        if self._transaction_transport_clean(tx):
            return
        tx['state'] = 'ABORTED'
        tx['result'] = 'TRANSPORT_FAULT'
        self._trace_event(tx, 'ABORTED', '%s transport taint' % context)
        self._fail_recovery_attempt(tx, '%s transport taint' % context)
        self._last_probe = self._snapshot_transaction(tx)
        self._set_fault('HARD_COMM_FAULT', '%s_TRANSACTION_TAINTED' % context)
        raise self._printer.command_error(
            'M_Bamboo Eddy Safety: %s transaction invalidated by an I2C '
            'transport fault' % context)

    def _handle_homing_move_end(self, hmove):
        tx = self._active_transaction
        if tx is None or tx.get('kind') not in ('HOMING', 'PROBE'):
            return
        try:
            involved = any(es is self for es, name in hmove.endstops)
        except Exception:
            involved = False
        if not involved:
            return
        tx['halt_position_reconstructed'] = True
        tx['final'] = list(self._printer.lookup_object('toolhead').get_position())
        self._trace_event(tx, 'HALT_RECONSTRUCTED', tx.get('kind'))
        if not self._transaction_transport_clean(tx):
            tx['state'] = 'ABORTED'
            tx['result'] = 'TRANSPORT_FAULT'
            self._trace_event(tx, 'ABORTED', 'transport taint at halt reconstruction')
            self._fail_recovery_attempt(tx, 'transport taint at halt reconstruction')
            self._last_probe = self._snapshot_transaction(tx)
            self._active_transaction = None
            self._set_fault('HARD_COMM_FAULT',
                            '%s_TRANSACTION_TAINTED' % tx.get('kind'))
            raise self._printer.command_error(
                'M_Bamboo Eddy Safety: %s transaction invalidated by I2C '
                'transport fault' % tx.get('kind').lower())
        if tx.get('state') == 'ABORTED':
            # Preserve the terminal failure state.  Halt reconstruction is
            # still valuable evidence, but it must never make a failed
            # transaction look live or successful again.
            self._last_probe = self._snapshot_transaction(tx)
            self._diag(1, '%s %s ABORTED; halt position reconstructed final=%s'
                       % (self._tx_prefix(tx), tx.get('kind'),
                          self._format_pos(tx['final'])))
            if tx.get('kind') == 'HOMING':
                self._active_transaction = None
            return
        if tx.get('kind') == 'PROBE':
            # Motion has stopped and MCU halt positions are now reflected in
            # toolhead coordinates, but Eddy sample gathering/final transport
            # acceptance still has to complete before this can be SUCCESS.
            tx['state'] = 'HALT_RECONSTRUCTED'
            self._last_probe = self._snapshot_transaction(tx)
            self._diag(2, '%s PROBE halt position reconstructed final=%s' % (
                self._tx_prefix(tx), self._format_pos(tx['final'])))
            return
        if tx.get('state') == 'TRIGGERED':
            if self.homing_method == _ProbeType.TYPE_DEFAULT:
                self._reset_trusted_trigger(self._z_offset)
            tx['state'] = 'SUCCESS'
            tx['result'] = 'SUCCESS'
            self._trace_event(tx, 'SUCCESS', 'homing')
            self._last_probe = self._snapshot_transaction(tx)
            self._diag(1, '%s HOMING SUCCESS final=%s' % (
                self._tx_prefix(tx), self._format_pos(tx['final'])))
            if tx.get('recovery_attempt'):
                self._complete_recovery_success(tx)
                self._last_probe = self._snapshot_transaction(tx)
            self._active_transaction = None

    def _diag(self, level, message):
        if self._diagnostic_level >= level:
            self.gcode.respond_info("MBEDDY: " + message)

    def _format_pos(self, pos):
        if pos is None:
            return '<unknown>'
        return "(%.3f,%.3f,%.3f)" % (pos[0], pos[1], pos[2])

    def _raw_diag(self):
        getter = getattr(self._sensor_helper, 'get_diagnostic_status', None)
        if getter is None:
            return {}
        try:
            return getter() or {}
        except Exception:
            return {}

    def _raw_diag_text(self):
        diag = self._raw_diag()
        if not diag:
            return 'ldc=<unavailable>'
        keys = ('err_code', 'i2c_report_seen', 'sample_error_count',
                'cr1_data', 'cr2_data', 'sr1_data', 'sr2_data', 'dr_data')
        return 'ldc=' + ' '.join('%s=%s' % (key, diag[key])
                                 for key in keys if key in diag)

    def _new_transaction(self, kind, start_pos=None, target_pos=None):
        self._transaction_id += 1
        tx = {
            'id': self._transaction_id, 'kind': kind,
            'start': list(start_pos) if start_pos is not None else None,
            'target': list(target_pos) if target_pos is not None else None,
            'state': 'CREATED',
            'fault_seq_start': self._transport_seq(),
            'fault_seq_end': self._transport_seq(),
            'transport_tainted': False,
            'stop_requested': False,
            'halt_position_reconstructed': False,
            'trsync_active': False,
        }
        tx.update(self._next_probe_context)
        # Probe context belongs to exactly one transaction.  Do not let
        # QGL/non-contact metadata leak into a later contact probe.
        self._next_probe_context = {
            'caller': 'UNKNOWN', 'original_target_z': None,
            'bounded_target_z': None, 'reference_trigger_z': None,
            'probe_below_trigger_allowance': None, 'safety_floor_z': None,
        }
        self._active_transaction = tx
        self._trace_event(tx, 'CREATED', kind)
        return tx

    def _tx_prefix(self, tx=None):
        if tx is None:
            tx = self._active_transaction
        if tx is None:
            return '[----]'
        return '[%04d]' % (tx['id'],)

    def _trace_event(self, tx, event, detail=''):
        if tx is None:
            return
        timeline = tx.setdefault('timeline', [])
        timeline.append({
            'time': self._printer.get_reactor().monotonic(),
            'event': event,
            'detail': detail or '',
        })
        # Keep diagnostics bounded; the latest transaction only needs enough
        # evidence to reconstruct ordering around a fault.
        if len(timeline) > 24:
            del timeline[:-24]

    def _snapshot_transaction(self, tx):
        snap = dict(tx)
        snap['timeline'] = [dict(item) for item in tx.get('timeline', ())]
        return snap

    def _reset_trusted_trigger(self, z_value):
        self._trusted_trigger_z = z_value
        self._last_trusted_trigger_z = z_value
        self._diag(
            2, "trusted trigger reset z=%.3f source=HOMING" % (z_value,))

    def _note_trusted_probe_trigger(self, z_value):
        self._last_trusted_trigger_z = z_value
        if self._trusted_trigger_z is None or z_value < self._trusted_trigger_z:
            self._trusted_trigger_z = z_value
        self._diag(
            2, "trusted trigger update last=%.3f floor_reference=%.3f"
            % (z_value, self._trusted_trigger_z))

    def bound_probe_target(self, start_z, original_target_z):
        allowance = self._probe_below_trigger_allowance
        if allowance is None:
            return original_target_z, {}
        if self._trusted_trigger_z is None:
            raise self._printer.command_error(
                "M_Bamboo Eddy Safety: no trusted Eddy trigger reference; "
                "perform a successful Z homing cycle before probing")
        safety_floor_z = self._trusted_trigger_z - allowance
        bounded_target_z = max(original_target_z, safety_floor_z)
        return bounded_target_z, {
            'reference_trigger_z': self._trusted_trigger_z,
            'probe_below_trigger_allowance': allowance,
            'safety_floor_z': safety_floor_z,
        }

    def set_probe_context(self, caller, original_target_z, bounded_target_z,
                          safety_context=None):
        safety_context = safety_context or {}
        self._next_probe_context = {
            'caller': caller or 'UNKNOWN',
            'original_target_z': original_target_z,
            'bounded_target_z': bounded_target_z,
            'reference_trigger_z': safety_context.get('reference_trigger_z'),
            'probe_below_trigger_allowance': safety_context.get(
                'probe_below_trigger_allowance'),
            'safety_floor_z': safety_context.get('safety_floor_z'),
        }

    def _set_fault(self, state, reason):
        if state == 'HARD_COMM_FAULT' and self._transport_state == 'HEALTHY':
            self._transport_state = 'TRANSPORT_FAULT'
            self._recovery_authorized = False
        if self._fault_state is None:
            self._first_fault_state = state
            self._first_fault_reason = reason
            self._fault_state = state
            self._fault_reason = reason
        else:
            old_rank = self._FAULT_RANK.get(self._fault_state, 0)
            new_rank = self._FAULT_RANK.get(state, 0)
            if new_rank > old_rank:
                old_state, old_reason = self._fault_state, self._fault_reason
                self._fault_state = state
                self._fault_reason = reason
                self._diag(
                    0, "%s FAULT UPGRADED %s(%s) -> %s(%s)"
                    % (self._tx_prefix(), old_state, old_reason,
                       self._fault_state, self._fault_reason))
        self._diag(
            0, "%s FAULT state=%s reason=%s %s"
            % (self._tx_prefix(), self._fault_state, self._fault_reason,
               self._raw_diag_text()))
        if state == 'PROBE_NO_TRIGGER':
            self._diag(
                0, "%s NO_TRIGGER does not by itself prove an Eddy hardware "
                "failure; severe gantry misalignment or a probe/sensor "
                "fault are both possible." % (self._tx_prefix(),))
        if state == 'HARD_COMM_FAULT':
            self._diag(0, '%s TRANSPORT state=%s. %s' % (
                self._tx_prefix(), self._transport_state,
                self._recovery_guidance()))
        else:
            self._diag(
                0, "%s further Eddy Z operations BLOCKED for this Klipper "
                "session. FIRMWARE_RESTART is required to clear the lock. "
                "Before re-homing Z, verify gantry position, nozzle clearance, "
                "and Eddy/probe condition." % (self._tx_prefix(),))

    def _check_fault(self, allow_armed_recovery=False):
        # Close the serial-thread -> reactor notification race: a transport
        # fault sequence that exists but has not yet reached the registered
        # reactor callback is itself sufficient to block a new operation.
        self._consume_pending_transport_fault()
        if self._fault_state is None:
            return False
        if (allow_armed_recovery and self._safe_home_recovery_token
                and self._transport_state == 'TRANSPORT_RECOVERED'
                and self._recovery_authorized
                and not self._restart_required
                and not self._recovery_attempt_used):
            self._safe_home_recovery_token = False
            self._recovery_authorized = False
            self._recovery_attempt_used = True
            return True
        self._diag(
            0, "%s BLOCKED operation fault_state=%s reason=%s transport=%s"
            % (self._tx_prefix(), self._fault_state, self._fault_reason,
               self._transport_state))
        if self._fault_state == 'HARD_COMM_FAULT':
            raise self._printer.command_error(
                'M_Bamboo Eddy Safety: transport fault %s. %s'
                % (self._fault_reason, self._recovery_guidance()))
        raise self._printer.command_error(
            "M_Bamboo Eddy Safety: %s (%s); FIRMWARE_RESTART required "
            "before further Eddy Z probing"
            % (self._fault_state, self._fault_reason))

    def get_safety_status(self):
        return {
            'fault_latched': self._fault_state is not None,
            'fault_state': self._fault_state or 'HEALTHY',
            'fault_reason': self._fault_reason or '',
            'first_fault_state': self._first_fault_state or 'HEALTHY',
            'first_fault_reason': self._first_fault_reason or '',
            'transport_fault_seq': self._transport_seq(),
            'transport_fault_seq_handled': self._last_handled_transport_fault_seq,
            'transport_state': self._transport_state,
            'recovery_authorized': self._recovery_authorized,
            'restart_required': self._restart_required,
            'eddy_diagnostic_level': self._diagnostic_level,
            'eddy_safety_version': 'ES-R4-EC2',
        }

    def get_diagnostic_report(self):
        toolhead = self._printer.lookup_object('toolhead')
        eventtime = self._printer.get_reactor().monotonic()
        status = toolhead.get_status(eventtime)
        pos = toolhead.get_position()
        last = self._last_probe
        lines = [
            '=== M_Bamboo Eddy Status ===',
            'Safety version: ES-R4-EC2',
            'State: %s' % (self._fault_state or 'HEALTHY'),
            'Fault latched: %s' % ('Yes' if self._fault_state else 'No'),
            'Fault reason: %s' % (self._fault_reason or 'None'),
            'First fault: %s (%s)' % (
                self._first_fault_state or 'None',
                self._first_fault_reason or 'None'),
            'Transport fault seq handled/current: %s / %s' % (
                self._last_handled_transport_fault_seq, self._transport_seq()),
            'Transport state: %s' % (self._transport_state,),
            'Recovery armed: %s' % (
                'Yes' if self._recovery_authorized else 'No'),
            'Restart required: %s' % (
                'Yes' if self._restart_required else 'No'),
            'Recovery guidance: %s' % (self._recovery_guidance(),),
            'Last recovery check: %s' % (
                ('PASS seq=%s->%s reads=%d' % (
                    self._last_recovery_check.get('seq_start'),
                    self._last_recovery_check.get('seq_end'),
                    len(self._last_recovery_check.get('reads', ()))))
                if self._last_recovery_check.get('ok') else
                ('FAIL seq=%s->%s reads=%d' % (
                    self._last_recovery_check.get('seq_start'),
                    self._last_recovery_check.get('seq_end'),
                    len(self._last_recovery_check.get('reads', ()))))
                if self._last_recovery_check else 'None'),
            'Diagnostic level: %d' % (self._diagnostic_level,),
            'Probe below-trigger allowance: %s' % (
                ('%.3f mm' % self._probe_below_trigger_allowance)
                if self._probe_below_trigger_allowance is not None else 'stock'),
            'Trusted trigger floor reference: %s' % (
                ('%.3f' % self._trusted_trigger_z)
                if self._trusted_trigger_z is not None else 'None'),
            'Last trusted trigger: %s' % (
                ('%.3f' % self._last_trusted_trigger_z)
                if self._last_trusted_trigger_z is not None else 'None'),
            'Homed axes: %s' % (status.get('homed_axes', '') or '<none>'),
            'Current XYZ: %s' % (self._format_pos(pos),),
            'Last transaction: %s' % (last.get('id', 'None'),),
            'Last caller: %s' % (last.get('caller', 'None'),),
            'Last result: %s' % (last.get('result', 'None'),),
            'Last state: %s' % (last.get('state', 'None'),),
            'Last fault seq: %s -> %s' % (last.get('fault_seq_start', 'None'), last.get('fault_seq_end', 'None')),
            'Last transport tainted: %s' % (last.get('transport_tainted', False),),
            'Last transport callback delay: %s' % (
                ('%.3f ms' % last.get('transport_fault', {}).get('reactor_delay_ms'))
                if last.get('transport_fault', {}).get('reactor_delay_ms') is not None
                else 'None'),
            'Last stop requested: %s' % (last.get('stop_requested', False),),
            'Last halt reconstructed: %s' % (last.get('halt_position_reconstructed', False),),
            'Last start: %s' % (self._format_pos(last.get('start')),),
            'Last target: %s' % (self._format_pos(last.get('target')),),
            'Last final: %s' % (self._format_pos(last.get('final')),),
            'Last descent: %s' % (
                ('%.3f mm' % last['descent']) if last.get('descent') is not None
                else 'None'),
            'LDC telemetry: %s' % (self._raw_diag_text(),),
        ]
        timeline = last.get('timeline', ())
        if timeline:
            base_time = timeline[0].get('time', 0.)
            lines.append('Last event timeline:')
            for item in timeline:
                rel = item.get('time', base_time) - base_time
                detail = item.get('detail', '')
                lines.append('  +%.6fs %-24s %s' % (
                    rel, item.get('event', 'UNKNOWN'), detail))
        return '\n'.join(lines)

    # Interface for MCU_endstop
    def get_mcu(self):
        return self._mcu
    def add_stepper(self, stepper):
        self._dispatch.add_stepper(stepper)
    def get_steppers(self):
        return self._dispatch.get_steppers()
    def home_start(self, print_time, sample_time, sample_count, rest_time,
                   triggered=True):
        recovery_attempt = self._check_fault(allow_armed_recovery=True)
        if self._active_transaction is None:
            toolhead = self._printer.lookup_object('toolhead')
            tx = self._new_transaction('HOMING', toolhead.get_position(), None)
            tx['caller'] = 'HOMING'
            tx['recovery_attempt'] = bool(recovery_attempt)
            if recovery_attempt:
                self._trace_event(tx, 'RECOVERY_ATTEMPT', 'armed Safe Home Z')
                self._diag(0, '%s ARMED RECOVERY: starting one fresh Safe '
                           'Home Z homing transaction' % (self._tx_prefix(tx),))
            self._diag(1, "%s START caller=HOMING start=%s"
                       % (self._tx_prefix(tx),
                          self._format_pos(tx['start'])))
        self._trigger_time = 0.
        tx = self._active_transaction
        tx['state'] = 'ARMING'
        self._trace_event(tx, 'ARMING')
        tx['fault_seq_start'] = self._transport_seq()
        tx['fault_seq_end'] = tx['fault_seq_start']
        trigger_freq = self._calibration.height_to_freq(self._z_offset) if triggered == True else 1
        # [triggered] is used to distinguish whether to use contact homing
        self.homing_method = _ProbeType.TYPE_VIR_TOUCH if triggered == False else _ProbeType.TYPE_DEFAULT
        trigger_completion = self._dispatch.start(print_time)
        tx['trsync_active'] = True
        self._sensor_helper.setup_home(
            print_time, trigger_freq, self._dispatch.get_oid(),
            mcu.MCU_trsync.REASON_ENDSTOP_HIT, self.REASON_SENSOR_ERROR,
            homing_method=self.homing_method)
        tx['state'] = 'ARMED'
        self._trace_event(tx, 'ARMED')
        if not self._transaction_transport_clean(tx):
            self._abort_active_trsync(tx, 'FAULT_DURING_ARMING')
        else:
            tx['state'] = 'ACTIVE'
            self._trace_event(tx, 'ACTIVE', 'trsync armed')
        return trigger_completion
    def home_wait(self, home_end_time):
        self._dispatch.wait_end(home_end_time)
        trigger_time = self._sensor_helper.clear_home()
        res = self._dispatch.stop()
        if self._active_transaction is not None:
            self._active_transaction['trsync_active'] = False
        if res >= mcu.MCU_trsync.REASON_COMMS_TIMEOUT:
            if res == mcu.MCU_trsync.REASON_COMMS_TIMEOUT:
                self._set_fault('HARD_FAULT', 'COMMUNICATION_TIMEOUT')
                self._mark_active_aborted('COMMUNICATION_TIMEOUT')
                self.gcode.run_script_from_command('M117 Tip code: 122')
                raise self._printer.command_error(
                    "Communication timeout during homing")
            tx = self._active_transaction
            if (tx is not None and (tx.get('transport_tainted')
                                    or tx.get('transport_fault'))):
                # ES-R4 deliberately uses the existing trsync SENSOR_ERROR
                # reason as an active-stop transport.  Do not misreport that
                # stop channel as proof of an Eddy hardware/sensor failure.
                self._mark_active_aborted('TRANSPORT_FAULT')
                raise self._printer.command_error(
                    'Eddy transport fault during homing; action aborted. %s'
                    % (self._recovery_guidance(),))
            self._set_fault('HARD_FAULT', 'SENSOR_ERROR')
            self._mark_active_aborted('SENSOR_ERROR')
            self.gcode.run_script_from_command('M117 Tip code: 123')
            raise self._printer.command_error("Eddy current sensor error")
        if res != mcu.MCU_trsync.REASON_ENDSTOP_HIT:
            self._set_fault('PROBE_NO_TRIGGER', 'NO_TRIGGER')
            self._mark_active_aborted('NO_TRIGGER')
            return 0.
        if self._active_transaction is not None:
            self._trace_event(self._active_transaction, 'ENDSTOP_HIT')
        if self._diagnostic_level >= 2:
            self._diag(2, "%s ENDSTOP_HIT trigger_time=%.6f %s"
                       % (self._tx_prefix(), trigger_time,
                          self._raw_diag_text()))
        if self._mcu.is_fileoutput():
            return home_end_time
        self._trigger_time = trigger_time
        if (self._active_transaction is not None
                and self._active_transaction.get('kind') == 'HOMING'):
            # home_wait runs before HomingMove applies the final toolhead
            # coordinate, so do not report a misleading Z/descent here.
            tx = self._active_transaction
            tx['result'] = 'ENDSTOP_HIT'
            tx['state'] = 'TRIGGERED'
            self._trace_event(tx, 'TRIGGERED', 'homing endstop')
            tx['final'] = None
            tx['descent'] = None
            self._last_probe = self._snapshot_transaction(tx)
            self._diag(1, "%s HOMING endstop hit; awaiting halt reconstruction"
                       % (self._tx_prefix(tx),))
        if self._active_transaction is not None:
            self._require_transaction_transport_clean(
                self._active_transaction, self._active_transaction.get('kind', 'PROBE'))
        return trigger_time
    def query_endstop(self, print_time):
        return False # XXX
    # Interface for ProbeEndstopWrapper
    def _run_logged_probe(self, pos, speed, non_contact_probe):
        self._check_fault()
        toolhead = self._printer.lookup_object('toolhead')
        start_pos = list(toolhead.get_position())
        target_pos = list(pos)
        mode = 'NON_CONTACT' if non_contact_probe else 'CONTACT'
        tx = self._new_transaction('PROBE', start_pos, target_pos)
        tx['mode'] = mode
        self._trace_event(tx, 'PROBE_START', mode)
        allowance = tx.get('probe_below_trigger_allowance')
        reference_z = tx.get('reference_trigger_z')
        safety_floor_z = tx.get('safety_floor_z')
        self._diag(
            1, "%s START caller=%s mode=%s start=%s target=%s"
            % (self._tx_prefix(tx), tx.get('caller', 'UNKNOWN'), mode,
               self._format_pos(start_pos), self._format_pos(target_pos)))
        if self._diagnostic_level >= 2:
            self._diag(
                2, "%s TARGET original_z=%s bounded_z=%s reference_z=%s "
                "allowance=%s safety_floor_z=%s"
                % (self._tx_prefix(tx),
                   ('%.3f' % tx['original_target_z'])
                   if tx.get('original_target_z') is not None else 'None',
                   ('%.3f' % tx['bounded_target_z'])
                   if tx.get('bounded_target_z') is not None else 'None',
                   ('%.3f' % reference_z) if reference_z is not None else 'None',
                   ('%.3f' % allowance) if allowance is not None else 'None',
                   ('%.3f' % safety_floor_z)
                   if safety_floor_z is not None else 'None'))
        phoming = self._printer.lookup_object('homing')
        try:
            trig_pos = phoming.probing_move(
                self, pos, speed, non_contact_probe=non_contact_probe)
        except self._printer.command_error:
            final = list(toolhead.get_position())
            tx['final'] = final
            tx['result'] = self._fault_reason or 'COMMAND_ERROR'
            tx['state'] = 'ABORTED'
            tx['descent'] = start_pos[2] - final[2]
            self._trace_event(tx, 'COMMAND_ERROR', tx['result'])
            self._last_probe = self._snapshot_transaction(tx)
            self._diag(
                0, "%s FAILED result=%s final=%s descent=%.3f %s"
                % (self._tx_prefix(tx), tx['result'],
                   self._format_pos(final), tx['descent'],
                   self._raw_diag_text()))
            self._active_transaction = None
            raise
        self._require_transaction_transport_clean(tx, 'PROBE')
        if not self._trigger_time:
            final = list(toolhead.get_position())
            tx['final'] = final
            tx['result'] = 'NO_TRIGGER'
            tx['descent'] = start_pos[2] - final[2]
            self._last_probe = self._snapshot_transaction(tx)
            self._active_transaction = None
            return trig_pos
        start_time = self._trigger_time + 0.050
        end_time = start_time + 0.100
        toolhead_pos = toolhead.get_position()
        self._gather.note_probe(start_time, end_time, toolhead_pos)
        method = (_ProbeType.TYPE_DEFAULT if non_contact_probe
                  else _ProbeType.TYPE_VIR_TOUCH)
        result = self._gather.pull_probed(probe_method=method)[0]
        self._require_transaction_transport_clean(tx, 'PROBE')
        final = list(result)
        tx['final'] = final
        tx['result'] = 'SUCCESS'
        tx['state'] = 'SUCCESS'
        tx['descent'] = start_pos[2] - final[2]
        self._trace_event(tx, 'SUCCESS', mode)
        if non_contact_probe:
            self._note_trusted_probe_trigger(final[2])
        self._last_probe = self._snapshot_transaction(tx)
        self._diag(
            1, "%s TRIGGER OK result=%s descent=%.3f %s"
            % (self._tx_prefix(tx), self._format_pos(final),
               tx['descent'],
               self._raw_diag_text() if self._diagnostic_level >= 2 else ''))
        self._active_transaction = None
        return result

    def probing_move(self, pos, speed):
        return self._run_logged_probe(pos, speed, True)

    def contact_probing_move(self, pos, speed):
        return self._run_logged_probe(pos, speed, False)

    def multi_probe_begin(self):
        self._gather = EddyGatherSamples(self._printer, self._sensor_helper,
                                         self._calibration, self._z_offset)
    def multi_probe_end(self):
        self._gather.finish()
        self._gather = None
    def probe_prepare(self, hmove):
        pass
    def probe_finish(self, hmove):
        pass
    def get_position_endstop(self):
        return self._z_offset

# Implementing probing with "METHOD=scan"
class EddyScanningProbe:
    def __init__(self, printer, sensor_helper, calibration, z_offset, gcmd, safety):
        self._printer = printer
        self._sensor_helper = sensor_helper
        self._calibration = calibration
        self._z_offset = z_offset
        self._safety = safety
        toolhead = printer.lookup_object('toolhead')
        self._tx = safety._new_transaction(
            'RAPID_SCAN' if gcmd.get('METHOD', 'scan') == 'rapid_scan' else 'SCAN',
            toolhead.get_position(), None)
        self._tx['caller'] = 'BED_MESH_SCAN'
        self._tx['state'] = 'ACTIVE'
        self._safety._trace_event(self._tx, 'ACTIVE', 'scan')
        self._gather = EddyGatherSamples(printer, sensor_helper,
                                         calibration, z_offset)
        self._sample_time_delay = 0.050
        self._sample_time = gcmd.get_float("SAMPLE_TIME", 0.100, above=0.0)
        self._is_rapid = gcmd.get("METHOD", "scan") == 'rapid_scan'
        self._safety._active_scan_session = self
    def _rapid_lookahead_cb(self, printtime):
        start_time = printtime - self._sample_time / 2
        self._gather.note_probe_and_position(
            start_time, start_time + self._sample_time, printtime)
    def run_probe(self, gcmd):
        toolhead = self._printer.lookup_object("toolhead")
        if self._is_rapid:
            toolhead.register_lookahead_callback(self._rapid_lookahead_cb)
            return
        printtime = toolhead.get_last_move_time()
        toolhead.dwell(self._sample_time_delay + self._sample_time)
        start_time = printtime + self._sample_time_delay
        self._gather.note_probe_and_position(
            start_time, start_time + self._sample_time, start_time)
    def pull_probed_results(self):
        self._safety._require_transaction_transport_clean(self._tx, 'SCAN')
        if self._is_rapid:
            # Flush lookahead (so all lookahead callbacks are invoked)
            toolhead = self._printer.lookup_object("toolhead")
            toolhead.get_last_move_time()
        results = self._gather.pull_probed()
        self._safety._require_transaction_transport_clean(self._tx, 'SCAN')
        self._tx['state'] = 'SUCCESS'
        self._tx['result'] = 'SUCCESS'
        self._safety._trace_event(self._tx, 'SUCCESS', 'scan')
        self._safety._last_probe = self._safety._snapshot_transaction(self._tx)
        if self._safety._active_transaction is self._tx:
            self._safety._active_transaction = None
        # Allow axis_twist_compensation to update results
        for epos in results:
            self._printer.send_event("probe:update_results", epos)
        return results
    def end_probe_session(self):
        if self._gather is not None:
            self._gather.finish()
            self._gather = None
        if self._safety._active_scan_session is self:
            self._safety._active_scan_session = None

# Main "printer object"
class PrinterEddyProbe:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.calibration = EddyCalibration(config)
        # Sensor type
        sensors = { "ldc1612": ldc1612.LDC1612 }
        sensor_type = config.getchoice('sensor_type', {s: s for s in sensors})
        self.sensor_helper = sensors[sensor_type](config, self.calibration)
        # Probe interface
        self.mcu_probe = EddyEndstopWrapper(config, self.sensor_helper,
                                            self.calibration)
        self.calibration.set_safety(self.mcu_probe)
        self.cmd_helper = probe.ProbeCommandHelper(
            config, self, self.mcu_probe.query_endstop)
        self.probe_offsets = probe.ProbeOffsetsHelper(config)
        self.probe_session = probe.ProbeSessionHelper(config, self.mcu_probe)
        # Obtain contact_probe and non_contact_probe ocbject
        self.contact_probe = self.probe_session
        self.non_contact_probe = self.calibration
        #
        self.printer.add_object('probe', self)
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command(
            'M_BAMBOO_EDDY_STATUS', self.cmd_M_BAMBOO_EDDY_STATUS,
            desc='Report M_Bamboo Eddy safety and diagnostic state')
        self.gcode.register_command(
            'M_BAMBOO_EDDY_RECOVERY_CHECK',
            self.cmd_M_BAMBOO_EDDY_RECOVERY_CHECK,
            desc='Run a no-motion Eddy transport recovery health check')
        self.printer.register_event_handler('klippy:ready', self._handle_ready)
        self.vir_contact_speed = 0.
        if config.get('vir_contact_speed', None) is not None:
            self.vir_contact_speed = config.getfloat('vir_contact_speed', default=5., minval=1.)
        if config.has_section('stepper_z'):
            zconfig = config.getsection('stepper_z')
            self.z_position = zconfig.getfloat('position_min', 0.,
                                               note_valid=False)
        else:
            pconfig = config.getsection('printer')
            self.z_position = pconfig.getfloat('minimum_z_position', 0.,
                                               note_valid=False)
        self.gcode.register_command('RUN_PROBE_VIR_CONTACT', self.cmd_RUN_PROBE_VIR_CONTACT,
                                    desc=self.cmd_RUN_PROBE_VIR_CONTACT_help)
    def _handle_ready(self):
        allowance = self.mcu_probe._probe_below_trigger_allowance
        self.gcode.respond_info(
            "MBEDDY: M_Bamboo Eddy Safety ES-R4-EC2 initialized "
            "probe_below_trigger_allowance=%s diagnostic_level=%d"
            % (('%.3f' % allowance) if allowance is not None else 'stock',
               self.mcu_probe._diagnostic_level))

    def cmd_M_BAMBOO_EDDY_STATUS(self, gcmd):
        gcmd.respond_info(self.mcu_probe.get_diagnostic_report())

    def cmd_M_BAMBOO_EDDY_RECOVERY_CHECK(self, gcmd):
        self.mcu_probe.run_transport_recovery_check(gcmd)

    def prepare_safe_home_z_recovery(self):
        return self.mcu_probe.arm_safe_home_recovery()

    def add_client(self, cb):
        self.sensor_helper.add_client(cb)
    def validate_persistent_probe_config(self, context):
        # Generic probe.py calls this optional hook before it writes a probe
        # calibration result into Klipper's pending persistent config.
        self.mcu_probe._check_fault()
    def get_probe_params(self, gcmd=None):
        return self.probe_session.get_probe_params(gcmd)
    def get_offsets(self):
        return self.probe_offsets.get_offsets()
    def get_status(self, eventtime):
        status = self.cmd_helper.get_status(eventtime)
        status['is_calibrated'] = self.calibration.is_calibrated()
        status.update(self.mcu_probe.get_safety_status())
        status['probe_below_trigger_allowance'] = (
            self.mcu_probe._probe_below_trigger_allowance)
        status['trusted_trigger_z'] = self.mcu_probe._trusted_trigger_z
        return status
    def start_probe_session(self, gcmd):
        self.mcu_probe._check_fault()
        method = gcmd.get('METHOD', 'automatic').lower()
        if method in ('scan', 'rapid_scan'):
            z_offset = self.get_offsets()[2]
            return EddyScanningProbe(self.printer, self.sensor_helper,
                                     self.calibration, z_offset, gcmd,
                                     self.mcu_probe)
        return self.probe_session.start_probe_session(gcmd)
    def register_drift_compensation(self, comp):
        self.calibration.register_drift_compensation(comp)
    def run_non_contact_calibrate(self, gcmd, internal_endstop_offset, z_hop_speed=5.):
        self.mcu_probe._check_fault()
        toolhead = self.printer.lookup_object("toolhead")
        ## set z zero
        pos = toolhead.get_position()
        pos[2] = 0.
        toolhead.set_position(pos, homing_axes=(0, 1, 2))
        ## check 
        if self.non_contact_probe.is_calibrated() == True and gcmd.get("METHOD", "default") == 'default':
            gcmd.respond_info("Eddy data already exists")
            return
        ## calibrate LDC1612 device current
        if self.sensor_helper.dccal.get_drive_current() is None:
            toolhead.manual_move([None, None, 20.], z_hop_speed)
            gcmd_LDC = self.gcode.create_gcode_command("cmd_LDC_CALIBRATE", "cmd_LDC_CALIBRATE", {})
            self.sensor_helper.dccal.cmd_LDC_CALIBRATE(gcmd_LDC)
        else:
            toolhead.manual_move([None, None, 5.], z_hop_speed)
        ## eddy part
        gcmd_EDDY = self.gcode.create_gcode_command("cmd_EDDY_CALIBRATE", "cmd_EDDY_CALIBRATE", {'PROBE_SPEED': 90.})
        gcmd_ACCEPT = self.gcode.create_gcode_command("cmd_ACCEPT", "cmd_ACCEPT", {'Z': -internal_endstop_offset})
        ## calibrate and accept
        manual_probe_helper = self.non_contact_probe.cmd_EDDY_CALIBRATE(gcmd_EDDY)
        manual_probe_helper.move_z(-internal_endstop_offset)
        manual_probe_helper.cmd_ACCEPT(gcmd_ACCEPT)
    def run_contact_probe(self, gcmd):
        self.mcu_probe._check_fault()
        pgcmd = self.gcode.create_gcode_command(
            "RUN_PROBE_VIR_CONTACT", "RUN_PROBE_VIR_CONTACT",
            {'PROBE_SPEED': self.vir_contact_speed,
             'NON_CONTACT_PROBE': 0})
        self.contact_probe.start_probe_session(pgcmd)
        self.contact_probe.run_probe(pgcmd)
        pos = self.contact_probe.pull_probed_results()[0]
        self.contact_probe.end_probe_session()
        gcmd.respond_info("Result is z=%.6f" % (pos[2],))
        return pos
    def cmd_RUN_PROBE_VIR_CONTACT(self, gcmd):
        self.run_contact_probe(gcmd)
    cmd_RUN_PROBE_VIR_CONTACT_help = "VIRTUAL CONTACT PROBE"

class DummyDriftCompensation:
    def get_temperature(self):
        return 0.
    def note_z_calibration_start(self):
        pass
    def note_z_calibration_finish(self):
        pass
    def adjust_freq(self, freq, temp=None):
        return freq
    def unadjust_freq(self, freq, temp=None):
        return freq

def load_config_prefix(config):
    return PrinterEddyProbe(config)
