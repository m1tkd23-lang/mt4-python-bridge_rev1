# feature_inventory

最終更新日: 2026-04-21 (v4)

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

### A戦略（レンジ反転、bollinger_range_A）

* layer: domain
* status: implemented (要 Walk-Forward 検証, 要スプレッド影響測定)

* related_files:
  * src/mt4_bridge/strategies/bollinger_range_A.py
  * src/mt4_bridge/strategies/bollinger_range_v4_4.py
  * src/mt4_bridge/strategies/bollinger_range_v4_4_params.py
  * src/mt4_bridge/strategies/bollinger_range_v4_4_indicators.py
  * src/mt4_bridge/strategies/bollinger_range_v4_4_rules.py

* completion_links:
  * MVP 1. 戦略設計とファイル構造
  * MVP 2. バックテスト・最適化

* task_split_notes:
  * 入口: 2σ再突入のみ (3σ即時は無効化)
  * 対策①〜④ 全て実装・ON (個別 ENABLED フラグで切替可)
    - 対策① trend_up/trend_down state でエントリー抑制
    - 対策② bandwidth_expansion フラグでエントリー抑制
    - 対策③ 時刻フィルタ(broker hour 5/7/13 除外)
    - 対策④ H1 コンテキストフィルタ(H1 mom ±15 pips 閾値で逆張り禁止)
  * リスク定数: `SL_PIPS=20.0`, `TP_PIPS=20.0` をモジュール冒頭に保持
  * Walk-Forward 検証 未実施
  * ライブブローカー時刻との突き合わせ 未実施

* notes:
  * A単体 1年 BT: +708.9 pips / 崩壊月 1 (2025-08 -30.7)
  * A + B 合算 (combo_AB): +983.2 pips / 崩壊月 0 (2026-04-21 v2 更新)

---

### B戦略（トレンド追従、bollinger_trend_B）

* layer: domain
* status: implemented (要 Walk-Forward 検証, 要スプレッド影響測定)

* related_files:
  * src/mt4_bridge/strategies/bollinger_trend_B.py
  * src/mt4_bridge/strategies/bollinger_trend_B_params.py
  * src/mt4_bridge/strategies/bollinger_trend_B_indicators.py
  * src/mt4_bridge/strategies/bollinger_trend_B_rules.py

* completion_links:
  * MVP 1. 戦略設計とファイル構造
  * MVP 2. バックテスト・最適化

* task_split_notes:
  * 2026-04-21: 3分離構造化 + 修正1(TREND_SLOPE_THRESHOLD を 15倍厳格化) + 修正2(H1 順張り必須フィルタ) 実装
  * 2026-04-21 v2: 修正3 (時刻フィルタ) を本番化。`B_TIME_FILTER_ENABLED=True`, `B_ENTRY_BANNED_HOURS={4, 8, 10}`
    - 根拠: 2026-02 の SL 4件が broker hour 4/8/10 に集中、単独寄与 {4}=+0.8, {8}=+20.0, {10}=+18.0 で独立加算
    - 2026-02 崩壊月(-30.1 → +27.9, +58 改善)を解消
  * リスク定数: `SL_PIPS=20.0`, `TP_PIPS=40.0` を `bollinger_trend_B_params.py` に保持(本体で re-export)
  * 設計方針: A の弱点補完に特化、A が入れない H1 明確トレンド中に限定発火
  * 本番稼働は §8 対象外方針を維持(設計・BT のみ実施)

* notes:
  * B 単体 1年 BT: +268.4 pips / 崩壊月 0 (2026-04-21 v2 時点)
  * combo_AB (A+B, lane 別 SL/TP) 1年 BT: +983.2 pips / 崩壊月 0
  * B の発火頻度: 月 0 〜 7件(旧実装の 270件 から 95%+ 削減を維持)

---

### バックテストシミュレータ（backtest.simulator）

* layer: infrastructure
* status: implemented

* related_files:
  * src/backtest/simulator/engine.py
  * src/backtest/simulator/generic_runner.py
  * src/backtest/simulator/position_manager.py
  * src/backtest/simulator/intrabar.py
  * src/backtest/simulator/snapshots.py
  * src/backtest/simulator/stats.py
  * src/backtest/simulator/decision_log.py
  * src/backtest/simulator/trade_logger.py
  * src/backtest/simulator/models.py

* completion_links:
  * MVP 2. バックテスト・最適化
  * MVP 7. データ整合性

* task_split_notes:
  * v7 fast-path は 2026-04-21 に削除済み
  * 2026-04-21 に以下を拡張済み:
    - ExecutedTrade.exit_subtype（middle_touch_exit / range_failure_exit / opposite_state_exit / opposite_signal_exit / tp_upper_2sigma / tp_lower_2sigma / opposite_trend_exit）
    - ExecutedTrade.entry_bar_index / exit_bar_index（データセット上の絶対位置）
    - ExecutedTrade.unsuitable_bars_{band_walk, one_side_stay, bandwidth_expansion, slope_acceleration, total}
  * 2026-04-21 v2 追加:
    - `BacktestSimulator.__init__` に `lane_sl_pips` / `lane_tp_pips` 引数(dict, lane 別明示指定用)
    - `_create_position_from_decision` で `明示引数 > 戦術定数 (risk_config) > simulator fallback` の優先順位で SL/TP 解決

* notes:
  * SL/TP は保険、戦略決済が主体という設計意図に実態も合致（signal_close が 91〜97%）
  * generic path 一本化で見通し改善

---

### CSV ローダー / 連結 BT (backtest.csv_loader)

* layer: infrastructure

* status: implemented

* related_files:
  * src/backtest/csv_loader.py

* completion_links:
  * MVP 2. バックテスト・最適化
  * MVP 7. データ整合性

* task_split_notes:
  * 2026-04-21 v3 追加: `load_historical_bars_csv_multi(paths: list[Path]) -> HistoricalBarDataset`
    複数 CSV を時系列結合、重複時刻は後勝ち、digits/point は全ファイル最大値
  * 月跨ぎ BT でウォームアップ/強制決済の不連続を排除するために使用

* notes:
  * 連結 BT 12 ヶ月総合 (combo_AB): +1043.0 pips / 崩壊月ゼロ / worst 2025-06 (-7.0)
  * 月独立 BT (+983.2) との差分 +59.8 は主に月初 H1 フィルタ不発動のエントリー見逃し回復

---

### バックテスト分析エクスポート（backtest.export）

* layer: infrastructure
* status: implemented

* related_files:
  * src/backtest/export.py

* completion_links:
  * MVP 7. データ整合性

* task_split_notes:
  * 対象: export_trades_csv / export_decision_logs_csv / get_bar_level_logs_for_trade / export_bar_level_log_for_trade
  * 2026-04-21 新規作成

* notes:
  * 分析の手元運用に必要最低限の関数群を提供

---

### バックテストサービス (backtest.service)

* layer: usecase

* status: implemented

* related_files:
  * src/backtest/service.py

* completion_links:
  * MVP 2. バックテスト・最適化

* task_split_notes:
  * 2026-04-21 v3 追加: `run_all_months(..., connected=True)` オプション
    - True 時は全 CSV を `load_historical_bars_csv_multi` で結合 → 1 回の BT 実行 → `trade.entry_time` で月別集計
    - 月跨ぎの強制決済/ウォームアップ不連続を排除、本番相当の見積もりになる
    - artifacts は `[("connected", BacktestRunArtifacts)]` の単一要素リスト
  * False (default) では従来通り月独立 BT、後方互換維持

* notes:
  * combo_AB 連結 BT: +1043.0 / 崩壊月ゼロ (2026-04-21 v3 実測)

---

### バックテストループ・最適化（backtest.exploration_loop / evaluator）

* layer: usecase
* status: partial

* related_files:
  * src/backtest/exploration_loop.py
  * src/backtest/evaluator.py
  * src/backtest/aggregate_stats.py
  * src/backtest/apply_params.py
  * src/backtest/mean_reversion_analysis.py

* completion_links:
  * MVP 2. バックテスト・最適化

* task_split_notes:
  * 評価期間を「1ヶ月・3ヶ月・半年・1年」の4種に統一 未実装
  * 月別崩壊ゼロ判定ロジック 未実装
  * 最悪月劣化度スコア 未実装
  * Walk-Forward 検証 部分実装

* notes:
  * 既存の exploration_loop は A戦略を一定期間回して集計可
  * 4期間ロバストネスのアウトオブサンプル合格判定は未実装

---

### レジーム判定（A/B 共通モジュール）

* layer: domain
* status: not_implemented

* related_files:
  * (新規作成予定: src/mt4_bridge/regime/ 配下)

* completion_links:
  * MVP 4. レジーム判定（A/B 共通の分離モジュール）

* task_split_notes:
  * 現状 v4_4 本体と bollinger_trend_B 内に別々のレジーム判定がある
  * A停止判定と B発動判定の両用モジュールとして切り出す
  * ADX / Efficiency Ratio / BB Width の閾値設計は未定

* notes:
  * 本筋 §3.4 で新設合意された機能

---

### 戦術リスク定数解決（risk_config）

* layer: domain

* status: implemented

* related_files:
  * src/mt4_bridge/strategies/risk_config.py
  * src/mt4_bridge/strategies/bollinger_range_A.py (SL_PIPS/TP_PIPS)
  * src/mt4_bridge/strategies/bollinger_trend_B_params.py (SL_PIPS/TP_PIPS)
  * src/mt4_bridge/strategies/bollinger_combo_AB.py (LANE_STRATEGY_MAP)

* completion_links:
  * MVP 1. 戦略設計とファイル構造
  * MVP 3.5 ライブ運用（後段）

* task_split_notes:
  * 2026-04-21 v2 新規作成
  * `resolve_strategy_risk_pips(strategy_name)` / `resolve_lane_risk_pips(strategy_name, entry_lane)`
  * combo 戦術は `LANE_STRATEGY_MAP` 経由で子戦術の定数に委譲
  * BT simulator と app_cli の両方から呼ばれる

* notes:
  * 設計方針: SL/TP の正本は戦術ファイル。`config/app.yaml` の `risk:` セクションは 2026-04-21 v2 に削除。

---

### アプリ設定（app_config, app_cli）

* layer: infrastructure

* status: implemented

* related_files:
  * config/app.yaml
  * src/mt4_bridge/app_config.py
  * src/app_cli.py

* completion_links:
  * MVP 3.5 ライブ運用（後段）

* task_split_notes:
  * 2026-04-21 v2: `risk:` セクション削除 (戦術ファイル側が正本)
  * `RiskConfig` 削除、`AppConfig.risk` フィールド削除、`MT4_SL_PIPS`/`MT4_TP_PIPS` env var 読取削除
  * `app_cli._build_decision_with_risk`: `sl_pips`/`tp_pips` 引数廃止、戦術定数が None なら `SignalEngineError` を送出

* notes:
  * `app.yaml` 残存セクション: bridge / snapshot / signal / runtime のみ

---

### MT4 ブリッジサービス（mt4_bridge.services.bridge_service）

* layer: infrastructure
* status: implemented

* related_files:
  * src/mt4_bridge/services/bridge_service.py
  * src/mt4_bridge/command_writer.py
  * src/mt4_bridge/result_reader.py
  * src/mt4_bridge/snapshot_reader.py
  * src/mt4_bridge/command_guard.py
  * src/mt4_bridge/stale_detector.py
  * src/mt4_bridge/position_consistency.py
  * src/mt4_bridge/risk_manager.py
  * src/mt4_bridge/signal_engine.py
  * src/mt4_bridge/runtime_state.py
  * src/mt4_bridge/models.py
  * mt4/MQL4/Experts/BridgeWriterEA.mq4

* completion_links:
  * MVP 3.5 ライブ運用（後段）
  * MVP 7. エラー処理・耐障害性

* task_split_notes:
  * 対策①適用後の A/B 挙動での live 動作確認は未実施
  * ハートビート／Stale 検知は実装済み

* notes:
  * 本筋ではライブ運用は後段スコープ

---

### BT GUI アプリ（backtest_gui_app）

* layer: gui
* status: partial

* related_files:
  * src/backtest_gui.py
  * src/backtest_gui_app/views/main_window.py
  * src/backtest_gui_app/views/input_panel.py
  * src/backtest_gui_app/views/summary_panel.py
  * src/backtest_gui_app/views/result_tabs.py
  * src/backtest_gui_app/views/all_months_tab.py
  * src/backtest_gui_app/views/chart_overview_tab.py
  * src/backtest_gui_app/views/compare_ab_tab.py
  * src/backtest_gui_app/presenters/result_presenter.py
  * src/backtest_gui_app/services/run_config_builder.py
  * src/backtest_gui_app/widgets/linked_trade_chart_widget.py
  * src/backtest_gui_app/widgets/price_chart_widget.py

* completion_links:
  * MVP 3. GUI 運用

* task_split_notes:
  * 対策①適用後の動作未確認
  * 4期間ロバストネス表示・月別崩壊評価表示 未実装
  * パラメータ承認ゲートの GUI 導線 未確認

* notes:
  * 既存コードは存在する

---

### Chart 共通 widget (gui_common.widgets)

* layer: gui

* status: implemented

* related_files:
  * src/gui_common/widgets/linked_trade_chart_widget.py
  * src/gui_common/widgets/trades_table_widget.py

* completion_links:
  * MVP 3. GUI 運用

* task_split_notes:
  * 2026-04-21 v4 新規作成
  * linked_trade_chart_widget: ローソク+累積pips 連動、dark theme、lane 別マーカー、描画間引き(>=2000本で折れ線)、state 背景切替、x/y 両軸自動フィット(padding 12%)、scroll zoom/drag pan/reset zoom
  * trades_table_widget: 33 列(コア 11/詳細 22、default は詳細 hidden)、pips 色分け、崩壊ハイライト、Lane/Position/Pips フィルタ、trade_selected シグナル

* notes:
  * 既存 backtest_gui_app/widgets/linked_trade_chart_widget.py とは別実装。backtest_gui は最終的に廃止方針のため共通 widget 側を主系として育てる
  * dark theme 配色: 陽線 #7BD88F / 陰線 #FF7B72 / range lane buy=#6FA8FF・sell=#B084EB / trend lane buy=#7BD88F・sell=#F0A050 / exit=#F0C674

---

### Chart タブ (explore_gui_app)

* layer: gui

* status: implemented

* related_files:
  * src/explore_gui_app/views/chart_tab.py
  * src/explore_gui_app/views/chart_popup_window.py
  * src/explore_gui_app/constants.py

* completion_links:
  * MVP 3. GUI 運用

* task_split_notes:
  * 2026-04-21 v4 新規: BT 単発結果を Trades table で表示、Chart はモードレスポップアップで別ウィンドウ
  * 同時 1 枚ガード、Table 選択で自動 open & focus、BT 再実行で既存を閉じて新 artifacts に差替
  * All months + connected=True の artifacts も取れるので、全期間チャート表示に対応

* notes:
  * Explore 未実行でも Strategy コンボ + CSV 指定で BT 単発→ Chart の流れが独立して使える

---

### 探索 GUI アプリ（explore_gui_app）

* layer: gui
* status: implemented (GUI 実起動で Explore/BT 単発/Chart 確認済、承認ゲート未)

* related_files:
  * src/explore_gui.py
  * src/explore_cli.py
  * src/explore_gui_app/views/main_window.py
  * src/explore_gui_app/views/backtest_panel.py
  * src/explore_gui_app/views/chart_tab.py (v4 新規)
  * src/explore_gui_app/views/chart_popup_window.py (v4 新規)
  * src/explore_gui_app/views/analysis_panel.py
  * src/explore_gui_app/views/input_panel.py
  * src/explore_gui_app/views/parameter_dialog.py
  * src/explore_gui_app/views/result_panel.py
  * src/explore_gui_app/constants.py (v4 新規: AVAILABLE_STRATEGIES 共有)
  * src/explore_gui_app/services/month_selection.py
  * src/explore_gui_app/services/refinement.py

* completion_links:
  * MVP 3. GUI 運用

* task_split_notes:
  * 2026-04-21 v4: Backtest 単発タブに Strategy コンボ + CSV 手動指定 + 進捗バー + 連結 BT チェックを追加、Explore 未実行でも独立動作可
  * 2026-04-21 v4: 戦術定数 SL/TP の read-only ラベル表示 (combo 時は lane 別)
  * 2026-04-21 v4: レイアウト改修 (上段 3 カラム + 下段 Splitter で details/notes)
  * 2026-04-21 v4: Chart タブ新設、TradesTableWidget + ChartPopupWindow 連動、同時 1 枚ガード
  * 2026-04-21 v2: `_AVAILABLE_STRATEGIES` に `bollinger_range_A`, `bollinger_combo_AB` 追加(v4 で constants.py に分離)
  * 承認ゲートは未接続

* notes:
  * BT 実行 → Chart タブで全期間チャート & trade 連動ズームまで動線が通った状態
  * 連結 BT + Chart + Trades 絞り込みで BT 結果分析が1つの GUI 内で完結

---

### 月別崩壊ゼロ判定（評価関数）

* layer: usecase
* status: not_implemented

* related_files:
  * (新規予定: src/backtest/robustness_evaluator.py など)

* completion_links:
  * MVP 2. バックテスト・最適化

* task_split_notes:
  * 4期間（1ヶ月・3ヶ月・半年・1年）それぞれで月別分解し、崩壊月ゼロかを判定
  * 最悪月劣化度スコアを返す
  * 戦術候補の足切りフィルタとして使う

* notes:
  * 本筋 §3.2 と §6 で採用基準として明文化

---

### AB 同時稼働枠（bollinger_combo_AB）

* layer: domain
* status: implemented (BT 面, 本番再現性未検証)

* related_files:
  * src/mt4_bridge/strategies/bollinger_combo_AB.py
  * src/mt4_bridge/strategies/risk_config.py

* completion_links:
  * MVP 2. バックテスト・最適化
  * MVP 3.5 ライブ運用（後段）

* task_split_notes:
  * 2026-04-21 v2: BT で lane 別 SL/TP 対応完了 (BacktestSimulator に `lane_sl_pips`/`lane_tp_pips`、戦術定数フォールバックで解決)
  * `LANE_STRATEGY_MAP = {"range": "bollinger_range_A", "trend": "bollinger_trend_B"}` を公開
  * GUI (explore_gui) の戦略選択肢に `bollinger_combo_AB` を追加済
  * 本番経路: `app_cli` は multi-decision を list で受け、各 decision に戦術定数経由の SL/TP を付ける
  * EA (`BridgeWriterEA.mq4`) は magic_number 44001/44002 で lane 分離、command meta の `entry_lane` を読む
  * **未検証**: 同一バーで range/trend 同時発火時の EA 順序処理、command_guard との協調、デモ口座での実行一致

* notes:
  * combo_AB 1年 BT: +983.2 pips / 崩壊月 0 (worst 2025-06 -18.4)
  * 本筋 §6 で B 本番稼働は対象外扱いだが、BT としては combo_AB を主軸として運用できる状態

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
