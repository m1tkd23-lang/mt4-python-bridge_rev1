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
* status: partial

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

---

### GUI パラメータ変更・即時再計算

* layer: gui / usecase
* status: partial

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
  * [TASK-0010 ギャップ分析] パラメータ変更検知による自動再計算は未実装（ボタン押下式のみ）。completion_definition の「即時反映」がボタン押下式で許容されるか自動再計算が必要かの方針が未決定

* notes:
  * 戦術固有パラメータの GUI 変更 UI は TASK-0017 で実装済み。戦術選択変更時にパラメータ UI が動的に切り替わる
  * [TASK-0018 実装済み] All Months タブからの全月一括実行時にも戦術パラメータオーバーライドに対応。InputPanel の GUI 値を AllMonthsWorker に dict で引数渡しし、各月の run_backtest() 内で apply_strategy_overrides コンテキストマネージャにより適用・復元

---

### 構造化ログ出力（trade_id / lane_id / reason_code）

* layer: domain / infrastructure
* status: partial

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

* notes:
  * decision_log.py は各バーの判定記録として維持。trade_logger.py はトレード単位のライフサイクルログとして独立

---

### trade_id によるトレード追跡

* layer: domain
* status: partial

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

* notes:
  * trade_id はオプショナルフィールド（デフォルト None）であり、既存コードとの後方互換性を維持

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
* status: partial

* related_files:
  * src\backtest_gui_app\views\main_window.py
  * src\backtest\simulator\engine.py

* completion_links:
  * 5. 操作性

* task_split_notes:
  * GUI は存在し単月バックテストは実行可能だが、パラメータ変更→即時再計算の応答速度は未検証
  * V7 fast-path 最適化が simulator に存在し、高速化の素地はある

* notes:
  * 複数月一括評価の実行時間も未検証

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
* status: not_implemented

* related_files:
  * src\backtest\evaluator.py
  * src\backtest\exploration_loop.py
  * src\explore_cli.py
  * src\mt4_bridge\strategy_generator.py

* completion_links:
  * 6. 品質

* task_split_notes:
  * exploration_loop.py + strategy_generator.py で戦術パラメータ探索の仕組みは存在
  * ただし「月平均150〜200pips」という基準での全月横断評価は未実装
  * 全月合算でプラス・赤字月非連続・月別ばらつき抑制等の安定性評価は未実装

* notes:
  * 探索の枠組みは存在するが、completion_definition の品質基準を満たす評価ロジックが不足

---

### 全月安定性評価（赤字月非連続・ばらつき抑制）

* layer: usecase
* status: partial

* related_files:
  * src\backtest\aggregate_stats.py

* completion_links:
  * 6. 品質

* task_split_notes:
  * aggregate_stats.py に deficit_month_count（赤字月数）・max_consecutive_deficit_months（赤字月連続数）・monthly_pips_stddev（月別ばらつき標準偏差）を実装済み
  * 採択条件としての全月合算成績＋月別安定性の両立評価は未実装

* notes:
  * 安定性指標の算出ロジックは aggregate_stats.py に実装済みだが、閾値判定・採択基準への組み込みは未実装

---

### エラー処理・耐障害性

* layer: infrastructure
* status: partial

* related_files:
  * src\mt4_bridge\snapshot_reader.py
  * src\mt4_bridge\stale_detector.py
  * src\mt4_bridge\command_guard.py
  * src\backtest\simulator\models.py

* completion_links:
  * 7. エラー処理・耐障害性

* task_split_notes:
  * snapshot_reader.py で JSON パースエラー処理済み
  * stale_detector.py でデータ鮮度検出・ブロック済み
  * command_guard.py で重複信号防止済み
  * ただし completion_definition の「ログが取れないロジックは採択しない」「構造化項目 reason_code 必須」は未実装

* notes:
  * リアルタイム側のエラー処理は比較的充実しているが、ログ品質制約の実装は不足

---

### データ整合性（シミュレーターと MT4 の挙動一致）

* layer: domain / infrastructure
* status: partial

* related_files:
  * src\mt4_bridge\models.py
  * src\backtest\simulator\engine.py
  * MT4\MQL4\Experts\BridgeWriterEA.mq4

* completion_links:
  * 8. データ整合性

* task_split_notes:
  * models.py でシミュレーター・リアルタイム共通のデータモデルを定義
  * BridgeWriterEA.mq4 がMT4側のブリッジとして存在
  * ただし event_type / reason_code / lane_id / trade_id のログ概念一致は未実装
  * 「シミュレーター専用の曖昧な簡略判定を避ける」は設計方針であり、現状の実装での乖離有無は精査が必要

* notes:
  * MT4側（MQL4）と Python 側の構造的な対応は取れているが、ログ意味体系の一致は未達

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
  * 3. GUI最適化支援機能
  * 6. 品質

* task_split_notes:
  * exploration_loop.py で生成→バックテスト→評価のサイクルが実装済み
  * strategy_generator.py でパラメータ変化戦術の自動生成が実装済み
  * bac/ 配下に自動生成された戦術ファイルが60件以上存在
  * ただし GUI 経由の探索統合は未実装

* notes:
  * CLI ベースの探索は動作するが、GUI 統合・全月横断評価との接続は未実装

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
