from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, int, str)
    finished = Signal()


class TaskWorker(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.function())
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class CancellableWorker(QRunnable):
    """Run a task that cooperatively checks a cancellation flag."""

    def __init__(self, function: Callable[[Callable[[int, int, str], None], Callable[[], bool]], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def report_progress(self, current: int, total: int, label: str) -> None:
        self.signals.progress.emit(current, total, label)

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.function(self.report_progress, self.is_cancelled))
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
