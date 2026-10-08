#!/usr/bin/env python3
"""Source-extracted GR1 entry regression, no hardware or motion."""
from types import SimpleNamespace
from test_rc5_combined_runtime import make_supervisor, GCmd, CmdError, load_class

class Cmd(GCmd):
    def __init__(self, params=None):
        super().__init__(); self.params = params or {}
    def get_command_parameters(self):
        return self.params

def setup(state='TRANSPORT_FAULT', params=None):
    calls = []
    def original(g):
        calls.append(('original', dict(g.params)))
        s._status.update(transport_state='HEALTHY', fault_latched=False,
                         z_recovery_required=False)
        s.homed = True
        return 'ok'
    s = make_supervisor(original); s._original = {'G28': original}
    s._status.update(transport_state=state, fault_latched=state!='HEALTHY',
                     restart_required=False, z_recovery_required=True)
    s.homed = False; s._z_homed = lambda: s.homed
    def check(g):
        calls.append('check')
        s._status['transport_state'] = 'TRANSPORT_RECOVERED'
    probe_cls = load_class("PrinterEddyProbe")
    calibration_cls = load_class("EddyCalibration")
    s._probe_obj = object.__new__(probe_cls)
    s._probe_obj.calibration = object.__new__(calibration_cls)
    s._probe_obj.calibration.cal_freqs = [1., 2., 3.]
    s._probe_obj.mcu_probe = SimpleNamespace(
        _consume_pending_transport_fault=lambda: None,
        run_transport_recovery_check=check)
    s._safe_home = lambda: object()
    return s, Cmd(params), calls

def fails(fn, text):
    try: fn()
    except CmdError as e: assert text in str(e), str(e)
    else: raise AssertionError('missing error: '+text)

def test_axes_and_one_home():
    for params in ({}, {'Z':'0'}):
        s,g,c=setup(params=params)
        assert s._dispatch('G28',g)=='ok'
        assert c==['check',('original',params)] and s._recover_calls==0
        assert s.recovery_count==1 and s.recovered_total==1
        assert s.last_result=='ENTRY_RECOVERED_SUCCESS' and not s.active
    for params in ({'X':'0'}, {'Y':'0'}, {'X':'0','Y':'0'}):
        s,g,c=setup(params=params);s._dispatch('G28',g)
        assert c==[('original',params)] and s.recovery_count==0

def test_healthy_passthrough():
    for params in ({}, {'Z':'0'}, {'X':'0','Z':'0'}, {'X':'0','Y':'0','Z':'0'}):
        s,g,c=setup('HEALTHY',params);s._dispatch('G28',g)
        assert c==[('original',params)] and s.recovery_count==0

def test_locks_and_mixed_axes():
    for params in ({'X':'0','Z':'0'}, {'Y':'0','Z':'0'}, {'X':'0','Y':'0','Z':'0'}):
        s,g,c=setup(params=params);fails(lambda:s._dispatch('G28',g),'mixed Z')
        assert c==[]
    for state in ('HARD_COMM_FAULT','TRANSPORT_FAULT'):
        s,g,c=setup(state);s._status['restart_required']=True
        fails(lambda:s._dispatch('G28',g),'locked');assert c==[]
    s,g,c=setup();s._probe_obj.calibration.cal_freqs=[]
    fails(lambda:s._dispatch('G28',g),'not calibrated');assert c==[]

def test_check_failure_terminal():
    s,g,c=setup()
    def check(g): c.append('check');raise CmdError('check failed')
    s._probe_obj.mcu_probe.run_transport_recovery_check=check
    fails(lambda:s._dispatch('G28',g),'check failed')
    assert c==['check'] and s._recover_calls==0 and not s.active

def test_home_failure_terminal():
    for new_fault in (False, True):
        s,g,c=setup()
        def original(g):
            c.append('failed home')
            if new_fault:s._status['transport_fault_seq']+=1
            raise CmdError('home failed')
        s._original['G28']=original
        fails(lambda:s._dispatch('G28',g),'home failed')
        assert c==['check','failed home'] and s._recover_calls==0
        assert s.recovery_count==1 and not s.active and s.owner=='IDLE'

def test_owner_passthrough():
    for nested in (True,False):
        s,g,c=setup();s.active=nested;s._start_owner_active=lambda:not nested
        s._dispatch('G28',g)
        assert c==[('original',{})] and s.recovery_count==0

def test_postcondition():
    s,g,c=setup()
    s._original['G28']=lambda g:c.append('no home')
    fails(lambda:s._dispatch('G28',g),'did not restore')
    assert s.recovered_total==0 and s._recover_calls==0

def test_new_fault_still_uses_old_recovery():
    s,g,c=setup('HEALTHY');n=[0]
    def original(g):
        n[0]+=1
        if n[0]==1:
            s._status['transport_fault_seq']+=1
            raise CmdError('new fault')
    s._original['G28']=original;s._dispatch('G28',g)
    assert n[0]==2 and s._recover_calls==1

def test_actual_macro_route():
    from jinja2 import Environment
    from pathlib import Path
    raw = (Path(__file__).resolve().parents[1] / 'release/config/g28.block').read_text()
    body = raw.split('gcode:', 1)[1].split('# <<<', 1)[0]
    template = Environment(variable_start_string='{', variable_end_string='}').from_string(body)
    for params, expected in (({}, ['M_BAMBOO_HOME_ALL']),
                             ({'Z':'0'}, ['M_BAMBOO_HOME_Z'])):
        s,g,c=setup(params=params)
        def original(g):
            commands = [x.strip() for x in template.render(
                printer={'probe': {'is_calibrated': True}}, params=g.params,
                rawparams='').splitlines() if x.strip()]
            c.extend(commands)
            assert commands == expected
            s.homed = True
            s._status.update(transport_state='HEALTHY', fault_latched=False,
                             z_recovery_required=False)
        s._original['G28']=original
        s._dispatch('G28',g)
        assert c == ['check'] + expected
        assert s._recover_calls == 0

def test_unhealthy_check_result():
    s,g,c=setup()
    s._probe_obj.mcu_probe.run_transport_recovery_check=lambda g:c.append('check')
    fails(lambda:s._dispatch('G28',g),'did not recover')
    assert c==['check'] and s._recover_calls==0

if __name__=='__main__':
    tests=[v for k,v in list(globals().items()) if k.startswith('test_')]
    for t in tests:t()
    print('G28 entry regression PASS (%d groups)'%len(tests))
