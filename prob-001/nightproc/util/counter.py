"""Thread-safe atomic counter."""

import threading


class AtomicCounter:
    def __init__(self, initial=0):
        self._value = initial
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._value += 1
            return self._value

    @property
    def value(self):
        # int reads are atomic in CPython but we keep this consistent
        with self._lock:
            return self._value

    def __repr__(self):
        return f"AtomicCounter({self._value})"
