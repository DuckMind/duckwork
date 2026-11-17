"""Thread-safe registry for harness-neutral session adapters."""

from __future__ import annotations

import threading

from spectator.core.contracts import (
    AdapterConflictError,
    SessionAdapter,
    SessionDescriptor,
    SessionNotFoundError,
)


class AdapterRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._adapters: dict[str, SessionAdapter] = {}

    def register(self, adapter: SessionAdapter, *, replace: bool = False) -> SessionDescriptor:
        if not isinstance(adapter, SessionAdapter):
            raise TypeError("adapter does not satisfy SessionAdapter")
        session_id = adapter.descriptor.session_id
        with self._lock:
            if session_id in self._adapters and not replace:
                raise AdapterConflictError(f"session already registered: {session_id}")
            self._adapters[session_id] = adapter
        return adapter.descriptor

    def get(self, session_id: str) -> SessionAdapter:
        with self._lock:
            adapter = self._adapters.get(session_id)
        if adapter is None:
            raise SessionNotFoundError(session_id)
        return adapter

    def unregister(self, session_id: str) -> None:
        with self._lock:
            self._adapters.pop(session_id, None)

    def list_descriptors(self) -> tuple[SessionDescriptor, ...]:
        with self._lock:
            descriptors = [adapter.descriptor for adapter in self._adapters.values()]
        return tuple(sorted(descriptors, key=lambda item: item.session_id))
