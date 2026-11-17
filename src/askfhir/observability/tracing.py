"""Tracing: OpenTelemetry-semantic spans for the RAG pipeline.

A *trace* is one request; a *span* is one timed stage inside it. Spans
carry the attributes an on-call engineer actually filters by — model
names, candidate counts, scores, abstention decisions — so a slow or
wrong answer can be replayed stage by stage.

Exporters:
- in-memory ring buffer (backs the ``/observability/traces`` endpoint),
- JSONL file (``ASKFHIR_TRACE_FILE``) — one JSON object per span,
  ingestible by any log pipeline,
- OpenTelemetry bridge: when ``opentelemetry-sdk`` is installed and
  ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, spans are mirrored to a real
  OTel tracer so they land in Jaeger / Tempo / Langfuse / Phoenix
  alongside the rest of a production stack.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


def _new_id(n_bytes: int) -> str:
    return uuid.uuid4().hex[: n_bytes * 2]


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start_ns: int
    end_ns: int | None = None
    attributes: dict = field(default_factory=dict)
    status: str = "ok"

    @property
    def duration_ms(self) -> float:
        if self.end_ns is None:
            return 0.0
        return (self.end_ns - self.start_ns) / 1e6

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_unix_ns": self.start_ns,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status,
            "attributes": self.attributes,
        }


class _OtelBridge:
    """Mirrors spans into OpenTelemetry when the SDK is available."""

    def __init__(self) -> None:
        self._tracer = None
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(
                resource=Resource.create({"service.name": "askfhir"})
            )
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer("askfhir")
        except Exception:
            self._tracer = None  # observability must never break the app

    @property
    def active(self) -> bool:
        return self._tracer is not None

    @contextmanager
    def span(self, name: str, attributes: dict) -> Iterator[None]:
        if self._tracer is None:
            yield
            return
        with self._tracer.start_as_current_span(name) as sp:
            for k, v in attributes.items():
                if isinstance(v, (str, int, float, bool)):
                    sp.set_attribute(k, v)
            yield


class Tracer:
    """Thread-safe span recorder with a bounded in-memory history."""

    def __init__(self, max_traces: int = 200, trace_file: str | None = None):
        self._lock = threading.Lock()
        self._spans: list[Span] = []
        self._max_spans = max_traces * 12  # ~12 spans per trace
        self._trace_file = trace_file or os.environ.get("ASKFHIR_TRACE_FILE")
        self._otel = _OtelBridge()
        self._local = threading.local()

    # ------------------------------------------------------------- context
    def _stack(self) -> list[Span]:
        if not hasattr(self._local, "stack"):
            self._local.stack = []
        return self._local.stack

    @contextmanager
    def span(self, name: str, **attributes) -> Iterator[Span]:
        stack = self._stack()
        parent = stack[-1] if stack else None
        span = Span(
            name=name,
            trace_id=parent.trace_id if parent else _new_id(16),
            span_id=_new_id(8),
            parent_span_id=parent.span_id if parent else None,
            start_ns=time.time_ns(),
            attributes=dict(attributes),
        )
        stack.append(span)
        try:
            with self._otel.span(name, span.attributes):
                yield span
        except Exception:
            span.status = "error"
            raise
        finally:
            span.end_ns = time.time_ns()
            stack.pop()
            self._record(span)

    # -------------------------------------------------------------- record
    def _record(self, span: Span) -> None:
        with self._lock:
            self._spans.append(span)
            if len(self._spans) > self._max_spans:
                del self._spans[: len(self._spans) - self._max_spans]
        if self._trace_file:
            try:
                with open(self._trace_file, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(span.to_dict()) + "\n")
            except OSError:
                pass  # tracing must never fail a request

    # --------------------------------------------------------------- query
    def recent_traces(self, limit: int = 20) -> list[dict]:
        """Most recent traces, spans nested under their root span."""
        with self._lock:
            spans = list(self._spans)
        by_trace: dict[str, list[Span]] = {}
        for sp in spans:
            by_trace.setdefault(sp.trace_id, []).append(sp)
        traces = []
        for trace_id, t_spans in list(by_trace.items())[-limit:]:
            root = next((s for s in t_spans if s.parent_span_id is None), None)
            traces.append(
                {
                    "trace_id": trace_id,
                    "root": root.name if root else None,
                    "duration_ms": round(root.duration_ms, 3) if root else None,
                    "attributes": root.attributes if root else {},
                    "spans": [
                        {
                            "name": s.name,
                            "duration_ms": round(s.duration_ms, 3),
                            "status": s.status,
                            "attributes": s.attributes,
                        }
                        for s in sorted(t_spans, key=lambda s: s.start_ns)
                    ],
                }
            )
        return traces[::-1]

    @property
    def otel_active(self) -> bool:
        return self._otel.active

    def trace_file_path(self) -> str | None:
        return str(Path(self._trace_file)) if self._trace_file else None
