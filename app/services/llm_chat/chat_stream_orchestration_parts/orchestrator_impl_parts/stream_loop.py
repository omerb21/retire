import sys as _sys

from . import stream_loop_main as _impl

_sys.modules[__name__] = _impl
