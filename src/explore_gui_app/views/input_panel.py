# src\explore_gui_app\views\input_panel.py
from __future__ import annotations

import glob
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backtest.exploration_loop import BOLLINGER_PARAM_VARIATION_RANGES
from backtest_gui_app.widgets.collapsible_section import CollapsibleSection
from explore_gui_app.views.parameter_dialog import ParameterDialog

_AVAILABLE_STRATEGIES = [
    "bollinger_range_v4_4",
    "bollinger_range_v4_4_tuned_a",
    "bollinger_trend_B",
]


class ExploreInputPanel(QWidget):
    """Input panel for bollinger exploration configuration."""

    run_requested = Signal()
    refine_requested = Signal()
    confirm_all_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._param_ranges: dict[str, tuple[float, float, float]] = dict(
            BOLLINGER_PARAM_VARIATION_RANGES.get(_AVAILABLE_STRATEGIES[0], {})
        )
        self._base_param_overrides: dict[str, float] | None = None
        self._seed_param_overrides_list: list[dict[str, float]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        strategy_section = self._build_strategy_section()
        csv_section = self._build_csv_section()
        loop_section = self._build_loop_config_section()
        param_section = self._build_param_section()

        layout.addWidget(strategy_section)
        layout.addWidget(csv_section)
        layout.addWidget(loop_section)
        layout.addWidget(param_section)

        btn_row = QHBoxLayout()
        self.run_button = QPushButton("Run Exploration")
        self.refine_button = QPushButton("Refine From Trends")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        btn_row.addWidget(self.run_button)
        btn_row.addWidget(self.refine_button)
        btn_row.addWidget(self.stop_button)
        layout.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        self.confirm_all_button = QPushButton("全期間で確認する (Phase 2)")
        self.confirm_all_button.setEnabled(False)
        self.confirm_all_button.setToolTip(
            "Phase 1 の上位候補を CSV Dir 内の全 CSV で再評価します"
        )
        btn_row2.addWidget(self.confirm_all_button)
        btn_row2.addStretch(1)
        layout.addLayout(btn_row2)

        layout.addStretch(1)

        self.run_button.clicked.connect(self.run_requested.emit)
        self.refine_button.clicked.connect(self.refine_requested.emit)
        self.confirm_all_button.clicked.connect(self.confirm_all_requested.emit)
        self._refresh_param_summary()

    # ------------------------------------------------------------------
    # Strategy section
    # ------------------------------------------------------------------

    def _build_strategy_section(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(4, 4, 4, 4)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(_AVAILABLE_STRATEGIES)
        self.strategy_combo.currentTextChanged.connect(self._on_strategy_changed)
        form.addRow("Strategy:", self.strategy_combo)

        return CollapsibleSection("Strategy Selection", box, expanded=True)

    def _on_strategy_changed(self, strategy_name: str) -> None:
        self._param_ranges = dict(
            BOLLINGER_PARAM_VARIATION_RANGES.get(strategy_name, {})
        )
        self._base_param_overrides = None
        self._seed_param_overrides_list = []
        self._param_section.setTitle(f"Exploration Parameters ({strategy_name})")
        self._refresh_param_summary()

    # ------------------------------------------------------------------
    # CSV section
    # ------------------------------------------------------------------

    # CSV selection mode constants
    MODE_SELECTED_3_MONTHS = "selected_3_months"
    MODE_ALL_CSVS = "all_csvs"
    MODE_CUSTOM = "custom"

    def _build_csv_section(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # --- CSV File row ---
        form_top = QFormLayout()
        csv_row = QHBoxLayout()
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Single CSV file for primary evaluation")
        browse_csv = QPushButton("Browse...")
        browse_csv.clicked.connect(self._browse_csv)
        csv_row.addWidget(self.csv_path_edit, 1)
        csv_row.addWidget(browse_csv)
        form_top.addRow("CSV File:", csv_row)

        # --- CSV Dir row ---
        dir_row = QHBoxLayout()
        self.csv_dir_edit = QLineEdit()
        self.csv_dir_edit.setPlaceholderText(
            "Directory with monthly CSVs (optional, for cross-month eval)"
        )
        browse_dir = QPushButton("Browse...")
        browse_dir.clicked.connect(self._browse_csv_dir)
        dir_row.addWidget(self.csv_dir_edit, 1)
        dir_row.addWidget(browse_dir)
        form_top.addRow("CSV Dir:", dir_row)
        layout.addLayout(form_top)

        # --- CSV selection mode radio buttons ---
        mode_label = QLabel("CSV Selection Mode:")
        layout.addWidget(mode_label)

        self._csv_mode_group = QButtonGroup(self)
        self._radio_3months = QRadioButton("Selected 3 months (latest 3 CSVs)")
        self._radio_all = QRadioButton("All CSVs in folder")
        self._radio_custom = QRadioButton("Custom selection")
        self._radio_3months.setChecked(True)

        self._csv_mode_group.addButton(self._radio_3months)
        self._csv_mode_group.addButton(self._radio_all)
        self._csv_mode_group.addButton(self._radio_custom)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self._radio_3months)
        mode_row.addWidget(self._radio_all)
        mode_row.addWidget(self._radio_custom)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        # --- CSV selection info label ---
        self._csv_selection_info = QLabel("")
        self._csv_selection_info.setWordWrap(True)
        layout.addWidget(self._csv_selection_info)

        # --- Custom selection checklist (scroll area) ---
        self._custom_scroll = QScrollArea()
        self._custom_scroll.setWidgetResizable(True)
        self._custom_scroll.setMaximumHeight(150)
        self._custom_check_container = QWidget()
        self._custom_check_layout = QVBoxLayout(self._custom_check_container)
        self._custom_check_layout.setContentsMargins(4, 4, 4, 4)
        self._custom_check_layout.setSpacing(2)
        self._custom_scroll.setWidget(self._custom_check_container)
        self._custom_scroll.setVisible(False)
        layout.addWidget(self._custom_scroll)

        # Store checkbox references
        self._csv_checkboxes: list[QCheckBox] = []

        # Disable mode selection initially (enabled when CSV Dir is set)
        self._set_csv_mode_enabled(False)

        # Connect signals
        self.csv_dir_edit.textChanged.connect(self._on_csv_dir_changed)
        self._csv_mode_group.buttonClicked.connect(self._on_csv_mode_changed)

        return CollapsibleSection("Data Source", box, expanded=True)

    def _set_csv_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable CSV selection mode radio buttons."""
        self._radio_3months.setEnabled(enabled)
        self._radio_all.setEnabled(enabled)
        self._radio_custom.setEnabled(enabled)
        if not enabled:
            self._csv_selection_info.setText("")
            self._custom_scroll.setVisible(False)

    def _scan_csv_dir(self, dir_path: str) -> list[str]:
        """Scan a directory for CSV files, return sorted list of absolute paths."""
        if not dir_path or not os.path.isdir(dir_path):
            return []
        pattern = os.path.join(dir_path, "*.csv")
        files = sorted(glob.glob(pattern))
        return files

    def _on_csv_dir_changed(self, text: str) -> None:
        """Called when CSV Dir text changes."""
        dir_path = text.strip()
        has_dir = bool(dir_path) and os.path.isdir(dir_path)
        self._set_csv_mode_enabled(has_dir)
        if has_dir:
            self._refresh_csv_selection()

    def _on_csv_mode_changed(self) -> None:
        """Called when CSV selection mode radio button changes."""
        self._refresh_csv_selection()

    def _refresh_csv_selection(self) -> None:
        """Refresh CSV selection info and custom checklist based on current mode."""
        dir_path = self.csv_dir_edit.text().strip()
        csv_files = self._scan_csv_dir(dir_path)
        mode = self.get_csv_selection_mode()

        # Update custom checklist visibility
        self._custom_scroll.setVisible(mode == self.MODE_CUSTOM)

        if not csv_files:
            self._csv_selection_info.setText("No CSV files found in directory.")
            self._rebuild_custom_checklist([])
            return

        if mode == self.MODE_SELECTED_3_MONTHS:
            selected = csv_files[-3:] if len(csv_files) >= 3 else csv_files
            names = [os.path.basename(f) for f in selected]
            self._csv_selection_info.setText(
                f"Selected {len(selected)} of {len(csv_files)} CSVs: "
                + ", ".join(names)
            )
        elif mode == self.MODE_ALL_CSVS:
            self._csv_selection_info.setText(
                f"All {len(csv_files)} CSVs in folder will be used."
            )
        elif mode == self.MODE_CUSTOM:
            self._rebuild_custom_checklist(csv_files)
            checked = sum(1 for cb in self._csv_checkboxes if cb.isChecked())
            self._csv_selection_info.setText(
                f"{checked} of {len(csv_files)} CSVs selected."
            )

    def _rebuild_custom_checklist(self, csv_files: list[str]) -> None:
        """Rebuild the custom selection checklist with checkboxes for each CSV."""
        # Clear existing checkboxes
        for cb in self._csv_checkboxes:
            self._custom_check_layout.removeWidget(cb)
            cb.deleteLater()
        self._csv_checkboxes.clear()

        # Add new checkboxes
        for filepath in csv_files:
            cb = QCheckBox(os.path.basename(filepath))
            cb.setProperty("csv_path", filepath)
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_custom_check_changed)
            self._custom_check_layout.addWidget(cb)
            self._csv_checkboxes.append(cb)

    def _on_custom_check_changed(self) -> None:
        """Update info label when custom checkboxes change."""
        total = len(self._csv_checkboxes)
        checked = sum(1 for cb in self._csv_checkboxes if cb.isChecked())
        self._csv_selection_info.setText(
            f"{checked} of {total} CSVs selected."
        )

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
    # Loop config section
    # ------------------------------------------------------------------

    def _build_loop_config_section(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(4, 4, 4, 4)

        self.max_iterations_spin = QSpinBox()
        self.max_iterations_spin.setRange(1, 1000)
        self.max_iterations_spin.setValue(10)
        form.addRow("Max Iterations:", self.max_iterations_spin)

        self.max_improve_retries_spin = QSpinBox()
        self.max_improve_retries_spin.setRange(0, 100)
        self.max_improve_retries_spin.setValue(1)
        form.addRow("Improve Retries:", self.max_improve_retries_spin)

        self.max_param_variations_spin = QSpinBox()
        self.max_param_variations_spin.setRange(1, 100)
        self.max_param_variations_spin.setValue(3)
        form.addRow("Param Variations:", self.max_param_variations_spin)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        form.addRow("Random Seed:", self.seed_spin)

        return CollapsibleSection("Loop Config", box, expanded=True)

    # ------------------------------------------------------------------
    # Parameter section
    # ------------------------------------------------------------------

    def _build_param_section(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.param_summary_label = QLabel()
        self.edit_params_button = QPushButton("Edit Parameters...")
        self.edit_params_button.clicked.connect(self._open_param_dialog)
        top_row.addWidget(self.param_summary_label, 1)
        top_row.addWidget(self.edit_params_button)
        layout.addLayout(top_row)

        self.param_detail_label = QLabel()
        self.param_detail_label.setWordWrap(True)
        layout.addWidget(self.param_detail_label)

        self.refinement_info_label = QLabel()
        self.refinement_info_label.setWordWrap(True)
        layout.addWidget(self.refinement_info_label)

        strategy_name = self.strategy_combo.currentText()
        self._param_section = CollapsibleSection(
            f"Exploration Parameters ({strategy_name})",
            box,
            expanded=True,
        )
        return self._param_section

    def _open_param_dialog(self) -> None:
        dialog = ParameterDialog(
            parent=self,
            strategy_name=self.strategy_combo.currentText(),
            current_ranges=self._param_ranges,
        )
        if dialog.exec():
            self._param_ranges = dialog.get_ranges()
            self._refresh_param_summary()

    def _refresh_param_summary(self) -> None:
        count = len(self._param_ranges)
        self.param_summary_label.setText(f"{count} parameter(s) enabled")

        if not self._param_ranges:
            self.param_detail_label.setText("No exploration parameters enabled.")
        else:
            lines: list[str] = []
            for qualified_key, (lo, hi, step) in self._param_ranges.items():
                name = qualified_key.split("::", 1)[1]
                lines.append(f"{name}: {lo} .. {hi} (step {step})")
            self.param_detail_label.setText("\n".join(lines))

        base_count = len(self._base_param_overrides or {})
        seed_count = len(self._seed_param_overrides_list)
        if base_count == 0 and seed_count == 0:
            self.refinement_info_label.setText("Refinement seeds: none")
        else:
            self.refinement_info_label.setText(
                f"Refinement seeds prepared: base={base_count} value(s), seed candidates={seed_count}"
            )

    # ------------------------------------------------------------------
    # Public getters / setters
    # ------------------------------------------------------------------

    def get_csv_path(self) -> str:
        return self.csv_path_edit.text().strip()

    def get_csv_dir(self) -> str | None:
        text = self.csv_dir_edit.text().strip()
        return text if text else None

    def get_csv_selection_mode(self) -> str:
        """Return the current CSV selection mode string."""
        if self._radio_all.isChecked():
            return self.MODE_ALL_CSVS
        if self._radio_custom.isChecked():
            return self.MODE_CUSTOM
        return self.MODE_SELECTED_3_MONTHS

    def get_csv_paths(self) -> list[str] | None:
        """Build csv_paths list based on current CSV selection mode.

        Returns None if CSV Dir is not set (backward-compatible single CSV mode).
        """
        dir_path = self.csv_dir_edit.text().strip()
        if not dir_path or not os.path.isdir(dir_path):
            return None

        csv_files = self._scan_csv_dir(dir_path)
        if not csv_files:
            return None

        mode = self.get_csv_selection_mode()

        if mode == self.MODE_SELECTED_3_MONTHS:
            return csv_files[-3:] if len(csv_files) >= 3 else list(csv_files)
        elif mode == self.MODE_ALL_CSVS:
            return list(csv_files)
        elif mode == self.MODE_CUSTOM:
            selected = [
                cb.property("csv_path")
                for cb in self._csv_checkboxes
                if cb.isChecked()
            ]
            return selected if selected else None

        return None

    def get_max_iterations(self) -> int:
        return self.max_iterations_spin.value()

    def get_max_improve_retries(self) -> int:
        return self.max_improve_retries_spin.value()

    def get_max_param_variations(self) -> int:
        return self.max_param_variations_spin.value()

    def get_random_seed(self) -> int:
        return self.seed_spin.value()

    def get_param_override_ranges(self) -> dict[str, tuple[float, float, float]]:
        return dict(self._param_ranges)

    def set_param_override_ranges(
        self,
        ranges: dict[str, tuple[float, float, float]],
    ) -> None:
        self._param_ranges = dict(ranges)
        self._refresh_param_summary()

    def get_base_param_overrides(self) -> dict[str, float] | None:
        if not self._base_param_overrides:
            return None
        return dict(self._base_param_overrides)

    def set_base_param_overrides(
        self,
        overrides: dict[str, float] | None,
    ) -> None:
        self._base_param_overrides = dict(overrides) if overrides else None
        self._refresh_param_summary()

    def get_seed_param_overrides_list(self) -> list[dict[str, float]]:
        return [dict(seed) for seed in self._seed_param_overrides_list]

    def set_seed_param_overrides_list(
        self,
        seeds: list[dict[str, float]] | None,
    ) -> None:
        self._seed_param_overrides_list = [dict(seed) for seed in (seeds or [])]
        self._refresh_param_summary()

    def get_strategy_name(self) -> str:
        return self.strategy_combo.currentText()