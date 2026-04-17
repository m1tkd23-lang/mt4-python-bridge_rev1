# 過去TASK作業記録

## 目的
plannerが次タスクを判断するための短い知見のみを残す

**記録フォーマット仕様:** 各エントリは `## TASK-XXXX : タイトル` の見出しに続き、`- [task_type/risk_level] 変更要点`・`- 関連: ファイルパス`・`- 注意: 補足事項`（任意）の3〜4行構造で記録する。### サブセクション形式は使用しない。

---



























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

- 実行日時: 2026-04-17 08:45
- task_type: research
- risk_level: low

### 変更内容
コード変更なし。検証のみ。data/USDJPY-cd5_20250521_monthly 配下の 12 ヶ月 CSV + bollinger_range_v4_4 戦略（既定 SL/TP 10pips, pip_size 0.01, Conservative intrabar, close_open_position_at_end=True, initial_balance 1,000,000, money_per_pip 100）で AllMonthsWorker の run_all_months + analyze_all_months_mean_reversion 経路を headless 再現スクリプト（TEST/task0116_headless_e2e_check.py）で実行。12 ヶ月すべて正常読込・集計 OK、mr_summary 非 None、monthly_table 5 列と全期間 MR パネルの表示文字列が AllMonthsTab._populate_* と一致、クラッシュなし、monthly 合計と all_period total_range_trades が一致（consistency 確認）。

### 関連ファイル
- TEST/task0116_headless_e2e_check.py
- TEST/task0116_lane_check.py
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- bollinger_range_v4_4 / bollinger_range_v4_4_tuned_a は SignalDecision に entry_lane を設定しないため generic_runner 側で lane="legacy" に正規化される。結果として 12 ヶ月すべてで total_range_trades=0 となり、monthly_table MR 列は count=0 / rate=N/A / avg_bars=N/A、全期間 MR パネルも総数 0 / 割合 N/A で落ちずに描画される（range 0 件月の仕様通り）。
- MR 表示に実データ（非ゼロ）を流すには entry_lane="range" を出力する戦略（例: bollinger_range_v4_6, bollinger_range_A 系）が必要。v4_4 系の仕様自体は MR range レーン非該当で、MR 表示を介した性能評価は別戦略 or 別タスクで行う。
- GUI 実機起動 (QApplication 下 Run All Months ボタン → progress 応答 → キャンセル → 再実行 UI 挙動) の目視確認は auto-run で実行不能のため未実施。headless パイプライン一致確認で機能同等性まで担保しているが、UI 応答・キャンセル挙動は carry_over として残る。
- AllMonthsWorker.run() 内 analyze_all_months_mean_reversion の except Exception: mr_summary=None サイレントフォールバックは依然残存（carry_over）。
















## TASK-0116 : backtest_gui_app の All Months タブ + MR 表示を USDJPY 12ヶ月 CSV 実データで GUI 実機 e2e 検証する

- 実行日時: 2026-04-17 08:41
- task_type: research
- risk_level: low

### 変更内容
data/USDJPY-cd5_20250521_monthly の 12ヶ月 CSV + bollinger_range_v4_4 戦略で run_all_months + analyze_all_months_mean_reversio...

### 関連ファイル
- TEST/task0116_headless_e2e_check.py
- TEST/task0116_lane_check.py
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- GUI 実機 (QApplication 下 Run/Cancel/再実行) の目視確認は本 task 内で未実施。Qt スレッド・signal/slot・progress_bar 更新・キャンセル後の clear_results の実機 regression は headless では検出不能。
- v4_4 系戦略は entry_lane='range' を吐かないため monthly_table MR 5 列・全期間 MR パネルに非ゼロ値が入った状態での描画整合は未確認（仕様通り 0 / N/A までしか e2e 検証できていない）。
- AllMonthsWorker.run() の analyze_all_months_mean_reversion サイレントフォールバック (except Exception: mr_summary=None, logger 出力なし) は carry_over として未対処で、MR 表示が N/A に落ちた場合の原因特定が困難。















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

- 実行日時: 2026-04-17 14:55
- task_type: chore
- risk_level: low

### 変更内容
TASK-0127 のシム物理削除後の回帰防止ネットとして、コード変更なしの検証のみ実施。(a) `git show HEAD:src/backtest_gui_app/services/strategy_params.py` と現行 `src/gui_common/strategy_params.py` を `diff` したところ、差分は 1 行目のパスコメントと末尾改行のみで実行ロジックは byte-identical であることを確認。(b) 単月（2026-03）ヘッドレスバックテストを `bollinger_range_v4_4` と `bollinger_trend_B` の 2 戦術で各 2 回ずつ実行し、4 指標（trades / total_pips / profit_factor / win_rate）を含む全統計値が完全一致（bit-stable、±0 差分）。数値は `bollinger_range_v4_4: trades=273, total_pips=390.00, PF=1.4347, win_rate=61.538%` / `bollinger_trend_B: trades=348, total_pips=-46.70, PF=0.9688, win_rate=52.011%`。(c) Qt offscreen モードで `BacktestMainWindow` / `ExploreMainWindow` 構築と `ParameterDialog` の 3 戦術（bollinger_range_v4_4 / bollinger_trend_B / bollinger_combo_AB_v1）に対する show→close が全て例外なしで成功。(d) 旧 import パス `backtest_gui_app.services.strategy_params` は `ModuleNotFoundError` で正しく到達不能。

### 関連ファイル
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md
- src/gui_common/strategy_params.py
- src/backtest/service.py
- src/backtest_gui_app/views/main_window.py
- src/explore_gui_app/views/parameter_dialog.py
- src/explore_gui_app/services/refinement.py

### 注意点
- 本検証は auto-run 非ブロッキング運用のため Qt offscreen プラットフォームでの構築確認のみ実施。constraint 5『人の目による画面確認 1 回以上』は auto-run で充足できず、人手で `python src/backtest_gui.py` / `python src/explore_gui.py` を 1 度ずつ起動し (i) backtest_gui で bollinger_range_v4_4 単月実行を 1 回実施、(ii) explore_gui で refinement ダイアログ（Parameter Dialog）を開閉する目視確認を残タスク化する必要がある。
- 『直前 commit 基準との数値一致』の判定は、shim ファイル（HEAD 版）と `gui_common/strategy_params.py` の byte-identical 化 + 現行コードの run-to-run determinism から間接的に証明した。完全に厳密な pre/post 比較（HEAD チェックアウト版での実測値比較）は working tree を改変せずには実施できなかったため代替手段を採用した。
- carry_over from TASK-0127/TASK-0126（未解消継続）: HEAD には TASK-0123 以降の src/ 配下・src/gui_common/ 新規・task_history 系・TEST/ 新規ファイル等の未コミット差分が依然混在。explore_gui主導移行マップ §5 のサブエントリ化検討も未着手のまま継続。




## TASK-0128 : シム削除後の非ブロッキング GUI スモーク検証（backtest_gui ワンショット数値一致 + explore_gui refinement ダイアログ開閉）

- 実行日時: 2026-04-17 14:47
- task_type: chore
- risk_level: low

### 変更内容
TASK-0127 シム削除後の回帰防止ネットとして、ヘッドレス単月バックテスト 2 戦術 × 2 回の数値 bit 一致、offscreen Qt での主要ウィンドウ / ParameterDialog 構築開閉、HEAD 旧シムと gu...

### 関連ファイル
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- constraint 5『人の目による画面確認 1 回以上』が auto-run 内では未充足。手動 GUI 起動による目視確認を follow-up タスクで実施するまで回帰防止ネットは完成しない。
- 数値一致判定は pre/post 実測比較ではなく『旧シムと gui_common の byte-identical 化（diff=コメント+EOF 改行のみ）＋ 現行コードの run-to-run determinism』による間接証明。shim が 245 行完全複製であった事実に依拠しており、将来 gui_common 側に変更が入った後は同手法では再現不能。
- carry_over from TASK-0127: HEAD に TASK-0123 以降の src/・src/gui_common/ 新規・task_history・TEST/ 新規等の未コミット差分が混在しており、ハンク選別コミット作業が未実施。
- carry_over from TASK-0126（未解消継続）: explore_gui主導移行マップ §5 のサブエントリ化検討は Phase 2 実装タスク起案時まで持ち越し。




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


## TASK-0131 : explore_gui 統合 Phase 2 の director 事前判断タスク（Compare A/B 帰属・タブ B 重複許容・タブ D Phase 帰属の 3 点確定）

- 実行日時: 2026-04-17 16:35
- task_type: research
- risk_level: low

### 変更内容
Phase 2 着手前の director 事前判断 3 点を確定し、explore_gui主導移行マップ.md §9-2・§11-1・§11-2・§11-3・§11-4・§12-3 および feature_inventory.md『統合運...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md
- .claude_orchestrator/docs/feature_inventory.md

### 注意点
- T-I（README 3 アプリ併存運用ガイド）が Phase 2 後半まで未反映のまま Phase 2 実装を回すと、Compare A/B の切替運用と手動 apply_params.py 運用の案内が口頭・非公式にとどまる可能性がある
- タブ B 重複許容の用途境界は『誘導リンク』という UI 表示に依存するため、T-C 実装タスクでリンク文の文言・配置が完了条件から漏れると境界が曖昧化する可能性がある
- タブ D の Phase 3 再評価トリガ『L2 採択頻度が月次 1 回以上』が定性的で、採択イベントの観測手段が未整理のため、再評価のきっかけ検知が遅れる可能性がある（Phase 3 着手タスク起案時に観測手段の設計が必要）