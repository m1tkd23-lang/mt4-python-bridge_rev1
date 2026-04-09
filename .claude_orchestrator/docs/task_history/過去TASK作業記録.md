# 過去TASK作業記録

## 目的
plannerが次タスクを判断するための短い知見のみを残す

---


















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














## TASK-0025 : MFE/MAE ratio による補助品質指標の最小実装（成績算出への統合）

- 実行日時: 2026-04-09 16:27
- task_type: feature
- risk_level: low

### 変更内容
MFE/MAE ratio 補助品質指標を BacktestStats・AggregateStats に追加し、月別平均・全月合算平均を算出する最小実装を完了。CLI 出力にも表示追加済み。

### 関連ファイル
- src/backtest/simulator/models.py
- src/backtest/simulator/stats.py
- src/backtest/aggregate_stats.py
- src/backtest/runner.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- GUI All Months タブに MFE/MAE ratio が表示されない（既存表示は非破壊・後続タスクで対応）
- 全月合算 avg_mfe_mae_ratio が月別平均の単純平均であり、トレード数加重平均ではない（補助指標のため現時点では許容）













## TASK-0026 : GUI All Months タブへの MFE/MAE ratio 表示追加（月別テーブル列 + aggregate パネル）

- 実行日時: 2026-04-09 16:40
- task_type: feature
- risk_level: low

### 変更内容
All Months タブの月別テーブルに Avg MFE/MAE 列（9列目）を追加し、aggregate パネルに Avg MFE/MAE フィールドを追加した。None 時は "-" 表示、小数点以下2桁表示。

### 関連ファイル
- src/backtest_gui_app/views/all_months_tab.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- 全月合算 avg_mfe_mae_ratio は月別平均の単純平均であり、トレード数加重平均ではない（TASK-0025 から既知・補助指標のため現時点では許容）












## TASK-0027 : Single Month SummaryPanel への avg_mfe_mae_ratio 表示追加

- 実行日時: 2026-04-09 16:57
- task_type: feature
- risk_level: low

### 変更内容
SummaryPanel の summary_fields に ('avg_mfe_mae_ratio', 'Avg MFE/MAE') を追加し、BacktestDisplaySummary への avg_mfe_mae_ratio フィ...

### 関連ファイル
- src/backtest/view_models.py
- src/backtest_gui_app/views/summary_panel.py
- src/backtest_gui_app/presenters/result_presenter.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- none











## TASK-0028 : GUI A/B 比較タブの追加（compare_ab GUI 接続）

- 実行日時: 2026-04-09 17:13
- task_type: feature
- risk_level: low

### 変更内容
GUI Compare A/B タブを新規作成し、A単体/B単体/A+B合成の3パターン全月合算成績比較をGUIから実行・表示可能にした。QThread非同期実行・3フェーズプログレス・キャンセル機能・戦術パラメータオーバーライドに対応。

### 関連ファイル
- src/backtest_gui_app/views/compare_ab_tab.py
- src/backtest_gui_app/views/main_window.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- CompareABWorker が compare_ab() を直接呼ばず内部ロジックを複製しているため、compare_ab() 変更時に乖離リスクあり（現時点では低リスク）
- GUI 手動起動確認が未実施（import チェックのみ）。ランタイムエラーの潜在可能性は排除できないが構造的リスクは低い










## TASK-0029 : 採択結果の bollinger_combo_AB.py 反映ワークフロー最小実装（CLI パラメータ書き出し）

- 実行日時: 2026-04-09 17:23
- task_type: feature
- risk_level: medium

### 変更内容
CLI ツール apply_params.py を新規作成し、戦術パラメータの恒久書き出し機能を実装。--list / --dry-run / --backup / --set / --lane-a / --lane-b の全モードで動作確...

### 関連ファイル
- src/backtest/apply_params.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- LANE_A/LANE_B 書き換え後の import 文未連動（combo ファイル外の動的ロード機構に依存、現時点では低リスク）
- 正規表現ベースの定数書き換えは想定外フォーマットに脆弱（現時点の戦術ファイルでは問題なし）
- StrategyParamSpec 未登録パラメータの型推論フォールバックによる意図しない型変換リスク









## TASK-0030 : completion_definition 全セクション充足度棚卸し・MVP 完成度最終評価

- 実行日時: 2026-04-09 17:36
- task_type: research
- risk_level: low

### 変更内容
completion_definition.md 全8セクション26項目を feature_inventory.md および実装コードと突き合わせ、項目ごとの充足状況を一覧化した。implemented=15, partial=8, not...

### 関連ファイル
- none

### 注意点
- feature_inventory と completion_definition の粒度差による status 乖離（fi_match=false 4項目）が未整理のまま残存。後続タスクで整合性修正が必要
- セクション6（品質）の not_implemented 2項目（月平均利益基準評価・統合採択条件）は新規ロジック実装が必要であり MVP 完成への最大ギャップ
- セクション8（データ整合性）3項目の partial はすべて MT4 実環境依存であり、バックテスト側のみでは完了できない可能性がある








## TASK-0031 : 月平均利益基準の全月横断評価ロジック実装（completion_definition セクション6 ギャップ解消）

- 実行日時: 2026-04-09 17:44
- task_type: feature
- risk_level: medium

### 変更内容
evaluator.py に全月横断評価関数 evaluate_cross_month() を追加し、all_months_tab の aggregate パネルに Cross-Month Verdict / Reasons 表示を実装した...

### 関連ファイル
- src/backtest/evaluator.py
- src/backtest_gui_app/views/all_months_tab.py

### 注意点
- Cross-Month Reasons の QLabel ワードラップ未設定により長文時の表示切れリスクあり（軽微・後続タスクで対応可）
- CrossMonthThresholds のデフォルト値（150/200 pips）の実運用データでの妥当性は未検証（閾値パラメータ化済みのため変更容易）
- all_months_tab.py に未使用インポート CrossMonthThresholds が残存（動作影響なし・後続で清掃可）







## TASK-0032 : 全月合算成績+月別安定性の統合採択条件実装（completion_definition セクション6 最終ギャップ解消）

- 実行日時: 2026-04-09 17:53
- task_type: feature
- risk_level: medium

### 変更内容
evaluate_integrated() を evaluator.py に追加し、全月合算成績と月別安定性を統合した ADOPT/IMPROVE/DISCARD 判定を実装。GUI All Months タブに Integrated Ve...

### 関連ファイル
- src/backtest/evaluator.py
- src/backtest_gui_app/views/all_months_tab.py
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- IntegratedThresholds デフォルト値（max_drawdown_pips=200, max_monthly_pips_stddev=300 等）の実運用データでの妥当性は未検証。パラメータ化済みのため変更容易だが初期値が緩すぎる可能性あり
- GUI 実機動作確認が未実施（import レベルの確認のみ）。レイアウト崩れや表示切れが起きうる
- min_total_pips=0.0 に対し DISCARD 条件が <= 比較のため total_pips が正確に 0.0 でも DISCARD になる境界値挙動






## TASK-0033 : completion_definition セクション6 status 注釈追記 + feature_inventory「月平均利益基準の探索・確認」partial 更新

- 実行日時: 2026-04-09 18:03
- task_type: docs
- risk_level: low

### 変更内容
feature_inventory.md「全月安定性評価」エントリへのスコープ外変更を revert し、TASK-0033 開始前の状態に復元した。constraint 内の変更（completion_definition.md セクショ...

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- HTML コメント形式の注釈は Markdown レンダラで非表示のため、ソースを直接閲覧しない利用者には情報が伝わらない（機能上は問題なし、将来的に可視形式への変更を検討）
- feature_inventory「全月安定性評価」エントリの status: partial が実装状態（implemented 相当）と不整合のまま残存（本タスクスコープ外）





## TASK-0034 : feature_inventory「全月安定性評価（赤字月非連続・ばらつき抑制）」status: partial→implemented 更新

- 実行日時: 2026-04-09 18:09
- task_type: docs
- risk_level: low

### 変更内容
feature_inventory.md の「全月安定性評価（赤字月非連続・ばらつき抑制）」エントリを partial→implemented に更新し、related_files に evaluator.py を追加、task_split...

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- feature_inventory.md のワーキングツリー差分に TASK-0034 スコープ外の変更（月平均利益基準エントリ）が混在しており、コミット時にスコープ外変更が混入しないよう注意が必要




## TASK-0035 : feature_inventory「月平均利益基準の探索・確認」エントリ未コミット差分の正式反映

- 実行日時: 2026-04-09 18:14
- task_type: docs
- risk_level: low

### 変更内容
feature_inventory.md「月平均利益基準の探索・確認」エントリの未コミット差分を検証し、実装事実との整合を確認。ワーキングツリー上の変更内容（status: not_implemented→partial、TASK-0031...

### 関連ファイル
- none

### 注意点
- feature_inventory.md に「全月安定性評価」エントリの未コミット差分（TASK-0034 承認済み）が混在しており、git add 時に一括ステージングするとスコープ外変更が混入する



## TASK-0036 : TASK-0034/0035 検証済み docs 未コミット差分の一括コミット

- 実行日時: 2026-04-09 18:19
- task_type: docs
- risk_level: low

### 変更内容
TASK-0034/0035 検証済み docs 差分4ファイルを一括コミット完了。evaluator.py・all_months_tab.py はスコープ外として除外。

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md
- .claude_orchestrator/docs/completion_definition.md
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- .claude_orchestrator/docs/task_history/archive/task_history_archive.md

### 注意点
- src/backtest/evaluator.py・src/backtest_gui_app/views/all_months_tab.py の未コミット実装差分がワーキングツリーに残存しており、後続タスクでの誤混入リスクが継続


## TASK-0037 : evaluator.py・all_months_tab.py 未コミット実装差分のコミット整理（TASK-0031/0032 由来）

- 実行日時: 2026-04-09 18:24
- task_type: chore
- risk_level: low

### 変更内容
evaluator.py (+274行) と all_months_tab.py (+13行) の TASK-0031/0032 由来実装差分を git diff で検証し、対象2ファイルのみをコミットした。

### 関連ファイル
- src/backtest/evaluator.py
- src/backtest_gui_app/views/all_months_tab.py

### 注意点
- feature_inventory.md の関連エントリ status が実装コミット済み状態と乖離したまま（後続タスクで対応予定）