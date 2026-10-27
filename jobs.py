"""Background job runner with a progress dialog.

Network work runs in a small thread pool; everything that touches the Anki
collection is marshalled to the main thread with ``call_on_main`` and its
result (or exception) is handed back, so success/error counts are truthful.
"""

import html
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable

from aqt import mw
from aqt.qt import *

from .theme import tokens
from .ui_common import muted, style_primary

STATUS_STYLE = {
    "ok": ("✔", "#34c759"),
    "skip": ("↷", "#8e8e93"),
    "error": ("✘", "#ff3b30"),
    "info": ("•", "#007aff"),
}


def call_on_main(fn: Callable, timeout: float = 120):
    """Run ``fn`` on the GUI thread and return its result (re-raising errors)."""
    if threading.current_thread() is threading.main_thread():
        return fn()
    done = threading.Event()
    box: dict = {}

    def run():
        try:
            box["result"] = fn()
        except BaseException as e:  # noqa: BLE001 - forwarded to the caller
            box["error"] = e
        finally:
            done.set()

    mw.taskman.run_on_main(run)
    if not done.wait(timeout):
        raise TimeoutError("Anki's main thread did not respond")
    if "error" in box:
        raise box["error"]
    return box.get("result")


class Metric(QWidget):
    def __init__(self, caption: str, color: str = ""):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.value = QLabel("0")
        self.value.setObjectName("metricValue")
        if color:
            self.value.setStyleSheet(f"color: {color};")
        cap = QLabel(caption)
        cap.setObjectName("secondary")
        lay.addWidget(self.value)
        lay.addWidget(cap)

    def set(self, n) -> None:
        self.value.setText(str(n))


class ProgressDialog(QDialog):
    def __init__(self, parent, title: str, total: int):
        super().__init__(parent)
        self.setObjectName("progress")
        self.setWindowTitle(title)
        self.resize(640, 520)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.total = total
        self.counts = {"ok": 0, "skip": 0, "error": 0}
        self.paused = False
        self.cancelled = False
        self.running = True
        self.started = time.time()
        self._build(title)

    def _build(self, title: str):
        t = tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(14)

        self.headline = QLabel(title)
        self.headline.setObjectName("headline")
        layout.addWidget(self.headline)
        self.subline = QLabel()
        muted(self.subline)
        layout.addWidget(self.subline)

        self.bar = QProgressBar()
        self.bar.setMaximum(max(self.total, 1))
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)

        metrics = QHBoxLayout()
        metrics.setSpacing(32)
        self.m_ok = Metric("Done", t["ok"])
        self.m_skip = Metric("Skipped")
        self.m_err = Metric("Failed", t["bad"])
        for m in (self.m_ok, self.m_skip, self.m_err):
            metrics.addWidget(m)
        metrics.addStretch()
        layout.addLayout(metrics)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFrameShape(QFrame.Shape.NoFrame)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPixelSize(12)
        self.log_view.setFont(mono)
        self.log_view.document().setMaximumBlockCount(2000)
        layout.addWidget(self.log_view, 1)

        row = QHBoxLayout()
        row.addStretch()
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        self.close_btn = QPushButton("Done")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.hide()
        style_primary(self.close_btn)
        self.close_btn.setMinimumWidth(120)
        for b in (self.pause_btn, self.cancel_btn, self.close_btn):
            row.addWidget(b)
        layout.addLayout(row)
        self._refresh()

    # -- called on the main thread -------------------------------------------

    def log(self, msg: str, status: str = "info"):
        icon, color = STATUS_STYLE.get(status, STATUS_STYLE["info"])
        self.log_view.append(
            f'<span style="color:{color}">{icon}</span> {html.escape(msg)}'
        )

    def record(self, status: str, msg: str):
        self.counts[status] += 1
        self.log(msg, status)
        self._refresh()

    def _refresh(self):
        done = sum(self.counts.values())
        self.bar.setValue(done)
        elapsed = int(time.time() - self.started)
        if not self.running:
            state = "Cancelled" if self.cancelled else "Finished"
            self.subline.setText(f"{state} · {done} of {self.total} · {elapsed}s")
        elif self.paused:
            self.subline.setText(f"Paused · {done} of {self.total}")
        else:
            eta = ""
            if 0 < done < self.total:
                eta = f" · about {int(elapsed / done * (self.total - done))}s left"
            self.subline.setText(f"Working · {done} of {self.total}{eta}")
        self.m_ok.set(self.counts["ok"])
        self.m_skip.set(self.counts["skip"])
        self.m_err.set(self.counts["error"])

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.setText("Resume" if self.paused else "Pause")
        self.log("Paused" if self.paused else "Resumed")
        self._refresh()

    def cancel(self):
        if not self.running or self.cancelled:
            return
        self.cancelled = True
        self.paused = False
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.log("Cancelling… finishing the items already in flight")

    def finish(self):
        self.running = False
        self.pause_btn.hide()
        self.cancel_btn.hide()
        self.close_btn.show()
        self._refresh()
        self.log("Cancelled" if self.cancelled else "Finished")

    def reject(self):  # Esc / window close
        if self.running:
            self.cancel()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.running:
            self.cancel()
            event.ignore()
        else:
            super().closeEvent(event)


def run_job(
    parent,
    title: str,
    items: Iterable,
    handler: Callable,
    label: Callable = str,
    workers: int = 3,
    on_finished: Callable = None,
):
    """Run ``handler(item, log)`` for every item.

    ``handler`` runs in a worker thread and returns ``(status, message)`` where
    status is "ok", "skip" or "error". Raising an exception counts as an error.
    """
    items = list(items)
    dlg = ProgressDialog(parent, title, len(items))
    dlg.show()
    if not items:
        dlg.log("Nothing to do.")
        dlg.finish()
        return dlg

    def log(msg: str):
        mw.taskman.run_on_main(lambda: dlg.log(msg))

    def work(item):
        if dlg.cancelled:
            return
        while dlg.paused and not dlg.cancelled:
            time.sleep(0.1)
        if dlg.cancelled:
            return
        try:
            status, msg = handler(item, log)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            status, msg = "error", f"{label(item)}: {e}"
        mw.taskman.run_on_main(lambda: dlg.record(status, msg))

    def coordinate():
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            list(pool.map(work, items))

    def done(future):
        try:
            future.result()
        except Exception as e:  # noqa: BLE001
            dlg.log(f"Unexpected error: {e}", "error")
        dlg.finish()
        mw.reset()
        if on_finished:
            on_finished(dlg)

    mw.taskman.run_in_background(coordinate, on_done=done, uses_collection=False)
    return dlg
