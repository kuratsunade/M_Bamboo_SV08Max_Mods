#!/usr/bin/env python3
"""Source-level mock regression for materialized RC5 RS1+GR1 classes.

The test extracts the actual class definitions from backend/probe_eddy_current.py
with ast, so it exercises the implementation shipped to the machine without
importing the full Klipper runtime.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'backend' / 'probe_eddy_current.py'


def load_class(name):
    tree = ast.parse(SRC.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, str(SRC), 'exec'), ns)
    return ns[name]


class CmdError(Exception):
    pass


class GCmd:
    def __init__(self):
        self.info = []
    def error(self, msg):
        return CmdError(msg)
    def respond_info(self, msg):
        self.info.append(msg)


class Printer:
    command_error = CmdError


class Gather:
    def __init__(self):
        self.calls = []
    def note_probe_and_position(self, *args):
        self.calls.append(args)


def test_rs1_callback():
    cls = load_class('EddyScanningProbe')
    obj = cls.__new__(cls)
    obj._sample_time = 0.1
    obj._ended = False
    g = Gather()
    obj._gather = g
    obj._rapid_lookahead_cb(10.0)
    assert len(g.calls) == 1
    expected = (9.95, 10.05, 10.0)
    assert all(abs(a-b) < 1e-12 for a, b in zip(g.calls[0], expected))

    obj._ended = True
    obj._rapid_lookahead_cb(11.0)
    assert len(g.calls) == 1, 'ended callback must be no-op'

    obj._ended = False
    obj._gather = None
    obj._rapid_lookahead_cb(12.0)
    assert len(g.calls) == 1, 'released gather callback must be no-op'


def make_supervisor(handler):
    cls = load_class('MBambooRecoverySupervisor')
    s = cls.__new__(cls)
    s.printer = Printer()
    s._original = {'BED_MESH_CALIBRATE': handler}
    s.active = False
    s.owner = 'IDLE'
    s.last_owner = 'NONE'
    s.last_result = 'IDLE'
    s.recovery_count = 0
    s.recovered_total = 0
    s._start_owner_active = lambda: False
    s._status = {'transport_fault_seq': 0, 'preflight_failed_count': 0}
    s._safety_status = lambda: dict(s._status)
    s._recover_calls = 0
    def recover(gcmd):
        s._recover_calls += 1
    s._recover = recover
    return s


def test_gr1_success():
    calls = []
    s = make_supervisor(lambda g: calls.append('run') or 'ok')
    assert s._dispatch('BED_MESH_CALIBRATE', GCmd()) == 'ok'
    assert calls == ['run']
    assert s._recover_calls == 0
    assert s.last_result == 'SUCCESS'
    assert s.active is False and s.owner == 'IDLE'


def test_gr1_non_eddy_error():
    def handler(g):
        raise CmdError('ordinary failure')
    s = make_supervisor(handler)
    try:
        s._dispatch('BED_MESH_CALIBRATE', GCmd())
    except CmdError as e:
        assert 'ordinary failure' in str(e)
    else:
        raise AssertionError('non-Eddy command_error was swallowed')
    assert s._recover_calls == 0
    assert s.last_result == 'NON_EDDY_ERROR'


def test_gr1_recover_then_replay():
    calls = []
    s = None
    def handler(g):
        calls.append('run')
        if len(calls) == 1:
            s._status['transport_fault_seq'] += 1
            raise CmdError('transport fault')
        return 'ok'
    s = make_supervisor(handler)
    g = GCmd()
    assert s._dispatch('BED_MESH_CALIBRATE', g) == 'ok'
    assert calls == ['run', 'run']
    assert s._recover_calls == 1
    assert s.recovery_count == 1
    assert s.recovered_total == 1
    assert s.last_result == 'RECOVERED_SUCCESS'
    assert any('replaying the whole operation once' in x for x in g.info)


def test_gr1_second_fault_stops():
    calls = []
    s = None
    def handler(g):
        calls.append('run')
        s._status['transport_fault_seq'] += 1
        raise CmdError('transport fault')
    s = make_supervisor(handler)
    try:
        s._dispatch('BED_MESH_CALIBRATE', GCmd())
    except CmdError as e:
        assert 'second Eddy/PREARM fault' in str(e)
    else:
        raise AssertionError('second fault was retried or swallowed')
    assert calls == ['run', 'run']
    assert s._recover_calls == 1
    assert s.last_result == 'SECOND_EDDY_FAULT'


def test_gr1_nested_owner_passthrough():
    calls = []
    s = make_supervisor(lambda g: calls.append('run') or 'ok')
    s.active = True
    assert s._dispatch('BED_MESH_CALIBRATE', GCmd()) == 'ok'
    assert calls == ['run']
    assert s._recover_calls == 0

    s.active = False
    s._start_owner_active = lambda: True
    assert s._dispatch('BED_MESH_CALIBRATE', GCmd()) == 'ok'
    assert calls == ['run', 'run']
    assert s._recover_calls == 0


def test_gr1_recovery_failure_is_terminal():
    calls = []
    s = None
    def handler(g):
        calls.append('run')
        s._status['preflight_failed_count'] += 1
        raise CmdError('prearm failed')
    s = make_supervisor(handler)
    def failed_recover(g):
        s._recover_calls += 1
        raise CmdError('recovery failed')
    s._recover = failed_recover
    try:
        s._dispatch('BED_MESH_CALIBRATE', GCmd())
    except CmdError as e:
        assert 'recovery failed' in str(e)
    else:
        raise AssertionError('recovery failure was swallowed')
    assert calls == ['run']
    assert s._recover_calls == 1


def main():
    test_rs1_callback()
    test_gr1_success()
    test_gr1_non_eddy_error()
    test_gr1_recover_then_replay()
    test_gr1_second_fault_stops()
    test_gr1_nested_owner_passthrough()
    test_gr1_recovery_failure_is_terminal()
    print('RC5 combined runtime mock regression: PASS')


if __name__ == '__main__':
    main()
