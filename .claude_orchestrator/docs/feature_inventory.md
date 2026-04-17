# feature_inventory

## 目的

この文書は、repo 内の主要機能を棚卸しし、現在の状態を整理するための一覧である。  
planner / plan_director は、この文書を参照して以下を判断する。

* 既実装か
* 未接続か
* 一部完了か
* 未実装か
* 対象外か
* 重複 proposal になっていないか
* 次にどの層を前進させるべきか

---

## 状態ラベル

* `implemented`
* `gui_unconnected`
* `partial`
* `not_implemented`
* `gui_connected`
* `out_of_scope`

---

## 記載ルール

各機能は以下を必ず記載する。

* 機能名
* layer
* status
* related_files
* completion_links
* task_split_notes
* notes

---

## 機能一覧

### 月別CSVバックテスト実行

* layer: domain / infrastructure
* status: implemented

* related_files:
  * src\backtest\csv_loader.py
  * src\backtest\service.py
  * src\backtest\runner.py
  * src\backtest\simulator\engine.py
  * src\backtest\simulator\generic_runner.py
  * src\backtest\simulator\v7_runner.py
  * src\backtest\simulator\snapshots.py
  * data\USDJPY-cd5_20250521_monthly\

* completion_links:
  * 1. バックテスト・ポジション管理機能

* task_split_notes:
  * 単月実行・全月一括実行ともに csv_loader + service + simulator で実現済み
  * 全月一括実行は CLI (runner.py) 経由で可能だが、GUI からの全月一括実行は別機能として扱う

* notes:
  * csv_loader は tab/comma 両対応、MT4日時形式パース済み
  * 月別CSV は 2025-05 〜 2026-04 の12ヶ月分が存在

---

### A/B 2レーン戦術適用

* layer: domain
* status: implemented

* related_files:
  * src\mt4_bridge\strategies\bollinger_range_v4_4.py
  * src\mt4_bridge\strategies\bollinger_range_v4_4_tuned_a.py
  * src\mt4_bridge\strategies\bollinger_trend_B.py
  * src\mt4_bridge\strategies\bollinger_combo_AB.py
  * src\mt4_bridge\strategies\bollinger_combo_AB_v1.py
  * src\mt4_bridge\strategies\bollinger_range_v4_6_1.py
  * src\mt4_bridge\signal_engine.py

* completion_links:
  * 1. バックテスト・ポジション管理機能

* task_split_notes:
  * A（レンジ系）戦術: bollinger_range 系 v1〜v7_1 に多数バリエーション存在
  * B（トレンド系）戦術: bollinger_trend_B 系に B, B2, B2_early_exit, B3, B3_weak_start が存在
  * combo_AB が A/B 統合戦術として存在
  * signal_engine が戦術の動的ロード・評価を担当
  * [TASK-0099/0100] bollinger_range_v4_4_tuned_a を正式コミット済み。explore_gui・backtest_gui 両方の戦略選択リストに登録済み

* notes:
  * 戦術バリエーションが多く、最終採択の絞り込みは未実施
  * [TASK-0099] tuned_a は v4_4 ベースのパラメータ調整バリアント（BOLLINGER_PERIOD=26, BOLLINGER_SIGMA=1.9, RANGE_SLOPE_THRESHOLD=0.0006 等）

---

### ポジション管理（1レーン1ポジション制約）

* layer: domain
* status: implemented

* related_files:
  * src\backtest\simulator\position_manager.py
  * src\mt4_bridge\runtime_state.py
  * src\mt4_bridge\position_consistency.py
  * src\mt4_bridge\models.py

* completion_links:
  * 1. バックテスト・ポジション管理機能

* task_split_notes:
  * シミュレーター側: position_manager.py でレーン別ポジション管理
  * リアルタイム側: runtime_state.py + position_consistency.py でレーン別管理・整合性検証
  * ポジション状態（未保有/保有中/決済待ち）は models.py の enum で定義済み

* notes:
  * バックテスト側・リアルタイム側の両方で1レーン1ポジション制約を実装済み

---

### SL/TP処理（Intrabar fill）

* layer: domain
* status: implemented

* related_files:
  * src\backtest\simulator\intrabar.py
  * src\mt4_bridge\risk_manager.py

* completion_links:
  * 1. バックテスト・ポジション管理機能

* task_split_notes:
  * intrabar.py がバー内での SL/TP ヒット判定を実装
  * risk_manager.py が pips からの SL/TP 価格計算を担当

* notes:
  * バックテストシミュレーターに統合済み

---

### 成績算出（総pips・勝率・PF・最大DD・取引回数）

* layer: domain
* status: implemented

* related_files:
  * src\backtest\simulator\stats.py
  * src\backtest\evaluator.py
  * src\backtest\view_models.py

* completion_links:
  * 2. 評価・比較機能

* task_split_notes:
  * stats.py で総pips, 勝率, PF, 最大DD, 取引回数を算出済み
  * evaluator.py で ADOPT/IMPROVE/DISCARD の閾値判定を実装済み

* notes:
  * 月別算出は csv_loader + service の単月実行を繰り返すことで可能

---

### 全月合算成績算出

* layer: domain / usecase
* status: implemented

* related_files:
  * src\backtest\aggregate_stats.py
  * src\backtest\service.py
  * src\backtest\runner.py

* completion_links:
  * 2. 評価・比較機能

* task_split_notes:
  * aggregate_stats.py で月別 BacktestStats リストから全月合算成績を算出（総pips・勝率・PF・最大DD・取引回数・月別ばらつき標準偏差・赤字月数・赤字月連続数）
  * service.py の run_all_months でCSVディレクトリ一括実行→合算成績返却
  * runner.py の --csv-dir オプションでCLI経由の全月一括実行→合算成績出力

* notes:
  * GUI統合は別タスクのスコープ
  * close_compare_v1.py 復旧済み（TASK-0005）。CLI e2e 動作確認完了（12ヶ月一括実行→合算成績出力成功）
  * 全月通算 PF を月別 average_win/loss 近似から gross_profit_pips/gross_loss_pips 精密計算に修正済み（TASK-0009）

---

### MFE/MAE ratio 補助品質指標

* layer: domain
* status: implemented

* related_files:
  * src\backtest\simulator\models.py
  * src\backtest\simulator\stats.py
  * src\backtest\aggregate_stats.py
  * src\backtest\runner.py

* completion_links:
  * 2. 評価・比較機能

* task_split_notes:
  * TASK-0025 で実装: 各トレードの mfe_pips / mae_pips から MFE/MAE ratio を算出し、月別平均・全月合算平均を BacktestStats / AggregateStats に追加
  * mae_pips=0 のトレードは ratio=None として集計から除外
  * MFE/MAE が None のトレード（旧データ）も集計対象から除外

* notes:
  * 補助指標であり、採択判定ロジックの主指標としては扱わない
  * CLI の全月合算サマリー・compare_ab 比較表にも表示追加済み
  * [TASK-0026 実装済み] GUI All Months タブの月別テーブルに Avg MFE/MAE 列を追加、aggregate パネルに Avg MFE/MAE フィールドを追加
  * [TASK-0027 実装済み] GUI Single Month SummaryPanel に Avg MFE/MAE フィールドを追加（None 時 '-' 表示、小数点以下2桁）

---

### A単体・B単体・A+B合成成績比較

* layer: usecase
* status: implemented

* related_files:
  * src\backtest\service.py
  * src\backtest\runner.py
  * src\mt4_bridge\strategies\bollinger_combo_AB.py
  * src\mt4_bridge\strategies\bollinger_combo_AB_v1.py

* completion_links:
  * 2. 評価・比較機能

* task_split_notes:
  * service.py の compare_ab() で A単体/B単体/A+B合成の3パターン全月一括バックテスト→比較を実装
  * runner.py の --compare-ab オプションで CLI 経由の比較表出力が可能
  * combo モジュールの LANE_A_STRATEGY / LANE_B_STRATEGY 定数で A/B 戦術名を解決

* notes:
  * CLI e2e 動作確認済み（TASK-0007）: bollinger_combo_AB_v1 で --compare-ab 12ヶ月一括比較が正常動作
  * bollinger_combo_AB_v1 の LANE_B_STRATEGY 参照先を bollinger_trend_B3_weak_start に修正済み（旧 v3_1 は不在だった）
  * bollinger_combo_AB（非v1）の required_bars 不足問題を修正済み（TASK-0008）: bollinger_range_v4_4.py の required_bars を BOLLINGER_PERIOD → BOLLINGER_PERIOD+1 に修正し、--compare-ab 12ヶ月一括比較が正常動作することを確認
  * [TASK-0028 実装済み] GUI Compare A/B タブを追加し、compare_ab 相当の3パターン比較（A単体/B単体/A+B合成）をGUIから実行・結果表示可能にした。QThread非同期実行・プログレス表示・キャンセル機能・戦術パラメータオーバーライド対応

---

### GUI バックテスト画面

* layer: gui
* status: implemented

* related_files:
  * src\backtest_gui.py
  * src\backtest_gui_app\views\main_window.py
  * src\backtest_gui_app\views\input_panel.py
  * src\backtest_gui_app\views\summary_panel.py
  * src\backtest_gui_app\views\result_tabs.py
  * src\backtest_gui_app\views\chart_overview_tab.py
  * src\backtest_gui_app\views\all_months_tab.py
  * src\backtest_gui_app\widgets\chart_widget.py（TASK-0141 / T-D 第1段で `gui_common.widgets.chart_widget` への再エクスポートシムに置換）
  * src\backtest_gui_app\widgets\price_chart_widget.py
  * src\backtest_gui_app\widgets\time_series_chart_widget.py（TASK-0141 / T-D 第1段で `gui_common.widgets.time_series_chart_widget` への再エクスポートシムに置換）
  * src\backtest_gui_app\widgets\linked_trade_chart_widget.py
  * src\backtest_gui_app\widgets\collapsible_section.py（TASK-0141 / T-D 第1段で `gui_common.widgets.collapsible_section` への再エクスポートシムに置換）
  * src\gui_common\widgets\collapsible_section.py（TASK-0141 / T-D 第1段で正式な配置先）
  * src\gui_common\widgets\chart_widget.py（TASK-0141 / T-D 第1段で正式な配置先、`MatplotlibChart`）
  * src\gui_common\widgets\time_series_chart_widget.py（TASK-0141 / T-D 第1段で正式な配置先）
  * src\gui_common\widgets\mean_reversion_summary_widget.py（TASK-0141 / S-3 で新規作成。`MeanReversionSummary` dataclass を直接受け取る共通 11 項目表示ウィジェット）
  * src\backtest_gui_app\presenters\result_presenter.py
  * src\backtest_gui_app\services\run_config_builder.py
  * src\backtest_gui_app\constants.py
  * src\backtest_gui_app\helpers.py

* completion_links:
  * 3. GUI最適化支援機能

* task_split_notes:
  * 既存 GUI (backtest_gui.py + backtest_gui_app) は PySide6 ベースで存在
  * 戦術選択・CSV選択・実行・結果表示・チャート表示が実装済み
  * completion_definition では「src\backtest_gui.py を参考に新規GUIを作成する」とあり、新規作成が必要か既存改修かの方針確認が必要
  * [TASK-0012 実装済み] 全月一括実行の GUI 対応: CSVディレクトリ選択UI・全月一括実行ボタン・月別成績一覧表・全月合算成績表示を All Months タブとして追加。run_all_months() への接続完了
  * [TASK-0013 実装済み] 全月一括実行の QThread 非同期化: AllMonthsWorker(QThread) で月別バックテストをワーカースレッドで実行し、月数ベースプログレスバー表示・実行ボタン無効化・シグナル経由の結果更新を実装。GUIフリーズを回避
  * [TASK-0015 実装済み] 全月一括実行のキャンセル機能: requestInterruption() + progress_callback 内チェックによる中断機構。Cancel ボタン追加・キャンセル時 UI リセット実装
  * [TASK-0010 ギャップ分析] 全月通算損益推移チャートが未実装: 単月分の損益推移チャートは実装済みだが全月通算は未対応（TASK-0012 スコープ外） → [TASK-0016 実装済み] 全月通算損益推移チャート（累積 pips 折れ線 + 月境界補助線）を All Months タブに追加
  * [TASK-0141 実装済み / 2026-04-18] T-D 第1段（§12-2 2段移設の第1段）として `CollapsibleSection` / `MatplotlibChart` / `TimeSeriesChartWidget` の3ウィジェットを `src\backtest_gui_app\widgets\` から `src\gui_common\widgets\` へ物理移設。`src\backtest_gui_app\widgets\{collapsible_section,chart_widget,time_series_chart_widget}.py` は旧 import パス互換のための再エクスポートシムとして残置（後続 F6 で削除予定）。`SummaryPanel` / `InputPanel` / `ResultTabs` / `AllMonthsTab` / `ChartOverviewTab` / `BacktestResultPresenter` の import 文は既存シム経由で動作継続（正式 import は `gui_common.widgets.*`）。また T-D / S-3 として `SummaryPanel` の MR 11 項目表示を新規共通ウィジェット `gui_common.widgets.mean_reversion_summary_widget.MeanReversionSummaryWidget` へ切り出し、`SummaryPanel.mean_reversion_widget` として露出。`BacktestResultPresenter._populate_mean_reversion` / `clear_result_views` は共通ウィジェットの `set_summary(MeanReversionSummary | None)` を呼ぶだけの薄い委譲に縮約。`summary_labels` 辞書から MR キー（`mr_*` 11 個）は除去され、MR 表示の状態管理は共通ウィジェット側に集約

* notes:
  * GUI の基本骨格は存在するが、completion_definition が要求する全項目を満たしているかは精査が必要
  * TASK-0012 で月別成績表・全月合算成績の GUI 表示を追加済み。全月通算損益推移チャートは TASK-0016 で実装完了
  * [TASK-0026 実装済み] All Months タブの月別テーブルに Avg MFE/MAE 列（9列目）を追加、aggregate パネルに Avg MFE/MAE フィールドを追加
  * [TASK-0027 実装済み] Single Month SummaryPanel に Avg MFE/MAE フィールドを追加
  * [TASK-0028 実装済み] Compare A/B タブを追加: A単体/B単体/A+B合成の3パターン全月合算成績比較テーブルをGUIで表示。QThread非同期実行・3フェーズプログレス・キャンセル機能・戦術パラメータオーバーライド対応
  * [TASK-0052 昇格判定] status を partial → implemented に昇格。completion_definition セクション3 が要求する4項目（新規GUI作成・パラメータ変更・再計算即時反映・月別成績表/全体成績/損益推移/補助表示）はすべて充足済み。partial 残留の理由だった「GUI 探索ループ統合」はセクション3 のスコープ外（セクション6 品質に帰属）であり、本エントリの status を制約する根拠にならないと判断

---

### GUI パラメータ変更・即時再計算

* layer: gui / usecase
* status: implemented

* related_files:
  * src\backtest_gui_app\views\input_panel.py
  * src\backtest_gui_app\services\run_config_builder.py
  * src\gui_common\strategy_params.py

* completion_links:
  * 3. GUI最適化支援機能

* task_split_notes:
  * input_panel.py で戦術・CSV選択は可能
  * SL/TP/Balance 等のシミュレーション設定パラメータは GUI 上で変更可能、Run backtest ボタンで再計算→結果反映が可能
  * [TASK-0010 ギャップ分析 → TASK-0017 実装済み] 戦術固有パラメータの動的変更 UI を追加: bollinger_range_v4_4 / bollinger_combo_AB 系の主要パラメータ（BOLLINGER_PERIOD, BOLLINGER_SIGMA, BOLLINGER_EXTREME_SIGMA, RANGE_SLOPE_THRESHOLD, RANGE_BAND_WIDTH_THRESHOLD, RANGE_MIDDLE_DISTANCE_THRESHOLD, TREND_SLOPE_THRESHOLD, STRONG_TREND_SLOPE_THRESHOLD）を SpinBox/DoubleSpinBox で編集可能。ランタイムオーバーライド方式により戦術ファイル自体は変更しない
  * [TASK-0010 ギャップ分析 → TASK-0017 実装済み] 戦術固有パラメータを GUI 上で変更し Run backtest で即時反映する仕組みを実装: strategy_params.py の apply_strategy_overrides コンテキストマネージャでモジュール定数を一時的にオーバーライドし、バックテスト完了後に復元
  * [TASK-0012 実装済み] 全月一括実行→結果即時反映の GUI 導線を All Months タブとして追加
  * [TASK-0050 MVP充足判定] completion_definition セクション3 各項目の充足状況:
    * (1)「src\backtest_gui.py を参考に新規GUIを作成する」→ implemented: backtest_gui_app パッケージとして PySide6 ベースの新規 GUI を構築済み
    * (2)「GUI上から主要パラメータを変更できる」→ implemented: input_panel.py で SL/TP/Balance + 戦術固有パラメータ（BOLLINGER_PERIOD 等8項目）を SpinBox/DoubleSpinBox で変更可能
    * (3)「パラメータ変更後に再計算し、結果を即時反映できる」→ implemented（ボタン押下式）: Run backtest ボタンでパラメータ変更→再計算→結果反映が動作。apply_strategy_overrides によるランタイムオーバーライドで即時反映を実現
    * (4)「月別成績表、全体成績、損益推移、必要な補助表示を確認できる」→ implemented: All Months タブ（月別成績表・全月合算成績・損益推移チャート）、SummaryPanel（単月成績）、Compare A/B タブ（3パターン比較）を実装済み
  * [TASK-0050 方針確定] 自動再計算（パラメータ変更検知トリガー）は MVP 必須ではない。「即時反映」はボタン押下式（Run backtest → 再計算 → 結果更新）で MVP 充足と判定。自動再計算は将来の UX 改善として扱う

* notes:
  * 戦術固有パラメータの GUI 変更 UI は TASK-0017 で実装済み。戦術選択変更時にパラメータ UI が動的に切り替わる
  * [TASK-0018 実装済み] All Months タブからの全月一括実行時にも戦術パラメータオーバーライドに対応。InputPanel の GUI 値を AllMonthsWorker に dict で引数渡しし、各月の run_backtest() 内で apply_strategy_overrides コンテキストマネージャにより適用・復元
  * [TASK-0050 MVP充足判定] completion_definition セクション3「パラメータ変更後に再計算し、結果を即時反映できる」について、ボタン押下式（Run backtest ボタン）での MVP 充足を正式判定。TASK-0049 の implementer/reviewer/director 全員がボタン押下式での充足を推奨しており、方針を確定。自動再計算（パラメータ変更検知トリガー）は MVP 必須ではなく、将来の UX 改善として扱う
  * [TASK-0100] bollinger_range_v4_4_tuned_a 用パラメータ定義を strategy_params.py に追加済み（STRATEGY_PARAM_MAP に tuned_a エントリ登録、実際のデフォルト値準拠）
  * [TASK-0123 / Phase 1 Step 2 完了] `strategy_params` の物理配置を `src/backtest_gui_app/services/strategy_params.py` から `src/gui_common/strategy_params.py` へ移設。explore_gui 主導移行マップの Phase 1 Step 2（共通基盤の層破り解消）に対応。`StrategyParamSpec` / `STRATEGY_PARAM_MAP` / `get_param_specs` / `read_current_defaults` / `apply_strategy_overrides` は `gui_common.strategy_params` を正式な import 元とする
  * [TASK-0127 / Phase 2 冒頭] `src/backtest_gui_app/services/strategy_params.py` の再エクスポートシムを完全削除（2026-04-17）。旧 import パス `backtest_gui_app.services.strategy_params` の残存ゼロを repo 全体 grep で確認済み

### GUIレイアウト再設計（Standard画面の情報密度整理）

* layer: gui
* status: implemented

* related_files:
  * src\backtest_gui_app\views\main_window.py
  * src\backtest_gui_app\views\input_panel.py
  * src\backtest_gui_app\views\result_tabs.py
  * src\backtest_gui_app\views\summary_panel.py
  * src\backtest_gui_app\views\chart_overview_tab.py
  * src\backtest_gui_app\views\all_months_tab.py
  * src\backtest_gui_app\views\compare_ab_tab.py

* completion_links:
  * 3. GUI最適化支援機能
  * 5. 操作性

* task_split_notes:
  * [TASK-0117 実装済み] Standard 画面を「左サイドバー + 右ワークスペース」型へ再設計。`_build_standard_page` を 上下 2 段構造から 左右 2 段構造へ変更し、左 380px に InputPanel（QScrollArea ラップ）、右に SummaryPanel（KPI ストリップ + 詳細）と ResultTabs を縦 splitter で配置することでチャート主役の情報密度に整理した
  * [TASK-0117 実装済み] InputPanel の Parameters セクションを 3 列横並び → 単一 Form + アクションブロック縦組みへ変更し、サイドバー幅でも全項目が読める構造に変更
  * [TASK-0117 実装済み] SummaryPanel を主要 KPI（Total pips / Win rate / Profit factor / Max DD pips / Trades / Verdict）の横並びカードと、詳細 2 列セクション、Verdict reasons の 3 ブロックに整理
  * 既存の InputPanel / SummaryPanel / ResultTabs の責務分離・signals は変更せず、result_presenter.summary_labels が参照する key set を維持

* notes:
  * 機能追加・売買ロジック変更は行わず、既存機能を壊さない範囲での GUI 改修のみを実施
  * Run / Cancel ボタンに role プロパティ（primary / danger）を付与し、ダークテーマ QSS と連動して視覚優先度を表現
  * QScrollArea ラップにより 1080p 以下の縦解像度でも InputPanel 全項目へ到達可能

### ダークテーマ用スタイルシート基盤（QSS）

* layer: gui
* status: implemented

* related_files:
  * src\backtest_gui_app\styles\__init__.py
  * src\backtest_gui_app\styles\dark_theme.py
  * src\backtest_gui_app\views\main_window.py
  * src\backtest_gui_app\views\input_panel.py
  * src\backtest_gui_app\views\result_tabs.py
  * src\backtest_gui_app\views\summary_panel.py
  * src\backtest_gui_app\widgets\collapsible_section.py（TASK-0141 / T-D 第1段で `gui_common.widgets.collapsible_section` への再エクスポートシムに置換）
  * src\backtest_gui_app\widgets\chart_widget.py（TASK-0141 / T-D 第1段で `gui_common.widgets.chart_widget` への再エクスポートシムに置換）
  * src\backtest_gui_app\widgets\time_series_chart_widget.py（TASK-0141 / T-D 第1段で `gui_common.widgets.time_series_chart_widget` への再エクスポートシムに置換）
  * src\gui_common\widgets\collapsible_section.py（TASK-0141 / T-D 第1段で正式な配置先）
  * src\gui_common\widgets\chart_widget.py（TASK-0141 / T-D 第1段で正式な配置先。暫定的に `backtest_gui_app.styles.DARK_THEME_COLORS` / `style_matplotlib_figure` を import している。T-E で `gui_common.styles` 新設時に解消予定）
  * src\gui_common\widgets\time_series_chart_widget.py（TASK-0141 / T-D 第1段で正式な配置先。スタイル import は `chart_widget.py` と同条件）
  * src\backtest_gui_app\constants.py

* completion_links:
  * 3. GUI最適化支援機能
  * 5. 操作性

* task_split_notes:
  * [TASK-0117 実装済み] `src\backtest_gui_app\styles\dark_theme.py` を新規追加し、`DARK_THEME_COLORS`（17 色トークン）と QSS 文字列、`apply_dark_theme(target)`、`style_matplotlib_figure(figure, axes)` を提供。ダーク寄りダッシュボードに合わせた配色・KPI 強調・タブ / テーブル / 入力欄統一を一括で適用できる基盤
  * [TASK-0117 実装済み] `BacktestMainWindow.__init__` で `apply_dark_theme(self)` を呼び出し、ウィンドウ全体に QSS を適用
  * [TASK-0117 実装済み] `MatplotlibChart` / `TimeSeriesChartWidget` の Figure facecolor・軸色・grid 色をダークパレットへ統一（`style_matplotlib_figure` 経由）。canvas widget 自体の background も QSS と一致させた
  * [TASK-0117 実装済み] `CollapsibleSection` のヘッダ QToolButton に `role="section-header"` プロパティを付与し、QSS で見出し強調可能にした
  * [TASK-0117 実装済み] Run / Cancel / Clear ボタンに role プロパティ（primary / danger）を付与し、QSS と連動
  * [TASK-0141 実装済み / 2026-04-18] T-D 第1段で `MatplotlibChart` / `TimeSeriesChartWidget` / `CollapsibleSection` の定義を `gui_common.widgets` 配下に移設。移設後も Figure facecolor・軸色・grid 色のダーク統一挙動は `style_matplotlib_figure` 経由で維持（`gui_common.widgets.chart_widget` / `time_series_chart_widget` は暫定的に `backtest_gui_app.styles` から import する逆依存を内包し、T-E で `gui_common.styles` 新設時に解消予定）

* notes:
  * 初期スコープはダークテーマ固定。将来のテーマ切替を行う場合は `apply_dark_theme` と並列で `apply_light_theme` を追加する設計余地を残してある
  * `LinkedTradeChartWidget`（candle 含むチャート）はハードコード色（"black"/"white" 等）を持つため、本タスクではダーク化対象外。視認性影響評価のうえ後続タスクで対応する候補
  * matplotlib の facecolor は figure clear のたびに resetされるため、各 plot 関数末尾で `style_matplotlib_figure` を再適用する形に統一済み

---

### 構造化ログ出力（trade_id / lane_id / reason_code）

* layer: domain / infrastructure
* status: implemented

* related_files:
  * src\backtest\simulator\trade_logger.py
  * src\backtest\simulator\models.py
  * src\backtest\service.py

* completion_links:
  * 4. ログ・追跡・最終統合機能

* task_split_notes:
  * TASK-0019 で JSON Lines 形式のトレードライフサイクルログ出力基盤を実装済み（ENTRY / SL_HIT / TP_HIT / SIGNAL_CLOSE / FORCED_END イベント）
  * 単月バックテスト実行時にオプショナルで trade_log_path を指定すると JSONL ファイルを出力可能
  * [TASK-0020 実装済み] 全月一括実行時にも月別 JSONL トレードログを出力可能: run_all_months() に trade_log_dir 引数を追加し、各月の CSV stem をファイル名として logs/trade_logs/{label}.jsonl に出力
  * [TASK-0020 実装済み] GUI の All Months タブに Trade Log チェックボックスを追加し、AllMonthsWorker 経由で trade_log_dir を渡す
  * [TASK-0021 実装済み] CLI --trade-log-dir オプション（--csv-dir 全月一括実行時）および --trade-log-path オプション（--csv 単月実行時）を runner.py に追加し、コマンドライン経由でトレードログ出力先を指定可能にした
  * [TASK-0022 実装済み] compare_ab() に trade_log_dir 引数を追加し、指定時に lane_a / lane_b / combo サブディレクトリへ自動振り分けして月別 JSONL トレードログを出力。runner.py の _run_compare_ab() で既存 --trade-log-dir CLI 引数を compare_ab() に接続済み。未指定時は従来動作（ログ出力なし）を維持
  * [TASK-0024 実装済み] MFE（Maximum Favorable Excursion）・MAE（Maximum Adverse Excursion）・holding_bars の3フィールドを ExecutedTrade に追加し、EXIT 系イベントの JSONL 出力に含めるようにした。MFE/MAE は pips 単位、holding_bars はバー数。SimulatedPosition にバー処理ループ内で max_favorable_price / max_adverse_price を追跡し、決済時に pips 換算して ExecutedTrade に引き渡す
  * [TASK-0055 実装済み] SKIP（見送り）イベントを JSONL 出力に追加。decision_logs から HOLD かつポジション未保有のエントリーを抽出し、reason_code 付きで構造化記録（reason_code: range_reentry_blocked / entry_event_not_allowed / no_entry_condition / hold_no_entry）。write_trade_log_jsonl に include_skip_events オプション追加（デフォルト有効）

* notes:
  * decision_log.py は各バーの判定記録として維持。trade_logger.py はトレード単位のライフサイクルログとして独立

---

### trade_id によるトレード追跡

* layer: domain
* status: implemented

* related_files:
  * src\backtest\simulator\models.py
  * src\backtest\simulator\position_manager.py
  * src\backtest\simulator\trade_logger.py

* completion_links:
  * 4. ログ・追跡・最終統合機能

* task_split_notes:
  * TASK-0019 で ExecutedTrade / SimulatedPosition に trade_id フィールドを追加し、T-{ticket:04d} 形式で一意な ID を付与
  * トレードライフサイクル（ENTRY → EXIT系イベント）を JSON Lines で追跡可能
  * [TASK-0024 実装済み] holding_bars / MFE / MAE を ExecutedTrade に追加し、トレードライフサイクルログの EXIT イベントに出力
  * [TASK-0055 実装済み] trade_id を Optional（デフォルト None）→必須（str）に変更。SimulatedPosition・ExecutedTrade の両方で trade_id フィールドのデフォルト値を削除し、型を str に変更。全既存呼び出し元（position_manager.py）は keyword 引数で trade_id を渡しており互換性問題なし

* notes:
  * trade_id は必須フィールド（str）。T-{ticket:04d} 形式で一意な ID を付与

---

### 最終統合（採択結果の bollinger_combo_AB.py 反映）

* layer: usecase
* status: implemented

* related_files:
  * src\mt4_bridge\strategies\bollinger_combo_AB.py
  * src\backtest\apply_params.py
  * src\gui_common\strategy_params.py

* completion_links:
  * 4. ログ・追跡・最終統合機能

* task_split_notes:
  * [TASK-0029 実装済み] CLI ツール apply_params.py を新規作成: 指定された戦術パラメータ値セットを戦術モジュールファイルの定数として恒久的に上書き保存する機能を実装
  * LANE_A_STRATEGY / LANE_B_STRATEGY の書き換え、および戦術固有パラメータ定数（BOLLINGER_PERIOD, BOLLINGER_SIGMA 等）の書き換えに対応
  * --list でパラメータ一覧表示、--dry-run でプレビュー、--backup で .bak 作成が可能
  * 再実行時の結果再現性検証は、書き出し後に runner.py --compare-ab で同一結果を確認するワークフローとして提供

* notes:
  * strategy_params.py の StrategyParamSpec を参照してパラメータ定義を取得する設計。GUI のランタイムオーバーライド（一時的）と apply_params.py の恒久書き込みが明確に分離されている
  * 自動探索・最適化ループは本ツールのスコープ外
  * [TASK-0123 / Phase 1 Step 2 完了] `strategy_params` の正式 import 元は `src\gui_common\strategy_params.py`。apply_params.py も gui_common.strategy_params から StrategyParamSpec / STRATEGY_PARAM_MAP を参照する
  * [TASK-0127 / Phase 2 冒頭] `src\backtest_gui_app\services\strategy_params.py` の再エクスポートシムを完全削除（2026-04-17）。旧 import パス `backtest_gui_app.services.strategy_params` の残存ゼロを repo 全体 grep で確認済み

---

### GUI 応答速度（実用的な速度での再評価）

* layer: gui
* status: implemented

* related_files:
  * src\backtest_gui_app\views\main_window.py
  * src\backtest\simulator\engine.py
  * src\backtest\service.py

* completion_links:
  * 5. 操作性

* task_split_notes:
  * [TASK-0057] 定量検証実施済み。bollinger_combo_AB 戦略・12ヶ月データで計測
  * 単月バックテスト: 0.4〜2.8秒（平均約2.1秒、初月・最終月はデータ量少で高速）
  * 全月一括バックテスト（12ヶ月）: 約26秒
  * 「実用的な速度」基準: 単月5秒以内、全月一括60秒以内 → 両方クリア

* notes:
  * 計測環境: Windows ローカル Python (.venv)、bollinger_combo_AB（2レーン combo 戦略）
  * GUI は AllMonthsWorker (QThread) で非同期実行のため、全月一括中も UI はブロックされない

---

### Windows ローカル Python 実行

* layer: infrastructure
* status: implemented

* related_files:
  * config\app.yaml
  * src\app_cli.py
  * src\backtest_gui.py

* completion_links:
  * 5. 操作性

* task_split_notes:
  * なし

* notes:
  * Windows 環境での Python 実行を前提として構成済み

---

### 月平均利益基準の探索・確認

* layer: usecase
* status: implemented

* related_files:
  * src\backtest\evaluator.py
  * src\backtest\exploration_loop.py
  * src\explore_cli.py
  * src\mt4_bridge\strategy_generator.py

* completion_links:
  * 6. 品質

* task_split_notes:
  * exploration_loop.py + strategy_generator.py で戦術パラメータ探索の仕組みは存在
  * [TASK-0031 実装済み] evaluate_cross_month() で月平均 pips 基準（min 150 / target 200）の全月横断評価を実装
  * [TASK-0032 実装済み] evaluate_integrated() で全月合算成績（総pips・PF・最大DD）と月別安定性（赤字月比率・連続赤字月・月別ばらつき stddev）を統合した採択判定を実装。ADOPT/IMPROVE/DISCARD を返す。閾値はパラメータ化済み
  * [TASK-0040 実装済み] exploration_loop.py の run_single_exploration() 内で csv_dir 指定時に全月バックテスト→aggregate_monthly_stats→evaluate_cross_month/evaluate_integrated を実行。ExplorationResult に cross_month_evaluation / integrated_evaluation / aggregate_stats フィールドを追加し、integrated verdict を最終判定として使用。既存単月評価フローは維持

* notes:
  * 基準判定ロジック（evaluate_cross_month / evaluate_integrated）と探索ループの接続が TASK-0040 で実装完了。csv_dir 未指定時は従来の単月評価のみで動作（後方互換性維持）
  * [TASK-0041 方針明文化] 最適化主対象は bollinger_range / bollinger_trend 系の既存戦術。close_compare / ma_cross テンプレート戦略は対象外。詳細は `project_core/最適化方針_bollinger戦略.md` を参照

---

### 全月安定性評価（赤字月非連続・ばらつき抑制）

* layer: usecase
* status: implemented

* related_files:
  * src\backtest\aggregate_stats.py
  * src\backtest\evaluator.py

* completion_links:
  * 6. 品質

* task_split_notes:
  * aggregate_stats.py に deficit_month_count（赤字月数）・max_consecutive_deficit_months（赤字月連続数）・monthly_pips_stddev（月別ばらつき標準偏差）を実装済み
  * [TASK-0032 実装済み] evaluator.py の evaluate_integrated() で全月合算成績（総pips・PF・最大DD）と月別安定性（赤字月比率・連続赤字月・月別ばらつき stddev）を統合した採択判定を実装。ADOPT/IMPROVE/DISCARD を返す。閾値はパラメータ化済み

* notes:
  * 安定性指標の算出は aggregate_stats.py、閾値判定・採択基準への組み込みは evaluator.py の evaluate_integrated() で実装済み

---

### エラー処理・耐障害性

* layer: infrastructure
* status: implemented

* related_files:
  * src\mt4_bridge\snapshot_reader.py
  * src\mt4_bridge\stale_detector.py
  * src\mt4_bridge\command_guard.py
  * src\backtest\simulator\models.py
  * src\backtest\evaluator.py
  * src\backtest\simulator\trade_logger.py

* completion_links:
  * 7. エラー処理・耐障害性

* task_split_notes:
  * snapshot_reader.py で JSON パースエラー処理済み
  * stale_detector.py でデータ鮮度検出・ブロック済み
  * command_guard.py で重複信号防止済み
  * TASK-0058: evaluator.py に check_log_quality() / evaluate_backtest_with_log_guard() を追加し「ログが取れないロジックは採択しない」を実装
  * TASK-0058: trade_logger.py に _validate_reason_code() を追加し「構造化項目 reason_code 必須」の強制を実装

* notes:
  * リアルタイム側エラー処理（snapshot_reader / stale_detector / command_guard）とバックテスト側ログ品質制約（evaluator log guard / trade_logger reason_code 検証）の両方が実装済み

---

### データ整合性（シミュレーターと MT4 の挙動一致）

* layer: domain / infrastructure
* status: implemented

* related_files:
  * src\mt4_bridge\models.py
  * src\backtest\simulator\engine.py
  * src\backtest\simulator\log_concept_mapping.py
  * src\backtest\simulator\trade_logger.py
  * MT4\MQL4\Experts\BridgeWriterEA.mq4

* completion_links:
  * 8. データ整合性

* task_split_notes:
  * models.py でシミュレーター・リアルタイム共通のデータモデルを定義
  * BridgeWriterEA.mq4 がMT4側のブリッジとして存在
  * TASK-0059 で log_concept_mapping.py を新設し event_type / reason_code / lane_id / trade_id のログ概念対応表を定義
  * trade_logger.py がマッピング定数を参照し、イベント出力時に概念一致を検証
  * engine.py のエントリー条件判定・SL/TP 処理・ポジション管理ロジックを精査し、シミュレーター専用の簡略判定がないことを確認済み（SL/TP 計算は mt4_bridge.risk_manager を共用、エントリー判定は同一戦略関数を使用）

* notes:
  * MT4側（MQL4）と Python 側の構造的対応に加え、ログ意味体系の対応表（log_concept_mapping.py）を整備。trade_logger.py がマッピング定数を参照し概念一致を保証

---

### リアルタイムブリッジ（MT4-Python連携）

* layer: infrastructure
* status: implemented

* related_files:
  * src\app_cli.py
  * src\app_watch.py
  * src\app_watch_gui.py
  * src\mt4_bridge\services\bridge_service.py
  * src\mt4_bridge\snapshot_reader.py
  * src\mt4_bridge\command_writer.py
  * src\mt4_bridge\result_reader.py
  * src\mt4_bridge\runtime_state.py
  * src\mt4_bridge\app_config.py
  * MT4\MQL4\Experts\BridgeWriterEA.mq4

* completion_links:
  * 9. 将来拡張（MVP後）

* task_split_notes:
  * MT4-Python ブリッジ基盤は完成しており、スナップショット読取・コマンド送信・結果取得が動作する
  * ただしリアルタイム自動売買自体は MVP 対象外

* notes:
  * MVP の主目的はバックテスト・最適化であり、このブリッジ基盤は将来のリアルタイム運用の基盤

---

### 戦術パラメータ探索ループ

* layer: usecase
* status: implemented

* related_files:
  * src\backtest\exploration_loop.py
  * src\explore_cli.py
  * src\mt4_bridge\strategy_generator.py
  * src\mt4_bridge\strategies\bac\

* completion_links:
  * 6. 品質
  * ~~3. GUI最適化支援機能~~ → [TASK-0052 スコープ整理] GUI 探索ループ統合はセクション3 本文の4項目に含まれない。セクション3 へのリンクは completion_links の過剰紐付けであり、探索ループ機能の帰属先はセクション6（品質）。GUI 統合は将来拡張（セクション9 相当）として扱う

* task_split_notes:
  * exploration_loop.py で生成→バックテスト→評価のサイクルが実装済み
  * strategy_generator.py でパラメータ変化戦術の自動生成が実装済み（close_compare / ma_cross テンプレート方式、主対象外）
  * bac/ 配下に自動生成された戦術ファイルが60件以上存在
  * [TASK-0042 実装済み] bollinger 系既存戦術のパラメータオーバーライド探索を exploration_loop.py に追加: run_bollinger_exploration()（単一パラメータセットでの bollinger 戦術バックテスト実行）、run_bollinger_exploration_loop()（パラメータバリエーション生成→バックテスト→評価の反復探索ループ）、generate_bollinger_param_variations()（BOLLINGER_PARAM_VARIATION_RANGES に基づくパラメータバリエーション自動生成）、BOLLINGER_PARAM_VARIATION_RANGES（bollinger 系戦術ごとのパラメータ探索値域定義）
  * GUI 経由の探索統合は未実装。explore_gui.py として別エントリポイントで新規作成予定（TASK-0065 方針確定）

* notes:
  * CLI ベースの探索は動作するが、GUI 統合は未実装。GUI 化は explore_gui.py（別エントリポイント）として新規作成する方針（TASK-0065 で方針確定）
  * [TASK-0041 方針明文化] 探索ループの主対象を bollinger 系既存戦術に切り替える方針を明文化。詳細は `project_core/最適化方針_bollinger戦略.md` を参照
  * [TASK-0042 実装済み] TASK-0041 方針に基づき、exploration_loop.py に bollinger 系パラメータオーバーライド探索モード（run_bollinger_exploration / run_bollinger_exploration_loop / generate_bollinger_param_variations / BOLLINGER_PARAM_VARIATION_RANGES）を実装完了。既存戦術 + パラメータオーバーライド方式での探索が可能になった。~~実データ CSV を用いた結合テストは未実施（後続タスクで対応必須）~~ → TASK-0062 で A単体結合テスト6項目全PASSにより解消済み（2026-04-10）
  * [TASK-0061 方針明文化] ボリンジャー専用 exploration_loop 方針を `project_core/最適化方針_bollinger戦略.md` に明文化。探索フローは「A単体→B単体→A/B組み合わせ→combo_AB反映」の4段階。generate_strategy_file() は使わず apply_strategy_overrides() によるランタイム一時上書きで評価する方式を固定

---

### 探索専用GUI（explore_gui.py）

* layer: gui
* status: implemented

* related_files:
  * src\explore_gui.py（TASK-0067 で新規作成済み）
  * src\explore_gui_app\__init__.py（TASK-0067 で新規作成済み）
  * src\explore_gui_app\views\__init__.py（TASK-0067 で新規作成済み）
  * src\explore_gui_app\views\main_window.py（TASK-0067 で新規作成済み、TASK-0074/0076/0078/0132/0137/0139/0141 で更新）
  * src\explore_gui_app\views\input_panel.py（TASK-0067 で新規作成済み）
  * src\explore_gui_app\views\result_panel.py（TASK-0067 で新規作成済み、TASK-0075 で修正）
  * src\explore_gui_app\views\parameter_dialog.py（パラメータ範囲編集ダイアログ）
  * src\explore_gui_app\views\analysis_panel.py（TASK-0137 で新規作成、TASK-0141 / S-3 で共通 `MeanReversionSummaryWidget` へリファクタ）
  * src\explore_gui_app\views\backtest_panel.py（TASK-0139 で新規作成。タブ B「Backtest 単発」: 探索結果 1 候補の単発検証専用パネル。重複許容方針に従い `backtest_gui_app` 側 `InputPanel` / `SummaryPanel` をコピー方式で再実装）
  * src\gui_common\widgets\mean_reversion_summary_widget.py（TASK-0141 / S-3 で新規作成。AnalysisPanel / SummaryPanel から共有される MR 11 項目表示ウィジェット）
  * src\backtest\exploration_loop.py（既存・接続先、TASK-0074/0076/0077 で更新）

* completion_links:
  * 6. 品質
  * 9. 将来拡張（MVP後）— GUI 統合部分

* task_split_notes:
  * 既存 backtest_gui.py / backtest_gui_app は単発バックテスト・全月集計・A/B比較の責務を持ち、探索ループとは責務が異なるため別エントリポイントとして分離する
  * エントリポイント: src\explore_gui.py、内部パッケージ: src\explore_gui_app（backtest_gui_app とは独立）
  * 初期スコープ（A単体探索）:
    * bollinger_range_v4_4 を対象とした A単体パラメータ探索
    * 探索回数 / improve回数 / variation数 / seed の入力
    * 固定パラメータ / 探索対象パラメータ / 範囲 / 刻みの設定
    * 実行中ログの表示
    * iteration ごとの結果一覧表示
    * 上位候補の確認
  * 後続拡張:
    * B単体探索（bollinger_trend_B 系） → TASK-0085 で実装済み（戦略選択UI追加）
    * A/B組み合わせ探索
    * apply_params.py による採択結果の恒久反映導線

* notes:
  * 探索ループ（exploration_loop.py）は CLI ベースで動作確認済み（TASK-0042/TASK-0062）
  * GUI 化により探索条件の視覚的設定と結果の比較観察を可能にする
  * 既存 backtest_gui.py への機能追加（タブ追加等）ではなく、別画面として新規作成する方針
  * 3レーン以上への拡張は行わない
  * [TASK-0067 実装済み] explore_gui.py エントリポイントと explore_gui_app パッケージ基本骨格（main_window / input_panel / result_panel）を新規作成。BollingerLoopConfig 経由で run_bollinger_exploration_loop に接続する GUI フレームを構築済み
  * [TASK-0069 修正済み] exploration_loop.py の BOLLINGER_PARAM_VARIATION_RANGES をローカルコピー方式（copy.deepcopy）に修正し、モジュールグローバル dict の汚染を防止
  * [TASK-0070 修正済み] main_window.py の BOLLINGER_PARAM_VARIATION_RANGES 直接書き換えを除去し、BollingerLoopConfig.param_variation_ranges 経由のローカルコピー方式に修正。GUI からの2回連続探索でもパラメータ範囲が初期値から一致するようになった
  * [TASK-0072 残課題整理] 残課題一覧（初期スコープ分は TASK-0073〜0078 で全件解消済み）:
    * GUI 実機起動確認 → TASK-0073 で解消
    * Stop ボタンの即時停止 → TASK-0074 で解消（exploration_loop に thread 引数・isInterruptionRequested チェックを追加）
    * B単体探索・A/B組み合わせ探索・apply_params.py 連携は後続拡張スコープ（初期スコープ外）
  * [TASK-0073 起動確認済み] GUI 実機起動確認を実施。PySide6 ウィンドウ描画正常、input_panel / result_panel 正常表示。起動不能バグなし
  * [TASK-0074 実装済み] exploration_loop に thread 引数を追加し、各イテレーションで isInterruptionRequested をチェック。Stop ボタンによる即時停止を実現
  * [TASK-0075 修正済み] 探索フロー全通し確認を実施し、result_panel の win_rate 表示フォーマットバグを修正
  * [TASK-0076 実装済み] on_iteration_done コールバックを追加し、iteration_done Signal によるリアルタイム結果表示を実現
  * [TASK-0077 修正済み] on_iteration_done コールバック呼び出しに例外ハンドリングを追加し、コールバック例外でループが停止しないよう安全化
  * [TASK-0078 実装済み] 進捗表示（Iteration N / M）をステータスバーに追加
  * [TASK-0079 昇格判定] 初期スコープ6項目すべての充足を確認し、status を partial → implemented に更新
  * [TASK-0085 実装済み] 戦略選択コンボボックスを input_panel に追加し、bollinger_trend_B を選択可能にした。パラメータ表示・ParameterDialog は選択戦略に応じて動的に切り替わる。後続拡張の B単体探索対応が完了
  * [TASK-0132 実装済み / 2026-04-17] `src/explore_gui_app/views/main_window.py` の MainWindow をトップレベル QTabWidget 化し、3 タブ構成（A: Explore / B: Backtest 単発 / C: Analysis）を導入。タブ A に既存 `ExploreInputPanel` / `ExploreResultPanel` を収容、タブ B / C は placeholder（空 QWidget）として設置。タブ D「Apply」は TASK-0131 確定方針（Phase 3 帰属）に従い未設置。詳細は `project_core/explore_gui主導移行マップ.md` §11-1 T-A を参照
  * [TASK-0137 実装済み / 2026-04-17] タブ C の中身として `AnalysisPanel` を新規作成し、Phase 2 finished_ok 後の全月合算 MR サマリー 11 項目を表示。`_MRAnalysisWorker`（QThread）非同期パスを `main_window.py` に追加
  * [TASK-0139 実装済み / 2026-04-17] タブ B の中身として `BacktestPanel` を新規作成し、直近採択候補の `strategy_name` + `param_overrides` + CSV 経路を自動転送する `_push_candidate_to_backtest_panel` フックを `main_window.py` に追加。`_BacktestWorker`（QThread）で `run_backtest` / `run_all_months` を非同期実行
  * [TASK-0141 実装済み / 2026-04-18] T-D / S-3 として `AnalysisPanel` の MR 11 項目グリッド + `set_summary` 実装を新規共通ウィジェット `gui_common.widgets.mean_reversion_summary_widget.MeanReversionSummaryWidget` へ切り出し、`AnalysisPanel` は外枠タイトル + 共通ウィジェットを配置する薄いコンテナに縮約。`backtest_gui_app.views.summary_panel.SummaryPanel` も同共通ウィジェットを参照するため、TASK-0137 申し送りで残っていた『MR 表示ロジックの 2 系統並存』が解消された（`set_summary(MeanReversionSummary | None)` の dataclass 直渡し方式でデータフロー統一）

---

### 複数月評価フロー（CSV選択モード・2段階探索）

* layer: gui / usecase
* status: implemented

* related_files:
  * src\explore_gui_app\views\input_panel.py
  * src\explore_gui_app\views\main_window.py
  * src\backtest\exploration_loop.py
  * src\explore_gui_app\views\result_panel.py
  * .claude_orchestrator\docs\project_core\複数月評価フロー方針.md

* completion_links:
  * 3. GUI最適化支援機能

* task_split_notes:
  * Step 1: CSV選択モード（Selected 3 months / All CSVs / Custom）の GUI 導入と BollingerLoopConfig への csv_paths フィールド追加。exploration_loop で csv_paths を csv_dir より優先する分岐追加
  * Step 2: 2段階フロー（Phase 1: 探索 / Phase 2: 確認）の明示化。GUI に Phase 表示と全期間確認導線を追加
  * Step 3: refine の複数月集約ベース強化。Phase 1/Phase 2 結果の区別表示と最終採択判定支援

* notes:
  * TASK-0087 で方針文書（複数月評価フロー方針.md）を作成済み。TASK-0088 director approve 済み
  * 現状の探索フローは単一CSV中心であり、複数月安定性が主軸になっていない
  * csv_paths / csv_path / csv_dir の3フィールド優先順位ロジック確定済み（TASK-0090）: csv_paths > csv_dir > csv_path。csv_paths 指定時は csv_path = csv_paths[-1]（最新CSV）。詳細は複数月評価フロー方針.md 参照
  * IntegratedThresholds (min_avg_pips_per_month=150) が3ヶ月評価でも妥当かは実データ検証が必要（TASK-0088 carry_over）
  * [TASK-0091 実装済み] BollingerLoopConfig / BollingerExplorationConfig / ExplorationConfig / LoopConfig の4 dataclass に csv_paths: list[str] | None フィールドを追加。csv_paths > csv_dir > csv_path の優先分岐ロジックを _resolve_csv_files ヘルパーで実装完了（Step 1 バックエンド部分）。GUI 側の CSV 選択モード実装は後続タスク
  * [TASK-0094 実装済み] Step 2: Phase 表示（Phase 1: 探索中 / Phase 2: 確認中）を result_panel に追加。「全期間で確認する」ボタンを input_panel に追加し、Phase 1 完了後に有効化。Phase 2 は Phase 1 上位候補を csv_dir 全 CSV で再評価する _Phase2Worker で実行。result_panel に月別内訳テーブルと Phase 2 結果テーブルを追加。exploration_loop.py のバックエンドロジックは変更なし
  * [TASK-0095 実装済み] Step 3: Phase 1/Phase 2 結果の verdict 別色分け表示を追加。Phase 2 完了後に全期間集約サマリーパネル（総pips・PF・月別ばらつき・赤字月数・MFE/MAE ratio・採択判定）を表示。refinement.py の score_cross_month() が integrated_evaluation を優先参照する既存設計を確認・活用。全 Step 完了により status を implemented に昇格

### 統合運用GUI方針（explore_gui 主導）

* layer: gui / usecase
* status: partial

* related_files:
  * src\explore_gui.py
  * src\explore_gui_app\views\main_window.py
  * src\explore_gui_app\views\input_panel.py
  * src\explore_gui_app\views\result_panel.py
  * src\backtest\service.py
  * src\backtest\exploration_loop.py
  * src\backtest\mean_reversion_analysis.py
  * src\backtest_gui.py
  * src\backtest_gui_app\views\main_window.py

* completion_links:
  * 3. GUI最適化支援機能
  * 5. 操作性
  * 9. 将来拡張（MVP後）

* task_split_notes:
  * 現状は backtest_gui.py 側に単発バックテスト・全月表示・比較表示が集まり、explore_gui.py 側に探索機能が分離して存在している
  * 今後は explore_gui.py を主画面候補として位置付け、バックテスト・探索・パラメータ調整・分析確認を集約する方向で整理する
  * 既存機能を即時統合するのではなく、まずは「どの画面を主導線にするか」を固定し、必要機能を段階的に explore_gui 側へ寄せる
  * backtest_gui.py は過渡的に維持しつつ、責務の再整理対象として扱う

* notes:
  * 目的は「機能が各所に散らばった状態」を解消し、探索・調整・確認の中心を explore_gui 側へ集約すること
  * 単なる見た目変更ではなく、GUI導線全体の再編方針に関するエントリ
  * 最終的には、必要な機能だけを美しく表示する統合運用GUIへ発展させる前提
  * [TASK-0121 追加] 移行マップを `project_core/explore_gui主導移行マップ.md` に新規作成。機能3分類（移す/残す/保留）、Phase 1〜3 移行プラン、不足部品の洗い出しを整理。本エントリの後続タスクはこのマップを分解単位として使用
  * [TASK-0130 追加] 同マップに §8〜12 を追記し、(1) 4層モデル（バックテスト/探索/分析/実運用）の責務と接続点、(2) explore_gui 統合後の画面構成案（Phase 1/2/3 の各タブ構成）、(3) 実運用層 (L4) の安全制御方針（GUI から `command_writer` を直接呼ばない・`apply_params.py` を `--dry-run` → 確認ダイアログ → `--backup` で書き込み・既存 `command_guard` を bypass する API を作らない）、(4) Phase 2 着手用の次タスク分解 T-A〜T-I と推奨着手順、(5) 非対象範囲・既知リスク・director 確認候補を明文化。後続実装タスクは本マップ §11 を分解単位として使用
  * [TASK-0131 追加 / 2026-04-17] Phase 2 着手前の director 事前判断 3 点を確定: (a) Compare A/B（T-F）は backtest_gui 側に残置で確定（Phase 2 非対象）、(b) タブ B「Backtest 単発」(T-C) は重複許容で進めるが用途を「探索結果の 1 候補を単発検証」に限定、(c) タブ D「Apply」(T-G) は Phase 3 帰属に確定（Phase 2 完了時点のタブ構成は A/B/C の 3 タブ）。詳細根拠と再評価トリガは `project_core/explore_gui主導移行マップ.md` §11 各サブタスクおよび §12-3 を参照
  * [TASK-0132 実装済み / 2026-04-17] §11-1 T-A（トップレベル QTabWidget 化）完了。`src/explore_gui_app/views/main_window.py` で 3 タブ構成（A: Explore / B: Backtest 単発 / C: Analysis）を導入し、タブ A に既存 `ExploreInputPanel` / `ExploreResultPanel` を収容、タブ B / C は placeholder（空 QWidget）として設置。タブ D「Apply」は TASK-0131 確定方針に従い Phase 3 帰属で未設置（空フレームも配置しない）。後続の T-B / T-C サブタスクで各 placeholder タブの中身を実装する


### バックテスト・探索・実運用統合アプリ構想

* layer: gui / usecase / infrastructure
* status: not_implemented

* related_files:
  * src\explore_gui.py
  * src\explore_gui_app\views\main_window.py
  * src\app_watch.py
  * src\app_watch_gui.py
  * src\app_cli.py
  * src\mt4_bridge\services\bridge_service.py
  * src\mt4_bridge\snapshot_reader.py
  * src\mt4_bridge\command_writer.py
  * src\mt4_bridge\runtime_state.py
  * src\backtest\service.py
  * src\backtest\exploration_loop.py
  * src\backtest\mean_reversion_analysis.py

* completion_links:
  * 5. 操作性
  * 8. データ整合性
  * 9. 将来拡張（MVP後）

* task_split_notes:
  * 最終ゴールは、バックテスト・探索・パラメータ調整・実トレード監視/実行を1つの統合アプリとして扱えるようにすること
  * 初期段階では、explore_gui 側にバックテスト/探索/分析機能を整理し、実運用系（app_watch.py / app_watch_gui.py）は未統合のまま維持する
  * 次段階で、MT4 ブリッジ監視や runtime 状態表示、実行中パラメータ確認などを explore_gui 主導の統合画面へ取り込む方針を検討する
  * 実トレード実行機能の直接統合は高リスクのため、GUI統合・状態可視化・安全制御の設計を先行させる

* notes:
  * 現時点では構想段階であり、実装済みではないため status は not_implemented
  * 目的は「調整しながらトレードを行う」統合運用環境の実現
  * app_watch.py 側の実運用責務と backtest/explore 側の分析責務を混ぜる前に、役割分離と接続点を設計する必要がある
  * このエントリは今後のオーケストラ設計・機能集約の基準点として使う
  * [TASK-0121 追加] 本構想の段階的移行プラン（Phase 1: 共有基盤切り出し / Phase 2: explore_gui 主導線化 / Phase 3: 実運用監視統合）を `project_core/explore_gui主導移行マップ.md` に記載。Phase 3 は本エントリ配下の実装候補として扱う
  * [TASK-0130 追加] 同マップ §8（4層モデル）・§10（実運用統合の安全制御方針）が本エントリの「役割分離と接続点を設計する必要がある」「GUI統合・状態可視化・安全制御の設計を先行させる」を具体化。Phase 3 の実装候補（タブ E「Live」追加 / read-only runtime 表示 → watch start/stop 取り込み → apply_params GUI 導線 → coordinated apply の段階導入順）も §10-2 に明示済み

---

### 観測用パラメータ定義（bollinger_range_v4_4_params.py）

* layer: domain
* status: implemented

* related_files:
  * src\mt4_bridge\strategies\bollinger_range_v4_4_params.py

* completion_links:
  * 6. 品質

* task_split_notes:
  * [TASK-0106 実装済み] bollinger_range_v4_4_params.py に観測用パラメータ 13 個を追加。売買ロジックには影響しない設定値群
  * 追加パラメータ一覧:
    * MEAN_REVERSION_LOOKAHEAD_BARS_LIST（中央回帰事後検証の先読みバー数リスト）
    * MEAN_REVERSION_TOUCH_EPSILON（バンド端タッチ判定の許容誤差）
    * BAND_WALK_LOOKBACK_BARS（バンドウォーク検出の後方参照バー数）
    * BAND_WALK_MIN_HITS（バンドウォーク判定の最小ヒット数）
    * BAND_EDGE_ZONE_RATIO（バンド端 zone 幅の比率）
    * MIDDLE_CROSS_LOOKBACK_BARS（ミドルライン横断確認の後方参照バー数）
    * ONE_SIDE_STAY_LOOKBACK_BARS（片側滞在確認の後方参照バー数）
    * BAND_WIDTH_EXPANSION_LOOKBACK_BARS（バンド幅拡大検出の後方参照バー数）
    * BAND_WIDTH_EXPANSION_THRESHOLD（バンド幅拡大判定の変化率しきい値）
    * TREND_SLOPE_ACCEL_LOOKBACK_BARS（トレンド傾き加速度計算の後方参照バー数）
    * TREND_SLOPE_ACCEL_THRESHOLD（加速度有意判定のしきい値）
    * PROGRESS_CHECK_BARS（エントリー後中央回帰進捗確認バー数）
    * MIN_PROGRESS_TO_MIDDLE_RATIO（進捗率しきい値）

* notes:
  * 後続の観測関数（TASK-0107）で参照される設定値。既存の売買用パラメータとは独立した観測専用セクションとして追加

---

### 観測用純粋関数（bollinger_range_v4_4_indicators.py）

* layer: domain
* status: implemented

* related_files:
  * src\mt4_bridge\strategies\bollinger_range_v4_4_indicators.py
  * src\mt4_bridge\strategies\bollinger_range_v4_4_params.py

* completion_links:
  * 6. 品質

* task_split_notes:
  * [TASK-0107 実装済み] bollinger_range_v4_4_indicators.py に観測用純粋関数 7 個を追加。既存売買ロジックには接続しない
  * 追加関数一覧:
    * _calculate_band_walk_stats（バンドウォーク統計: upper/lower ヒット数・比率）
    * _calculate_middle_cross_stats（ミドルライン横断統計: 横断回数・有無）
    * _calculate_one_side_stay_stats（片側滞在統計: above/below 比率・完全片側判定）
    * _calculate_band_width_expansion_ratio（バンド幅拡大比率: 現在/過去バンド幅・拡大率）
    * _calculate_trend_slope_acceleration_ratio（トレンド傾き加速度: 現在/過去傾き・加速比率）
    * _calculate_progress_to_middle（中央回帰進捗: 進捗率・距離・正規化進捗）
    * _check_mean_reversion_lookahead（中央回帰先読み検証: N バー以内の回帰成否）

* notes:
  * 全関数が副作用のない純粋関数で、count/ratio/数値指標を dict で返す設計
  * 観測用パラメータ（TASK-0106）を参照。後続タスクで decision log 出力への接続や中央回帰分析での利用が予定されている
### RangeObservation 構造化観測オブジェクト

* layer: domain
* status: implemented

* related_files:
  * src\mt4_bridge\strategies\bollinger_range_v4_4_rules.py
  * src\mt4_bridge\strategies\bollinger_range_v4_4.py

* completion_links:
  * 6. 品質
  * 4. ログ・追跡・最終統合機能

* task_split_notes:
  * [TASK-0109 実装済み] A戦術の現在バー時点の観測値を構造化して保持する `RangeObservation` dataclass を `bollinger_range_v4_4_rules.py` に追加
  * `build_range_observation(...)` により、market_state / band 情報 / slope / band walk / middle cross / one-side-stay / bandwidth expansion / slope acceleration / range_unsuitable_flag 群を1オブジェクトへ集約
  * `range_observation_to_dict(...)` を追加し、後続の debug_metrics / decision log 接続に使える辞書化導線を用意

* notes:
  * 観測値を自然文ではなく構造化オブジェクトとして扱う基盤
  * 売買判定ロジックそのものには未接続であり、観測保持専用の責務として導入
  * 後続タスクで decision log / trade log / 中央回帰分析基盤へ接続予定

### A戦術観測値の strategy 接続（debug_metrics 経由）

* layer: domain / infrastructure
* status: partial

* related_files:
  * src\mt4_bridge\strategies\bollinger_range_v4_4.py
  * src\mt4_bridge\models.py
  * src\mt4_bridge\strategies\bollinger_range_v4_4_rules.py
  * src\mt4_bridge\strategies\bollinger_range_v4_4_indicators.py

* completion_links:
  * 4. ログ・追跡・最終統合機能
  * 6. 品質

* task_split_notes:
  * [TASK-0110 実装済み] `bollinger_range_v4_4.py` の共通評価フローから `build_range_observation(...)` を呼び出す接続を追加
  * 観測計算関数（band walk / middle cross / one-side-stay / bandwidth expansion / trend slope acceleration）を利用して `RangeObservation` を毎バー生成
  * 生成した観測値は `range_observation_to_dict(...)` により辞書化し、`SignalDecision.debug_metrics` に格納
  * `SignalDecision` に正式フィールド追加は行わず、既存の `debug_metrics` 拡張口を利用

* notes:
  * strategy 本体から観測値を外部露出できる状態までは到達済み
  * ただし `decision_log.py` / `trade_logger.py` / `BacktestDecisionLog` / `ExecutedTrade` への正式保存は未接続
  * 観測生成失敗時の扱いは売買判定優先であり、追跡性強化（logger.debug 等）は後続改善対象
  * decision log への正式保存が未完のため status は partial

---

### Aエントリー後の中央回帰成否集計基盤

* layer: domain
* status: implemented

* related_files:
  * src\backtest\mean_reversion_analysis.py
  * src\backtest\simulator\models.py
  * src\backtest\csv_loader.py
  * src\backtest\service.py
  * src\backtest_gui_app\views\summary_panel.py
  * src\backtest_gui_app\presenters\result_presenter.py
  * src\mt4_bridge\strategies\bollinger_range_v4_4_indicators.py

* completion_links:
  * 6. 品質

* task_split_notes:
  * [TASK-0112 実装済み] A戦術（range レーン）エントリー後の中央回帰成否を定量集計する post-analysis 基盤を新規作成
  * `analyze_mean_reversion(result, dataset)` で BacktestResult + HistoricalBarDataset からレンジレーントレードを抽出し、各トレードの中央回帰成否を分析
  * `summarize_mean_reversion(records)` でトレード単位の分析結果を集約統計に変換
  * 集計対象: bars_to_mean_reversion / success_within_3,5,8,12 / max_progress_to_middle_ratio / max_adverse_excursion_from_entry
  * 既存売買ロジック・バックテスト結果への影響なし
  * [TASK-0113 実装済み] `analyze_all_months_mean_reversion(monthly_artifacts)` を追加し、`AllMonthsResult.monthly_artifacts` から月別 `MeanReversionSummary` と全期間合算 `MeanReversionSummary` を一括取得できる導線を作成。返り値は新規 dataclass `AllMonthsMeanReversionSummary(monthly, all_period)`。全期間合算は全月のレコードを再集計するため平均系指標は全期間分布に基づく。range トレード0件の月は空 `MeanReversionSummary` を返す。`run_all_months` / `AllMonthsResult` の構造は変更していない

* notes:
  * entry_middle_band を回帰目標として使用（エントリー時点の middle band 固定値）
  * 到達判定: buy → close >= middle, sell → close <= middle
  * 到達失敗時は bars_to_mean_reversion = None, success_within_N = False
  * [TASK-0113] `BacktestRunArtifacts` を読むため `backtest.service` を `TYPE_CHECKING` 下で import し循環参照を回避
  * [TASK-0114] runner.py CLI (--csv-dir) 経由で AllMonthsMeanReversionSummary 表示に対応済み（_print_mean_reversion_summary_block / print_all_months_mean_reversion_summary）
  * [TASK-0115] backtest_gui_app の All Months タブに AllMonthsMeanReversionSummary 表示を接続済み。AllMonthsWorker で run_all_months 後に analyze_all_months_mean_reversion を実行し、monthly_table に MR 5列（Trades / Fail / Succ≤5 / Rate≤5 / Avg Bars）＋ 全期間 MR パネルを追加。CLI の _print_mean_reversion_summary_block と同じ指標セットを GUI で表示。MR 分析失敗時は空パネル ("N/A") にフォールバック。採択判定ロジックへの接続は引き続き後続タスクスコープ
  * [TASK-0119] 単月バックテストでも MeanReversionSummary を確認できるよう、`run_backtest` 内で `summarize_mean_reversion(analyze_mean_reversion(...))` を実行し、`BacktestRunArtifacts.mean_reversion_summary: MeanReversionSummary | None` を追加。Standard 画面の SummaryPanel に折りたたみ式「Mean reversion (range lane)」セクションを追加し、BacktestResultPresenter から total_range_trades / success/fail カウント・success_rate・success_within_3/5/8/12 (count + %)・avg_bars_to_reversion・avg_max_progress_ratio・avg_max_adverse_excursion を表示。range トレード0件でも安全に "0" / "N/A" が出るよう MeanReversionSummary 側の None 表現に従う。分析失敗時は artifacts 側で None にフォールバックし GUI 表示は全て "N/A"。停止条件・採択ロジックへの自動反映は引き続き後続タスクスコープ

---

## planner / plan_director 用ルール

### planner

* `implemented` を未実装として提案しない
* `gui_unconnected` は導線補完として扱う
* `partial` は不足箇所を具体化する
* `out_of_scope` は mainline で優先しない

### plan_director

* `implemented` は重複として減点
* `gui_unconnected` は導線補完として評価
* `partial` は completion_definition との接続で評価
* `not_implemented` は完成条件への寄与で評価

---

## 更新ルール

* task 完了後に更新する
* 状態を曖昧にしない
* completion_definition と整合させる
* 重複機能を作らない
