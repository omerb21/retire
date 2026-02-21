import warnings
from contextlib import contextmanager

from sqlalchemy.exc import SAWarning


@contextmanager
def capture_identity_map_sawarnings():
    messages: list[str] = []
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always", category=SAWarning)
        yield messages

    for w in recorded:
        if issubclass(w.category, SAWarning):
            messages.append(str(w.message))
