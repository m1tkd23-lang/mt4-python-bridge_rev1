# src\explore_gui_app\views\backtest_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backtest.aggregate_stats import AggregateStats
from backtest.service import BacktestRunArtifacts
from explore_gui_app.constants import AVAILABLE_STRATEGIES
from mt4_bridge.strategies.risk_config import (
    resolve_lane_risk_pips,
    resolve_strategy_risk_pips,
)


_KPI_FIELDS: list[tuple[str, str]] = [
    ("total_pips", "Total pips"),
    ("win_rate_percent", "Win rate"),
    ("profit_factor", "Profit factor"),
    ("max_drawdown_pips", "Max DD pips"),
    ("trades", "Trades"),
    ("verdict", "Verdict"),
]

_DETAIL_FIELDS: list[tuple[str, str]] = [
    ("wins", "Wins"),
    ("losses", "Losses"),
    ("average_pips", "Avg pips"),
    ("max_consecutive_wins", "Max consec wins"),
    ("max_consecutive_losses", "Max consec losses"),
]

_SUMMARY_KEYS: tuple[str, ...] = tuple(
    key for key, _ in (*_KPI_FIELDS, *_DETAIL_FIELDS)
)


class BacktestPanel(QWidget):
    """Minimal Backtest 単発 panel for the explore_gui タブ B.

    Runs ``backtest.service.run_backtest`` (single CSV) or
    ``backtest.service.run_all_months`` (CSV dir) for the most recently
    accepted exploration candidate (strategy + param overrides) and
    displays an 11-field summary (6 KPI + 5 details).

    Behavior intentionally duplicates the backtest_gui_app InputPanel /
    SummaryPanel field set per TASK-0131 / TASK-0136 / TASK-0139 (重複許容).
    Common-widget extraction is deferred to T-D.
    """

    MODE_SINGLE = "single"
    MODE_ALL_MONTHS = "all_months"

    run_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._summary_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 上段: 候補情報 | データソース | マーケット設定 を横並びにして縦空間を節約
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self._build_candidate_section(), 2)
        top_row.addWidget(self._build_source_section(), 3)
        top_row.addWidget(self._build_market_section(), 3)
        layout.addLayout(top_row)

        # アクション + KPI strip
        layout.addWidget(self._build_action_section())
        layout.addWidget(self._build_kpi_strip())

        # 下段: Details (左) + Notes/Log (右) を Splitter で可変分割
        bottom_split = QSplitter(Qt.Horizontal)
        bottom_split.addWidget(self._build_details_section())
        bottom_split.addWidget(self._build_notes_section())
        bottom_split.setStretchFactor(0, 1)
        bottom_split.setStretchFactor(1, 2)
        bottom_split.setChildrenCollapsible(False)
        layout.addWidget(bottom_split, 1)

        self.set_candidate(strategy_name=None, param_overrides=None)
        self.clear_summary()

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_candidate_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        box.setMinimumWidth(240)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        title = QLabel("<b>Strategy 選択 / Explore 候補</b>")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Strategy コンボ: 手動で戦略選択できるようにする (Explore 未実行でも BT 可)。
        # Explore 側の set_candidate() が呼ばれるとここと同期する。
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(AVAILABLE_STRATEGIES)
        self.strategy_combo.currentTextChanged.connect(self._on_strategy_combo_changed)

        self.params_value_label = QLabel("(default)")
        self.params_value_label.setWordWrap(True)
        self.params_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        form.addRow("Strategy:", self.strategy_combo)
        form.addRow("Param overrides:", self.params_value_label)
        layout.addLayout(form)

        hint = QLabel(
            "Strategy はコンボで直接選択できます。Explore を実行すると "
            "候補戦術と param overrides が自動で反映されます。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 10px; color: #9aa;")
        layout.addWidget(hint)

        layout.addStretch(1)

        return box

    def _build_source_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        box.setMinimumWidth(320)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        layout.addWidget(QLabel("<b>Run mode / Data source</b>"))

        self._mode_group = QButtonGroup(self)
        self._radio_single = QRadioButton("Single CSV")
        self._radio_all = QRadioButton("All months in CSV Dir")
        self._radio_single.setChecked(True)
        self._mode_group.addButton(self._radio_single)
        self._mode_group.addButton(self._radio_all)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self._radio_single)
        mode_row.addWidget(self._radio_all)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        # 連結 BT: All months 選択時のみ効く。
        # 有効時は全 CSV を時系列結合して 1 本で BT し、trade.entry_time で
        # 月別集計。月跨ぎのウォームアップ不連続/強制決済を排除し本番相当の値になる。
        self._connected_checkbox = QCheckBox(
            "Connect CSVs before backtest (contiguous run; All months mode only)"
        )
        self._connected_checkbox.setChecked(False)
        self._radio_single.toggled.connect(self._on_mode_toggled)
        self._radio_all.toggled.connect(self._on_mode_toggled)
        layout.addWidget(self._connected_checkbox)
        self._on_mode_toggled()

        single_row = QHBoxLayout()
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Single CSV path")
        single_browse = QPushButton("Browse...")
        single_browse.clicked.connect(self._browse_csv)
        single_row.addWidget(QLabel("CSV File:"))
        single_row.addWidget(self.csv_path_edit, 1)
        single_row.addWidget(single_browse)
        layout.addLayout(single_row)

        dir_row = QHBoxLayout()
        self.csv_dir_edit = QLineEdit()
        self.csv_dir_edit.setPlaceholderText("CSV directory (used in All months mode)")
        dir_browse = QPushButton("Browse...")
        dir_browse.clicked.connect(self._browse_csv_dir)
        dir_row.addWidget(QLabel("CSV Dir:"))
        dir_row.addWidget(self.csv_dir_edit, 1)
        dir_row.addWidget(dir_browse)
        layout.addLayout(dir_row)

        return box

    def _build_market_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        box.setMinimumWidth(260)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        layout.addWidget(QLabel("<b>Market parameters</b>"))

        self.symbol_edit = QLineEdit("BACKTEST")
        self.timeframe_edit = QLineEdit("M1")
        self.pip_size_edit = QLineEdit("0.01")
        self.sl_pips_edit = QLineEdit("10")
        self.tp_pips_edit = QLineEdit("10")

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        form.addRow("Symbol", self.symbol_edit)
        form.addRow("Timeframe", self.timeframe_edit)
        form.addRow("Pip size", self.pip_size_edit)
        form.addRow("SL pips", self.sl_pips_edit)
        form.addRow("TP pips", self.tp_pips_edit)
        layout.addLayout(form)

        # 戦術ファイル側 (SL_PIPS/TP_PIPS 定数) の実効値を read-only で表示。
        # 上記 SL/TP 入力欄は simulator への fallback のみで、戦術定数が
        # 定義されていればそちらが優先される (mt4_bridge.strategies.risk_config)。
        self._strategy_risk_label = QLabel("Strategy SL/TP: (no candidate)")
        self._strategy_risk_label.setWordWrap(True)
        self._strategy_risk_label.setStyleSheet(
            "font-size: 11px; color: #9aa; padding-top: 4px;"
        )
        self._strategy_risk_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._strategy_risk_label)
        layout.addStretch(1)

        return box

    def _build_action_section(self) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.run_button = QPushButton("Run backtest")
        self.run_button.setMinimumHeight(32)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        self.run_button.clicked.connect(self.run_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)

        # 進捗バー。All months (connected=False) では N ヶ月中 i ヶ月を定量表示。
        # Single / connected モードは indeterminate (marquee) で稼働中であることを示す。
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumWidth(240)
        self.progress_bar.setVisible(False)

        layout.addWidget(self.run_button)
        layout.addWidget(self.stop_button)
        layout.addSpacing(8)
        layout.addWidget(self.progress_bar, 1)
        return box

    def _build_kpi_strip(self) -> QWidget:
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        for key, title in _KPI_FIELDS:
            strip_layout.addWidget(self._build_kpi_card(key, title), 1)
        return strip

    def _build_kpi_card(self, key: str, title: str) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setMinimumWidth(96)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)

        title_label = QLabel(title.upper())
        title_label.setStyleSheet("font-size: 10px; color: gray;")

        value_label = QLabel("-")
        value_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_label.setWordWrap(True)
        self._summary_labels[key] = value_label

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card

    def _build_details_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        box.setMinimumWidth(220)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(QLabel("<b>Details</b>"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(3)
        for row, (key, label_text) in enumerate(_DETAIL_FIELDS):
            label = QLabel(label_text)
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setWordWrap(True)
            self._summary_labels[key] = value
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
        layout.addLayout(grid)
        layout.addStretch(1)
        return box

    def _build_notes_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        box.setMinimumWidth(280)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(QLabel("<b>Status / Notes</b>"))

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMinimumHeight(80)
        layout.addWidget(self.notes_text)
        return box

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV Files (*.csv)"
        )
        if path:
            self.csv_path_edit.setText(path)

    def _browse_csv_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select CSV directory")
        if path:
            self.csv_dir_edit.setText(path)

    # ------------------------------------------------------------------
    # Public getters / setters
    # ------------------------------------------------------------------

    def get_mode(self) -> str:
        if self._radio_all.isChecked():
            return self.MODE_ALL_MONTHS
        return self.MODE_SINGLE

    def set_mode(self, mode: str) -> None:
        if mode == self.MODE_ALL_MONTHS:
            self._radio_all.setChecked(True)
        else:
            self._radio_single.setChecked(True)
        self._on_mode_toggled()

    def _on_mode_toggled(self) -> None:
        """All months モードのときだけ連結チェックボックスを有効化。"""
        all_mode = self._radio_all.isChecked()
        self._connected_checkbox.setEnabled(all_mode)
        if not all_mode:
            self._connected_checkbox.setChecked(False)

    def get_connected(self) -> bool:
        return (
            self._radio_all.isChecked()
            and self._connected_checkbox.isChecked()
        )

    def get_csv_path(self) -> str:
        return self.csv_path_edit.text().strip()

    def set_csv_path(self, path: str | None) -> None:
        self.csv_path_edit.setText(path or "")

    def get_csv_dir(self) -> str:
        return self.csv_dir_edit.text().strip()

    def set_csv_dir(self, path: str | None) -> None:
        self.csv_dir_edit.setText(path or "")

    def get_symbol(self) -> str:
        return self.symbol_edit.text().strip() or "BACKTEST"

    def get_timeframe(self) -> str:
        return self.timeframe_edit.text().strip() or "M1"

    def get_pip_size(self) -> float:
        return float(self.pip_size_edit.text().strip() or "0.01")

    def get_sl_pips(self) -> float:
        return float(self.sl_pips_edit.text().strip() or "10")

    def get_tp_pips(self) -> float:
        return float(self.tp_pips_edit.text().strip() or "10")

    def set_market_defaults(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        pip_size: float | None = None,
        sl_pips: float | None = None,
        tp_pips: float | None = None,
    ) -> None:
        if symbol is not None:
            self.symbol_edit.setText(symbol)
        if timeframe is not None:
            self.timeframe_edit.setText(timeframe)
        if pip_size is not None:
            self.pip_size_edit.setText(str(pip_size))
        if sl_pips is not None:
            self.sl_pips_edit.setText(str(sl_pips))
        if tp_pips is not None:
            self.tp_pips_edit.setText(str(tp_pips))

    def set_candidate(
        self,
        *,
        strategy_name: str | None,
        param_overrides: dict[str, float] | None,
    ) -> None:
        """Explore 側からの候補反映、または手動 combo 変更時の内部状態更新。

        strategy_name が AVAILABLE_STRATEGIES に含まれていれば combo を
        その値に合わせて同期する (signal は blockSignals で抑止)。
        None なら combo は現状維持 (= 手動選択や初期値を尊重)。
        """
        self._candidate_overrides = (
            dict(param_overrides) if param_overrides else None
        )

        if strategy_name:
            idx = self.strategy_combo.findText(strategy_name)
            if idx >= 0:
                self.strategy_combo.blockSignals(True)
                self.strategy_combo.setCurrentIndex(idx)
                self.strategy_combo.blockSignals(False)
                self._candidate_strategy = strategy_name
            else:
                # combo に無い戦術名: combo は現値維持、内部も combo 値に合わせる
                self._candidate_strategy = self.strategy_combo.currentText().strip() or None
        else:
            # 現在の combo 値を候補として保持 (初期化時 None でも combo デフォルトが効く)
            self._candidate_strategy = self.strategy_combo.currentText().strip() or None

        if not param_overrides:
            self.params_value_label.setText("(default)")
        else:
            lines = [
                f"{k.split('::')[-1]} = {v}"
                for k, v in sorted(param_overrides.items())
            ]
            self.params_value_label.setText("\n".join(lines))

        self._refresh_strategy_risk_label(self._candidate_strategy)

    def _on_strategy_combo_changed(self, name: str) -> None:
        """ユーザが combo を手動変更した時: 候補戦略を更新し overrides をリセット。

        Explore から set_candidate() 経由で combo を同期する場合は
        blockSignals 済みなのでこのハンドラは呼ばれない。
        """
        self._candidate_strategy = name.strip() or None
        self._candidate_overrides = None
        self.params_value_label.setText("(default)")
        self._refresh_strategy_risk_label(self._candidate_strategy)

    def _refresh_strategy_risk_label(self, strategy_name: str | None) -> None:
        """戦術ファイル側の SL_PIPS/TP_PIPS 実効値をラベルに反映する。

        combo 戦術 (LANE_STRATEGY_MAP を持つ) は range/trend lane それぞれの値
        を両方表示する。単一戦術なら strategy 全体の SL/TP を 1 行で表示。
        戦術が SL_PIPS/TP_PIPS を持たなければ "(not defined)" を出し、
        simulator の SL/TP 入力欄がそのまま使われる旨を示す。
        """
        if not strategy_name:
            self._strategy_risk_label.setText("Strategy SL/TP: (no candidate)")
            return

        range_sl, range_tp = resolve_lane_risk_pips(strategy_name, "range")
        trend_sl, trend_tp = resolve_lane_risk_pips(strategy_name, "trend")
        plain_sl, plain_tp = resolve_strategy_risk_pips(strategy_name)

        def fmt(sl: float | None, tp: float | None) -> str:
            if sl is None or tp is None:
                return "(not defined)"
            return f"SL={sl:g} / TP={tp:g}"

        # combo 判定: range と trend で異なる値になっている場合は lane 別表示
        is_combo_like = (range_sl, range_tp) != (trend_sl, trend_tp)
        if is_combo_like:
            text = (
                f"Strategy SL/TP (combo, lane-specific, from {strategy_name} constants):\n"
                f"  range lane: {fmt(range_sl, range_tp)}\n"
                f"  trend lane: {fmt(trend_sl, trend_tp)}\n"
                f"  (Market SL/TP inputs above are fallback only.)"
            )
        elif plain_sl is not None and plain_tp is not None:
            text = (
                f"Strategy SL/TP (from {strategy_name} constants): {fmt(plain_sl, plain_tp)}\n"
                f"  (Market SL/TP inputs above are fallback only.)"
            )
        else:
            text = (
                f"Strategy SL/TP ({strategy_name}): (not defined)\n"
                f"  Market SL/TP inputs above will be used."
            )
        self._strategy_risk_label.setText(text)

    def get_candidate_strategy(self) -> str | None:
        # combo の現在値を正とする (Explore が set_candidate しても combo に反映済)
        text = self.strategy_combo.currentText().strip()
        return text or None

    def get_candidate_overrides(self) -> dict[str, float] | None:
        overrides = getattr(self, "_candidate_overrides", None)
        return dict(overrides) if overrides else None

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        if running:
            self.begin_progress_indeterminate()
        else:
            self.hide_progress()

    # ------------------------------------------------------------------
    # Progress API
    # ------------------------------------------------------------------

    def begin_progress_indeterminate(self) -> None:
        """開始時: total 不明なので indeterminate 表示。"""
        self.progress_bar.setRange(0, 0)  # marquee 動作
        self.progress_bar.setFormat("running...")
        self.progress_bar.setVisible(True)

    def set_progress(self, current: int, total: int) -> None:
        """月別 BT 等、total が判るケース用。total<=0 は indeterminate へ戻す。"""
        if total <= 0:
            self.begin_progress_indeterminate()
            return
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total} ({(current*100)//max(total,1)}%)")
        self.progress_bar.setVisible(True)

    def hide_progress(self) -> None:
        self.progress_bar.setVisible(False)
        self.progress_bar.reset()

    def set_status(self, text: str) -> None:
        self.notes_text.setPlainText(text)

    def append_log(self, text: str) -> None:
        self.notes_text.append(text)

    # ------------------------------------------------------------------
    # Summary display
    # ------------------------------------------------------------------

    def clear_summary(self) -> None:
        for key in _SUMMARY_KEYS:
            self._summary_labels[key].setText("-")

    def show_single_artifacts(self, artifacts: BacktestRunArtifacts) -> None:
        summary = artifacts.summary
        labels = self._summary_labels
        labels["total_pips"].setText(f"{summary.total_pips:.2f}")
        labels["win_rate_percent"].setText(f"{summary.win_rate_percent:.2f}%")
        labels["profit_factor"].setText(
            self._format_profit_factor(summary.profit_factor)
        )
        labels["max_drawdown_pips"].setText(f"{summary.max_drawdown_pips:.2f}")
        labels["trades"].setText(str(summary.trades))
        labels["verdict"].setText(summary.verdict or "-")
        labels["wins"].setText(str(summary.wins))
        labels["losses"].setText(str(summary.losses))
        labels["average_pips"].setText(f"{summary.average_pips:.2f}")
        labels["max_consecutive_wins"].setText(str(summary.max_consecutive_wins))
        labels["max_consecutive_losses"].setText(
            str(summary.max_consecutive_losses)
        )

    def show_aggregate(self, aggregate: AggregateStats) -> None:
        labels = self._summary_labels
        labels["total_pips"].setText(f"{aggregate.total_pips:.2f}")
        labels["win_rate_percent"].setText(
            f"{aggregate.overall_win_rate:.2f}%"
        )
        labels["profit_factor"].setText(
            self._format_profit_factor(aggregate.overall_profit_factor)
        )
        labels["max_drawdown_pips"].setText(
            f"{aggregate.max_drawdown_pips:.2f}"
        )
        labels["trades"].setText(str(aggregate.total_trades))
        labels["verdict"].setText(f"{aggregate.month_count} months")
        labels["wins"].setText(str(aggregate.total_wins))
        labels["losses"].setText(str(aggregate.total_losses))
        labels["average_pips"].setText(
            f"{aggregate.average_pips_per_month:.2f}"
        )
        labels["max_consecutive_wins"].setText("-")
        labels["max_consecutive_losses"].setText(
            f"deficit streak: {aggregate.max_consecutive_deficit_months}"
        )

    @staticmethod
    def _format_profit_factor(value: float | None) -> str:
        if value is None:
            return "None"
        if value == float("inf"):
            return "inf"
        return f"{value:.2f}"
