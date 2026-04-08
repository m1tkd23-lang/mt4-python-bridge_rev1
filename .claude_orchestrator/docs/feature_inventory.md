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

---

### A単体・B単体・A+B合成成績比較

* layer: usecase
* status: not_implemented

* related_files:
  * （該当なし）

* completion_links:
  * 2. 評価・比較機能

* task_split_notes:
  * A単体/B単体の個別実行は可能だが、結果を並べて比較する仕組みが未実装
  * A+B合成成績の算出・比較ロジックが未実装

* notes:
  * combo_AB 戦術は A/B を統合実行するが、個別レーンの成績分離比較は未対応

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
  * パラメータ変更後の即時再計算・反映の実装度合いは要確認
  * 月別成績表・全体成績・損益推移の表示が completion_definition の要件を満たすか要確認

* notes:
  * GUI の基本骨格は存在するが、completion_definition が要求する全項目を満たしているかは精査が必要

---

### GUI パラメータ変更・即時再計算

* layer: gui / usecase
* status: partial

* related_files:
  * src\backtest_gui_app\views\input_panel.py
  * src\backtest_gui_app\services\run_config_builder.py

* completion_links:
  * 3. GUI最適化支援機能

* task_split_notes:
  * input_panel.py で戦術・CSV選択は可能
  * 主要パラメータ（ボリンジャー周期・σ等）を GUI 上で変更して即時再計算する仕組みの有無は要確認
  * パラメータ変更 UI が不足している場合は追加実装が必要

* notes:
  * 現状の GUI は戦術ファイル選択方式であり、個別パラメータの動的変更 UI は限定的と推定

---

### 構造化ログ出力（trade_id / lane_id / reason_code）

* layer: domain / infrastructure
* status: not_implemented

* related_files:
  * src\backtest\simulator\decision_log.py

* completion_links:
  * 4. ログ・追跡・最終統合機能

* task_split_notes:
  * decision_log.py は各バーの判定結果（action, reason, market_state 等）を記録するが、completion_definition が要求する構造化ログ仕様（trade_id, lane_id, reason_code, event_type 等）には未対応
  * JSON Lines / CSV 形式での機械集計可能なログ保存は未実装
  * 「なぜエントリーしたか」「なぜ見送ったか」「なぜ決済したか」の追跡は decision_log の reason フィールドで部分的に可能だが、completion_definition の粒度には不足

* notes:
  * decision_log.py は基礎的な判定記録であり、completion_definition が定義する event_type / reason_code / indicators 等のフル仕様ログとは別物

---

### trade_id によるトレード追跡

* layer: domain
* status: not_implemented

* related_files:
  * （該当なし）

* completion_links:
  * 4. ログ・追跡・最終統合機能

* task_split_notes:
  * 現在のシミュレーターは ExecutedTrade で結果を保持するが、一意な trade_id の付与・ライフサイクル追跡は未実装
  * completion_definition の TRADE_CLOSED イベント仕様（entry_reason_code, exit_reason_code, holding_bars, MFE/MAE 等）は未実装

* notes:
  * なし

---

### 最終統合（採択結果の bollinger_combo_AB.py 反映）

* layer: usecase
* status: not_implemented

* related_files:
  * src\mt4_bridge\strategies\bollinger_combo_AB.py

* completion_links:
  * 4. ログ・追跡・最終統合機能

* task_split_notes:
  * bollinger_combo_AB.py は存在するが、評価上位の A/B 組み合わせを確定して反映するワークフローは未実装
  * 再実行時の結果再現性の検証手段も未実装

* notes:
  * 戦術ファイル自体は存在するため、パラメータ確定・書き込みのプロセスが必要

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
