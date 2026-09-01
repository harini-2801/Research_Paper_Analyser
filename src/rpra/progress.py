"""
Progress Panel (Requirement 12).

Rich-based live progress display.  Can also be used in callback mode
when the UI is not available (e.g., during tests).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from rpra.models import ProgressEvent, PipelineStageStatus

logger = logging.getLogger(__name__)

_STATUS_STYLE = {
    PipelineStageStatus.PENDING: "dim",
    PipelineStageStatus.RUNNING: "yellow",
    PipelineStageStatus.COMPLETE: "green",
    PipelineStageStatus.FAILED: "bold red",
}

_STATUS_ICON = {
    PipelineStageStatus.PENDING: "○",
    PipelineStageStatus.RUNNING: "⟳",
    PipelineStageStatus.COMPLETE: "✓",
    PipelineStageStatus.FAILED: "✗",
}


class ProgressPanel:
    """
    Collects ProgressEvents and renders a live Rich table.
    Also persists events to a structured JSON log file.
    """

    def __init__(self, log_path: str | Path | None = None) -> None:
        self._events: list[ProgressEvent] = []
        self._stage_status: dict[str, PipelineStageStatus] = {}
        self._console = Console()
        self._log_path = Path(log_path) if log_path else None
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Callback (used by pipeline stages)
    # ------------------------------------------------------------------

    def on_event(self, event: ProgressEvent) -> None:
        """Receive and store a progress event."""
        self._events.append(event)
        self._stage_status[event.stage] = event.status
        self._console.print(self._format_event(event))
        self._persist_event(event)

    def callback(self) -> Callable[[ProgressEvent], None]:
        """Return a callable suitable for passing as *on_progress*."""
        return self.on_event

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _format_event(self, event: ProgressEvent) -> Text:
        style = _STATUS_STYLE.get(event.status, "")
        icon = _STATUS_ICON.get(event.status, "?")
        elapsed = f"  [{event.elapsed_seconds:.2f}s]" if event.elapsed_seconds else ""
        text = Text()
        text.append(f"{icon} ", style=style)
        text.append(f"[{event.stage}]", style="bold cyan")
        text.append(f" {event.message}{elapsed}", style=style)
        return text

    def summary_table(self) -> Table:
        table = Table(title="Pipeline Progress", show_lines=True)
        table.add_column("Stage", style="bold cyan")
        table.add_column("Status")
        table.add_column("Last Message")

        stage_latest: dict[str, ProgressEvent] = {}
        for ev in self._events:
            stage_latest[ev.stage] = ev

        for stage, ev in sorted(stage_latest.items()):
            style = _STATUS_STYLE.get(ev.status, "")
            icon = _STATUS_ICON.get(ev.status, "?")
            table.add_row(
                stage,
                Text(f"{icon} {ev.status.value}", style=style),
                ev.message[:80],
            )
        return table

    def print_summary(self) -> None:
        self._console.print(self.summary_table())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_event(self, event: ProgressEvent) -> None:
        if not self._log_path:
            return
        try:
            with self._log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.model_dump(), default=str) + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to write to log: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def completion_percentage(self, total_expected: int) -> float:
        if total_expected == 0:
            return 100.0
        completed = sum(
            1 for e in self._events
            if e.status == PipelineStageStatus.COMPLETE
        )
        return round(100.0 * completed / total_expected, 1)
