# Support for reading frequency samples from ldc1612
#
# Copyright (C) 2020-2024  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from . import bus, bulk_sensor

MIN_MSG_TIME = 0.100

BATCH_UPDATES = 0.100

LDC1612_ADDR = 0x2a

LDC1612_FREQ = 12000000
SETTLETIME = 0.005
DRIVECUR = 15
DEGLITCH = 0x05 # 10 Mhz

LDC1612_MANUF_ID = 0x5449
LDC1612_DEV_ID = 0x3055

REG_RCOUNT0 = 0x08
REG_OFFSET0 = 0x0c
REG_SETTLECOUNT0 = 0x10
REG_CLOCK_DIVIDERS0 = 0x14
REG_ERROR_CONFIG = 0x19
REG_CONFIG = 0x1a
REG_MUX_CONFIG = 0x1b
REG_DRIVE_CURRENT0 = 0x1e
REG_MANUFACTURER_ID = 0x7e
REG_DEVICE_ID = 0x7f

# Known-good measurement-mode CONFIG value used by this Sovol fork.
# Keep this explicit so transport-tainted calibration never restores a
# potentially corrupted register value read over the same failing bus.
MEASUREMENT_REG_CONFIG = 0x001 | (1<<12) | (1<<10) | (1<<9)

class ErrBitMap:
    I2C_BUS_NACK = 1
    I2C_BUS_TIMEOUT = 2
    I2C_BUS_BUSY = 5
    I2C_BUS_ERR = 7

I2C_ERROR_BITS = (
    (ErrBitMap.I2C_BUS_NACK, 'I2C_BUS_NACK'),
    (ErrBitMap.I2C_BUS_TIMEOUT, 'I2C_BUS_TIMEOUT'),
    (ErrBitMap.I2C_BUS_BUSY, 'I2C_BUS_BUSY'),
    (ErrBitMap.I2C_BUS_ERR, 'I2C_BUS_ERR'),
)

def decode_i2c_error(raw_code):
    known = []
    known_mask = 0
    for bit, name in I2C_ERROR_BITS:
        mask = 1 << bit
        if raw_code & mask:
            known.append(name)
            known_mask |= mask
    return known, raw_code & ~known_mask

# Tool for determining appropriate DRIVE_CURRENT register
class DriveCurrentCalibrate:
    def __init__(self, config, sensor):
        self.printer = config.get_printer()
        self.sensor = sensor
        self.drive_cur = config.getint("reg_drive_current", DRIVECUR,
                                       minval=0, maxval=31)
        self.name = config.get_name()
        gcode = self.printer.lookup_object('gcode')
        gcode.register_mux_command("LDC_CALIBRATE_DRIVE_CURRENT",
                                   "CHIP", self.name.split()[-1],
                                   self.cmd_LDC_CALIBRATE,
                                   desc=self.cmd_LDC_CALIBRATE_help)
    def get_drive_current(self):
        return self.drive_cur
    cmd_LDC_CALIBRATE_help = "Calibrate LDC1612 DRIVE_CURRENT register"
    def cmd_LDC_CALIBRATE(self, gcmd):
        # A prior transport fault in this Klipper session is authoritative.
        # Gate before add_client(), because add_client() synchronously runs
        # _start_measurements() and therefore performs I2C transactions.
        fault_seq_start = self.sensor.get_transport_fault_seq()
        trusted_through = self.sensor.get_transport_trusted_through_seq()
        if fault_seq_start > trusted_through:
            raise self.printer.command_error(
                'LDC1612 drive-current calibration blocked: transport fault '
                'seq=%d has not been recovered (trusted through seq=%d). '
                'Run M_BAMBOO_EDDY_RECOVERY_CHECK and complete the armed G28 '
                'recovery, or use FIRMWARE_RESTART.'
                % (fault_seq_start, trusted_through))
        is_in_progress = True
        def handle_batch(msg):
            return is_in_progress
        self.sensor.add_client(handle_batch)
        toolhead = self.printer.lookup_object("toolhead")
        toolhead.dwell(0.100)
        toolhead.wait_moves()
        # BatchBulkHelper.add_client() synchronously starts measurements in
        # this Sovol fork, so REG_CONFIG is already the known measurement-mode
        # value.  Do not read/restore REG_CONFIG through a potentially failing
        # I2C transaction and later write that untrusted value back.
        self.sensor.set_reg(REG_CONFIG, 0x001 | (1<<9))
        toolhead.wait_moves()
        toolhead.dwell(0.100)
        toolhead.wait_moves()
        reg_drive_current0 = self.sensor.read_reg(REG_DRIVE_CURRENT0)
        self.sensor.set_reg(REG_CONFIG, MEASUREMENT_REG_CONFIG)
        candidate_drive_cur = (reg_drive_current0 >> 6) & 0x1f
        self.sensor.set_reg(REG_DRIVE_CURRENT0, candidate_drive_cur << 11)
        # Give queued I2C responses/fault reports a reactor opportunity before
        # accepting or persisting the result.  The transaction-wide sequence
        # check remains the authority; exact response ordering is still a
        # hardware-validation item.
        toolhead.wait_moves()
        toolhead.dwell(0.050)
        toolhead.wait_moves()
        is_in_progress = False
        if self.sensor.transport_fault_since(fault_seq_start):
            raise self.printer.command_error(
                'LDC1612 drive-current calibration aborted: I2C transport fault '
                'occurred during this calibration transaction')
        # Report found value to user only after transport integrity is accepted.
        self.drive_cur = candidate_drive_cur
        gcmd.respond_info(
            "%s: reg_drive_current: %d\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "with the above and restart the printer." % (self.name, self.drive_cur))
        configfile = self.printer.lookup_object('configfile')
        configfile.set(self.name, 'reg_drive_current', "%d" % (self.drive_cur,))

# Interface class to LDC1612 mcu support
class LDC1612:
    def __init__(self, config, calibration=None):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.calibration = calibration
        self.dccal = DriveCurrentCalibrate(config, self)
        self.data_rate = 250
        # Setup mcu sensor_ldc1612 bulk query code
        self.i2c = bus.MCU_I2C_from_config(config,
                                           default_addr=LDC1612_ADDR,
                                           default_speed=100000)
        self.mcu = mcu = self.i2c.get_mcu()
        self.oid = oid = mcu.create_oid()
        self.query_ldc1612_cmd = None
        self.ldc1612_setup_home_cmd = self.query_ldc1612_home_state_cmd = None
        if config.get('intb_pin', None) is not None:
            ppins = config.get_printer().lookup_object("pins")
            pin_params = ppins.lookup_pin(config.get('intb_pin'))
            if pin_params['chip'] != mcu:
                raise config.error("ldc1612 intb_pin must be on same mcu")
            mcu.add_config_cmd(
                "config_ldc1612_with_intb oid=%d i2c_oid=%d intb_pin=%s"
                % (oid, self.i2c.get_oid(), pin_params['pin']))
        else:
            mcu.add_config_cmd("config_ldc1612 oid=%d i2c_oid=%d"
                               % (oid, self.i2c.get_oid()))
        mcu.add_config_cmd("query_ldc1612 oid=%d rest_ticks=0"
                           % (oid,), on_restart=True)
        mcu.register_config_callback(self._build_config)
        # Bulk sample message reading
        chip_smooth = self.data_rate * BATCH_UPDATES * 2
        self.ffreader = bulk_sensor.FixedFreqReader(mcu, chip_smooth, ">I")
        self.last_error_count = 0
        # Transport-integrity evidence. Safety policy remains in the Eddy
        # probe layer, but transport faults must be preserved losslessly.
        self._last_i2c_diagnostic = {}
        self._transport_fault_seq = 0
        # Highest transport-fault sequence that the Eddy Safety Core has
        # explicitly re-trusted after a successful armed Safe Home recovery.
        # This is a monotonic authorization watermark, not a live bus-health
        # flag.  A newer fault immediately makes transport-sensitive
        # calibration ineligible again.
        self._transport_trusted_through_seq = 0
        self._transport_fault_handlers = []
        # Process messages in batches
        self.batch_bulk = bulk_sensor.BatchBulkHelper(
            self.printer, self._process_batch,
            self._start_measurements, self._finish_measurements, BATCH_UPDATES)
        self.name = config.get_name().split()[-1]
        hdr = ('time', 'frequency', 'z')
        self.batch_bulk.add_mux_endpoint("ldc1612/dump_ldc1612", "sensor",
                                         self.name, {'header': hdr})
        self.i2c_err_flag = 0
        mcu.register_response(self._response_i2c_error, "ldc1612_i2c_report")
        mcu.register_response(self._response_query_loop, "ldc1612_query_loop_report")
        self.gcode.register_command("EDDY_QUERY_LOOP", self.cmd_LDC1612_QUERY_LOOP, desc="query loop")
        self.freq = 0
        self.last_freq = 0
        self.freq_array = []
        self.time_record = 0
    def _build_config(self):
        cmdqueue = self.i2c.get_command_queue()
        self.query_ldc1612_cmd = self.mcu.lookup_command(
            "query_ldc1612 oid=%c rest_ticks=%u", cq=cmdqueue)
        self.ffreader.setup_query_command("query_status_ldc1612 oid=%c",
                                          oid=self.oid, cq=cmdqueue)
        self.ldc1612_setup_home_cmd = self.mcu.lookup_command(
            "ldc1612_setup_home oid=%c clock=%u threshold=%u"
            " trsync_oid=%c trigger_reason=%c error_reason=%c"
            " homing_method=%u", cq=cmdqueue)
        self.query_ldc1612_home_state_cmd = self.mcu.lookup_query_command(
            "query_ldc1612_home_state oid=%c",
            "ldc1612_home_state oid=%c homing=%c trigger_clock=%u",
            oid=self.oid, cq=cmdqueue)
    def get_mcu(self):
        return self.i2c.get_mcu()
    def read_reg(self, reg):
        params = self.i2c.i2c_read([reg], 2)
        response = bytearray(params['response'])
        return (response[0] << 8) | response[1]
    def set_reg(self, reg, val, minclock=0):
        self.i2c.i2c_write([reg, (val >> 8) & 0xff, val & 0xff],
                           minclock=minclock)
    def add_client(self, cb):
        self.batch_bulk.add_client(cb)
    def get_transport_fault_seq(self):
        return self._transport_fault_seq
    def get_transport_trusted_through_seq(self):
        return self._transport_trusted_through_seq
    def mark_transport_recovered_through(self, seq):
        # Policy authority lives in probe_eddy_current.py.  This low-level
        # helper only records the sequence watermark granted by that layer.
        seq = int(seq)
        if seq > self._transport_fault_seq:
            raise self.printer.command_error(
                'LDC1612 transport recovery watermark exceeds current fault '
                'sequence')
        self._transport_trusted_through_seq = max(
            self._transport_trusted_through_seq, seq)
    def register_transport_fault_handler(self, cb):
        self._transport_fault_handlers.append(cb)
    def transport_fault_since(self, seq):
        return self._transport_fault_seq != seq
    def check_transport_health(self, settle_time=0.200, read_count=3,
                               read_gap=0.050):
        # Explicit no-motion health check used by M_Bamboo recovery.  Do not
        # trust the legacy i2c_err_flag here: it is historical and is not
        # cleared by later successful transactions.  Instead require repeated
        # valid identity reads with no new transport_fault_seq evidence.
        reactor = self.printer.get_reactor()
        reactor.pause(reactor.monotonic() + settle_time)
        seq_start = self.get_transport_fault_seq()
        reads = []
        error = None
        for index in range(read_count):
            try:
                manuf_id = self.read_reg(REG_MANUFACTURER_ID)
                dev_id = self.read_reg(REG_DEVICE_ID)
            except Exception as exc:
                error = str(exc)
                break
            reads.append((manuf_id, dev_id))
            # Let a corresponding asynchronous ldc1612_i2c_report reach the
            # reactor before the read is accepted as healthy.  This is an
            # explicit guard against the host-ordering uncertainty of the
            # Sovol synchronous-I2C / async-error-report ABI.
            reactor.pause(reactor.monotonic() + read_gap)
            if self.get_transport_fault_seq() != seq_start:
                break
        seq_end = self.get_transport_fault_seq()
        ids_ok = (len(reads) == read_count and all(
            manuf == LDC1612_MANUF_ID and dev == LDC1612_DEV_ID
            for manuf, dev in reads))
        return {
            'ok': bool(ids_ok and seq_end == seq_start and error is None),
            'seq_start': seq_start,
            'seq_end': seq_end,
            'reads': tuple(reads),
            'error': error,
            'settle_time': settle_time,
            'read_gap': read_gap,
        }
    def _notify_transport_fault(self, evidence):
        for cb in list(self._transport_fault_handlers):
            try:
                cb(dict(evidence))
            except Exception:
                logging.exception('LDC1612 transport fault handler failed')
    # Homing
    def setup_home(self, print_time, trigger_freq,
                   trsync_oid, hit_reason, err_reason, homing_method):
        clock = self.mcu.print_time_to_clock(print_time)
        tfreq = int(trigger_freq * (1<<28) / float(LDC1612_FREQ) + 0.5)
        self.ldc1612_setup_home_cmd.send(
            [self.oid, clock, tfreq, trsync_oid, hit_reason, err_reason, homing_method])
    def clear_home(self):
        self.ldc1612_setup_home_cmd.send([self.oid, 0, 0, 0, 0, 0, 0])
        if self.mcu.is_fileoutput():
            return 0.
        params = self.query_ldc1612_home_state_cmd.send([self.oid])
        tclock = self.mcu.clock32_to_clock64(params['trigger_clock'])
        return self.mcu.clock_to_print_time(tclock)
    # Measurement decoding
    def _convert_samples(self, samples):
        freq_conv = float(LDC1612_FREQ) / (1<<28)
        count = 0
        for ptime, val in samples:
            mv = val & 0x0fffffff
            if mv != val:
                self.last_error_count += 1
            samples[count] = (round(ptime, 6), round(freq_conv * mv, 3), 999.9)
            count += 1
    # Start, stop, and process message batches
    def _start_measurements(self):
        # In case of miswiring, testing LDC1612 device ID prevents treating
        # noise or wrong signal as a correctly initialized device
        retry_cnt = 0
        fault_seq_start = self.get_transport_fault_seq()
        manuf_id = self.read_reg(REG_MANUFACTURER_ID)
        dev_id = self.read_reg(REG_DEVICE_ID)
        # Loop test to prevent external interference when read only once, read the wrong data
        while (manuf_id != LDC1612_MANUF_ID or dev_id != LDC1612_DEV_ID):
            if retry_cnt > 2:
                if self.transport_fault_since(fault_seq_start):
                    if self.i2c_err_flag & (1 << ErrBitMap.I2C_BUS_BUSY) and self.i2c_err_flag & (1 << ErrBitMap.I2C_BUS_TIMEOUT):
                        self.gcode.run_script_from_command('M117 Tip code: 112')
                        msg = "LDC1612 I2C bus busy or timeout error,please check the connection between the sensor module and the mainboard."
                    else:
                        self.gcode.run_script_from_command('M117 Tip code: 113')
                        msg = "LDC1612 I2C bus error.There may have been internal or external interference during the communication."
                else:
                    self.gcode.run_script_from_command('M117 Tip code: 114')
                    msg = "Invalid ldc1612 id (got %x,%x vs %x,%x).\n\
                           This is generally indicative of connection problems\n\
                           (e.g. faulty wiring) or a faulty ldc1612 chip."\
                           % (manuf_id, dev_id, LDC1612_MANUF_ID, LDC1612_DEV_ID)
                raise self.printer.command_error(msg)
            manuf_id = self.read_reg(REG_MANUFACTURER_ID)
            dev_id = self.read_reg(REG_DEVICE_ID)
            retry_cnt += 1 
        # Setup chip in requested query rate
        rcount0 = LDC1612_FREQ / (16. * (self.data_rate - 4))
        self.set_reg(REG_RCOUNT0, int(rcount0 + 0.5))
        self.set_reg(REG_OFFSET0, 0)
        self.set_reg(REG_SETTLECOUNT0, int(SETTLETIME*LDC1612_FREQ/16. + .5))
        self.set_reg(REG_CLOCK_DIVIDERS0, (1 << 12) | 1)
        self.set_reg(REG_ERROR_CONFIG, (0x1f << 11) | 1)
        self.set_reg(REG_MUX_CONFIG, 0x0208 | DEGLITCH)
        self.set_reg(REG_CONFIG, MEASUREMENT_REG_CONFIG)
        self.set_reg(REG_DRIVE_CURRENT0, self.dccal.get_drive_current() << 11)
        # Start bulk reading
        rest_ticks = self.mcu.seconds_to_clock(0.5 / self.data_rate)
        self.query_ldc1612_cmd.send([self.oid, rest_ticks])
        logging.info("LDC1612 starting '%s' measurements", self.name)
        # Initialize clock tracking
        self.ffreader.note_start()
        self.last_error_count = 0
    def _finish_measurements(self):
        # Halt bulk reading
        self.query_ldc1612_cmd.send_wait_ack([self.oid, 0])
        self.ffreader.note_end()
        logging.info("LDC1612 finished '%s' measurements", self.name)
    def _process_batch(self, eventtime):
        samples = self.ffreader.pull_samples()
        self._convert_samples(samples)
        if not samples:
            return {}
        if self.calibration is not None:
            self.calibration.apply_calibration(samples)
        return {'data': samples, 'errors': self.last_error_count,
                'overflows': self.ffreader.get_last_overflows()}
    def _response_i2c_error(self, params):
        raw_code = params["err_code"]
        known_bits, unknown_bits = decode_i2c_error(raw_code)
        self.i2c_err_flag = raw_code  # legacy/display-only last error
        self._transport_fault_seq += 1
        evidence = {
            'seq': self._transport_fault_seq,
            'host_receive_time': self.printer.get_reactor().monotonic(),
            'cr1_data': params['cr1_data'],
            'cr2_data': params['cr2_data'],
            'sr1_data': params['sr1_data'],
            'sr2_data': params['sr2_data'],
            'dr_data': params['dr_data'],
            'err_code': raw_code,
            'known_bits': tuple(known_bits),
            'unknown_bits': unknown_bits,
        }
        self._last_i2c_diagnostic = evidence
        logging.info(
            "report ldc1612 i2c register: cr1_data=%u cr2_data=%u "
            "sr1_data=%u sr2_data=%u dr_data=%u err_code=%u decoded=%s "
            "unknown_bits=%u seq=%u",
            params["cr1_data"], params["cr2_data"],
            params["sr1_data"], params["sr2_data"],
            params["dr_data"], raw_code,
            '|'.join(known_bits) if known_bits else 'UNKNOWN',
            unknown_bits, self._transport_fault_seq)
        reactor = self.printer.get_reactor()
        reactor.register_async_callback(
            lambda eventtime, ev=dict(evidence): self._notify_transport_fault(ev))
    def get_diagnostic_status(self):
        status = {
            'err_code': self.i2c_err_flag,
            'i2c_report_seen': bool(self._last_i2c_diagnostic),
            'sample_error_count': self.last_error_count,
            'transport_fault_seq': self._transport_fault_seq,
        }
        status.update(self._last_i2c_diagnostic)
        return status
    def write_data_to_file(self, time_value, z_pos, frequency_value):
        try:
            with open('/home/sovol/klipper/klippy/extras/sensor_data.txt', 'a') as file:
                file.write(f"{time_value} {z_pos} {frequency_value}\n")
                file.flush()
        except FileNotFoundError as e:
            print(f"File not found: {e}")
        except PermissionError as e:
            print(f"Permission error: {e}")
        except Exception as e:
            print(f"Other error: {e}")
    def cmd_LDC1612_QUERY_LOOP(self, gcmd):
        self.freq_array.clear()
        rest_ticks = 0
        if gcmd.get("SWITCH", "OFF") == "ON":
            rest_ticks = self.mcu.seconds_to_clock(0.5 / self.data_rate)
        gcmd.respond_info("rest_ticks:%u" % (rest_ticks))
        self.query_ldc1612_cmd.send([self.oid, rest_ticks])
    def _response_query_loop(self, params):
        kin = self.printer.lookup_object('toolhead').get_kinematics()
        _stepper_z = kin.get_steppers()[2]
        _z_cmd_pos = _stepper_z.get_commanded_position()
        self.last_freq = self.freq
        self.freq = params['freq']
        self.time_record+=1
        self.freq_array.append(self.freq)
        self.write_data_to_file(self.time_record, _z_cmd_pos, self.freq)
        # if self.freq != self.last_freq:
        #     self.write_data_to_file(self.time_record, _z_cmd_pos, self.freq)
        if self.freq_array.count(self.freq) == 0:
            self.freq_array.append(self.freq)
            print(f'freq_array:{self.freq_array}')
