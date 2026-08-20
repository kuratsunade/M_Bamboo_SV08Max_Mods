import importlib.util, sys, types
from pathlib import Path

pkg=types.ModuleType('mbpkg'); pkg.__path__=[]; sys.modules['mbpkg']=pkg
mcu=types.ModuleType('mcu')
class Trsync:
    REASON_COMMS_TIMEOUT=4
    REASON_ENDSTOP_HIT=2
mcu.MCU_trsync=Trsync
class DummyDispatch: pass
mcu.TriggerDispatch=DummyDispatch
sys.modules['mcu']=mcu
for name in ('ldc1612','probe','manual_probe'):
    mod=types.ModuleType('mbpkg.'+name)
    if name=='ldc1612': mod.LDC1612=object
    sys.modules['mbpkg.'+name]=mod

path=Path(__file__).resolve().parent.parent / 'backend' / 'probe_eddy_current.py'
spec=importlib.util.spec_from_file_location('mbpkg.probe_eddy_current', path)
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)
C=mod.EddyEndstopWrapper

class Reactor:
    def __init__(self): self.t=100.0
    def monotonic(self): self.t += .001; return self.t
class Printer:
    command_error=RuntimeError
    def __init__(self): self.r=Reactor()
    def get_reactor(self): return self.r
class G:
    def __init__(self): self.lines=[]
    def respond_info(self,m): self.lines.append(m)
class Sensor:
    def __init__(self, owner, plan): self.owner=owner; self.seq=0; self.plan=list(plan); self.marked=[]
    def get_transport_fault_seq(self): return self.seq
    def mark_transport_recovered_through(self, seq): self.marked.append(seq)
    def get_diagnostic_status(self):
        return {'seq':self.seq,'err_code':34,'known_bits':('I2C_BUS_NACK','I2C_BUS_BUSY'),'unknown_bits':0,'host_receive_time':99.0}
    def check_transport_health(self, settle_time=.2, read_count=3, read_gap=.05):
        action=self.plan.pop(0) if self.plan else 'ok'
        start=self.seq
        if action=='fault':
            self.seq += 1
            ev={'seq':self.seq,'err_code':34,'known_bits':('I2C_BUS_NACK','I2C_BUS_BUSY'),'unknown_bits':0,'host_receive_time':99.0}
            self.owner._handle_transport_fault(ev)
            return {'ok':False,'seq_start':start,'seq_end':self.seq,'reads':(), 'error':None}
        if action=='bad':
            return {'ok':False,'seq_start':start,'seq_end':self.seq,'reads':((0,0),), 'error':None}
        reads=tuple([(0x5449,0x3055)]*read_count)
        return {'ok':True,'seq_start':start,'seq_end':self.seq,'reads':reads,'error':None}

def obj(plan):
    o=C.__new__(C)
    o._printer=Printer(); o.gcode=G(); o._active_transaction=None; o._active_scan_session=None
    o._fault_state=o._fault_reason=o._first_fault_state=o._first_fault_reason=None
    o._last_handled_transport_fault_seq=0; o._transport_state='HEALTHY'; o._recovery_authorized=False
    o._recovery_attempt_used=False; o._safe_home_recovery_token=False; o._restart_required=False; o._last_recovery_check={}
    o._preflight_active=False; o._preflight_context=None; o._preflight_fault_seen=False; o._preflight_last_fault={}; o._z_recovery_required=False
    o._preflight_check_count=0; o._preflight_transient_recovered_count=0; o._preflight_failed_count=0
    o._transport_fault_count=0; o._transport_fault_type_counts={}; o._transport_fault_context_counts={}; o._last_counted_transport_fault_seq=0; o._last_transport_fault={}
    o._recovery_check_count=0; o._recovery_check_pass_count=0; o._armed_recovery_success_count=0
    o._diagnostic_level=2; o._trsync_trigger_cmd=None; o._last_probe={}; o._trusted_trigger_z=None; o._last_trusted_trigger_z=None
    o._sensor_helper=Sensor(o,plan)
    return o

# clean
x=obj(['ok']); assert x.preflight_transport_ready('SAFE_HOME_Z') is True
assert x._transport_fault_count==0 and x._preflight_check_count==1
# one transient, then two clean windows
x=obj(['fault','ok','ok']); assert x.preflight_transport_ready('SAFE_HOME_Z') is True
assert x._fault_state is None and x._transport_state=='HEALTHY'
assert x._transport_fault_count==1 and x._preflight_transient_recovered_count==1
assert x._sensor_helper.marked==[1]
# duplicate late callback must not re-latch
x._handle_transport_fault({'seq':1,'err_code':34,'known_bits':('I2C_BUS_NACK','I2C_BUS_BUSY'),'unknown_bits':0,'host_receive_time':99.0})
assert x._fault_state is None and x._transport_fault_count==1
# persistent prearm failure blocks before motion, but recovery check can restore without G28
x=obj(['fault','bad','bad'])
try: x.preflight_transport_ready('SAFE_HOME_Z'); raise AssertionError('expected block')
except RuntimeError: pass
assert x._fault_state=='HARD_COMM_FAULT' and x._transport_state=='TRANSPORT_FAULT' and not x._z_recovery_required
x._sensor_helper.plan=['ok']
class GC:
    def __init__(self): self.lines=[]
    def respond_info(self,m): self.lines.append(m)
    def error(self,m): return RuntimeError(m)
g=GC(); x.run_transport_recovery_check(g)
assert x._fault_state is None and x._transport_state=='HEALTHY' and not x._recovery_authorized
assert any('normal operations may resume' in line for line in g.lines)
# active motion fault must still require armed Z recovery
x=obj([])
x._active_transaction={'id':1,'kind':'HOMING','caller':'HOMING','state':'ACTIVE','trsync_active':False,'timeline':[],'fault_seq_start':0,'fault_seq_end':0}
x._sensor_helper.seq=1
x._handle_transport_fault({'seq':1,'err_code':34,'known_bits':('I2C_BUS_NACK','I2C_BUS_BUSY'),'unknown_bits':0,'host_receive_time':99.0})
assert x._z_recovery_required and x._fault_state=='HARD_COMM_FAULT'
x._active_transaction=None; x._sensor_helper.plan=['ok']; g=GC(); x.run_transport_recovery_check(g)
assert x._transport_state=='TRANSPORT_RECOVERED' and x._recovery_authorized
assert any('Z is still UNTRUSTED' in line for line in g.lines)
print('PASS: pre-arm transport state-machine mock tests')
