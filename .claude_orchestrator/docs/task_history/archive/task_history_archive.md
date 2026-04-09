# Task History Archive

This file is not part of the normal planner/task_router context.
Only referenced when necessary.

---

## TASK-0001 : 開発の目的本筋の理解

- 実行日時: 2026-04-09 06:28
- task_type: research
- risk_level: low

### 変更内容
開発の目的本筋.md を読み込み、プロジェクトの目的・評価基準・制約条件・ログ設計方針を把握した。変更は一切行っていない。

### 関連ファイル
- none

### 注意点
- none

## TASK-0002 : completion_definition.md の具体化

- 実行日時: 2026-04-09 06:36
- task_type: docs
- risk_level: low

### 変更内容
開発の目的本筋.md のセクション2〜6を根拠に、completion_definition.md の全プレースホルダを具体的な完成条件に書き換えた。

### 関連ファイル
- .claude_orchestrator/docs/completion_definition.md

### 注意点
- MVP中心機能6項目を4カテゴリに統合しているため、planner・task_router がカテゴリ単位で参照する際に元の6項目との対応関係が不明確になる可能性がある
- 未確定事項5件が確定した際に completion_definition.md への反映漏れが発生するリスクがある

## TASK-0003 : feature_inventory.md の具体化と completion_definition.md との整合

- 実行日時: 2026-04-09 06:50
- task_type: docs
- risk_level: low

### 変更内容
repo 内の既存コードを棚卸しし、completion_definition.md の全セクション（1〜9）と対応する18機能を feature_inventory.md に記載した。各機能について実在ファイルの確認に基づき status...

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- GUI関連3機能（バックテスト画面・パラメータ変更即時再計算・GUI応答速度）の status は画面操作なしのコード構造推定であり、実際の機能充足度と乖離する可能性がある
- completion_definition セクション3 の新規GUI作成 vs 既存改修の方針未確定により GUI 関連機能の status が変動しうる
- セクション7〜8 が1〜6と同列に記載されており planner が MVP主要機能と補助要件を混同するリスクがある

## TASK-0004 : 全月合算成績算出ロジックの実装

- 実行日時: 2026-04-09 07:05
- task_type: feature
- risk_level: low

### 変更内容
director指示の3件（デッドコード削除・feature_inventory status整合性修正2件）を全て実施完了。

### 関連ファイル
- src/backtest/aggregate_stats.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- close_compare_v1.py 欠損が解消されるまで backtest モジュール全体の import が失敗し、aggregate_stats.py の実行時検証ができない
- PF 算出が月別統計からの近似であり、average_win_pips=0 かつ wins>0 のエッジケースで実際の PF と乖離する可能性がある（低リスク）
- max_drawdown_pips が月別最悪値の max() であり cross-month equity curve ベースではない点が仕様として明示されていない

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
















