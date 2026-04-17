# 過去TASK作業記録

## 目的
plannerが次タスクを判断するための短い知見のみを残す

**記録フォーマット仕様:** 各エントリは `## TASK-XXXX : タイトル` の見出しに続き、`- [task_type/risk_level] 変更要点`・`- 関連: ファイルパス`・`- 注意: 補足事項`（任意）の3〜4行構造で記録する。### サブセクション形式は使用しない。

---




































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










## TASK-0132 : explore_gui トップレベル QTabWidget 化（T-A）: タブ A 稼働 + タブ B/C 空フレーム、タブ D 空フレームは設置しない 3 タブ構成

- 実行日時: 2026-04-17 16:49
- task_type: feature
- risk_level: medium

### 変更内容
explore_gui の ExploreMainWindow にトップレベル QTabWidget を導入し、タブ A (Explore) に既存の ExploreInputPanel / ExploreResultPanel を収容、タ...

### 関連ファイル
- src/explore_gui_app/views/main_window.py

### 注意点
- 実ユーザー操作による Run / Stop / Refine / Phase 2 全通しの手動確認は未実施。offscreen 起動・タブ切替・パネル収容 assert までの自動検証に留まるため、コミット前の user 側最終確認が必須。
- TASK-0131 carry_over（T-I README 3 アプリ併存運用ガイド未反映 / タブ B 用途境界の誘導リンク文言 / タブ D 再評価トリガ『L2 採択頻度 月次 1 回』の観測手段未整理）は本タスク未対処のまま Phase 2 後続で順次解消する必要がある。
- §9-2 の Live status 枠 / ステータスバー Phase 昇格表示は本タスクスコープ外で未実装。後続 T-H / T-I 相当で扱う必要がある。









## TASK-0133 : TASK-0132 T-A 実装完了の docs 反映（feature_inventory.md + explore_gui主導移行マップ.md §11-1 T-A）

- 実行日時: 2026-04-17 21:18
- task_type: docs
- risk_level: low

### 変更内容
TASK-0132 T-A 実装完了の旨を feature_inventory.md の 2 エントリ（『探索専用GUI（explore_gui.py）』『統合運用GUI方針（explore_gui 主導）』）notes 末尾と、explo...

### 関連ファイル
- .claude_orchestrator/docs/feature_inventory.md
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- §11-1 T-A 見出し括弧書き『タブ B/C/D は空フレームを設置』の旧表現は未改訂のまま。サブバレットで TASK-0131 確定方針が優先される旨を明示しているが、見出しのみ読んだ読者がタブ D 空フレーム設置を誤認する残存リスクは存在する。
- explore_gui 実機起動による Run / Stop / Refine / Phase 2 全通しの手動確認は本タスクスコープ外で未実施。TASK-0132 carry_over として user 側での履行が引き続き必要。








## TASK-0134 : explore_gui主導移行マップ.md §11-1 T-A 見出し括弧書き『タブ B/C/D は空フレームを設置』の文言改訂（タブ D を含めない表現へ）

- 実行日時: 2026-04-17 21:24
- task_type: docs
- risk_level: low

### 変更内容
explore_gui主導移行マップ.md §11-1 T-A 見出し括弧書きを『タブ A のみ稼働、タブ B/C は placeholder、タブ D は未設置（Phase 3 帰属）』に改訂し、見出しのみ読んでもタブ D 非設置を誤認し...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- §11-1 T-A 配下 TASK-0132 サブバレット（line 308）に旧見出し引用表現『見出しの《タブ B/C/D は空フレームを設置》より TASK-0131 確定が優先され』が歴史的経緯として残存する。内容整合は維持されているが、見出し改訂後に旧表現引用と読み取れるかは読み手リテラシーに依存（重要度低）。
- [carry_over 継承] explore_gui 実機起動による Run / Stop / Refine / Phase 2 全通し手動確認は本 task スコープ外で未実施。TASK-0132 carry_over として user 側履行が引き続き必要。







## TASK-0135 : explore_gui主導移行マップ.md §11-1 T-A TASK-0132 サブバレット（line 308 付近）内の旧見出し引用表現『タブ B/C/D は空フレームを設置』の文面整理（軽量 docs 改訂）

- 実行日時: 2026-04-17 21:35
- task_type: docs
- risk_level: low

### 変更内容
explore_gui主導移行マップ.md §11-1 T-A 配下 TASK-0132 サブバレット（line 308）内の旧見出し引用表現『タブ B/C/D は空フレームを設置』を除去し、現 §11-1 T-A 見出し括弧書き『タブ A...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- [carry_over 継承] explore_gui 実機起動による Run / Stop / Refine / Phase 2 全通し手動確認は本 task スコープ外で未実施。TASK-0132 carry_over として user 側履行が引き続き必要。
- nice_to_have として reviewer が挙げた『文末括弧書き内の見出し具体文引用を省略し簡潔表現化する更なる軽量化』は本 task 必須ではないが、T-B / T-C 起案時の §11 参照頻度増加タイミングで再評価の余地がある（重要度低）。






## TASK-0136 : T-B（タブ C Analysis 最小実装）起案前の director 事前判断タスク：タブ C 最小スコープ・責務境界・既存 analysis_panel 再利用範囲の 3 点確定

- 実行日時: 2026-04-17 21:48
- task_type: research
- risk_level: low

### 変更内容
T-B 起案前の director 事前判断 3 点（タブ C 最小スコープ / 責務境界 / 既存 analysis_panel 再利用範囲）について、§9-2・§11-1 T-B・§11-2 T-F・§12-3 と既存コード実態を突合し...

### 関連ファイル
- none

### 注意点
- C1-a 採択により §9-2 の『MR サマリー + 全期間集約 + 月別ばらつき』フル像との差分が Phase 2 完了時点で残る。T-B 実装起案後の docs 反映 task にて §9-2 注記追記もしくは Phase 2 追補 task 起案の要否を判断する必要がある。
- C3-a コピー方式採用により MR 表示ロジックが一時的に 2 系統（backtest_gui_app 側 / explore_gui 側）並存する。T-D（gui_common/widgets/ 化判断）まで表記ズレ発生リスクを持ち越す。
- explore_gui 実機起動による Run/Stop/Refine/Phase 2 全通し手動確認は TASK-0132/0135 からの carry_over として user 側履行継続中。T-B 完了後も同スコープの手動確認が必要。
- §11-1 T-A サブバレット文末括弧書き内の見出し具体文引用省略による軽量化（TASK-0135 nice_to_have）は T-B / T-C 起案時の §11 参照頻度増加タイミングで再評価（重要度低、必要時のみ起案）。





## TASK-0137 : T-B（タブ C Analysis 最小実装）: explore_gui タブ C に Phase 2 MR サマリー 11 項目表示を新規 analysis_panel.py で実装する

- 実行日時: 2026-04-17 22:14
- task_type: feature
- risk_level: medium

### 変更内容
explore_gui タブ C を placeholder から新規 AnalysisPanel（MR サマリー 11 項目の読み取り専用ビュー）に差し替え、Phase 2 完了時に最良候補の全月合算 MR サマリーを背景ワーカーで計算し...

### 関連ファイル
- src/explore_gui_app/views/analysis_panel.py
- src/explore_gui_app/views/main_window.py

### 注意点
- C3-a コピー方式により MR 表示ロジックが backtest_gui_app 側（result_presenter._populate_mean_reversion / summary_panel）と explore_gui 側（AnalysisPanel.set_summary）の 2 系統で並存。T-D 着手前に片側だけ改修すると表記ズレが発生する恐れがある。後続 docs 反映 task で『片側変更時は他方同時メンテ必須』の運用ルールを明示化することで緩和する。
- Phase 2 完了後の MR analysis は best 候補 overrides で csv_dir 配下 CSV を再 run_backtest するため、Phase 2 本体と同程度以上の追加計算時間が発生する。進捗表示はログ行のみで進捗バーは未実装のため、user 視点では『Phase 2 完了 → タブ C 数値反映』間が無通知待機になる。UX 改善は T-D 付近で検討する nice_to_have。
- reviewer nice_to_have に挙がった『Phase 2 が Stop 割り込みで途中終了しても _on_phase2_finished_ok が走り _start_mr_analysis が実行される』『_MRAnalysisWorker 実行中に Stop ボタンが無効で user 停止不可』『_MRAnalysisWorker が requestInterruption で途中終了した場合 self._mr_analysis_worker が解放されない』の 3 点は C1-a 最小完了条件には影響しないが、T-D 付近で改修検討が必要。
- docs 反映（§11-1 T-B サブバレット追記 / §9-2 最小スコープ注記 or Phase 2 追補 task 起案要否 / 過去TASK作業記録.md 追記）は本 task で未実施。後続 docs 反映 task の起案が必須 followup として残る。
- explore_gui 実機起動による Run/Stop/Refine/Phase 2 全通し手動目視確認は本 task スコープ外（TASK-0132/0135 carry_over）。本 task で追加した Phase 2 → MR analysis 非同期反映動作も実機確認が未了のまま後続 task に進む。




## TASK-0138 : TASK-0136/TASK-0137 完了分の docs 反映（explore_gui主導移行マップ.md §11-1 T-B サブバレット追記 + §9-2 タブ C 最小スコープ注記判断 + 過去TASK作業記録.md 追記）

- 実行日時: 2026-04-17 22:53
- task_type: docs
- risk_level: low

### 変更内容
explore_gui主導移行マップ.md §11-1 T-B 配下に TASK-0137 実装サブバレット（TASK-0132 §11-1 T-A 追記パターン踏襲）を追記し、§9-2 タブ C 記述に C1-a 最小スコープ注記（Pha...

### 関連ファイル
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md

### 注意点
- C3-a 採択により MR 表示ロジックが backtest_gui_app 側 (result_presenter._populate_mean_reversion / summary_panel) と explore_gui 側 (AnalysisPanel.set_summary) の 2 系統並存。§9-2 / §11-1 T-B / 過去TASK作業記録.md / 将来の feature_inventory.md の四重管理となり、T-D 着手時に整合性再点検が必須。
- §9-2 タブ C 末尾注記と §11-1 T-B 配下サブバレットの二重管理リスク。T-D 再評価時に AnalysisPanel UI 拡張判断と §9-2 / §11-1 T-B 整合確認を同時に実施する必要がある。
- explore_gui 実機起動による Run/Stop/Refine/Phase 2 全通し + TASK-0137 で追加した Phase 2 → MR analysis 非同期反映動作の手動目視確認は本 TASK スコープ外で TASK-0132/0135/0136/0137 carry_over として user 側履行継続。docs 上は『反映済み』でも実機挙動の最終裏付けは別系統で必要。
- §9-2 タブ C 末尾追記が 1 文に複数論点を凝縮しており可読性が劣る（reviewer nice_to_have）。T-D 周辺で軽量 docs 整理 task として改行 / サブバレット化を検討する余地が残る（重要度低）。




## TASK-0139 : T-C（タブ B Backtest 単発 最小実装）: explore_gui タブ B に探索結果 1 候補の単月/全月 backtest 実行 UI を新規 backtest_panel.py で実装する

- 実行日時: 2026-04-17 23:30
- task_type: feature
- risk_level: medium

### 変更内容
explore_gui タブ B（Backtest 単発）を空フレームから新規 BacktestPanel に差し替え、Phase 1 / Phase 2 完了時に最後に採択された探索候補の strategy_name + param_overrides + 直近 CSV / CSV Dir をパネルに自動転送し、Single CSV / All months モード切替で `backtest.service.run_backtest` または `run_all_months` を `_BacktestWorker`（QThread）非同期実行できるようにした。Summary は 6 KPI（total_pips / win_rate / profit_factor / max_dd_pips / trades / verdict）+ 5 詳細（wins / losses / avg_pips / max_consecutive_wins / max_consecutive_losses）= 11 項目。Stop は T-C スコープ通り『実行中は Run を無効化 + ログに stop 要求を表示』の最小機能のみ実装し、`run_backtest` 自体の中断は T-D で再評価。重複許容方針（TASK-0131 / TASK-0136 確定）に従い `backtest_gui_app` 側 InputPanel / SummaryPanel フィールド構成をコピー方式で再実装し、`gui_common/widgets/` 化は T-D に先送り。

### 関連ファイル
- src/explore_gui_app/views/backtest_panel.py
- src/explore_gui_app/views/main_window.py
- TEST/smoke_t_c_backtest_panel.py
- .claude_orchestrator/docs/project_core/explore_gui主導移行マップ.md
- .claude_orchestrator/docs/task_history/過去TASK作業記録.md

### 注意点
- 重複許容方針採用により Backtest 単発 UI が backtest_gui_app 側（InputPanel / SummaryPanel / result_presenter）と explore_gui 側（BacktestPanel）の 2 系統並存となる。TASK-0137 の MR 表示 2 系統並存と合わせ、T-D（gui_common/widgets/ 化判断）まで『片側変更時は他方同時メンテ必須』の運用ルールを維持する。
- Stop ボタンは T-C スコープにより『最小機能（実行中無効化のみ）』で、`run_backtest` / `run_all_months` 実行中の割り込み停止は実装していない。長尺の全月バックテスト実行中は完了まで停止できない。中断機構の追加は T-D / 後続で再評価。
- BacktestPanel に押し出される候補は `loop_result.adopted` を優先し、不在時は `_phase1_results` から `aggregate_stats.average_pips_per_month` 最大、無ければ `total_pips` 最大の単一候補を `_best_phase1_result` で算出。Phase 2 完了時は最良候補（同基準）を上書きで再転送する。
- 詳細チャート観察・手動パラメータ調整は backtest_gui Standard ページに残置で、explore_gui タブ B はあくまで『探索結果の 1 候補を単発検証』のみに用途限定（§11-1 T-C / TASK-0131 確定方針）。詳細チャート誘導文言の UI 追加は本 task では未実装。
- offscreen 自動検証（タブ A↔B↔C 切替非クラッシュ / `app.exec` ret=0 / 単月 backtest 実行 → 11 項目 summary 反映 = `total_pips=-18.80, trades=87, verdict=discard` を `USDJPY-cd5_20250521_2025-05.csv` で確認）は通過。実ユーザー操作による Run/Stop/Refine/Phase 2 → タブ B 候補転送 → 単月/全月 backtest 実行の手動目視確認は TASK-0132/0135/0136/0137/0138 carry_over として user 側履行継続。
- §9-2 フル像（全期間集約 / 月別ばらつき）への対応は T-D 再評価時に判断する方針。feature_inventory.md への反映は T-D で一括実施するため本 task では未実施。
- feature_inventory.md への explore_gui_app/views/backtest_panel.py エントリ追加は constraints により T-D 一括反映方針で持ち越し。T-D 起案時に反映漏れを網羅的に回収する手順を担保する必要がある。


## TASK-0140 : T-D 起案前 director 事前判断：gui_common/widgets/ 化判断スコープ確定（BacktestPanel + AnalysisPanel 2 系統並存コスト評価 / Stop 中断機構再評価 / feature_inventory.md 一括反映 / §9-2 フル像追補要否 / 詳細チャート誘導文言 / set_candidate 空 dict 仕様 を同梱）

- 実行日時: 2026-04-17 23:37
- task_type: research
- risk_level: low

### 変更内容
T-D 起案前 director 事前判断の判断材料を整備した。2系統並存の実コード差分・Stop 中断機構の未実装箇所・feature_inventory.md 反映漏れ・§9-2 差分・誘導文言欠落・set_candidate 空 di...

### 関連ファイル
- none

### 注意点
- T-D 本体 task 起案時に §12-2 の 2 段移設方針（move + シム残置 → 後続でシム削除）が constraints に明記されない場合、実装側が一括削除まで進めて T-D スコープが肥大化するリスク。next_actions (b) (a) で明示済みだが起案時の転記漏れに注意。
- feature_inventory.md 一括反映は TASK-0033 memory（スコープ外変更 revert 必要の過去事例）のリスクを内包。T-D 本体 task 起案時に反映対象ファイルを列挙的に明示する必要あり。
- S-3 共通 MR widget のデータフロー統一（dataclass 直 vs dict 経由）は T-D 本体 implementer の pre_implementation_plan で確定する方針としたため、T-D 本体 task 起案時に constraints でその委任を明記しないと実装段階で論点迷走の余地が残る。
- S-4 Stop 中断機構を bucket_C（対象外）に置くが、TASK-0139 carry_over『T-D / 後続で必須再評価』の継承は F2 独立 follow-up task として明示継続させた。起案順位が後ろに下がるため、長尺の全月バックテスト中断不能状態が T-D 完了後もしばらく継続する運用リスクは残置。
- Phase 1/2 完了時の候補自動転送が Phase 2 best で上書きされる設計および explore_gui 実機起動手動目視確認（Run/Stop/Refine/Phase 2 → タブ B 候補転送 → Run）は本 task スコープ外のため未確認のまま継続。F7 で集約履行 task を起案予定。


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