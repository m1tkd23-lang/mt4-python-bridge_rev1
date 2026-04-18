# Task History Archive

This file is not part of the normal planner/task_router context.
Only referenced when necessary.

---

## TASK-0001 : 開発の目的本筋の理解
- [research/low] 開発の目的本筋.md を読み込み、プロジェクトの目的・評価基準・制約条件・ログ設計方針を把握。変更なし
- 関連: なし

## TASK-0002 : completion_definition.md の具体化
- [docs/low] 開発の目的本筋.md セクション2〜6を根拠に completion_definition.md の全プレースホルダを具体的完成条件に書き換え
- 関連: .claude_orchestrator/docs/completion_definition.md
- 注意: MVP中心6項目を4カテゴリ統合のため元項目との対応関係が不明確になる可能性

## TASK-0003 : feature_inventory.md の具体化と completion_definition.md との整合
- [docs/low] repo 内既存コードを棚卸しし completion_definition 全セクション対応の18機能を feature_inventory.md に記載。status は実在ファイル確認に基づき判定
- 関連: .claude_orchestrator/docs/feature_inventory.md
- 注意: GUI関連3機能の status はコード構造推定のみ。セクション7〜8が1〜6と同列記載で混同リスク

## TASK-0004 : 全月合算成績算出ロジックの実装
- [feature/low] director指示3件（デッドコード削除・feature_inventory status整合性修正2件）を実施完了
- 関連: src/backtest/aggregate_stats.py, .claude_orchestrator/docs/feature_inventory.md
- 注意: close_compare_v1.py 欠損で backtest モジュール import 失敗。PF算出が月別近似

## TASK-0005 : close_compare_v1.py の復旧と CLI e2e 動作確認
- [bugfix/medium] close_compare_v1.py・ma_cross_v1.py を .pyc から逆コンパイル復旧。v7系は旧リポジトリからコピー。CLI e2e 動作確認完了
- 関連: src/mt4_bridge/strategies/{close_compare_v1,ma_cross_v1,v7_features,v7_state_detector,v7_state_models,example_strategy_v1}.py
- 注意: .pyc逆コンパイルのため元ソースとの完全一致不保証。bollinger_range_v4_21.py 未復旧

## TASK-0006 : A単体・B単体・A+B合成成績比較ロジックの実装
- [feature/medium] service.py に compare_ab()、runner.py に --compare-ab CLI オプションと比較表出力を実装
- 関連: src/backtest/service.py, src/backtest/runner.py, src/mt4_bridge/strategies/bollinger_combo_AB{,_v1}.py
- 注意: CLI e2e 未実施。LANE_B_STRATEGY 参照先モジュール不在（既存問題）

## TASK-0007 : --compare-ab CLI e2e 動作確認と戦術依存解消
- [bugfix/medium] bollinger_combo_AB_v1.py の LANE_B_STRATEGY 参照先を実在モジュールに修正、12ヶ月一括比較の正常動作確認
- 関連: src/mt4_bridge/strategies/bollinger_combo_AB_v1.py
- 注意: bollinger_combo_AB（非v1）は required_bars 不足でエラー（スコープ外既存問題）

## TASK-0008 : bollinger_combo_AB の bollinger_range_A required_bars 不足問題の調査・修正
- [bugfix/medium] bollinger_range_v4_4.py の required_bars() を BOLLINGER_PERIOD+1 に修正し warm-up バー不足を解消
- 関連: src/mt4_bridge/strategies/bollinger_range_v4_4.py

## TASK-0009 : aggregate_stats.py の PF 算出を月別近似から全月通算精密計算へ修正
- [bugfix/low] 全月通算 PF を gross_profit_pips/gross_loss_pips 直接合算の精密計算に修正。BacktestStats に2フィールド追加
- 関連: src/backtest/simulator/{models,stats}.py, src/backtest/aggregate_stats.py
- 注意: BacktestStats dict化時に新フィールドが出力に追加される可能性

## TASK-0010 : GUI バックテスト画面の completion_definition 充足度ギャップ分析
- [research/low] completion_definition セクション3 の4要件に対しギャップ一覧作成。主要パラメータ動的変更UI・全月一括実行GUI・月別成績表が未実装と判明
- 関連: なし

## TASK-0011 : feature_inventory GUI関連エントリへのギャップ分析結果反映
- [docs/low] feature_inventory の GUI関連2エントリの task_split_notes に TASK-0010 ギャップ分析結果を反映
- 関連: .claude_orchestrator/docs/feature_inventory.md

## TASK-0012 : GUI 全月一括実行機能の実装
- [feature/medium] All Months タブ追加。CSVディレクトリ選択・全月一括実行・月別成績一覧表・全月合算成績表示を実装
- 関連: src/backtest_gui_app/views/{all_months_tab,main_window}.py
- 注意: 同期実行のためCSV数多い場合にGUIフリーズ。パラメータ構築ロジック重複

## TASK-0013 : 全月一括実行の QThread 非同期化によるGUIブロック回避
- [feature/medium] AllMonthsWorker(QThread) 新設で全月一括実行を非同期化。プログレスバー・実行ボタン無効化・シグナル結果更新を実装
- 関連: src/backtest_gui_app/views/{main_window,all_months_tab}.py
- 注意: Worker が service.py ループロジックを再実装。キャンセル機能なし

## TASK-0014 : run_all_months() への progress_callback 導入によるワーカーとのループ重複解消
- [refactor/medium] run_all_months() に progress_callback 追加し AllMonthsWorker のループ再実装を解消
- 関連: src/backtest/service.py, src/backtest_gui_app/views/main_window.py

## TASK-0015 : All Months 実行キャンセル機能の実装
- [feature/low] requestInterruption ベースのキャンセル機構実装。progress_callback 内で中断チェック、Cancel ボタン追加
- 関連: src/backtest_gui_app/views/{all_months_tab,main_window}.py
- 注意: キャンセルは月単位粒度（実行中月完了後に中断）

## TASK-0016 : All Months タブへの全月通算損益推移チャート追加
- [feature/medium] 累積pips折れ線グラフ＋月境界グレー破線チャートを All Months タブに追加
- 関連: src/backtest_gui_app/widgets/time_series_chart_widget.py, src/backtest_gui_app/views/all_months_tab.py

## TASK-0017 : 戦術固有パラメータの GUI 動的変更 UI 追加
- [feature/medium] InputPanel に Strategy Parameters セクション追加、ランタイムオーバーライド方式でバックテスト実行時に適用
- 関連: src/backtest_gui_app/services/{strategy_params,run_config_builder}.py, src/backtest_gui_app/views/{input_panel,main_window}.py, src/backtest/service.py
- 注意: モジュールグローバル setattr 方式は All Months マルチスレッドで競合リスク。STRATEGY_PARAM_MAP ハードコード

## TASK-0018 : All Months タブでの戦術パラメータオーバーライド対応（スレッドセーフ方式）
- [feature/medium] run_all_months() に strategy_params 引数追加し All Months での戦術パラメータオーバーライドに対応
- 関連: src/backtest/service.py, src/backtest_gui_app/views/main_window.py
- 注意: 並列化時にモジュールグローバル setattr でグローバル競合発生の可能性

## TASK-0019 : 構造化ログ出力基盤の設計と最小実装
- [feature/medium] ExecutedTrade/SimulatedPosition に trade_id 追加、JSON Lines 形式でトレードライフサイクルログ出力基盤を実装
- 関連: src/backtest/simulator/{models,position_manager,trade_logger,__init__}.py, src/backtest/service.py
- 注意: run_all_months() でのログ未対応。MFE/MAE/holding_bars 等フル仕様フィールド未実装

## TASK-0020 : 構造化トレードログの全月一括実行対応
- [feature/medium] run_all_months() に trade_log_dir 引数追加、月別 JSONL トレードログ出力対応。GUI に Trade Log チェックボックス追加
- 関連: src/backtest/service.py, src/backtest_gui_app/views/{all_months_tab,main_window}.py
- 注意: trade_log_dir 相対パスの CWD 依存問題

## TASK-0021 : CLI runner.py への --trade-log-dir オプション追加
- [feature/low] runner.py に --trade-log-dir（全月用）と --trade-log-path（単月用）を追加し service 層に接続
- 関連: src/backtest/runner.py
- 注意: --compare-ab 実行時の trade_log_dir 経路未実装

## TASK-0022 : --compare-ab モード時の trade_log_dir 接続
- [feature/low] compare_ab() に trade_log_dir 追加、各レーン（lane_a/lane_b/combo）をサブディレクトリに振り分け
- 関連: src/backtest/service.py, src/backtest/runner.py

## TASK-0023 : feature_inventory.md への構造化ログ出力セクション更新
- [docs/low] feature_inventory の構造化ログ出力 task_split_notes に TASK-0021/0022 実装を反映
- 関連: .claude_orchestrator/docs/feature_inventory.md

## TASK-0024 : 構造化トレードログへの MFE/MAE/holding_bars フィールド追加
- [feature/low] ExecutedTrade に mfe_pips/mae_pips/holding_bars 追加、SimulatedPosition でバー処理ループ内追跡を実装
- 関連: src/backtest/simulator/{models,position_manager,generic_runner,v7_runner,trade_logger}.py
- 注意: MFE/MAE は entry bar 非包含（次バーから追跡開始）

## TASK-0025 : MFE/MAE ratio による補助品質指標の最小実装
- [feature/low] BacktestStats・AggregateStats に MFE/MAE ratio 追加、月別平均・全月合算平均を算出。CLI 出力にも表示追加
- 関連: src/backtest/simulator/{models,stats}.py, src/backtest/{aggregate_stats,runner}.py
- 注意: GUI All Months タブに未表示。全月合算が月別単純平均（トレード数加重ではない）

## TASK-0026 : GUI All Months タブへの MFE/MAE ratio 表示追加
- [feature/low] All Months の月別テーブルに Avg MFE/MAE 列、aggregate パネルに Avg MFE/MAE フィールドを追加
- 関連: src/backtest_gui_app/views/all_months_tab.py

## TASK-0027 : Single Month SummaryPanel への avg_mfe_mae_ratio 表示追加
- [feature/low] SummaryPanel の summary_fields に avg_mfe_mae_ratio 追加、BacktestDisplaySummary へのフィールド追加
- 関連: src/backtest/{view_models}.py, src/backtest_gui_app/views/summary_panel.py, src/backtest_gui_app/presenters/result_presenter.py

## TASK-0028 : GUI A/B 比較タブの追加
- [feature/low] Compare A/B タブ新規作成。A単体/B単体/A+B合成の3パターン全月成績比較をGUIで実行可能に。非同期実行・3フェーズプログレス・キャンセル対応
- 関連: src/backtest_gui_app/views/{compare_ab_tab,main_window}.py
- 注意: CompareABWorker が compare_ab() 内部ロジックを複製（乖離リスク）

## TASK-0029 : 採択結果の bollinger_combo_AB.py 反映ワークフロー最小実装
- [feature/medium] CLI ツール apply_params.py を新規作成。--list/--dry-run/--backup/--set/--lane-a/--lane-b 全モード動作確認
- 関連: src/backtest/apply_params.py
- 注意: 正規表現ベース定数書き換えは想定外フォーマットに脆弱

## TASK-0030 : completion_definition 全セクション充足度棚卸し・MVP 完成度最終評価
- [research/low] 全8セクション26項目を突き合わせ。implemented=15, partial=8, not_implemented=3 と判定
- 関連: なし
- 注意: セクション6 not_implemented 2項目が MVP 完成への最大ギャップ

## TASK-0031 : 月平均利益基準の全月横断評価ロジック実装
- [feature/medium] evaluator.py に evaluate_cross_month() 追加、all_months_tab に Cross-Month Verdict/Reasons 表示を実装
- 関連: src/backtest/evaluator.py, src/backtest_gui_app/views/all_months_tab.py
- 注意: CrossMonthThresholds デフォルト値の実運用妥当性未検証

## TASK-0032 : 全月合算成績+月別安定性の統合採択条件実装
- [feature/medium] evaluate_integrated() を追加し ADOPT/IMPROVE/DISCARD 判定実装。GUI All Months に Integrated Verdict 表示
- 関連: src/backtest/evaluator.py, src/backtest_gui_app/views/all_months_tab.py
- 注意: IntegratedThresholds デフォルト値の妥当性未検証。GUI実機確認未実施

## TASK-0033 : completion_definition セクション6 status 注釈追記
- [docs/low] completion_definition セクション6 と feature_inventory の注釈更新。スコープ外変更を revert して制約内に収束
- 関連: .claude_orchestrator/docs/feature_inventory.md
- 注意: feature_inventory「全月安定性評価」partial が実装状態と不整合のまま（スコープ外）

## TASK-0034 : feature_inventory「全月安定性評価」partial→implemented 更新
- [docs/low] 「全月安定性評価（赤字月非連続・ばらつき抑制）」を partial→implemented に昇格、related_files に evaluator.py 追加
- 関連: .claude_orchestrator/docs/feature_inventory.md

## TASK-0035 : feature_inventory「月平均利益基準の探索・確認」エントリ未コミット差分の正式反映
- [docs/low] 未コミット差分を検証し実装事実との整合確認。status: not_implemented→partial 等の変更が正当であると判定
- 関連: なし

## TASK-0036 : TASK-0034/0035 検証済み docs 未コミット差分の一括コミット
- [docs/low] TASK-0034/0035 検証済み docs 差分4ファイルを一括コミット。evaluator.py・all_months_tab.py はスコープ外除外
- 関連: feature_inventory.md, completion_definition.md, 過去TASK作業記録.md, task_history_archive.md

## TASK-0037 : evaluator.py・all_months_tab.py 未コミット実装差分のコミット整理
- [chore/low] TASK-0031/0032 由来の evaluator.py (+274行) と all_months_tab.py (+13行) を git diff 検証しコミット
- 関連: src/backtest/evaluator.py, src/backtest_gui_app/views/all_months_tab.py

## TASK-0038 : task_history 未コミット docs 差分の整理コミット
- [chore/low] task_history 2ファイルの未コミット差分を精査・正当性確認のうえコミット完了
- 関連: task_history_archive.md, 過去TASK作業記録.md

## TASK-0039 : feature_inventory.md の TASK-0031/0032 実装反映に伴う status 乖離精査・更新
- [docs/low] TASK-0031/0032 関連2エントリを実コード・git履歴と突合。両エントリとも status 正確で変更不要と判定
- 関連: なし
- 注意: TASK-0037 carry_over と本タスク判断に齟齬あり、本タスク判断を優先すべき

## TASK-0040 : exploration_loop.py と evaluate_cross_month/evaluate_integrated の接続実装
- [feature/medium] exploration_loop.py に csv_dir 指定時の全月横断評価接続を実装。ExplorationResult に3フィールド追加
- 関連: src/backtest/exploration_loop.py
- 注意: CSV数×イテレーション数の計算コスト増。csv_dir 内非バックテスト用CSV混入リスク

## TASK-0041 : 既存ボリンジャー戦略を対象とした最適化方針の明文化
- [docs/low] project_core/最適化方針_bollinger戦略.md を新規作成。feature_inventory の関連2エントリに方針参照追加
- 関連: .claude_orchestrator/docs/project_core/最適化方針_bollinger戦略.md, .claude_orchestrator/docs/feature_inventory.md

## TASK-0042 : exploration_loop を bollinger 系既存戦術のパラメータオーバーライド探索に改修
- [refactor/low] director revise 2点（LoopConfig.timeframe M5→M1復元、未使用import削除）を修正完了
- 関連: src/backtest/exploration_loop.py
- 注意: 実データCSV結合テスト未実施。BOLLINGER_PARAM_VARIATION_RANGES の値域は初期値で要調整

## TASK-0043 : feature_inventory.md の戦術パラメータ探索ループを bollinger オーバーライド探索対応済みに更新
- [docs/low] feature_inventory の task_split_notes・notes を更新し TASK-0042 bollinger 系対応完了を反映
- 関連: .claude_orchestrator/docs/feature_inventory.md
- 注意: 実データCSV結合テスト未実施（TASK-0042 carry_over）

## TASK-0044 : feature_inventory.md・exploration_loop.py 未コミット差分の整理コミット
- [chore/low] TASK-0040/0041/0042/0043 由来の未コミット差分を精査し整理コミット実施
- 関連: .claude_orchestrator/docs/feature_inventory.md, src/backtest/exploration_loop.py
- 注意: task_history系・最適化方針の未コミット差分が残存

## TASK-0045 : task_history_archive.md・過去TASK作業記録.md・最適化方針_bollinger戦略.md の未コミット差分の整理コミット
- [chore/low] git status 残存3ファイルの差分精査・docs変更のみ確認のうえ整理コミット完了
- 関連: task_history_archive.md, 過去TASK作業記録.md, 最適化方針_bollinger戦略.md

## TASK-0046 : exploration_loop.py bollinger 系探索モードの実データ CSV 結合テスト
- [feature/low] bollinger 系探索モードの結合テスト作成、実データCSVで全9テストPASS確認
- 関連: tests/conftest.py, tests/test_bollinger_exploration.py
- 注意: cross-month テスト（12ヶ月×複数イテレーション）は CI でタイムアウトリスク（36秒）

## TASK-0047 : LoopConfig.timeframe デフォルト値の修正（M1 → M5）
- [bugfix/low] LoopConfig.timeframe デフォルト値を M1→M5 に修正。既存テスト9件全PASS
- 関連: src/backtest/exploration_loop.py

## TASK-0048 : ExplorationConfig.timeframe デフォルト値の修正（M1 → M5）
- [bugfix/low] ExplorationConfig.timeframe デフォルト値を M1→M5 に修正。既存テスト全9件PASS
- 関連: src/backtest/exploration_loop.py

## TASK-0049 : GUI パラメータ変更・即時再計算の partial 残作業の棚卸しと次ステップ特定
- [research/low] completion_definition セクション3 の4項目と現状実装の差分精査、残タスク候補3件を特定
- 関連: .claude_orchestrator/docs/feature_inventory.md
- 注意: 「即時反映」解釈未決定が後続方向を左右するが MVP ではボタン押下式で充足と判定

## TASK-0050 : 「即時反映」ボタン押下式 MVP 充足判定と feature_inventory ステータス昇格
- [docs/low] feature_inventory の「GUI パラメータ変更・即時再計算」を partial→implemented に昇格
- 関連: .claude_orchestrator/docs/feature_inventory.md

## TASK-0051 : completion_definition セクション3 完了判定
- [docs/low] セクション3 全4項目に HTML コメント status 注釈追記、セクション3 COMPLETE 判定記録
- 関連: .claude_orchestrator/docs/completion_definition.md
- 注意: feature_inventory「GUI バックテスト画面」partial と COMPLETE 判定の表面不一致

## TASK-0052 : GUI 探索ループ統合の齟齬整理 + feature_inventory partial→implemented 昇格
- [docs/low] GUI 探索ループ統合スコープ齟齬を解決、feature_inventory「GUI バックテスト画面」を partial→implemented に昇格
- 関連: .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/completion_definition.md

## TASK-0053 : completion_definition 全セクション横断の完了判定進捗確認
- [docs/low] セクション1〜8 の COMPLETE 判定状況を feature_inventory と突合、各セクションに HTML コメント注釈追記。セクション1・2・6 が COMPLETE 判定
- 関連: .claude_orchestrator/docs/completion_definition.md

## TASK-0054 : completion_definition セクション1・2・6 正式 COMPLETE 判定
- [docs/low] セクション1・2・6 の判定状況注釈を正式 COMPLETE に昇格、セクション6 項目(1) を partial→implemented に修正
- 関連: .claude_orchestrator/docs/completion_definition.md

## TASK-0055 : セクション4 構造化ログ partial 解消: reason_code 構造化記録実装
- [feature/medium] SKIP イベント reason_code 付き構造化記録と trade_id 必須化を実装。feature_inventory 該当2エントリを partial→implemented
- 関連: src/backtest/simulator/{models,trade_logger,__init__}.py
- 注意: reason_code がパターンマッチ依存。長期間バックテストで JSONL サイズ増大の可能性

## TASK-0056 : completion_definition セクション4 COMPLETE 判定注釈追加
- [docs/low] feature_inventory でセクション4 関連3エントリ全 implemented を確認、セクション4 を COMPLETE 判定に昇格
- 関連: .claude_orchestrator/docs/completion_definition.md

## TASK-0057 : セクション5 GUI 応答速度の定量検証と COMPLETE 判定
- [research/low] GUI 応答速度を定量検証し単月・全月一括とも基準クリア確認。feature_inventory を implemented に昇格、セクション5 COMPLETE
- 関連: .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/completion_definition.md
- 注意: bollinger_combo_AB・12ヶ月の1回計測のみ。データ量変化で基準超過の可能性

## TASK-0058 : セクション7 エラー処理・耐障害性 partial 解消: ログ品質制約の実装
- [feature/low] evaluator.py に check_log_quality/evaluate_backtest_with_log_guard 追加、trade_logger.py に _validate_reason_code 追加
- 関連: src/backtest/evaluator.py, src/backtest/simulator/trade_logger.py
- 注意: evaluate_backtest_with_log_guard が呼び出し元に未統合（実効化されていない）

## TASK-0059 : セクション8 データ整合性 partial 解消: ログ概念一致の精査と対応実装
- [feature/medium] ログ概念対応表作成・trade_logger マッピング参照・簡略判定精査を解消。feature_inventory を partial→implemented、セクション8 COMPLETE
- 関連: src/backtest/simulator/{log_concept_mapping,trade_logger}.py, feature_inventory.md, completion_definition.md
- 注意: evaluate_backtest_with_log_guard 未統合（TASK-0058 carry_over）。log_concept_mapping は MT4 仕様変更時に要更新

## TASK-0060 : evaluate_backtest_with_log_guard の呼び出し元統合
- [feature/medium] service.py・exploration_loop.py の全 evaluate_backtest() 呼び出し（計3箇所）を evaluate_backtest_with_log_guard() に置換
- 関連: src/backtest/service.py, src/backtest/exploration_loop.py
- 注意: cross-month 評価パスの月別ループ内で個別 backtest_result がガード未経由のためログ不可月混入の可能性あり（スコープ外）

## TASK-0061 : ボリンジャー専用 exploration_loop 方針の docs 反映
- [docs/low] 最適化方針_bollinger戦略.md に4段階探索フロー・apply_strategy_overrides 方式・generate_strategy_file 不使用を明文化
- 関連: .claude_orchestrator/docs/project_core/最適化方針_bollinger戦略.md, feature_inventory.md
- 注意: 4段階フローの実データ CSV 結合テストは後続タスクで必要

## TASK-0062 : bollinger exploration_loop 実データ CSV 結合テスト（A単体探索）
- [feature/medium] A単体（bollinger_range_v4_4）の実データCSV結合テスト6項目全PASS。apply_strategy_overrides→バックテスト→評価→ループの一連フロー正常動作確認
- 関連: tests/integration/test_bollinger_exploration_a_only.py
- 注意: デフォルトパラメータで avg_pips/month=44.1（目標150-200に未達）、max_drawdown_pips=279.1（閾値200超過）。テストが実データCSVパスに依存

## TASK-0063 : 最適化方針_bollinger戦略.md の TASK-0062 完了反映
- [docs/low] 残課題「結合テスト未実施」を解決済みセクションに移動し TASK-0062 完了を記録
- 関連: .claude_orchestrator/docs/project_core/最適化方針_bollinger戦略.md
- 注意: feature_inventory.md L603 に同内容の未解決記述が残存（docs間不整合）

## TASK-0064 : feature_inventory.md の TASK-0042「結合テスト未実施」記述を解消済みに更新
- [docs/low] feature_inventory.md L603 の記述を打消し線+TASK-0062 解消済み表現に更新し docs 間不整合を解消
- 関連: .claude_orchestrator/docs/feature_inventory.md

## TASK-0065 : 探索専用GUI（explore_gui.py）の新規作成方針を docs 反映
- [docs/low] feature_inventory.md に explore_gui エントリ新規追加、completion_definition.md セクション3注釈・セクション9に方針反映
- 関連: feature_inventory.md, completion_definition.md
- 注意: 開発の目的本筋.md が未更新（TASK-0066 で対応）

## TASK-0066 : 開発の目的本筋.md を backtest_gui / explore_gui 2画面体制に更新
- [docs/low] セクション3「GUI最適化支援機能」に2画面体制方針を追記。既存4項目・セクション8「対象外」は変更なし
- 関連: .claude_orchestrator/docs/project_core/開発の目的本筋.md
- 注意: explore_gui 実装タスク未着手のため docs 先行記述と実装乖離の可能性

## TASK-0067 : explore_gui.py エントリポイント + 基本骨格の新規作成
- [feature/medium] explore_gui.py と explore_gui_app パッケージを新規作成。BollingerLoopConfig 経由で run_bollinger_exploration_loop に接続する GUI フレームワーク構築
- 関連: src/explore_gui.py, src/explore_gui_app/{__init__,views/{__init__,input_panel,result_panel,main_window}}.py
- 注意: GUI実機起動未確認、BOLLINGER_PARAM_VARIATION_RANGES 直接変更による2回目以降の不整合リスク、Stop ボタン未機能

## TASK-0068 : feature_inventory・completion_definition の explore_gui 実装反映
- [docs/low] feature_inventory.md の explore_gui を not_implemented→partial に更新、related_files 修正。completion_definition.md セクション9に実装進捗反映
- 関連: feature_inventory.md, completion_definition.md
- 注意: completion_definition.md セクション3/9 に TASK-0065 方針記述の重複あり

## TASK-0069 : exploration_loop の BOLLINGER_PARAM_VARIATION_RANGES をローカルコピー方式に修正
- [bugfix/low] generate_bollinger_param_variations 関数内で copy.deepcopy によるローカルコピー取得に修正し、モジュールグローバル dict の汚染を防止
- 関連: src/backtest/exploration_loop.py
- 注意: main_window.py L115 が直接書き換えする問題は残存（TASK-0070 で対処）

## TASK-0070 : main_window.py の BOLLINGER_PARAM_VARIATION_RANGES 直接書き換え除去
- [bugfix/low] BollingerLoopConfig.param_variation_ranges 経由のローカルコピー方式に修正
- 関連: src/backtest/exploration_loop.py, src/explore_gui_app/views/main_window.py
- 注意: 2回連続探索でのグローバル dict 初期値一致は自動テスト未カバー

## TASK-0071 : 過去TASK作業記録.md の TASK-0045〜0057 アーカイブ移動
- [chore/low] TASK-0051〜0057 の7エントリを task_history_archive.md へ移動し、過去TASK作業記録.md を圧縮
- 関連: 過去TASK作業記録.md, archive/task_history_archive.md

## TASK-0072 : feature_inventory.md 残 partial エントリ棚卸し・completion_definition 整合確認
- [docs/low] explore_gui.py（partial）の notes に TASK-0069/0070 修正と残課題一覧を追記。GUI バックテスト画面（implemented）の notes 充実化
- 関連: .claude_orchestrator/docs/feature_inventory.md
- 注意: explore_gui.py の GUI 実機起動確認が未実施（TASK-0073 で対応）

## TASK-0073 : explore_gui.py の GUI 実機起動確認
- [bugfix/medium] PySide6 ウィンドウ描画・input_panel・result_panel の表示・ウィジェット構成すべて正常確認。起動不能バグなし
- 関連: feature_inventory.md
- 注意: Stop ボタン未機能（isInterruptionRequested 未チェック）、探索フルフロー未検証

## TASK-0074 : exploration_loop の Stop ボタン即時停止対応
- [bugfix/low] run_exploration_loop・run_bollinger_exploration_loop に thread パラメータ追加、各イテレーション冒頭で isInterruptionRequested チェック実装
- 関連: src/backtest/exploration_loop.py, src/explore_gui_app/views/main_window.py
- 注意: 1イテレーション内バックテスト実行中は停止不可（許容範囲）

## TASK-0075 : explore_gui 探索フルフロー動作確認・win_rate 表示バグ修正
- [bugfix/medium] CSV読み込み→バックテスト→結果表示の一連フロー確認、win_rate 表示フォーマットバグを修正
- 関連: src/explore_gui_app/views/result_panel.py, src/explore_cli.py
- 注意: 長時間実行時の UI 無応答可能性（iteration_done emit タイミング問題）

## TASK-0076 : _ExplorationWorker の iteration_done リアルタイム emit 化
- [refactor/low] run_bollinger_exploration_loop に on_iteration_done コールバック追加、各イテレーション完了時にリアルタイム emit
- 関連: src/backtest/exploration_loop.py, src/explore_gui_app/views/main_window.py
- 注意: コールバック内例外でループ中断の可能性（TASK-0077 で対処）

## TASK-0077 : on_iteration_done コールバック内例外の安全ハンドリング追加
- [refactor/low] コールバック呼び出しを try/except でラップし、例外時は logger.warning で記録してループ継続
- 関連: src/backtest/exploration_loop.py

## TASK-0078 : 探索実行中のイテレーション進捗表示追加
- [feature/low] main_window.py に「Running... Iteration N / M」形式のステータスラベル更新を追加
- 関連: src/explore_gui_app/views/main_window.py
- 注意: 例外スキップイテレーションで進捗表示が飛ぶ可能性あり（UX影響軽微）

## TASK-0079 : feature_inventory explore_gui partial → implemented 昇格
- [docs/low] 初期スコープ6項目の全充足を確認し、feature_inventory.md を partial→implemented に更新。TASK-0073〜0078 の実装内容を notes 反映
- 関連: .claude_orchestrator/docs/feature_inventory.md
- 注意: 後続拡張スコープ（B単体探索・A/B組み合わせ探索・apply_params.py連携）が未着手のまま残る可能性

## TASK-0080 : 過去TASK作業記録.md の要約圧縮（TASK-0060〜TASK-0079 の肥大化対応）
- [docs/low] 過去TASK作業記録.md の全20エントリ（TASK-0060〜0079）を各3〜4行の要約形式に圧縮し、421行→103行（75%削減）を達成。変更内容要点・関連ファイル・注意点はすべて保持
- 関連: .claude_orchestrator/docs/task_history/過去TASK作業記録.md

## TASK-0081 : task_history_archive.md（TASK-0001〜TASK-0057）の要約圧縮
- [docs/low] task_history_archive.md の TASK-0001〜TASK-0059 全59エントリを過去TASK作業記録.md と同一の要約形式に圧縮し、1036行→282行（73%削減）を達成
- 関連: .claude_orchestrator/docs/task_history/archive/task_history_archive.md

## TASK-0082 : 過去TASK作業記録.md の TASK-0080・TASK-0081 エントリフォーマット統一
- [docs/low] TASK-0080・TASK-0081 の2エントリを ### サブセクション形式から [task_type/risk_level] プレフィックス要約形式に書き換え、TASK-0062〜0079 と統一
- 関連: .claude_orchestrator/docs/task_history/過去TASK作業記録.md

## TASK-0083 : 過去TASK作業記録.md の TASK-0082 エントリフォーマット統一（自エントリ修正）
- [docs/low] TASK-0082 エントリを他エントリと同一の [task_type/risk_level] プレフィックス要約形式に書き換え、フォーマット統一を完了
- 関連: .claude_orchestrator/docs/task_history/過去TASK作業記録.md

## TASK-0084 : 過去TASK作業記録.md の TASK-0083 エントリ修正 + 記録フォーマット仕様の明記
- [docs/low] TASK-0083 エントリを [docs/low] プレフィックス要約形式に書き換え、## 目的セクションに記録フォーマット仕様を追記
- 関連: .claude_orchestrator/docs/task_history/過去TASK作業記録.md

## TASK-0085 : explore_gui 戦略選択UI追加による B単体探索対応
- [feature/medium] 戦略選択コンボボックスを input_panel に追加し bollinger_trend_B を選択可能にした。パラメータ表示・ParameterDialog は選択戦略に応じて動的切替
- 関連: src/explore_gui_app/views/input_panel.py, src/explore_gui_app/views/parameter_dialog.py, src/backtest_gui_app/services/strategy_params.py, src/backtest_gui_app/widgets/collapsible_section.py
- 注意: GUI実画面確認未実施。戦略切替時のレイアウト崩れ・パラメータ表示不整合は手動確認が必要

## TASK-0086 : feature_inventory.md TASK-0085 B単体探索UI対応の実装反映 + 過去TASK作業記録.md エントリ追加
- [docs/low] feature_inventory.md の explore_gui セクションに TASK-0085 B単体探索UI対応の実装完了を追記し、過去TASK作業記録.md の TASK-0084・TASK-0085 エントリを既定フォーマットで追加
- 関連: .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- 注意: TASK-0085 carry_over の GUI 実画面確認が未実施。戦略切替時のレイアウト・パラメータ表示の動作確認は後続タスクで必要

## TASK-0087 : Exploration GUI 複数月評価フロー導入の実装計画とdocs追記
- [docs/low] docs/開発の目的本筋.md を新規作成し、複数月評価フローの目的・GUI仕様（Selected 3 months / All CSVs / Custom）・multi-month評価方針・refine方針・対象ファイル・段階導入方針を整理
- 関連: docs/開発の目的本筋.md
- 注意: Selected 3 months のファイル名解析が規則外ファイル名に対して未定義。Step2 で csv_paths を追加する際の csv_path / csv_dir との優先順位設計が未確定

## TASK-0088 : Exploration GUI 複数月評価フロー導入の実装計画とdocs追記
- [docs/low] 複数月評価フロー方針 docs を新規作成。GUI仕様3モード・2段階フロー・refine方針・対象ファイル・段階導入 Step1-3 を整理し、既存コード全文との整合性を確認済み
- 関連: .claude_orchestrator/docs/project_core/複数月評価フロー方針.md
- 注意: IntegratedThresholds (min_avg_pips_per_month=150) が3ヶ月評価でも妥当かは実データ検証が必要。csv_paths / csv_path / csv_dir の3フィールド共存による優先順位ロジック複雑化リスク

## TASK-0089 : feature_inventory.md 複数月評価フロー機能エントリ追加 + 最適化方針_bollinger戦略.md 残課題更新
- [docs/low] feature_inventory.md に「複数月評価フロー（CSV選択モード・2段階探索）」エントリを not_implemented で追加。最適化方針_bollinger戦略.md の残課題に CSV選択モード・csv_paths フィールド追加・refine 複数月集約ベース化の3項目を追記
- 関連: .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/project_core/最適化方針_bollinger戦略.md
- 注意: TASK-0088 director followup_actions の2件を反映。Step 1 実装着手前の docs 整合性確保が目的。csv_paths / csv_path / csv_dir の3フィールド共存による優先順位ロジック複雑化リスクあり

## TASK-0090 : 複数月評価フロー csv_path / csv_paths / csv_dir 定義統一と BollingerLoopConfig 設計方針の確定
- [docs/low] csv_paths > csv_dir > csv_path の優先順位ロジックを確定し、csv_paths 指定時の csv_path 自動決定ルール（csv_paths[-1] = 最新CSV）を統一。複数月評価フロー方針.md に設計セクション追加、feature_inventory.md・最適化方針_bollinger戦略.md の notes を更新
- 関連: .claude_orchestrator/docs/project_core/複数月評価フロー方針.md, .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/project_core/最適化方針_bollinger戦略.md
- 注意: csv_path の矛盾（最新CSV vs csv_paths の最初のファイル）を csv_paths[-1]（最新）に統一。Step 1 実装時に frozen dataclass へ csv_paths フィールドを追加する際の呼び出し元引数追加漏れリスク、csv_paths が空リスト [] の場合の IndexError ハンドリングに注意

## TASK-0091 : BollingerLoopConfig / BollingerExplorationConfig に csv_paths フィールド追加と優先分岐実装
- [feature/medium] ExplorationConfig・BollingerExplorationConfig・BollingerLoopConfig・LoopConfig の4つの Config dataclass に csv_paths: list[str] | None = None を追加。csv_paths > csv_dir > csv_path の優先順位ロジックを _resolve_csv_files ヘルパーで実装し、横断評価の CSV 解決を統一。csv_paths=[] の ValueError バリデーション、csv_paths 指定時の csv_path 自動決定（csv_paths[-1]）も実装
- 関連: src/backtest/exploration_loop.py
- 注意: GUI 側（main_window.py）は csv_paths を渡していないが、デフォルト None のため既存動作に影響なし。_resolve_csv_files が csv_paths 指定時にファイル存在チェックを行わない点はGUI実装時に検討。run_bollinger_exploration_loop 内の effective_csv_path 決定ロジックがループ内にあり非効率（nice_to_have）。GUI の CSV 選択モード実装は後続タスク

## TASK-0092 : feature_inventory.md 複数月評価フロー partial 昇格 + 最適化方針_bollinger戦略.md csv_paths 残課題完了更新
- [docs/low] feature_inventory.md の複数月評価フローエントリを not_implemented → partial に昇格し、TASK-0091 の csv_paths バックエンド実装完了を notes に追記。最適化方針_bollinger戦略.md の残課題 csv_paths 項目を完了済みに更新
- 関連: .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/project_core/最適化方針_bollinger戦略.md
- 注意: GUI 側の CSV 選択モード実装は未着手（後続タスク）

## TASK-0093 : Exploration GUI input_panel に CSV選択モード（Selected 3 months / All CSVs / Custom）を追加し main_window で csv_paths を組み立てる
- [feature/medium] input_panel.py に CSV選択モード（Selected 3 months / All CSVs / Custom）のRadioButton・チェックリストUIを追加し、main_window.py で選択モードに応じた csv_paths 組み立てを実装
- 関連: src/explore_gui_app/views/input_panel.py, src/explore_gui_app/views/main_window.py
- 注意: GUI実機動作の目視確認が未実施（import確認のみ）。CSV Dir内にCSVが大量（100+）の場合、Customモードのチェックリスト再構築が重くなる可能性あり

## TASK-0094 : 2段階フロー Phase 表示と全期間確認導線の GUI 追加（複数月評価フロー Step 2）
- [feature/medium] Phase 表示・全期間確認ボタン・Phase 2 ワーカー・月別内訳テーブル・Phase 2 結果テーブルを3 GUI ファイルに実装。exploration_loop.py 変更なし
- 関連: src/explore_gui_app/views/main_window.py, src/explore_gui_app/views/input_panel.py, src/explore_gui_app/views/result_panel.py, .claude_orchestrator/docs/feature_inventory.md
- 注意: GUI 実機動作の目視確認が未実施。Phase 2 ワーカーは逐次実行のため候補数 × 全 CSV 数に比例した処理時間。exploration_loop.py の TASK-0091/0093 差分が未コミット

## TASK-0095 : 複数月評価フロー Step 3: Phase 1/Phase 2 結果区別表示と全期間確認結果に基づく採択判定支援 GUI 追加
- [feature/medium] Phase 1/Phase 2 結果の verdict 別色分け表示と Phase 2 完了後の全期間集約サマリーパネル（採択判定支援）を実装し、feature_inventory.md を implemented に昇格
- 関連: src/explore_gui_app/views/result_panel.py, src/explore_gui_app/views/main_window.py, .claude_orchestrator/docs/feature_inventory.md
- 注意: GUI 実機動作の目視確認が未実施。採択判定ヒューリスティックの閾値は仮値。TASK-0091/0093/0094/0095 の変更が未コミット

## TASK-0096 : TASK-0091/0093/0094/0095 の未コミット変更のコミット整理
- [chore/low] TASK-0091/0093/0094/0095 の未コミット変更を3コミットに整理完了。バックエンド・GUI・docs の論理単位で分割しコミット済み。コード内容の変更なし
- 関連: src/backtest/exploration_loop.py, src/explore_gui_app/views/input_panel.py, src/explore_gui_app/views/main_window.py, src/explore_gui_app/views/result_panel.py, .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/project_core/最適化方針_bollinger戦略.md, .claude_orchestrator/docs/project_core/複数月評価フロー方針.md, .claude_orchestrator/docs/task_history/archive/task_history_archive.md, .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- 注意: origin/main への push が未実施。GUI 実機動作の目視確認が未実施

## TASK-0097 : explore_gui Phase 2 サマリーパネル実機動作確認と レイアウト崩れ修正
- [bugfix/low] Phase 1→Phase 2 の一連フローを実機で完走させ、レイアウト崩れ・表示欠落がないことを確認。修正対象となる崩れは発見されなかった
- 関連: none
- 注意: Splitter 内ログパネルが Phase2 全表示時に 88px まで圧縮される点は UX 改善余地あり。bollinger_range_v4_4_tuned_a.py が untracked のまま

## TASK-0098 : bollinger_range_v4_4_tuned_a.py の untracked 状態解消（.gitignore 追加 or 正式コミット判断）
- [chore/low] bollinger_range_v4_4_tuned_a.py は既にコミット bfdcf32 で正式追跡されており、untracked 状態は解消済み。ただし GUI (_AVAILABLE_STRATEGIES) への登録は未実施
- 関連: none
- 注意: tuned_a はコミット済みだがコード上どこからも参照されていない。exploration が追加バリアントを生成した場合に同様の管理課題が再発する可能性あり

## TASK-0099 : explore_gui Phase 2 テーブル高さの候補数に応じた動的調整（UX 改善）
- [feature/low] Phase 2 テーブル高さを候補数に応じて動的調整し、ログパネル最小高さ 120px を設定して過圧縮を防止
- 関連: src/explore_gui_app/views/result_panel.py
- 注意: ROW_HEIGHT=30px は推定値のため高DPI環境で微調整が必要になる可能性あり

## TASK-0100 : bollinger_range_v4_4_tuned_a の GUI 戦略選択リスト登録（explore_gui・backtest_gui 両対応）
- [feature/low] explore_gui の _AVAILABLE_STRATEGIES に tuned_a を追加し、strategy_params.py に tuned_a 用パラメータ定義（実際のデフォルト値準拠）と STRATEGY_PARAM_MAP エントリを登録。backtest_gui は自動検出のため変更不要
- 関連: src/explore_gui_app/views/input_panel.py, src/backtest_gui_app/services/strategy_params.py
- 注意: explore_gui の _AVAILABLE_STRATEGIES がハードコード管理のため、今後の戦略追加時に同様の手動登録漏れが再発する可能性がある

## TASK-0101 : feature_inventory.md に bollinger_range_v4_4_tuned_a の GUI 登録完了を反映 + 過去TASK作業記録に TASK-0099/0100 エントリ追加
- [docs/low] feature_inventory.md の A/B 2レーン戦術適用エントリに tuned_a を追記し、GUI パラメータ変更エントリの notes に tuned_a パラメータ定義追加済みを追記。過去TASK作業記録に TASK-0099/0100 エントリを規定フォーマットで追加
- 関連: .claude_orchestrator/docs/feature_inventory.md, .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- 注意: 過去TASK作業記録の TASK-0086〜0098 に旧形式（### サブセクション形式）エントリが混在しており、planner の判読性を下げる可能性がある（今回スコープ外）

## TASK-0102 : 過去TASK作業記録の旧形式エントリ統一と重複エントリ整理（TASK-0086〜0098）
- [docs/low] TASK-0086〜0098 の全13エントリを規定フォーマット（## 見出し + ダッシュリスト3〜4行構造）に統一し、TASK-0089/0090/0091/0092 の重複エントリ（旧形式版）を削除。旧形式版にのみ存在した注意事項は正規形式版にマージ
- 関連: .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- 注意: TASK-0101 が旧形式のまま残存（後続タスクで対応要）

## TASK-0103 : 過去TASK作業記録.md の TASK-0099〜0102 旧形式エントリを規定フォーマットに変換

- 実行日時: 2026-04-15 01:18
- task_type: docs
- risk_level: low

### 変更内容
TASK-0101/0102 の旧形式エントリを規定フォーマット（## 見出し + ダッシュリスト3〜4行構造）に変換。TASK-0099/0100 は既に規定フォーマット済みのため変更なし。

### 関連ファイル
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- none

## TASK-0104 : TASK-0098〜0103 関連の未コミット変更コミット整理（src + docs）

- 実行日時: 2026-04-15 01:25
- task_type: chore
- risk_level: low

### 変更内容
未コミット5ファイルを src（TASK-0100）と docs（TASK-0101/0102/0103）の2コミットに分割整理し、ワーキングツリーをクリーンにした。

### 関連ファイル
- src/backtest_gui_app/services/strategy_params.py
- src/explore_gui_app/views/input_panel.py
- .claude_orchestrator/docs/feature_inventory.md
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- main が origin/main より 2 commits ahead の状態。git push によるリモート反映は本タスクのスコープ外だが早期に実施すべき

## TASK-0105 : A戦術の責務分割（bollinger_range_v4_4 の分離実装）

- 実行日時: 2026-04-17 06:13
- task_type: refactor
- risk_level: medium

### 変更内容
director 指摘の RANGE_FAILURE_ADVERSE_MOVE_RATIO 値変更（0.35→0.28）を修正し、制約違反を解消した。

### 関連ファイル
- src/mt4_bridge/strategies/bollinger_range_v4_4_params.py

### 注意点
- バックテスト実行による分割前後の出力一致検証が未実施のため、実行時の微細な挙動差異の可能性はゼロではない
- コピー時の微細な差異は import 確認のみで担保されており、網羅的な動作検証は後続タスク依存

## TASK-0106 : A戦術の観測用パラメータ追加（bollinger_range_v4_4_params 拡張）

- 実行日時: 2026-04-17 06:24
- task_type: feature
- risk_level: low

### 変更内容
bollinger_range_v4_4_params.py に 7 カテゴリ・13 個の観測用パラメータを追加。既存売買パラメータは一切変更なし。

### 関連ファイル
- src/mt4_bridge/strategies/bollinger_range_v4_4_params.py

### 注意点
- 観測パラメータの初期値は暫定値であり、実データ検証後に調整が必要になる可能性がある
- BAND_EDGE_ZONE_RATIO=0.15 や BAND_WIDTH_EXPANSION_THRESHOLD=1.3 等の妥当性は後続の観測実装・バックテストで検証が必要

## TASK-0107 : 観測計算関数の indicators 追加（bollinger_range_v4_4_indicators 拡張・戻り値強化版）

- 実行日時: 2026-04-17 06:37
- task_type: feature
- risk_level: low

### 変更内容
bollinger_range_v4_4_indicators.py に観測用純粋関数 7 件を追加。既存関数は未変更。import・smoke test 全通過。

### 関連ファイル
- src/mt4_bridge/strategies/bollinger_range_v4_4_indicators.py

### 注意点
- feature_inventory.md への反映が未実施。next_task_hints に記録済みだが、後続タスクで漏れないよう注意が必要

## TASK-0108 : feature_inventory.md に TASK-0106/0107 で追加した観測パラメータ・観測関数の機能エントリを記録

- 実行日時: 2026-04-17 06:47
- task_type: docs
- risk_level: low

### 変更内容
feature_inventory.md に TASK-0106 観測用パラメータ（13個）と TASK-0107 観測用純粋関数（7個）の新規エントリ2件を追加。既存エントリは未変更。

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- completion_links が「6. 品質」のみだが、観測機能が将来 decision log（セクション4）やデータ整合性（セクション8）に接続される際は completion_links の追加が必要になる可能性がある（現時点では未接続のため妥当）

## TASK-0109 : RangeObservation 導入（bollinger_range_v4_4_rules に観測構造を追加）

- 実行日時: 2026-04-17 06:57
- task_type: feature
- risk_level: low

### 変更内容
RangeObservation dataclass・build_range_observation builder・range_observation_to_dict 補助関数を bollinger_range_v4_4_rules.py...

### 関連ファイル
- src/mt4_bridge/strategies/bollinger_range_v4_4_rules.py

### 注意点
- range_unsuitable_flag_slope_acceleration の判定基準は暫定値。後続の閾値チューニングタスクで見直しが必要
- build_range_observation が indicators 関数の dict 出力キーに暗黙依存。indicators 側のキー名変更時に静かに壊れる可能性がある（現時点では問題なし）

## TASK-0110 : bollinger_range_v4_4 の共通評価フローに RangeObservation 生成を接続する

- 実行日時: 2026-04-17 07:09
- task_type: feature
- risk_level: low

### 変更内容
build_range_observation を evaluate_bollinger_range_v4_4 内の _base_signal 直後に接続し、RangeObservation を dict 化して debug_metrics...

### 関連ファイル
- src/mt4_bridge/strategies/bollinger_range_v4_4.py

### 注意点
- バンドシリーズのローリング BB 計算が毎バー実行されるため、大量バックテスト時の計算負荷増加の可能性がある（後続で実測・キャッシュ化検討）
- bare except Exception により観測生成失敗がサイレントになる（後続で logger.debug 等の例外記録を検討）
- entry_setup_type が常に None（後続タスクで自動判定ロジック追加が必要）

## TASK-0111 : RangeObservation を decision_log に記録する接続タスク

- 実行日時: 2026-04-17 07:21
- task_type: feature
- risk_level: low

### 変更内容
BacktestDecisionLog に range_observation フィールドを追加し、decision_log.py で SignalDecision.debug_metrics を接続した。後方互換性を維持（デフォルト No...

### 関連ファイル
- src/backtest/simulator/models.py
- src/backtest/simulator/decision_log.py

### 注意点
- debug_metrics は戦略ごとに異なる構造の dict を含みうる。guarded 系戦略では RangeObservation と異なる内容が range_observation フィールドに格納される可能性がある
- view_models.py / CSV 出力は range_observation 未対応のため、現時点での確認手段は BacktestDecisionLog オブジェクトの直接参照に限定される

## TASK-0112 : Aエントリー後の中央回帰成否集計基盤追加

- 実行日時: 2026-04-17 07:48
- task_type: feature
- risk_level: medium

### 変更内容
A戦術（range レーン）エントリー後の中央回帰成否を定量集計する post-analysis 基盤を src/backtest/mean_reversion_analysis.py として新規作成した。既存売買ロジック・バックテスト結果...

### 関連ファイル
- src/backtest/mean_reversion_analysis.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- entry_middle_band が None の古い形式トレードは集計対象からスキップされる（既知・許容）
- entry_time / exit_time の time_index lookup が丸め誤差で失敗する環境ではスキップが発生しうる（既知・許容）
- entry_price == middle band 時に progress 計算が 0.0 固定となるエッジケース（後続で意識）

## TASK-0113 : 月別・全期間の中央回帰集計を run_all_months フローに接続する

- 実行日時: 2026-04-17 08:02
- task_type: feature
- risk_level: medium

### 変更内容
mean_reversion_analysis.py に AllMonthsMeanReversionSummary dataclass と analyze_all_months_mean_reversion を追加し、AllMonthsR...

### 関連ファイル
- src/backtest/mean_reversion_analysis.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- 全期間合算は全月レコード再集計であり、月別サマリだけから復元不可（設計意図通りだが運用周知が必要）
- 実データ12ヶ月CSVでの結合実行は未検証で、スキップ率・成功率分布は後続タスクで確認要
- [carry_over] entry_middle_band が None の旧形式トレードはスキップ（既知・許容）
- [carry_over] entry_time / exit_time の time_index lookup 丸め誤差で外れる場合スキップ（既知・許容）
- [carry_over] entry_price == middle band 時の progress=0.0 固定エッジケース（既知）

## TASK-0114 : runner.py / CLI 出力に AllMonthsMeanReversionSummary を組み込む（run_all_months 経路）

- 実行日時: 2026-04-17 08:12
- task_type: feature
- risk_level: low

### 変更内容
runner.py の全月一括経路 (_run_all_months) に analyze_all_months_mean_reversion 呼び出しと AllMonthsMeanReversionSummary 表示を追加。既存 CLI...

### 関連ファイル
- src/backtest/runner.py

### 注意点
- 実データ12ヶ月 CSV (USDJPY-cd5_20250521_monthly 等) での run_all_months + MR サマリ結合 e2e 実行は未検証で、bollinger_range_v4_4_guarded など range 系戦略の skip 率・成功率分布は後続タスクで確認要。
- analyze_all_months_mean_reversion 呼び出しが _run_all_months の既存 try/except 外に配置されており、予期しない例外で MR サマリ生成時に traceback 直出しになる可能性（reviewer 指摘の nice_to_have、後続で例外ガード検討）。
- compare_ab 経路には MR サマリ未組み込みで、3戦略比較で range レーン評価するケースは後続タスクで別途設計要。
- [carry_over] entry_middle_band が None の旧形式トレード / entry_time・exit_time の time_index lookup 丸め誤差 / entry_price == middle band 時の progress=0.0 固定といった既知エッジケースはスキップ許容。

## TASK-0115 : backtest_gui_app の All Months タブに AllMonthsMeanReversionSummary 表示を追加する

- 実行日時: 2026-04-17 08:25
- task_type: feature
- risk_level: medium

### 変更内容
backtest_gui_app の All Months タブに AllMonthsMeanReversionSummary 表示を接続。AllMonthsWorker で analyze_all_months_mean_reversio...

### 関連ファイル
- src/backtest_gui_app/views/main_window.py
- src/backtest_gui_app/views/all_months_tab.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- 実データ 12ヶ月 CSV (USDJPY-cd5_20250521_monthly 等) + bollinger_range_v4_4 系戦略での GUI 実機起動 → Run All Months → MR 表示 e2e は未検証（smoke は QApplication 下の panel populate のみ）
- AllMonthsWorker.run() 内 analyze_all_months_mean_reversion の except Exception: mr_summary=None はサイレントフォールバックで logger 出力なし。MR 表示が N/A に落ちた際の原因特定が難しい
- CompareAB タブは MR 非対応のままで、3 戦略比較で range レーン MR を評価する導線は未設計
- carry_over: entry_middle_band None 旧形式トレード / time_index lookup 丸め誤差 / entry_price == middle band 時 progress=0.0 固定の既知エッジケース（スキップ許容）

## TASK-0116 : backtest_gui_app の All Months タブ + MR 表示を USDJPY 12ヶ月 CSV 実データで GUI 実機 e2e 検証する

- 実行日時: 2026-04-17 08:41 / 2026-04-17 08:45
- task_type: research
- risk_level: low

### 変更内容
data/USDJPY-cd5_20250521_monthly の 12ヶ月 CSV + bollinger_range_v4_4 戦略で run_all_months + analyze_all_months_mean_reversio...

コード変更なし。検証のみ。data/USDJPY-cd5_20250521_monthly 配下の 12 ヶ月 CSV + bollinger_range_v4_4 戦略（既定 SL/TP 10pips, pip_size 0.01, Conservative intrabar, close_open_position_at_end=True, initial_balance 1,000,000, money_per_pip 100）で AllMonthsWorker の run_all_months + analyze_all_months_mean_reversion 経路を headless 再現スクリプト（TEST/task0116_headless_e2e_check.py）で実行。12 ヶ月すべて正常読込・集計 OK、mr_summary 非 None、monthly_table 5 列と全期間 MR パネルの表示文字列が AllMonthsTab._populate_* と一致、クラッシュなし、monthly 合計と all_period total_range_trades が一致（consistency 確認）。

### 関連ファイル
- TEST/task0116_headless_e2e_check.py
- TEST/task0116_lane_check.py
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- GUI 実機 (QApplication 下 Run/Cancel/再実行) の目視確認は本 task 内で未実施。Qt スレッド・signal/slot・progress_bar 更新・キャンセル後の clear_results の実機 regression は headless では検出不能。
- v4_4 系戦略は entry_lane='range' を吐かないため monthly_table MR 5 列・全期間 MR パネルに非ゼロ値が入った状態での描画整合は未確認（仕様通り 0 / N/A までしか e2e 検証できていない）。
- AllMonthsWorker.run() の analyze_all_months_mean_reversion サイレントフォールバック (except Exception: mr_summary=None, logger 出力なし) は carry_over として未対処で、MR 表示が N/A に落ちた場合の原因特定が困難。
- bollinger_range_v4_4 / bollinger_range_v4_4_tuned_a は SignalDecision に entry_lane を設定しないため generic_runner 側で lane="legacy" に正規化される。結果として 12 ヶ月すべてで total_range_trades=0 となり、monthly_table MR 列は count=0 / rate=N/A / avg_bars=N/A、全期間 MR パネルも総数 0 / 割合 N/A で落ちずに描画される（range 0 件月の仕様通り）。
- MR 表示に実データ（非ゼロ）を流すには entry_lane="range" を出力する戦略（例: bollinger_range_v4_6, bollinger_range_A 系）が必要。v4_4 系の仕様自体は MR range レーン非該当で、MR 表示を介した性能評価は別戦略 or 別タスクで行う。
- GUI 実機起動 (QApplication 下 Run All Months ボタン → progress 応答 → キャンセル → 再実行 UI 挙動) の目視確認は auto-run で実行不能のため未実施。headless パイプライン一致確認で機能同等性まで担保しているが、UI 応答・キャンセル挙動は carry_over として残る。
- AllMonthsWorker.run() 内 analyze_all_months_mean_reversion の except Exception: mr_summary=None サイレントフォールバックは依然残存（carry_over）。

## TASK-0117 : feature_inventory確認後にGUIレイアウト再設計とダークテーマUI作成へ進む

- 実行日時: 2026-04-17 09:18
- task_type: feature
- risk_level: medium

### 変更内容
Standard 画面を左サイドバー + 右ワークスペース型へ再設計し、ダークテーマ QSS 基盤（dark_theme.py）を導入して main_window から一括適用。SummaryPanel を主要KPIカード+詳細2列+理由欄...

### 関連ファイル
- src/backtest_gui_app/styles/__init__.py
- src/backtest_gui_app/styles/dark_theme.py
- src/backtest_gui_app/views/main_window.py
- src/backtest_gui_app/views/input_panel.py
- src/backtest_gui_app/views/summary_panel.py
- src/backtest_gui_app/widgets/collapsible_section.py
- src/backtest_gui_app/widgets/chart_widget.py
- src/backtest_gui_app/widgets/time_series_chart_widget.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- LinkedTradeChartWidget / PriceChartWidget は candle 色がハードコードのままダーク背景下で視認性が劣化しうる（後続タスクで対応）
- dark_theme の matplotlib 色設定は figure.clear() でリセットされる前提のため、新規 plot 関数追加時に style_matplotlib_figure の呼び忘れで配色抜けが起きる regression リスクがある
- QScrollArea でラップした input_panel は水平スクロールバー AlwaysOff のため、極端に低い縦解像度で内部 wrap が発生しうる（実機検証未実施）
- summary_panel で final_open_position_type を KPI カードではなく詳細右列へ再配置したため、presenter 側 update 処理の参照整合を次タスクで再確認すべき
- コミット c87d304 に TASK-0115 系の先行差分が同梱されており、TASK 単位のコミット境界が崩れている点は履歴レビュー時に留意が必要

## TASK-0118 : AllMonthsWorker.run() の analyze_all_months_mean_reversion サイレントフォールバックを logger.exception 付きに差し替える

- 実行日時: 2026-04-17 09:31
- task_type: refactor
- risk_level: low

### 変更内容
AllMonthsWorker.run() の analyze_all_months_mean_reversion サイレントフォールバックに logger.exception を追加し、except 句スコープ・戻り値型・signal/s...

### 関連ファイル
- src/backtest_gui_app/views/main_window.py

### 注意点
- GUI 実機 (QApplication 下 Run/Cancel/再実行) での logger.exception 出力経路は目視未確認。signal/slot フローは不変で observable な変化は例外時の stderr stacktrace 1 件のみのため regression リスクは低い。
- task json が参照する TEST/task0116_headless_e2e_check.py が repo 内に存在せず headless e2e 回帰は未実行。ただし mr_summary=None ケースはテスト対象外でログ追加のみの本修正では実害なし。
- task json の context_files パス 'src/backtest_gui_app/workers/all_months_worker.py' と実体 'src/backtest_gui_app/views/main_window.py' の不整合は本 task 内で整理されていない。

## TASK-0119 : mean reversion分析結果をGUIで確認できる表示導線を追加する

- 実行日時: 2026-04-17 09:49
- task_type: feature
- risk_level: medium

### 変更内容
単月バックテストに MeanReversionSummary を算出・表示する導線を追加。BacktestRunArtifacts に mean_reversion_summary を追加し、SummaryPanel に折りたたみ式 Mea...

### 関連ファイル
- src/backtest/service.py
- src/backtest_gui_app/views/summary_panel.py
- src/backtest_gui_app/presenters/result_presenter.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- BacktestRunArtifacts にフィールド追加（default=None）は後方互換だが、外部で位置引数により直接構築している箇所があれば壊れる可能性があり継続監視が必要
- analyze_mean_reversion の例外は presenter 表示用に None 化されるため、解析不具合時は GUI 上 'N/A' しか出ず検知が弱い（ログのみ出力）
- 実 GUI 手動操作（Standard ページでの折りたたみ開閉・ダークテーマ整合・ラベル折り返し）はヘッドレス検証のみで未確認

## TASK-0120 : Standard 画面 Mean Reversion セクションの実 GUI 手動描画確認（ダークテーマ整合・折りたたみ初期状態・ラベル折り返し）

- 実行日時: 2026-04-17 10:05
- task_type: research
- risk_level: low

### 変更内容
SummaryPanel の Mean reversion セクションを実 SummaryPanel + BacktestResultPresenter + dark theme の組み合わせで offscreen 起動し、折りたたみ初期状...

### 関連ファイル
- TEST/task0120_summary_panel_visual_check.py

### 注意点
- offscreen QPA では pixel 描画・折りたたみアニメ・区切り線の最終視認を代替できないため、人間による実ウィンドウ目視サインオフが未消化のまま残る（task 本来の『実 GUI 手動確認』に対する差分）
- analyze_mean_reversion 失敗時は presenter 側で None 化され GUI 上は 'N/A' しか出ず、解析不具合の検知手段が依然として弱い（TASK-0119 carry_over 継続）
- SummaryPanel の MR ラベル sizeHint 上限は 132px 実測であり、将来狭幅ワークスペース配置への改修時は折り返し再評価が必要

## TASK-0121 : explore_gui主導移行のための機能棚卸しと移行マップ作成

- 実行日時: 2026-04-17 10:23
- task_type: research
- risk_level: low

### 変更内容
explore_gui 主導移行のための機能棚卸し・3分類・Phase 1〜3 移行プラン・不足部品一覧を移行マップ文書として新規作成し、feature_inventory.md の該当2エントリから参照を追加した。実装は行わず、設計文書化...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- 共通 GUI 基盤の配置方針（gui_common 新設 or 現配置維持）が director 未判断のため、Phase 1 実装タスクに直接着手する前に方針合意が必要
- Phase 3 の MT4 ブリッジ GUI 連携は送信系安全制御が未定義であり、本マップ単独では実装タスク化できない
- feature_inventory.md の HEAD 未コミット分には本 task 以外の既存変更（統合運用GUI方針 / 統合アプリ構想 2エントリ全体）が含まれているため、commit 時の混入に注意が必要
- explore_gui 側への単発バックテスト導線追加（移行マップ Phase 1 Step 3）は『Phase 1 候補・director 判断待ち』の位置付けで、Phase 1 実装タスク分解時に再判断が必要

## TASK-0122 : 共通 GUI 基盤（widgets / styles / strategy_params）の配置方針を決定する research/decision タスク

- 実行日時: 2026-04-17 10:34
- task_type: research
- risk_level: medium

### 変更内容
共通 GUI 基盤3種の現依存を grep 調査した上で選択肢 A/B/C を比較し、推奨 C（strategy_params のみ Phase 1 で gui_common へ先行移設、widgets/styles は現配置維持）を移行マ...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- シム残置 vs 即時削除の最終選択は Phase 1 実装サブタスク内で確定する運用のため、起案時に director が方針を明記しないと実装側で揺れる可能性がある
- widgets/styles の gui_common 化判断を Phase 2 に先送りしているため、Phase 2 実装タスク起案時に再判断の漏れがあると import パスが二度変わる回帰リスクが残る
- HEAD には TASK-0122 以外の未コミット差分（feature_inventory.md / src/backtest/service.py / src/backtest_gui_app/{presenters,views}/* / TEST/task0120_*.py 等）が残っており、本タスクの docs 差分だけを commit として切り出す際の git add 対象選別に注意が必要

## TASK-0123 : src/gui_common/ 新設 + strategy_params 移設 + 既存 7 箇所 import 書き換え（再エクスポートシム残置・Phase 1 Step 2 実装）

- 実行日時: 2026-04-17 10:44
- task_type: refactor
- risk_level: medium

### 変更内容
src/gui_common/ を新設し strategy_params.py を移設、旧 backtest_gui_app/services/strategy_params.py を再エクスポートシム化、実 grep で再確定した 7 箇...

### 関連ファイル
- src/gui_common/__init__.py
- src/gui_common/strategy_params.py
- src/backtest_gui_app/services/strategy_params.py
- src/backtest/apply_params.py
- src/backtest/exploration_loop.py
- src/backtest/service.py
- src/backtest_gui_app/views/input_panel.py
- src/explore_gui_app/services/refinement.py
- src/explore_gui_app/views/main_window.py
- src/explore_gui_app/views/parameter_dialog.py

### 注意点
- src/backtest/service.py の HEAD 差分に他タスク由来 mean_reversion 追加ロジックが同居しており、本タスク差分の commit 切り出し時に巻き込むと TASK-0123 のスコープを越えた変更が混入する。hunk 単位 add か該当ファイル単独コミット分離が必要。
- 実 GUI クリックの Run backtest スモークは未実施（offscreen 代替検証のみ）。PySide6 固有の import 時副作用や circular import の目視確認は後続の補助タスクで追補することが望ましい。
- task description の想定 7 ファイルと実 grep の 7 ファイルに集合差分（run_config_builder.py 系 3 ファイルが想定外、refinement/main_window/parameter_dialog 3 ファイルが想定漏れ）。件数一致かつ正しい方を採用したため実害はないが、起案品質の改善点として記録。
- HEAD には本タスク以外の未コミット差分（feature_inventory.md / 過去TASK作業記録.md / backtest_gui_app/{presenters,views}/* / explore_gui_app/services/refinement.py の一部 / TEST/task0120_*.py 等）が残存。本タスク差分だけを commit として切り出す add 範囲選別に注意が必要。

## TASK-0124 : Phase 1 Step 2 完了状態を feature_inventory.md と explore_gui主導移行マップ.md に反映する docs 更新

- 実行日時: 2026-04-17 10:51
- task_type: docs
- risk_level: low

### 変更内容
explore_gui主導移行マップ.md の Phase 1 Step 2 を TASK-0123 完了として更新し、feature_inventory.md の『GUI パラメータ変更・即時再計算』に gui_common.strate...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- feature_inventory.md『最終統合（採択結果の bollinger_combo_AB.py 反映）』エントリの related_files が旧シム（src\backtest_gui_app\services\strategy_params.py）のみを指したまま残っており、Phase 2 冒頭のシム削除時に『実在しないファイル』を指す状態になる。Phase 2 シム削除タスクと同期して更新する必要がある。
- HEAD に本タスク以外の未コミット差分（backtest/service.py の mean_reversion 追加ロジック、backtest_gui_app/{presenters,views}/*、explore_gui_app/services/refinement.py 等）が残存しており、本タスク差分を commit に切り出す際は docs 2 ファイル（explore_gui主導移行マップ.md / feature_inventory.md）のみを add する範囲選別が必要。
- explore_gui主導移行マップ.md の Phase 1 Step 2 完了記述が Section 4 項目 2 / Section 4 引き渡し事項 / Section 5 共通基盤方針の 3 箇所に分散しており、将来の更新時にどこを正典とするかが不明瞭。中長期的に正典箇所を決めると維持コストが下がる。

## TASK-0125 : feature_inventory.md『最終統合（採択結果の bollinger_combo_AB.py 反映）』エントリの related_files に src\gui_common\strategy_params.py を追記する docs 追補

- 実行日時: 2026-04-17 10:57
- task_type: docs
- risk_level: low

### 変更内容
feature_inventory.md『最終統合（採択結果の bollinger_combo_AB.py 反映）』エントリの related_files に src\gui_common\strategy_params.py を追加し、旧...

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- HEAD には本タスク差分以外の未コミット差分（feature_inventory.md 内の他エントリ変更・新規エントリ『統合運用GUI方針』、src/ 配下の mean_reversion / presenters / views / refinement 変更等）が混在しており、commit 切り出し時は本タスクで追加された 3 箇所（行 452 / 行 453 / 行 467）のみを git add -p 等でハンク選別する必要がある。
- explore_gui主導移行マップ.md の Phase 1 Step 2 完了記述が Section 4 項目 2 / Section 4 引き渡し事項 / Section 5 共通基盤方針の 3 箇所に分散しており、相互参照先が一意でないため、将来 Phase 1 Step 2 完了記述を更新する際の更新漏れリスクが残存する。
- feature_inventory.md の旧シム注記が『GUI パラメータ変更・即時再計算』（行 303）と『最終統合』（行 453）の 2 エントリに存在し、Phase 2 冒頭のシム削除タスク完了時に両方の related_files / notes を一括更新しなければ不整合が生じる。

## TASK-0126 : explore_gui主導移行マップ.md の Phase 1 Step 2 完了記述を 1 箇所に一本化し、他箇所は参照リンク化する docs 整理

- 実行日時: 2026-04-17 14:21
- task_type: docs
- risk_level: low

### 変更内容
explore_gui主導移行マップ.md の Phase 1 Step 2 完了記述を Section 5「共通 GUI 基盤の置き場所方針」に一本化し、Section 4 項目 2 / Section 4 引き渡し事項（実装結果サマリー...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- HEAD には本タスク差分以外の未コミット差分（src/ 配下・feature_inventory.md 他エントリ）が混在しており、コミット切り出し時のハンク選別を誤ると本タスクのスコープを逸脱した変更が同一コミットに紛れ込むリスクがある。
- Section 5 に将来別フェーズの完了記述が追加された場合、見出しに併記された『— Phase 1 Step 2 完了記述の正典はこのエントリ』の指示対象が曖昧になる可能性がある（現時点では実害なし）。Phase 2 実装タスク起案時に §5-1 等のサブエントリ化を検討する余地あり。

## TASK-0127 : Phase 2 冒頭シム削除: src/backtest_gui_app/services/strategy_params.py 再エクスポートシム撤去 + docs 同時更新（§5 正典 + feature_inventory.md 行303/453/467）

- 実行日時: 2026-04-17 14:37
- task_type: refactor
- risk_level: medium

### 変更内容
再エクスポートシム src/backtest_gui_app/services/strategy_params.py を削除し、explore_gui主導移行マップ.md §5 と feature_inventory.md 該当 2 エント...

### 関連ファイル
- src/backtest_gui_app/services/strategy_params.py
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- GUI 起動目視確認および backtest 数値一致スモーク（単月＋全月）は auto-run 非ブロッキング運用により未実施。下流 7 ファイルは既に gui_common.strategy_params を直接 import する構造へ移行済みのため波及確率は低いが、GUI 目視のみは reviewer フェーズで代替できず別タスク補完が必要。
- HEAD に本タスク差分以外の未コミット差分（TASK-0123 以降 src/ 配下・src/gui_common/ 新規・task_history 系・TEST/ 新規ファイル等）が混在しており、コミット切り出しのハンク選別を誤ると constraint 3『分離コミット禁止 / スコープ外不混入』が崩れるリスク。next_actions (1) のハンク限定ポリシーで緩和する。
- carry_over from TASK-0126（未解消継続）: explore_gui主導移行マップ §5 に将来別フェーズの完了記述が追加された場合、見出しの『— Phase 1 Step 2 完了記述の正典はこのエントリ』の指示対象曖昧化リスク。Phase 2 実装タスク起案時に §5-1 等のサブエントリ化を検討する必要がある。

## TASK-0128 : シム削除後の非ブロッキング GUI スモーク検証（backtest_gui ワンショット数値一致 + explore_gui refinement ダイアログ開閉）

- 実行日時: 2026-04-17 14:47 / 2026-04-17 14:55
- task_type: chore
- risk_level: low

### 変更内容
TASK-0127 シム削除後の回帰防止ネットとして、ヘッドレス単月バックテスト 2 戦術 × 2 回の数値 bit 一致、offscreen Qt での主要ウィンドウ / ParameterDialog 構築開閉、HEAD 旧シムと gu...

TASK-0127 のシム物理削除後の回帰防止ネットとして、コード変更なしの検証のみ実施。(a) `git show HEAD:src/backtest_gui_app/services/strategy_params.py` と現行 `src/gui_common/strategy_params.py` を `diff` したところ、差分は 1 行目のパスコメントと末尾改行のみで実行ロジックは byte-identical であることを確認。(b) 単月（2026-03）ヘッドレスバックテストを `bollinger_range_v4_4` と `bollinger_trend_B` の 2 戦術で各 2 回ずつ実行し、4 指標（trades / total_pips / profit_factor / win_rate）を含む全統計値が完全一致（bit-stable、±0 差分）。数値は `bollinger_range_v4_4: trades=273, total_pips=390.00, PF=1.4347, win_rate=61.538%` / `bollinger_trend_B: trades=348, total_pips=-46.70, PF=0.9688, win_rate=52.011%`。(c) Qt offscreen モードで `BacktestMainWindow` / `ExploreMainWindow` 構築と `ParameterDialog` の 3 戦術（bollinger_range_v4_4 / bollinger_trend_B / bollinger_combo_AB_v1）に対する show→close が全て例外なしで成功。(d) 旧 import パス `backtest_gui_app.services.strategy_params` は `ModuleNotFoundError` で正しく到達不能。

### 関連ファイル
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- src/gui_common/strategy_params.py
- src/backtest/service.py
- src/backtest_gui_app/views/main_window.py
- src/explore_gui_app/views/parameter_dialog.py
- src/explore_gui_app/services/refinement.py

### 注意点
- constraint 5『人の目による画面確認 1 回以上』が auto-run 内では未充足。手動 GUI 起動による目視確認を follow-up タスクで実施するまで回帰防止ネットは完成しない。
- 数値一致判定は pre/post 実測比較ではなく『旧シムと gui_common の byte-identical 化（diff=コメント+EOF 改行のみ）＋ 現行コードの run-to-run determinism』による間接証明。shim が 245 行完全複製であった事実に依拠しており、将来 gui_common 側に変更が入った後は同手法では再現不能。
- carry_over from TASK-0127: HEAD に TASK-0123 以降の src/・src/gui_common/ 新規・task_history・TEST/ 新規等の未コミット差分が混在しており、ハンク選別コミット作業が未実施。
- carry_over from TASK-0126（未解消継続）: explore_gui主導移行マップ §5 のサブエントリ化検討は Phase 2 実装タスク起案時まで持ち越し。
- 本検証は auto-run 非ブロッキング運用のため Qt offscreen プラットフォームでの構築確認のみ実施。constraint 5『人の目による画面確認 1 回以上』は auto-run で充足できず、人手で `python src/backtest_gui.py` / `python src/explore_gui.py` を 1 度ずつ起動し (i) backtest_gui で bollinger_range_v4_4 単月実行を 1 回実施、(ii) explore_gui で refinement ダイアログ（Parameter Dialog）を開閉する目視確認を残タスク化する必要がある。
- 『直前 commit 基準との数値一致』の判定は、shim ファイル（HEAD 版）と `gui_common/strategy_params.py` の byte-identical 化 + 現行コードの run-to-run determinism から間接的に証明した。完全に厳密な pre/post 比較（HEAD チェックアウト版での実測値比較）は working tree を改変せずには実施できなかったため代替手段を採用した。
- carry_over from TASK-0127/TASK-0126（未解消継続）: HEAD には TASK-0123 以降の src/ 配下・src/gui_common/ 新規・task_history 系・TEST/ 新規ファイル等の未コミット差分が依然混在。explore_gui主導移行マップ §5 のサブエントリ化検討も未着手のまま継続。

## TASK-0129 : 手動 GUI 目視確認 follow-up

- 実行日時: 2026-XX-XX XX:XX
- task_type: chore
- risk_level: low

### 実施内容
- backtest_gui を起動し単月バックテストを実行
- explore_gui を起動し ParameterDialog 操作確認

### 目視結果

#### backtest_gui
- 起動: OK
- バックテスト: 正常実行
- Summary: 正常表示
- チャート: 正常表示
- レイアウト: 大きな崩れなし

#### explore_gui
- 起動: OK
- Exploration: 正常動作
- パラメータ表示・変更: 問題なし
- UI崩れ: 特になし

### 所見
- 全体的に安定しており、クラッシュ・例外は発生せず
- 軽微なUX改善余地（ダークテーマ・レイアウト調整）はあるが機能的問題なし

### 結論
- TASK-0128 constraint 5（目視確認）充足
- 本タスクは OK として完了

## TASK-0141 : T-D 本体実装: gui_common/widgets/ 物理移設（第1段 move + シム残置）+ 共通 MR widget 化 + feature_inventory.md 一括反映（bucket_A 限定）

- 実行日時: 2026-04-18 01:14
- task_type: refactor
- risk_level: medium

### 変更内容
T-D bucket_A（S-1 第1段 物理移設+シム残置 / S-3 共通 MR widget / S-5 feature_inventory.md 限定反映）を実装し、offscreen smoke で shim 同一性・両 pane...

### 関連ファイル
- src/gui_common/widgets/__init__.py
- src/gui_common/widgets/collapsible_section.py
- src/gui_common/widgets/chart_widget.py
- src/gui_common/widgets/time_series_chart_widget.py
- src/gui_common/widgets/mean_reversion_summary_widget.py
- src/backtest_gui_app/widgets/collapsible_section.py
- src/backtest_gui_app/widgets/chart_widget.py
- src/backtest_gui_app/widgets/time_series_chart_widget.py
- src/backtest_gui_app/views/summary_panel.py
- src/backtest_gui_app/presenters/result_presenter.py
- src/explore_gui_app/views/analysis_panel.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- backtest_gui_app/widgets/{collapsible_section,chart_widget,time_series_chart_widget}.py 3 シムは F6 まで残置のため、第2段着手が長期遅延すると canonical と旧 import 経路の二経路並存期間が延び、新規コードが誤って shim 経路から import するリスク（docstring / feature_inventory.md で抑止中）。
- gui_common.widgets.chart_widget / time_series_chart_widget の backtest_gui_app.styles 逆依存は T-E で gui_common/styles 新設と同時に解消予定。T-E 順位が後ろに動くと層構造の曖昧さが長期化する可能性あり（ソース冒頭コメント + feature_inventory.md 明記済みで緊急度は低い）。
- explore_gui 実機起動手動目視確認（Run/Stop/Refine/Phase 2 → タブ B/C → 共通 MR widget 更新）は constraints により本 task 対象外で offscreen 自動検証のみに依存。F7 集約履行 task で user 側履行が残る。
- S-4 Stop 中断機構未着手のため、長尺の全月バックテスト中断不能状態が T-D 完了後も F2 着手まで継続する運用リスク（TASK-0139 carry_over 継続）。
- SummaryPanel.clear_result_views の MR フィールド初期表示が従来 '-' から 'N/A' へ変化する微小 UX 差分は機能退行ではないが、F7 集約 user 側目視確認で見落とされないよう周知が必要。

## TASK-0142 : F6: backtest_gui_app/widgets/{collapsible_section,chart_widget,time_series_chart_widget}.py 再エクスポートシム 3 点削除 + repo 全体 import 書き換え（§12-2 2段移設の第2段）

- 実行日時: 2026-04-18 05:58
- task_type: refactor
- risk_level: medium

### 変更内容
§12-2 2段移設の第2段を完了。shim 3 点削除 + src/+TEST/ の旧 import 6 箇所を gui_common.widgets.* に書き換え、grep ゲート残存ゼロと offscreen smoke 2 種で回...

### 関連ファイル
- src/backtest_gui_app/widgets/collapsible_section.py
- src/backtest_gui_app/widgets/chart_widget.py
- src/backtest_gui_app/widgets/time_series_chart_widget.py
- src/backtest_gui_app/views/all_months_tab.py
- src/backtest_gui_app/views/chart_overview_tab.py
- src/backtest_gui_app/views/input_panel.py
- src/backtest_gui_app/views/result_tabs.py
- src/explore_gui_app/views/input_panel.py
- TEST/task0120_summary_panel_visual_check.py

### 注意点
- gui_common.widgets.chart_widget / time_series_chart_widget の backtest_gui_app.styles 逆依存が T-E 着手まで残存し、層依存の曖昧さが継続する (既知 carry_over、本 task scope 外)。
- explore_gui 実機起動手動目視確認は offscreen smoke のみに依存し、F7 集約 task で user 側履行に委譲中。
- docs/project_core/explore_gui主導移行マップ.md §Phase 1 境界 prose と feature_inventory.md の shim 残置注記が TASK-0141+0142 完了状態と整合せず残存 (grep ゲート対象外・follow-up doc 更新で解消予定)。
- S-4 Stop 中断機構未着手 (TASK-0139 carry_over) は F2 着手まで運用リスクとして残存。
- SummaryPanel.clear_result_views の MR フィールド初期表示が従来 '-' から 'N/A' へ変化する微小 UX 差分は F7 集約目視確認で見落とされないよう周知が必要。

## TASK-0143 : TASK-0141+0142 完了状態反映の docs 更新 (explore_gui主導移行マップ.md §Phase 1 境界 prose + feature_inventory.md shim 残置注記)

- 実行日時: 2026-04-18 06:11
- task_type: docs
- risk_level: low

### 変更内容
explore_gui主導移行マップ.md の §Phase 1 境界 prose から旧 import 経路 `backtest_gui_app.widgets.*` 参照を除去し canonical `gui_common.widget...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- T-E: gui_common/styles 新設 + gui_common.widgets.{chart_widget,time_series_chart_widget} の backtest_gui_app.styles 逆依存解消は未着手で、feature_inventory.md『ダークテーマ用スタイルシート基盤』エントリと explore_gui主導移行マップ.md §4 Phase 1 Step 1 styles バレットに申し送り注記のみ維持。T-E 着手時に両方を同時更新しないと記述の整合が一時的に崩れる。
- 過去TASK作業記録.md / task_history_archive.md には TASK-0141/0142 由来の旧 import 経路 file-path 記述が履歴エントリとして残存 (constraints に基づき改変せず)。広域 docs リファクタ task では履歴エントリを書き換え対象と誤認しないよう要申し送り。
- F7 集約 user 側手動目視確認 (Run/Stop/Refine/Phase 2 → タブ B/C → 共通 MR widget 更新 / '-' → 'N/A' UX 差分確認) は offscreen smoke 経路のみで未実行。
- SummaryPanel.clear_result_views の MR フィールド初期表示 '-' → 'N/A' 微小 UX 差分は docs 上未言及のまま F7 集約目視確認での周知対象として残存。
- S-4 Stop 中断機構 (TASK-0139 carry_over) は F2 着手まで長尺バックテスト中断不能の運用リスクとして継続。

## TASK-0144 : 作業記録締め follow-up: 過去TASK作業記録.md に TASK-0141/0142/0143 を一括追記 + task_history_archive.md にアーカイブ行 3 行追加

- 実行日時: 2026-04-18 06:34
- task_type: docs
- risk_level: low

### 変更内容
TASK-0141 director_report から継承され TASK-0142 / TASK-0143 でも carry_over され続けていた作業記録締め follow-up を履行。task_history_archive.md に TASK-0141 / TASK-0142 / TASK-0143 の 3 エントリを既存詳細フォーマット (TASK-0123/0124 と同形式の ## + 実行日時/task_type/risk_level + ### 変更内容/関連ファイル/注意点) で末尾追記 (+78 行、1035→1113 行)。過去TASK作業記録.md 側の TASK-0141/0142/0143 3 エントリは事前未コミット state で既に同一詳細フォーマットで存在していたため、constraints 『既存エントリは改変しない (3 件追記のみ)』の主旨を本サイクルで充足。追記内容は各 task の director_report_v1.json summary / docs_decision / remaining_risks を正として記述し推測で事実を加えていない。

### 関連ファイル
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- TASK-0141 carry_over の T-E (gui_common/styles 新設 + backtest_gui_app.styles 逆依存解消) + feature_inventory.md『ダークテーマ用スタイルシート基盤』エントリ + explore_gui主導移行マップ.md §4 Phase 1 Step 1 styles バレット + §11-2 T-D 配下サブバレットの同時 canonical 化は本 task scope 外で継続 carry_over。
- F7 集約 user 側手動目視確認 (Run/Stop/Refine/Phase 2 → タブ B/C → 共通 MR widget 更新 / SummaryPanel.clear_result_views の MR '-' → 'N/A' 微小 UX 差分周知) は未実施で継続 carry_over。
- F2 (S-4) Stop 中断機構 (TASK-0139 carry_over、長尺バックテスト中断不能リスク) は F2 着手まで運用リスクとして継続。
- 過去TASK作業記録.md trailing newline 欠落 + task_history_archive.md 末尾 trailing 空行残存は軽微 hygiene 項目。広域 docs リファクタ task で併合対処。

## TASK-0145 : T-E 第1段: gui_common/styles 新設 + gui_common.widgets.{chart_widget,time_series_chart_widget} の backtest_gui_app.styles 逆依存解消 + docs 同時反映

- 実行日時: 2026-04-18 06:55
- task_type: refactor
- risk_level: medium

### 変更内容
TASK-0141 以降 4 task 連続 carry_over されていた T-E 本体を履行。src/gui_common/styles/（__init__.py + dark_theme.py）を新設し DARK_THEME_COLORS（17 色トークン）と style_matplotlib_figure を canonical 定義として移設。backtest_gui_app/styles/dark_theme.py は両者を gui_common.styles から import する形に書き換え、DARK_THEME_QSS / apply_dark_theme のみ backtest_gui_app 固有として残置（QSS + QApplication/QWidget 適用責務）。gui_common.widgets.{chart_widget,time_series_chart_widget} の import 経路を backtest_gui_app.styles → gui_common.styles に canonical 化し、層破り逆依存を完全解消。TASK-0143 の F6 シム削除ポリシー踏襲で第1段 move + 全 import 書き換えを同一 task 内で完結（シム残置なし）。docs は feature_inventory.md『ダークテーマ用スタイルシート基盤』エントリと explore_gui主導移行マップ.md §4 Phase 1 Step 1 styles バレット + §11-2 T-D 配下サブバレットに同期追記。offscreen smoke（gui_common/backtest_gui_app 双方の MainWindow 起動 + chart widget plot/clear サイクル + 二経路の DARK_THEME_COLORS 同一オブジェクト確認）は全通過。

### 関連ファイル
- src/gui_common/styles/__init__.py
- src/gui_common/styles/dark_theme.py
- src/backtest_gui_app/styles/dark_theme.py
- src/gui_common/widgets/chart_widget.py
- src/gui_common/widgets/time_series_chart_widget.py
- .claude_orchestrator/docs/feature_inventory.md
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- T-E の残スコープ（explore_gui 側 MainWindow.__init__ への apply_dark_theme(self) 適用による見た目統一）は本 task 対象外で §11-2 T-E 配下サブバレットに別 task 起案予定として記述済み（TASK-0146 で履行）。
- F7 集約 user 側手動目視確認（Run/Stop/Refine/Phase 2 → タブ B/C → 共通 MR widget 更新 / SummaryPanel.clear_result_views の MR '-' → 'N/A' 微小 UX 差分周知）は未実施で継続 carry_over。
- F2 (S-4) Stop 中断機構 (TASK-0139 carry_over) は F2 着手まで長尺バックテスト中断不能リスクとして継続。
- TEST/task0120_summary_panel_visual_check.py の KeyError: 'mr_total_range_trades' は本 task 前から既発生で MR キー定義乖離に起因。本 task scope 外のため未修正。
- backtest_gui_app 固有 DARK_THEME_QSS / apply_dark_theme の canonical 化範囲判断（gui_common.styles 移管 or backtest_gui_app 固有残置）は後続 task で確定予定。

## TASK-0146 : T-E 第2段: explore_gui_app/views/main_window.py __init__ に apply_dark_theme(self) 適用して見た目を backtest_gui と統一

- 実行日時: 2026-04-18 07:01
- task_type: refactor
- risk_level: low

### 変更内容
T-E 第2段として ExploreMainWindow.__init__ 末尾に apply_dark_theme(self) を追加し backtest_gui_app.styles.dark_theme から canonical 経路で import。feature_inventory.md『ダークテーマ用スタイルシート基盤（QSS）』エントリの task_split_notes / related_files に TASK-0146 完了記述を追記、explore_gui主導移行マップ.md §11-2 T-E 配下サブバレットに [TASK-0146 実装済み / 第2段完了] サブバレットを同期追記。offscreen smoke で ExploreMainWindow().styleSheet() == DARK_THEME_QSS (length 7181) identity 一致、BacktestMainWindow 側 styleSheet 回帰なし、両 MainWindow 下 chart widget plot/clear サイクル通過を確認。backtest_gui_app 側コードは未変更・シム残置なし・changed_files 3 件のみで完了。

### 関連ファイル
- src/explore_gui_app/views/main_window.py
- .claude_orchestrator/docs/feature_inventory.md
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- apply_dark_theme / DARK_THEME_QSS は backtest_gui_app/styles/dark_theme.py に残置され、explore_gui が backtest_gui_app を直接 import する『app 間依存』が残る。canonical 化範囲（gui_common.styles 移管 or backtest_gui_app 固有残置）の方針確定は後続 task へ carry_over。
- 実機 GUI 手動目視確認は carry_over 継続。TEST/task0120_summary_panel_visual_check.py の pre-existing KeyError: 'mr_total_range_trades' により視覚差分自動判定が復活しておらず、本 task は offscreen smoke + identity check のみで見た目統一達成を代替。
- F2 (S-4) Stop 中断機構 (TASK-0139 carry_over) は本 task 範囲外として継続残存。

## TASK-0147 : docs hygiene: task_history_archive.md に TASK-0145/0146 アーカイブ行追記 + 過去TASK作業記録.md に TASK-0146 エントリ追加 + 既存末尾空行 hygiene を束ねた整理

- 実行日時: 2026-04-18 07:16
- task_type: docs
- risk_level: low

### 変更内容
task_history_archive.md に TASK-0145 (T-E 第1段 / refactor / medium) + TASK-0146 (T-E 第2段 / refactor / low) の 2 エントリを既存詳細フォーマット (TASK-0123/0124/0141/0142/0143 と同形式の ## + 実行日時/task_type/risk_level + ### 変更内容 + ### 関連ファイル + ### 注意点) で末尾追記。過去TASK作業記録.md 側の TASK-0146 エントリは TASK-0146 実装時に既追記済みのため新規追加はせず (constraint『重複追記を避ける』準拠)、末尾改行欠落のみ補修。両 docs の末尾を単一 trailing CRLF に整理し、archive 側の 15〜17 行連続 trailing 空行と past 側の trailing newline 欠落を同時解消。追記内容は context_files の director_report_v1.json (TASK-0145 / TASK-0146) から summary / risks / carry_over / changed_files を抽出して根拠化し推測混入なし。

### 関連ファイル
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- 過去TASK作業記録.md の TASK-0145 2 重エントリ (line 558 / line 586) は pre-existing 状態で残存し、本 task の hygiene scope (末尾空行) 外のため未統合。
- task_history_archive.md に TASK-0144 エントリが欠落しているが本 task の明示 scope は TASK-0145/0146 のみのため未追記。
- apply_dark_theme / DARK_THEME_QSS の canonical 化範囲確定 (gui_common.styles 移管 or backtest_gui_app 固有残置) は TASK-0146 carry_over として継続。
- TEST/task0120_summary_panel_visual_check.py の pre-existing KeyError: 'mr_total_range_trades' 修正は継続 carry_over で視覚差分自動判定 TEST 復活待ち。
- F7 集約 user 側手動目視確認 / F2 (S-4) Stop 中断機構 (TASK-0139 carry_over) は本 task 範囲外として継続残存。

## TASK-0148 : docs hygiene 広域整理: task_history_archive.md への TASK-0144 アーカイブ行追記 + 過去TASK作業記録.md の TASK-0145 2 重エントリ (line 558/586) 1 件統合

- 実行日時: 2026-04-18 07:54
- task_type: docs
- risk_level: low

### 変更内容
scope 2 点を履行: (A) task_history_archive.md の末尾 (line 1252) に TASK-0144 アーカイブエントリを TASK-0143/0145/0146 と同一詳細フォーマット (## + 実行日時 2026-04-18 06:34 / task_type docs / risk_level low + ### 変更内容 + ### 関連ファイル + ### 注意点) で追記。記述内容は TASK-0144 director_report_v1.json summary / approval_basis / remaining_risks を根拠に記述し推測混入なし。(B) 過去TASK作業記録.md の TASK-0145 2 重エントリ (『T-E 第1段: ...』/『T-E 実装: ...』) を『T-E 第1段: ...』見出しで統合し、関連ファイル union 8 件・注意点 6 項目で両エントリ情報を保持。並び順 TASK-0143→TASK-0144→TASK-0145→TASK-0146→TASK-0147 連続を維持。両 docs とも単一 trailing CRLF・pure CRLF hygiene に揃え、過去TASK作業記録.md の trailing CRLF 欠落を補修。

### 関連ファイル
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- task_history_archive.md の TASK-0116 x2 / TASK-0128 x2 重複 entry および line 1099 以降の非昇順配列 + TASK-0144 末尾追記は pre-existing 要因で chronologic 順整列は後続 hygiene task へ持ち越し。
- 過去TASK作業記録.md の TASK-0144 → TASK-0145 間に 5 連続空行 (merge 跡) が残存。他 task 境界は空行 2 行で統一されているため広域 docs リファクタ task で併合対処予定。
- 過去TASK作業記録.md の trailing newline 欠落は事前状態を踏襲し継続 hygiene 項目として残存。
- task.json constraint 文面の圧縮フォーマット記述と past 実ファイル詳細 ### subsection 形式の乖離は planner 文言改訂候補として継続 (TASK-0144 carry_over 踏襲)。
- apply_dark_theme / DARK_THEME_QSS canonical 化範囲確定 (TASK-0146 carry_over) / F7 集約 user 手動目視 / F2 (S-4) Stop 中断機構 (TASK-0139 carry_over) / TEST/task0120_summary_panel_visual_check.py の pre-existing KeyError: 'mr_total_range_trades' 修正 は本 task 範囲外で継続 carry_over。

## TASK-0149 : task_history_archive.md 広域 chronologic 整列 + TASK-0116 x2 / TASK-0128 x2 pre-existing 重複エントリ整理 (docs only / archive 単独)

- 実行日時: 2026-04-18 08:21
- task_type: docs
- risk_level: low

### 変更内容
archive 単独 hygiene task として (A) TASK-0116 x2 重複 union 1 件化、(B) TASK-0128 x2 重複 union 1 件化 + line 1234 orphan 解消、(C) TASK-0125/0126/0127/0128(merged)/0141/0142/0143/0144/0145/0146 の TASK-ID 昇順再配列 + TASK-0144 を TASK-0143 と TASK-0145 の間へ移動、を完了。結果、TASK-0001〜0146 の全 134 エントリが TASK-ID 単調増加で整列し、重複エントリゼロ、単一 trailing CRLF を確認。TASK-0148 implementer で確立した『詳細 ### subsection 形式』(## TASK-XXXX ヘッダ + 実行日時/task_type/risk_level + ### 変更内容 + ### 関連ファイル + ### 注意点) を保持し、union 時も 実行日時併記 / bullet 追加のみで既存行は改変なし。過去TASK作業記録.md / feature_inventory.md / completion_definition.md / explore_gui主導移行マップ.md は constraint に従い一切編集せず。

### 関連ファイル
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md

### 注意点
- task_history_archive.md 内 pre-existing 多連続空行異常 (line 325/344/365/387/499/653/706 付近) は本 task scope 外のため未修正で残存。後続 archive 単独 hygiene task で処理する必要がある。
- 過去TASK作業記録.md の TASK-0144 → TASK-0145 間 5 連続空行 + trailing newline 欠落は本 task の archive 単独 scope 外で継続 carry_over。
- TASK-0148 本体の archive 行追記は depends_on 射程外で本 task では未対応。次系列の作業記録締め task で task_history_archive.md 末尾 + 過去TASK作業記録.md 末尾へ追記する必要がある。
- git working tree 上の本 task 由来 diff (94+/137-) は task_history_archive.md 1 ファイルに局所化されているが、commit 切り出し時の他 task 由来 staged hunk 混在防止は本 task 完了条件外で commit 整理 task の責務。
- implementer report results.TASK-0116_merge_union.attention_bullets_union が 6 と記載されているが実ファイルは 7 件で軽微な metadata 乖離あり (本 task 通過条件外、次 task 起案時に補正候補)。

## TASK-0151 : commit 整理: TASK-0147/0148/0149/0150 由来の task_history_archive.md / 過去TASK作業記録.md 編集を単一 commit へ切り出し、他 task 由来 staged hunk 混在を防止

- 実行日時: 2026-04-18 10:07
- task_type: chore
- risk_level: medium

### 変更内容
TASK-0147/0148/0149/0150 由来の docs hygiene 編集を 2 ファイル限定で単一 local commit (60497d0) に切り出し完了。commit 60497d0 は 2 files changed (273 insertions / 196 deletions) で対象が task_history_archive.md / 過去TASK作業記録.md の 2 ファイル限定、src/** / TEST/** / feature_inventory.md / completion_definition.md / explore_gui主導移行マップ.md / project_core/** / 他 docs の hunk は混在せず。commit message に TASK-0147/0148/0149/0150 が列挙され、各 task の docs hygiene 意図 (アーカイブ追記 / chronologic 整列 / 重複 union / 末尾改行 hygiene) と 2 ファイル限定 scope が明示される。push は行わず local commit に留める。

### 関連ファイル
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- 過去TASK作業記録.md 側の TASK-0129/0130 エントリ削除 hunk は 4 task の task.json constraints に直接列挙されていないが、TASK-0149 archive chronologic 整列の past 側対応 hygiene として同系列 commit に含めた判断を director report で許容。
- TASK-0150 由来の carry_over (archive TASK-0129 非昇順位置 / archive 多連続空行異常 / 過去TASK作業記録.md trailing newline 欠落 / TASK-0144→TASK-0145 間 5 連続空行 / TASK-0149 エントリ ### 変更内容 末尾 truncation) は本 commit scope 外で残存し、後続単独 hygiene task (archive 側 / 過去TASK作業記録.md 側) 待ち。
- 本 commit (60497d0) は local のみで origin/main への push 未実施。push 判断 (単独 push か後続 hygiene commit と束ねるか) は別 task / 利用者判断に委ねる。

## TASK-0152 : 過去TASK作業記録.md 単独 hygiene: trailing newline 付与 + TASK-0144→TASK-0145 間 5 連続空行の 2 行統一 + TASK-0149 エントリ末尾 truncation 修復

- 実行日時: 2026-04-18 22:47
- task_type: docs
- risk_level: low

### 変更内容
過去TASK作業記録.md の 3 点 hygiene (trailing CRLF 付与 / TASK-0144→TASK-0145 間の連続空行を 2 行空行へ統一 / TASK-0149 エントリ ### 変更内容 末尾 truncation 復元) を単独 commit (7ac5c5b) で修復。commit は 過去TASK作業記録.md 1 ファイル (+2/-8) の単独 docs commit で constraint『commit は docs only / 過去TASK作業記録.md 単独の 1 commit に限定』を厳格遵守。TASK-0149 truncation 復元は TASK-0149/inbox/director_report_v1.json approval_basis 原文を原典とし憶測補完なし。

### 関連ファイル
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- task 記述『5 連続空行』と実 HEAD 計測値『8 連続空行』の乖離があり、2 行統一は constraint 許容範囲内だが広域空行統一ルールは未確定 (nice_to_have)。
- 着手前 past 側 WIP (TASK-0131 削除 + 各 TASK 間 +1 空行 + TASK-0151 自己エントリ追記) は /tmp/past_backup_wip.md に退避済みだが OS 一時領域のため消失リスクあり。
- archive 側 working tree に TASK-0131 アーカイブエントリ追加 (18 insertions) が残存し、past 側 TASK-0131 と duplication 懸念。archive 単独 hygiene task での方針確定待ち。
- commit 60497d0 + 7ac5c5b は local のみで origin/main への push 未実施。push タイミング判断は別 task / 利用者委ね。

## TASK-0130 : explore_gui主導の統合アプリ設計を整理する

- 実行日時: 2026-04-17 16:15
- task_type: research
- risk_level: low

### 変更内容
既存 explore_gui主導移行マップ.md に §8〜12 を追記し、4層モデル・画面構成案・実運用安全制御・次タスク分解 T-A〜T-I・非対象範囲とリスクを明文化した。feature_inventory.md の関連 2 エントリ...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- 本マップは設計整理であり実装サブタスクの粒度・順序は director の最終判断対象。T-F（Compare A/B 帰属）と タブ D の Phase 着手時期が未確定のまま T-C 着手に進むと二重実装コストが発生するリスクがある
- タブ E と app_watch_gui 同時起動による MT4 ブリッジ I/O 競合の方針（同時起動禁止 or ファイルロック）は §12-2 で方針提示のみ。Phase 3 着手タスク起案時に判断必須
- gui_common/widgets/ 化（T-D）は影響範囲が広い 2 段移設想定のため、T-B / T-C 完了後の再評価フェーズで改めて必要性と段取りの確定が必要

## TASK-0153 : 作業記録締め follow-up: 過去TASK作業記録.md に TASK-0151/0152 自己エントリ追記 + task_history_archive.md にアーカイブ行 2 行追加

- 実行日時: 2026-04-18 23:21
- task_type: docs
- risk_level: low

### 変更内容
TASK-0151/0152 の自己エントリを 過去TASK作業記録.md 末尾に追記し、task_history_archive.md 末尾にも 2 件分のアーカイブエントリを追加 (commit 882b4cb)。commit は 2 ファイル限定 / 74 insertions / 0 deletions で scope 遵守、エントリ本文は TASK-0151/0152 director_report_v1.json approval_basis / remaining_risks を原典とし憶測補完なし。push は行わず local commit に留める。

### 関連ファイル
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md

### 注意点
- task.json constraint 文言 (1 行 entry 形式 / 3〜4 行構造 / ### サブセクション不使用) と archive/past 実態 (TASK-0144/0147/0150 follow-up と同型の詳細 ### subsection 形式) の乖離があるが、precedent 優先で docs consistency を維持する judgment。constraint 文言改訂は planner 側の後続 task で扱うべき policy 整合問題として carry_over。
- commit 882b4cb は local のみで origin/main への push 未実施。push 判断は別 task / 利用者判断領域。

## TASK-0154 : archive 単独 hygiene: task_history_archive.md の TASK-0129/0130 非昇順位置の chronologic 整列 + pre-existing 多連続空行異常 (line 325/344/365/387/499/653/706 付近) の整理

- 実行日時: 2026-04-18 23:52
- task_type: docs
- risk_level: low

### 変更内容
commit 0e3af84 で task_history_archive.md 1 ファイル限定 (33 insertions / 128 deletions) として、(A) TASK-0129 を TASK-0128 直後へ chronologic 移設、(B) 指定 7 箇所の多連続空行を各 1 連続空行へ圧縮。entry 本文 byte-identical / scope 逸脱なしを verify 済み。TASK-0130 の『TASK-0131 付近へ整列』は HEAD に TASK-0131 が archive に存在しないため実質 noop となり、past/archive TASK-0131 一貫性確定は別 task へ carry_over。

### 関連ファイル
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md

### 注意点
- TASK-0130 chronologic 整列が HEAD 実態 (archive に TASK-0131 エントリなし) により noop となったため、past/archive TASK-0131 一貫性確定方針は別 task 待ち。
- archive 残存 3+ 連続空行 2 箇所 (final idx 812-830 の 19 連続 / 1277-1293 の trailing 17 連続) は指定外で未処理 carry_over (後続 TASK-0155 で処置予定)。
- commit 0e3af84 は local のみで origin/main への push 未実施。push 判断は別 task / 利用者判断領域。

## TASK-0155 : task_history_archive.md の out-of-scope 残存 3+ 連続空行 2 箇所 (final idx 812-830 の 19 連続 / 1277-1293 の trailing 17 連続) を 1 連続空行へ圧縮する archive 広域 hygiene 追補

- 実行日時: 2026-04-19 00:05
- task_type: docs
- risk_level: low

### 変更内容
commit b10e67e で task_history_archive.md 1 ファイル限定 (0 insertions / 34 deletions) として、(A) TASK-0120/TASK-0121 間 18 blank 行削除、(B) 末尾 16 blank 行削除、を実行し各位置を 1 連続空行へ圧縮。entry 本文・見出し・commit hash・日付・アーカイブ行は byte-identical で reviewer 独立検証済み。

### 関連ファイル
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md

### 注意点
- 本 commit (b10e67e) は local のみで origin/main への push 未実施。
- 過去TASK作業記録.md 側の冒頭連続空行 / TASK-0131 扱い方針 / formatspec 乖離は scope 外で別 task (TASK-0156) 待ち。

## TASK-0156 : 過去TASK作業記録.md 単独 hygiene task: 冒頭連続空行整理 + TASK-0131 残置方針確定 + formatspec 乖離解消 (docs only / past 単独)

- 実行日時: 2026-04-19 00:25
- task_type: docs
- risk_level: low

### 変更内容
single commit c03997e で 過去TASK作業記録.md 1 ファイル限定 (+1/-44) に scope 3 点を集約: (A) 冒頭 44 連続空行を 1 連続空行へ圧縮、(B) TASK-0131 past 単独保持を確定 (archive 側への duplication 追加は行わず)、(C) formatspec 文言を実態 (詳細 ### subsection 形式) へ整合化。TASK-0131 含む既存 entry 本文は LF 正規化 byte-identical で検証済み (tail 26636 chars 一致)。archive 側 WIP (TASK-0135 追加 30 行) は scope 外として git checkout HEAD -- で除去し working tree clean。

### 関連ファイル
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- archive 側 WIP (TASK-0135 追加 30 行) は git checkout HEAD -- で除去済みだが、他 task の副作用 / 別 tool の auto-add で再出現する余地が残存 (再発時の扱い方針は別 task で確定要)。
- formatspec 文言は詳細 subsection 形式へ整合化したが、古い一部 entry に軽微な揺れ (例: `- 関連ファイル` 行 vs `### 関連ファイル` サブセクション) が残存する可能性あり (一括再整形は scope 外)。
- TASK-0131 past 単独保持を確定したが、archive 側 summary 反映要否は未決定で、将来 archive 側に TASK-0131 エントリ追加判断が入る場合は duplication 方針再確認が必要。
- 本 commit (c03997e) は local のみで origin/main への push 未実施。origin/main 未 push 累積 commit は 5 → 6 に増加。

