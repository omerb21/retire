import faulthandler
import pytest

faulthandler.enable()
faulthandler.dump_traceback_later(90, repeat=False)

raise SystemExit(pytest.main([
    "-q",
    r"tests\test_agent_eyes_stage2.py",
    "-vv",
    "-x",
    "-k",
    "test_emit_event_never_crashes"
]))
