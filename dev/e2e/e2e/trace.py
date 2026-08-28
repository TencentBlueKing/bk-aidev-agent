from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator


@dataclass
class ApiCall:
    sequence: int
    source: str
    module: str
    case: str
    scenario_id: str
    chain_id: str
    method: str
    url: str
    request_headers: dict[str, str]
    request_body: Any
    status: int | None = None
    response_headers: dict[str, str] | None = None
    response_body: Any = None
    duration_ms: int = 0
    error: str = ""


class ApiTraceRecorder:
    """Collect complete HTTP exchanges across runner and mock-server threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[ApiCall] = []
        self._current_case = ("runner", "应用启动与基础设施", "runner.infrastructure")
        self._active_chains: dict[str, list[str]] = {}
        self._sequence = 0

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
            self._current_case = ("runner", "应用启动与基础设施", "runner.infrastructure")
            self._active_chains.clear()
            self._sequence = 0

    @contextmanager
    def case(self, module: str, name: str, scenario_id: str) -> Iterator[None]:
        with self._lock:
            previous = self._current_case
            self._current_case = (module, name, scenario_id)
        try:
            yield
        finally:
            with self._lock:
                self._current_case = previous

    def start_call(
        self,
        *,
        source: str,
        method: str,
        url: str,
        request_headers: dict[str, str] | None = None,
        request_body: Any = None,
    ) -> ApiCall:
        with self._lock:
            self._sequence += 1
            module, case, scenario_id = self._current_case
            active_chains = self._active_chains.get(scenario_id, [])
            if source == "test-runner":
                chain_id = f"request-{self._sequence:04d}"
                self._active_chains.setdefault(scenario_id, []).append(chain_id)
            elif active_chains:
                chain_id = active_chains[-1]
            else:
                chain_id = f"standalone-{self._sequence:04d}"
            call = ApiCall(
                sequence=self._sequence,
                source=source,
                module=module,
                case=case,
                scenario_id=scenario_id,
                chain_id=chain_id,
                method=method.upper(),
                url=url,
                request_headers=dict(request_headers or {}),
                request_body=request_body,
            )
            self._calls.append(call)
            return call

    def finish_call(
        self,
        call: ApiCall,
        *,
        status: int | None = None,
        response_headers: dict[str, str] | None = None,
        response_body: Any = None,
        duration_ms: int = 0,
        error: str = "",
    ) -> None:
        with self._lock:
            call.status = status
            call.response_headers = dict(response_headers or {})
            call.response_body = response_body
            call.duration_ms = duration_ms
            call.error = error
            if call.source == "test-runner":
                active_chains = self._active_chains.get(call.scenario_id, [])
                if call.chain_id in active_chains:
                    active_chains.remove(call.chain_id)
                if not active_chains:
                    self._active_chains.pop(call.scenario_id, None)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(call) for call in self._calls]


API_TRACE = ApiTraceRecorder()
