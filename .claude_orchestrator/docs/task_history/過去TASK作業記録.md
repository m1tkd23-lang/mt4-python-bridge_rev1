# 過去TASK作業記録

## 目的
plannerが次タスクを判断するための短い知見のみを残す

---





## TASK-0005 : close_compare_v1.py の復旧と CLI e2e 動作確認

- 実行日時: 2026-04-09 07:16
- task_type: bugfix
- risk_level: medium

### 変更内容
close_compare_v1.py および ma_cross_v1.py を .pyc バイトコードから逆コンパイルして復旧し、v7_features/v7_state_detector/v7_state_models は旧リポジトリか...

### 関連ファイル
- src/mt4_bridge/strategies/close_compare_v1.py
- src/mt4_bridge/strategies/ma_cross_v1.py
- src/mt4_bridge/strategies/v7_features.py
- src/mt4_bridge/strategies/v7_state_detector.py
- src/mt4_bridge/strategies/v7_state_models.py
- src/mt4_bridge/strategies/example_strategy_v1.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- close_compare_v1.py・ma_cross_v1.py は .pyc からの手動逆コンパイルであり元ソースとの完全一致は保証されない（後続タスクで差分検証が必要）
- v7_features/v7_state_detector/v7_state_models は旧リポジトリからのコピーであり rev1 側独自変更との乖離の可能性がある
- bollinger_range_v4_21.py のソースが未復旧（現時点で import チェーンに影響なしだが動的ロード時に問題化する可能性）
- aggregate_stats.py の PF 算出が月別近似であり average_win_pips=0 かつ wins>0 のエッジケースで gross_profit が 0 になる





## TASK-0006 : A単体・B単体・A+B合成成績比較ロジックの実装

- 実行日時: 2026-04-09 07:25
- task_type: feature
- risk_level: medium

### 変更内容
service.py に compare_ab() メソッド、runner.py に --compare-ab CLI オプションと比較表出力を実装。combo モジュールに LANE_A_STRATEGY / LANE_B_STRATEG...

### 関連ファイル
- src/backtest/service.py
- src/backtest/runner.py
- src/mt4_bridge/strategies/bollinger_combo_AB.py
- src/mt4_bridge/strategies/bollinger_combo_AB_v1.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- CLI e2e 動作確認が未実施。実データでの --compare-ab 実行による表出力正常性の検証が必要
- bollinger_combo_AB_v1.py の LANE_B_STRATEGY が参照する bollinger_trend_B3_weak_start_v3_1 モジュールが不在（TASK-0006 以前からの既存問題）
- aggregate_stats.py の PF 算出が月別近似である点は TASK-0005 からの carry_over のまま残存





## TASK-0007 : --compare-ab CLI e2e 動作確認と戦術依存解消

- 実行日時: 2026-04-09 07:34
- task_type: bugfix
- risk_level: medium

### 変更内容
bollinger_combo_AB_v1.py の LANE_B_STRATEGY 参照先を実在する bollinger_trend_B3_weak_start に修正し、--compare-ab CLI で12ヶ月一括比較の正常動作を確...

### 関連ファイル
- src/mt4_bridge/strategies/bollinger_combo_AB_v1.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- bollinger_combo_AB（非v1）は bollinger_range_A の required_bars 不足で --compare-ab 実行時にエラーとなる（TASK-0007 スコープ外の既存問題）
- aggregate_stats.py の PF 算出が月別近似のまま残存（TASK-0005 carry_over）
- runner.py / service.py / bollinger_combo_AB.py の未コミット変更が残っている（TASK-0006 持ち越し含む）





## TASK-0008 : bollinger_combo_AB の bollinger_range_A required_bars 不足問題の調査・修正

- 実行日時: 2026-04-09 07:45
- task_type: bugfix
- risk_level: medium

### 変更内容
bollinger_range_v4_4.py の required_bars() が BOLLINGER_PERIOD(20) を返していたが、_calculate_previous_bollinger_bands が BOLLINGER...

### 関連ファイル
- src/mt4_bridge/strategies/bollinger_range_v4_4.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- bollinger_range_v4_4 を内部利用する戦術で warm-up バーが 1 本増加するが、安全側の変化であり実質的リスクなし





## TASK-0009 : aggregate_stats.py の PF 算出を月別近似から全月通算精密計算へ修正

- 実行日時: 2026-04-09 07:57
- task_type: bugfix
- risk_level: low

### 変更内容
全月通算 PF 算出を月別 average_win/loss 近似から BacktestStats の gross_profit_pips/gross_loss_pips を直接合算する精密計算に修正し、12ヶ月一括実行で PF 一致を確認...

### 関連ファイル
- src/backtest/simulator/models.py
- src/backtest/simulator/stats.py
- src/backtest/aggregate_stats.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- BacktestStats を dict/JSON 化している箇所がある場合、gross_profit_pips/gross_loss_pips フィールドが出力に追加される可能性がある（reviewer 指摘、影響は小さい）





## TASK-0010 : GUI バックテスト画面の completion_definition 充足度ギャップ分析

- 実行日時: 2026-04-09 08:07
- task_type: research
- risk_level: low

### 変更内容
completion_definition セクション3「GUI最適化支援機能」の4要件に対し、既存GUIの充足度を精査しギャップ一覧を作成した。主要パラメータ動的変更UI・全月一括実行GUI・月別成績表が未実装であり、BacktestSt...

### 関連ファイル
- none

### 注意点
- 戦術固有パラメータの動的変更 UI は戦術ごとのパラメータ構造差異が大きく、汎用設計の実装コストが読みにくい
- 全月一括実行の GUI 統合は非同期実行・プログレス表示・月別結果レイアウト等の設計判断が多く、単一タスクに収めると肥大化するリスクがある
- completion_definition の「即時反映」がボタン押下式で許容されるか自動再計算が必要かの方針が未決定





## TASK-0011 : feature_inventory GUI関連エントリへのギャップ分析結果反映

- 実行日時: 2026-04-09 08:20
- task_type: docs
- risk_level: low

### 変更内容
feature_inventory.md の GUI 関連2エントリ（GUI バックテスト画面・GUI パラメータ変更・即時再計算）の task_split_notes に TASK-0010 ギャップ分析結果を反映した。過去TASK作業記...

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- GUI 応答速度エントリの task_split_notes は今回未更新だが、TASK-0010 分析で応答速度固有の新規ギャップは検出されておらずスコープ外として妥当





## TASK-0012 : GUI 全月一括実行機能の実装

- 実行日時: 2026-04-09 08:33
- task_type: feature
- risk_level: medium

### 変更内容
GUI に All Months タブを追加し、CSVディレクトリ選択・全月一括実行ボタン・月別成績一覧表・全月合算成績表示を実装。service.py run_all_months() への接続完了。

### 関連ファイル
- src/backtest_gui_app/views/all_months_tab.py
- src/backtest_gui_app/views/main_window.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- 全月一括実行が同期実行のため、CSVファイル数が多い場合にGUIがフリーズする。後続タスクで QThread/QRunnable による非同期化が必要
- input_panel のパラメータを Standard タブと All Months タブで共用しているため、同時利用時にパラメータの意図しない共有が起きうる。MVP では許容範囲だが改善余地あり
- _run_all_months() のパラメータ構築ロジックが build_run_config() と重複しており、保守性の観点で共通化が望ましい





## TASK-0013 : 全月一括実行の QThread 非同期化によるGUIブロック回避

- 実行日時: 2026-04-09 08:41
- task_type: feature
- risk_level: medium

### 変更内容
AllMonthsWorker(QThread) を新設し、全月一括実行を非同期化。月数ベースプログレスバー表示・実行ボタン無効化・シグナル経由の結果更新を実装した。

### 関連ファイル
- src/backtest_gui_app/views/main_window.py
- src/backtest_gui_app/views/all_months_tab.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- AllMonthsWorker.run() が service.py の run_all_months() ループロジックを再実装しており、service.py側変更時にワーカー側の追従漏れが起きうる
- ウィンドウ終了時にワーカースレッドが実行中の場合の明示的クリーンアップがない（Qt parent-child による暗黙的破棄に依存）
- キャンセル機能がないため大量CSV時にユーザーが中断不可





## TASK-0014 : run_all_months() への progress_callback 導入によるワーカーとのループ重複解消

- 実行日時: 2026-04-09 08:49
- task_type: refactor
- risk_level: medium

### 変更内容
run_all_months() に optional な progress_callback 引数を追加し、AllMonthsWorker.run() のループロジック再実装を解消して run_all_months() への直接委譲に簡素...

### 関連ファイル
- src/backtest/service.py
- src/backtest_gui_app/views/main_window.py

### 注意点
- GUI 実機動作確認（All Months タブの進捗バー動作）は手動テスト扱い — 自動テストではカバー不可
- progress_callback はワーカースレッドから呼ばれるが、Qt Signal/Slot クロススレッド接続で配信されるため実質リスク低





## TASK-0015 : All Months 実行キャンセル機能の実装（requestInterruption + progress_callback 内チェック）

- 実行日時: 2026-04-09 08:56
- task_type: feature
- risk_level: low

### 変更内容
AllMonthsWorker に requestInterruption ベースのキャンセル機構を実装。progress_callback ラッパー内で isInterruptionRequested() をチェックし、Cancel ボタ...

### 関連ファイル
- src/backtest_gui_app/views/all_months_tab.py
- src/backtest_gui_app/views/main_window.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- GUI 実機動作確認は手動テスト扱い — 自動テストではカバー不可（carry_over from TASK-0014）
- キャンセルは月単位粒度: 現在実行中の月のバックテスト完了後に中断されるため数秒の遅延あり（設計上の制約）
- _AllMonthsCancelled 例外が service.py の run_all_months を貫通する設計のため、将来 finally ブロック追加時に干渉する可能性あり（現時点では問題なし）





## TASK-0016 : All Months タブへの全月通算損益推移チャート追加

- 実行日時: 2026-04-09 09:05
- task_type: feature
- risk_level: medium

### 変更内容
All Months タブに全月通算損益推移チャート（累積 pips 折れ線グラフ + 月境界グレー破線）を追加。TimeSeriesChartWidget に垂直補助線対応メソッドを追加し、AllMonthsTab で全月の Execut...

### 関連ファイル
- src/backtest_gui_app/widgets/time_series_chart_widget.py
- src/backtest_gui_app/views/all_months_tab.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- ExecutedTrade.exit_time が object 型宣言のため datetime 以外の値混入時にサイレントスキップされる（既存コード全体が datetime 前提のため現時点リスク低）
- 全月で数千トレードになった場合の matplotlib 描画パフォーマンスは未検証
- GUI 実機動作確認は手動テスト扱い（自動テストではカバー不可）





## TASK-0017 : 戦術固有パラメータの GUI 動的変更 UI 追加（ボリンジャー周期・σ倍率・閾値）

- 実行日時: 2026-04-09 09:18
- task_type: feature
- risk_level: medium

### 変更内容
Standard タブの InputPanel に戦術固有パラメータ編集 UI（Strategy Parameters セクション）を追加し、ランタイムオーバーライド方式でバックテスト実行時に適用する仕組みを実装した。revision 2 ...

### 関連ファイル
- src/backtest_gui_app/services/strategy_params.py
- src/backtest_gui_app/views/input_panel.py
- src/backtest_gui_app/services/run_config_builder.py
- src/backtest/service.py
- src/backtest_gui_app/views/main_window.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- ランタイムオーバーライド方式（モジュールグローバル setattr）は Standard タブ単月実行では問題ないが、All Months タブのマルチスレッド実行では競合リスクがある
- STRATEGY_PARAM_MAP はハードコードのため新戦術追加時に strategy_params.py の手動更新が必要
- GUI 実機動作確認（パラメータ変更→バックテスト再実行→結果即時反映）は手動テスト扱いで未実施





## TASK-0018 : All Months タブでの戦術パラメータオーバーライド対応（スレッドセーフ方式）

- 実行日時: 2026-04-09 09:31
- task_type: feature
- risk_level: medium

### 変更内容
All Months タブの全月一括実行に戦術パラメータオーバーライドを対応させた。run_all_months() に strategy_params 引数を追加し、AllMonthsWorker 経由で InputPanel の GUI...

### 関連ファイル
- src/backtest/service.py
- src/backtest_gui_app/views/main_window.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- 将来 run_all_months() を並列化（ThreadPoolExecutor 等）した場合、モジュールグローバル setattr 方式ではグローバル競合が発生する。その際はスレッドローカルまたはプロセス分離が必要
- GUI 実機動作確認（All Months タブでパラメータ変更→全月実行→結果にオーバーライド反映）は手動テスト扱いで未実施





## TASK-0019 : 構造化ログ出力基盤の設計と最小実装（trade_id・lane_id・reason_code）

- 実行日時: 2026-04-09 15:18
- task_type: feature
- risk_level: medium

### 変更内容
構造化ログ出力基盤を実装。ExecutedTrade/SimulatedPosition に trade_id を追加し、JSON Lines 形式でトレードライフサイクル（ENTRY/SL_HIT/TP_HIT/SIGNAL_CLOSE/...

### 関連ファイル
- src/backtest/simulator/models.py
- src/backtest/simulator/position_manager.py
- src/backtest/simulator/trade_logger.py
- src/backtest/simulator/__init__.py
- src/backtest/service.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- run_all_months() でのログ出力未対応。全月一括実行時は trade_id が月ごとにリセットされ重複するため、月別プレフィックス付与が必要
- entry の reason_code が簡易形式であり、将来の機械フィルタ用途では粒度不足の可能性
- MFE/MAE/holding_bars 等の completion_definition フル仕様フィールドが未実装
- run_all_months() 並列化時の trade_id グローバル一意性問題（carry_over from TASK-0018）





## TASK-0020 : 構造化トレードログの全月一括実行対応（run_all_months への trade_log 出力統合）

- 実行日時: 2026-04-09 15:32
- task_type: feature
- risk_level: medium

### 変更内容
run_all_months() に trade_log_dir 引数を追加し、全月一括実行時に月別 JSONL トレードログを出力可能にした。GUI の All Months タブに Trade Log チェックボックスを追加し AllM...

### 関連ファイル
- src/backtest/service.py
- src/backtest_gui_app/views/all_months_tab.py
- src/backtest_gui_app/views/main_window.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- GUI 実機動作確認（All Months タブで Trade Log チェック→全月実行→JSONL 出力）は手動テスト扱いで未実施
- trade_log_dir は相対パス Path('logs/trade_logs') で構築しており、GUI の CWD が repo root でない場合に意図しない場所に出力される可能性がある
- 将来 run_all_months() を並列化した場合、モジュールグローバル setattr 方式でグローバル競合が発生する





## TASK-0021 : CLI runner.py への --trade-log-dir オプション追加（全月一括実行時の JSONL 出力対応）

- 実行日時: 2026-04-09 15:43
- task_type: feature
- risk_level: low

### 変更内容
runner.py に --trade-log-dir（全月一括用）と --trade-log-path（単月用）の2つのオプションを追加し、既存の service 層引数に接続した。

### 関連ファイル
- src/backtest/runner.py

### 注意点
- carry_over: trade_log_dir に相対パスを指定した場合 CWD 依存で意図しない場所に出力される可能性がある（TASK-0020 から継続）
- carry_over: 将来 run_all_months() を並列化した場合、モジュールグローバル setattr 方式でグローバル競合が発生する（TASK-0020 から継続）
- --compare-ab 実行時に trade_log_dir を渡す経路は未実装（次タスクで対応）




## TASK-0022 : --compare-ab モード時の trade_log_dir 接続（各レーンをサブディレクトリに振り分け）

- 実行日時: 2026-04-09 15:53
- task_type: feature
- risk_level: low

### 変更内容
compare_ab() に trade_log_dir パラメータを追加し、各レーン（lane_a / lane_b / combo）をサブディレクトリに振り分けて run_all_months() に渡す接続を実装。CLI 側 _run...

### 関連ファイル
- src/backtest/service.py
- src/backtest/runner.py

### 注意点
- trade_log_dir に相対パスを指定した場合 CWD 依存で意図しない場所に出力される可能性がある（TASK-0020 からの継続課題、本タスクスコープ外）



## TASK-0023 : feature_inventory.md への構造化ログ出力セクション更新（TASK-0021/0022 実装反映）

- 実行日時: 2026-04-09 16:00
- task_type: docs
- risk_level: low

### 変更内容
feature_inventory.md の「構造化ログ出力」セクション task_split_notes に TASK-0021（CLI --trade-log-dir / --trade-log-path）と TASK-0022（com...

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- trade_log_dir 相対パス問題（TASK-0020 からの継続課題）が docs 上で明示されていないが、本タスクスコープ外であり initial_execution_notes に記録済みのため許容


## TASK-0024 : 構造化トレードログへの MFE/MAE/holding_bars フィールド追加

- 実行日時: 2026-04-09 16:11
- task_type: feature
- risk_level: low

### 変更内容
ExecutedTrade に mfe_pips/mae_pips/holding_bars フィールドを追加し、SimulatedPosition でバー処理ループ内の max_favorable_price/max_adverse_pr...

### 関連ファイル
- src/backtest/simulator/models.py
- src/backtest/simulator/position_manager.py
- src/backtest/simulator/generic_runner.py
- src/backtest/simulator/v7_runner.py
- src/backtest/simulator/trade_logger.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- MFE/MAE は entry bar を含まない（次バーから追跡開始）。MFE=0 ケースの解釈に後続タスクで注意が必要
- implementer report の risks 記述（entry bar 包含）と実装（entry bar 非包含）に齟齬があるが、実装自体は正しく動作しており本タスクの blocking issue ではない