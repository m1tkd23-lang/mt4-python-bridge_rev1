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

* notes:
  * 戦術バリエーションが多く、最終採択の絞り込みは未実施

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
  * src\backtest_gui_app\widgets\chart_widget.py
  * src\backtest_gui_app\widgets\price_chart_widget.py
  * src\backtest_gui_app\widgets\time_series_chart_widget.py
  * src\backtest_gui_app\widgets\linked_trade_chart_widget.py
  * src\backtest_gui_app\widgets\collapsible_section.py
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
  * src\backtest_gui_app\services\strategy_params.py

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
  * src\backtest_gui_app\services\strategy_params.py

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
  * ただし GUI 経由の探索統合は未実装

* notes:
  * CLI ベースの探索は動作するが、GUI 統合は未実装
  * [TASK-0041 方針明文化] 探索ループの主対象を bollinger 系既存戦術に切り替える方針を明文化。詳細は `project_core/最適化方針_bollinger戦略.md` を参照
  * [TASK-0042 実装済み] TASK-0041 方針に基づき、exploration_loop.py に bollinger 系パラメータオーバーライド探索モード（run_bollinger_exploration / run_bollinger_exploration_loop / generate_bollinger_param_variations / BOLLINGER_PARAM_VARIATION_RANGES）を実装完了。既存戦術 + パラメータオーバーライド方式での探索が可能になった。~~実データ CSV を用いた結合テストは未実施（後続タスクで対応必須）~~ → TASK-0062 で A単体結合テスト6項目全PASSにより解消済み（2026-04-10）
  * [TASK-0061 方針明文化] ボリンジャー専用 exploration_loop 方針を `project_core/最適化方針_bollinger戦略.md` に明文化。探索フローは「A単体→B単体→A/B組み合わせ→combo_AB反映」の4段階。generate_strategy_file() は使わず apply_strategy_overrides() によるランタイム一時上書きで評価する方式を固定

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
