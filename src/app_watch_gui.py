# src/app_watch_gui.py
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

import app_watch
from mt4_bridge.app_config import AppConfigError, load_app_config


MAX_LOG_BLOCKS = 1000


class WatchWorker(QObject):
    log_signal = Signal(str)
    status_signal = Signal(str)
    finished_signal = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        self.status_signal.emit("running")
        return_code = app_watch.run_watch(
            stop_event=self._stop_event,
            output_func=self.log_signal.emit,
        )
        self.status_signal.emit("stopped")
        self.finished_signal.emit(return_code)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MT4 Python Bridge Watch")
        self.resize(980, 720)

        self._thread: QThread | None = None
        self._worker: WatchWorker | None = None

        self._strategy_name, self._config_path_text = self._load_config_info()

        self._status_label = QLabel("Status: stopped")
        self._strategy_label = QLabel(f"Strategy: {self._strategy_name}")
        self._config_path_label = QLabel(f"Config: {self._config_path_text}")

        self._start_button = QPushButton("開始")
        self._stop_button = QPushButton("停止")
        self._stop_button.setEnabled(False)
        self._clear_button = QPushButton("ログクリア")

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(MAX_LOG_BLOCKS)

        self._start_button.clicked.connect(self._start_watch)
        self._stop_button.clicked.connect(self._stop_watch)
        self._clear_button.clicked.connect(self._log_view.clear)

        button_row = QHBoxLayout()
        button_row.addWidget(self._start_button)
        button_row.addWidget(self._stop_button)
        button_row.addWidget(self._clear_button)
        button_row.addStretch(1)

        info_row_1 = QHBoxLayout()
        info_row_1.addWidget(self._status_label)
        info_row_1.addSpacing(24)
        info_row_1.addWidget(self._strategy_label)
        info_row_1.addStretch(1)

        info_row_2 = QHBoxLayout()
        info_row_2.addWidget(self._config_path_label)
        info_row_2.addStretch(1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(info_row_1)
        layout.addLayout(info_row_2)
        layout.addLayout(button_row)
        layout.addWidget(self._log_view)

        self.setCentralWidget(central)

    def _load_config_info(self) -> tuple[str, str]:
        try:
            config = load_app_config()
            config_path = self._infer_config_path()
            return config.signal.strategy_name, str(config_path)
        except AppConfigError as exc:
            return f"(config load error: {exc})", "(unresolved)"
        except Exception as exc:
            return f"(unexpected error: {exc})", "(unresolved)"

    def _infer_config_path(self) -> Path:
        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir / "config" / "app.yaml"
        if candidate.exists():
            return candidate

        script_dir = Path(__file__).resolve().parents[1]
        return script_dir / "config" / "app.yaml"

    def _append_log(self, message: str) -> None:
        self._log_view.appendPlainText(message)
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._log_view.setTextCursor(cursor)
        self._log_view.ensureCursorVisible()

    def _set_running_ui(self, running: bool) -> None:
        self._start_button.setEnabled(not running)
        self._stop_button.setEnabled(running)
        self._status_label.setText(f"Status: {'running' if running else 'stopped'}")

    def _start_watch(self) -> None:
        if self._thread is not None:
            return

        self._thread = QThread(self)
        self._worker = WatchWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.status_signal.connect(self._on_worker_status)
        self._worker.finished_signal.connect(self._on_worker_finished)
        self._worker.finished_signal.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)

        self._append_log("=== watch start requested ===")
        self._set_running_ui(True)
        self._thread.start()

    def _stop_watch(self) -> None:
        if self._worker is None:
            return

        self._append_log("=== stop requested ===")
        self._worker.request_stop()
        self._stop_button.setEnabled(False)

    def _on_worker_status(self, status: str) -> None:
        self._status_label.setText(f"Status: {status}")

    def _on_worker_finished(self, return_code: int) -> None:
        self._append_log(f"=== watch finished (return_code={return_code}) ===")
        self._set_running_ui(False)

    def _cleanup_worker(self) -> None:
        self._thread = None
        self._worker = None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker is not None:
            reply = QMessageBox.question(
                self,
                "確認",
                "watch が実行中です。停止して終了しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return

            self._worker.request_stop()
            if self._thread is not None:
                self._thread.quit()
                self._thread.wait(3000)

        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())