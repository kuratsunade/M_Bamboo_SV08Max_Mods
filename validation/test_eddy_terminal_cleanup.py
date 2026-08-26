import importlib.util, sys, types
from pathlib import Path

pkg=types.ModuleType('mbpkg'); pkg.__path__=[]; sys.modules['mbpkg']=pkg
mcu=types.ModuleType('mcu')
class Trsync:
    REASON_COMMS_TIMEOUT=4
    REASON_ENDSTOP_HIT=2
mcu.MCU_trsync=Trsync
mcu.TriggerDispatch=object
sys.modules['mcu']=mcu
for name in ('ldc1612','probe','manual_probe'):
    mod=types.ModuleType('mbpkg.'+name)
    if name=='ldc1612': mod.LDC1612=object
    sys.modules['mbpkg.'+name]=mod

path=Path(__file__).resolve().parent.parent / 'backend' / 'probe_eddy_current.py'
spec=importlib.util.spec_from_file_location('mbpkg.probe_eddy_current', path)
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)

# Calibration client must be removed if movement fails after add_client.
class Sensor:
    def __init__(self): self.added=[]; self.removed=[]
    def add_client(self, cb): self.added.append(cb)
    def remove_client(self, cb): self.removed.append(cb)
class Kin:
    def get_steppers(self): return []
class Tool:
    def __init__(self): self.moves=0
    def get_kinematics(self): return Kin()
    def dwell(self, x): pass
    def get_position(self): return [0.,0.,0.,0.]
    def manual_move(self, p, speed): self.moves += 1; raise RuntimeError('move fail')
    def get_last_move_time(self): return 0.
    def flush_step_generation(self): pass
    def wait_moves(self): pass
class Drift:
    def __init__(self): self.started=0; self.finished=0
    def note_z_calibration_start(self): self.started += 1
    def note_z_calibration_finish(self): self.finished += 1
class Printer:
    command_error=RuntimeError
    def __init__(self): self.tool=Tool(); self.sensor=Sensor()
    def lookup_object(self, name):
        return self.tool if name=='toolhead' else self.sensor
cal=mod.EddyCalibration.__new__(mod.EddyCalibration)
cal.printer=Printer(); cal.name='probe_eddy_current eddy'; cal.drift_comp=Drift(); cal.gcode=types.SimpleNamespace()
try:
    cal.do_calibration_moves(5.)
    raise AssertionError('expected movement failure')
except RuntimeError as e:
    assert str(e)=='move fail'
assert len(cal.printer.sensor.added)==1
assert cal.printer.sensor.removed==cal.printer.sensor.added
assert cal.drift_comp.started==1 and cal.drift_comp.finished==1

# Late probe sample failure must terminalize and release active transaction.
class ProbeTool:
    def get_position(self): return [10.,20.,5.,0.]
class PHoming:
    def probing_move(self, *args, **kwargs): return [10.,20.,0.]
class PPrinter:
    command_error=RuntimeError
    def __init__(self): self.tool=ProbeTool(); self.homing=PHoming()
    def lookup_object(self,name): return self.tool if name=='toolhead' else self.homing
class GatherFail:
    def note_probe(self,*a): pass
    def pull_probed(self,**kw): raise RuntimeError('probe_eddy_current sensor outage')
probe=mod.EddyEndstopWrapper.__new__(mod.EddyEndstopWrapper)
probe._printer=PPrinter(); probe._gather=GatherFail(); probe._fault_reason=None; probe._diagnostic_level=0
probe._trigger_time=1.; probe._active_transaction=None; probe._last_probe={}; probe._trusted_trigger_z=None; probe._last_trusted_trigger_z=None
probe._next_probe_context={'caller':'TEST','original_target_z':None,'bounded_target_z':None,'reference_trigger_z':None,'probe_below_trigger_allowance':None,'safety_floor_z':None}
probe._transaction_id=0
probe._check_fault=lambda: None
probe._transport_seq=lambda: 0
probe._require_transaction_transport_clean=lambda tx,ctx: None
probe._diag=lambda *a: None
probe._raw_diag_text=lambda: ''
probe._format_pos=lambda p: str(p)
probe._trace_event=lambda tx,event,detail='': tx.setdefault('timeline',[]).append({'event':event,'detail':detail})
probe._snapshot_transaction=lambda tx: dict(tx)
try:
    probe._run_logged_probe([10.,20.,-1.],5.,False)
    raise AssertionError('expected sample outage')
except RuntimeError as e:
    assert 'sensor outage' in str(e)
assert probe._active_transaction is None
assert probe._last_probe.get('state')=='ABORTED'

# Scan late sample failure and session end must both release transaction state.
class Safety:
    def __init__(self):
        self.seq=0; self._active_transaction=None; self._active_scan_session=None; self._last_probe={}; self._fault_reason=None
    def _transport_seq(self): return self.seq
    def _require_transaction_transport_clean(self,tx,ctx): pass
    def _trace_event(self,tx,event,detail=''): tx.setdefault('timeline',[]).append({'event':event,'detail':detail})
    def _snapshot_transaction(self,tx): return dict(tx)
class SGather:
    def pull_probed(self): raise RuntimeError('scan outage')
    def finish(self): pass
safety=Safety(); scan=mod.EddyScanningProbe.__new__(mod.EddyScanningProbe)
scan._printer=types.SimpleNamespace(command_error=RuntimeError)
scan._safety=safety; scan._tx={'state':'ACTIVE','fault_seq_start':0,'timeline':[]}; scan._gather=SGather(); scan._is_rapid=False
safety._active_transaction=scan._tx; safety._active_scan_session=scan
try:
    scan.pull_probed_results(); raise AssertionError('expected scan outage')
except RuntimeError as e: assert 'scan outage' in str(e)
assert safety._active_transaction is None and scan._tx['state']=='ABORTED'
scan.end_probe_session()
assert safety._active_scan_session is None and scan._gather is None

print('PASS: Eddy terminal lifecycle cleanup tests')
