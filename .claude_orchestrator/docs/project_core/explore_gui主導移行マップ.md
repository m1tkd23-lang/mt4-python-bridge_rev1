# explore_gui 主導移行マップ

## 0. このドキュメントの位置付け

* feature_inventory.md の「統合運用GUI方針（explore_gui 主導）」「バックテスト・探索・実運用統合アプリ構想」を具体化する設計文書。
* MVP 完了状態（backtest_gui / explore_gui が分離存在）を壊さずに、explore_gui 側へ段階的に主導線を寄せるためのマップ。
* TASK-0121 で作成。実装タスクではなく、後続タスクの分解基準と変更禁止境界を固定することがゴール。

## 1. 現状（2026-04-17 時点）の3アプリ構造

### 1-1. backtest_gui.py / backtest_gui_app

責務: 単発バックテスト・全月集計・A/B比較・チャート可視化・パラメータ手動調整。  
主な構成:

* エントリポイント: `src/backtest_gui.py`
* Main window: `backtest_gui_app/views/main_window.py`（Standard / Chart view / All Months / Compare A/B の4タブ）
* Standard ページ: `InputPanel` + `SummaryPanel` + `ResultTabs`
* All Months タブ: `AllMonthsWorker`（QThread）+ `AllMonthsTab`（月別テーブル + 全期間集約 + MR サマリー）
* Compare A/B タブ: `CompareABWorker`（QThread）+ `CompareABTab`
* 中央回帰分析表示: Standard SummaryPanel + All Months タブ
* 戦術パラメータ手動オーバーライド: `backtest_gui_app/services/strategy_params.py`
* プレゼンター: `backtest_gui_app/presenters/result_presenter.py`
* ダークテーマ: `backtest_gui_app/styles/dark_theme.py`（全 GUI 基盤として再利用可能）
* チャート widget 群: `backtest_gui_app/widgets/`（price_chart / linked_trade）+ `gui_common/widgets/`（chart_widget / time_series_chart_widget / collapsible_section / mean_reversion_summary_widget。T-D = TASK-0141/0142 2段移設で canonical 化済み）

### 1-2. explore_gui.py / explore_gui_app

責務: bollinger 系戦術のパラメータ探索（Phase 1 選抜 → Phase 2 全期間確認）。  
主な構成:

* エントリポイント: `src/explore_gui.py`
* Main window: `explore_gui_app/views/main_window.py`（`_ExplorationWorker` / `_Phase2Worker` QThread）
* `ExploreInputPanel`: 戦略選択 / CSV 選択（Selected / All / Custom）/ ループ設定 / パラメータ範囲編集
* `ExploreResultPanel`: Iteration table / Exploration log / Monthly breakdown / Phase 2 results / Phase 2 summary
* `ParameterDialog`: パラメータ範囲・刻み編集ダイアログ
* refinement 補助: `explore_gui_app/services/refinement.py`
* バックエンド接続: `backtest.exploration_loop` の `run_bollinger_exploration` / `run_bollinger_exploration_loop`

### 1-3. app_watch.py / app_watch_gui.py

責務: MT4 リアルタイムブリッジの watch ループを GUI から起動・停止し、ログを可視化。  
主な構成:

* CLI 本体: `src/app_watch.py`（`run_watch` / `WATCH_INTERVAL_SECONDS = 1.0`）
* GUI: `src/app_watch_gui.py`（`WatchWorker(QObject)` + `QMainWindow`）
* ブリッジ層: `src/mt4_bridge/services/bridge_service.py`（`BridgeService.read_current_state` でスナップショット + コマンド結果を1まとめに）
* Runtime state: `src/mt4_bridge/runtime_state.py`
* スナップショット / 結果 I/O: `mt4_bridge/snapshot_reader.py`, `command_writer.py`, `result_reader.py`
* 設定: `mt4_bridge/app_config.py`

## 2. explore_gui 主導移行の責務定義

explore_gui を **「調整しながらトレードを行う」統合運用環境** の入口として再位置付けする。最終状態では以下3レイヤーを同一ウィンドウから扱えることを目標とする。

| レイヤー | explore_gui が担う責務 |
| --- | --- |
| 分析 | 単発バックテスト・全月集計・A/B 比較・中央回帰分析（backtest_gui 現責務）を取り込む |
| 調整 | 既存の bollinger 探索 Phase 1 / Phase 2・refinement・apply_params 連携 |
| 運用 | MT4 ブリッジの runtime 状態可視化・watch 起動/停止・安全制御（app_watch 現責務の統合） |

基本原則:

* 売買ロジック（`src/mt4_bridge/strategies/`, `src/backtest/simulator/`）はこの移行では触らない。
* 画面を1つに束ねる前に、各機能を独立したパッケージとして explore_gui 側へ寄せられる形に整える（即統合しない）。
* backtest_gui / app_watch_gui は維持したまま、機能を explore_gui 側から再利用できる状態を作る。

## 3. 機能3分類（移す / 残す / 保留）

### 3-1. explore_gui 側へ優先的に寄せる機能（Phase 1）

既存 backtest_gui_app のうち、探索と密接に絡むもの。UI 再構築不要で「モジュール再利用」で寄せられるものを優先する。

* 戦術パラメータ定義・オーバーライド機構  
  `backtest_gui_app/services/strategy_params.py`（`StrategyParamSpec`, `get_param_specs`）→ explore_gui からも既に参照されているので、配置を共有可能な場所へ移動候補。
* CollapsibleSection / MatplotlibChart / TimeSeriesChartWidget  
  `gui_common/widgets/`（T-D = TASK-0141/0142 2段移設完了で `backtest_gui_app/widgets/` 配下から移設済み）→ backtest_gui / explore_gui 双方から canonical 経路 `gui_common.widgets.*` で再利用中。
* ダークテーマ適用基盤  
  `backtest_gui_app/styles/dark_theme.py`（`apply_dark_theme`, `style_matplotlib_figure`）→ explore_gui 側でも統一適用可能にする。
* 中央回帰分析サマリー表示  
  `BacktestResultPresenter` が扱う MR セクション + All Months タブの MR 列。
* 単発バックテスト実行導線（`backtest.service.run_backtest` の GUI 接続）。

### 3-2. 当面 backtest_gui / app_watch 側に残置する機能（Phase 2 以降）

即移動するとリスクが高く、explore_gui 側に移しても有効性が薄いもの。

* Standard ページ（単発バックテストの詳細 UI / trades テーブル / Chart view タブ）  
  → 複雑な presenter 依存あり。explore_gui 側に必要になるまで残置。
* Compare A/B タブ（3フェーズ実行 / `CompareABWorker`）  
  → 現状の独立性が高く、当面は backtest_gui に残す方が安全。
* All Months タブ  
  → 単独タブとして残し、explore_gui Phase 2 画面と機能重複する部分のみ将来統合。
* app_watch / app_watch_gui  
  → リアルタイム運用責務。Phase 3 まで分離維持。
* MT4 ブリッジ送信系（`command_writer.py`）  
  → 実運用リスクのため、GUI から直接叩ける状態を避ける。

### 3-3. 将来の統合アプリ設計まで保留する機能（Phase 3）

設計判断が必要で、即時移行するとアーキテクチャを固めてしまう可能性のあるもの。

* MT4 ブリッジ `BridgeService` 経由の runtime 状態可視化を explore_gui に組み込む。
* `runtime_state.RuntimeState` を GUI 側リアクティブに表示する仕組み。
* バックテスト→apply_params→実運用反映の一貫フロー UI。
* watch ループ制御（開始/停止/パラメータ切替）を探索結果から直接起動する安全制御。
* 3アプリ統合後の単一ウィンドウ・タブ統合再設計。

## 4. 段階的移行プラン

### Phase 1 — 共有基盤の切り出しと explore_gui の分析機能強化

目的: explore_gui 側から backtest_gui_app の共通資産を再利用できる状態を作る。既存アプリの挙動を変えない。

1. 共有ウィジェット・スタイルの中立化（widgets は T-D = TASK-0141/0142 で `gui_common/widgets/` へ canonical 化完了。styles は T-E 着手まで `backtest_gui_app/styles/` に残置）  
   * widgets: `CollapsibleSection` / `MatplotlibChart` / `TimeSeriesChartWidget` は canonical 経路 `gui_common.widgets.{collapsible_section,chart_widget,time_series_chart_widget}` に統一済み（T-D 2段移設完了 = TASK-0141/0142）。再エクスポートシム運用は TASK-0142 で終了し、`backtest_gui_app.widgets.*` 経路は repo 内に残存しない。backtest_gui_app / explore_gui_app いずれの新規コードも `gui_common.widgets.*` を直接 import する。
   * styles: `backtest_gui_app/styles/` は T-E 着手まで現配置維持。T-E で `src/gui_common/styles/` を新設し、現在 `gui_common.widgets.{chart_widget,time_series_chart_widget}` が内包する `backtest_gui_app.styles` への逆依存（層破り）を解消する。
   * 初期 Phase 1 策定時（TASK-0121/0122）は widgets / styles を共に現配置維持とする選択肢 C を採択していたが、Phase 2 実装で `gui_common.widgets.*` 側の再利用が顕在化したため widgets のみ T-D で先行移設した。2 段移設（第1段 = TASK-0141 / 第2段 = TASK-0142 で完遂済み）の作業経緯詳細は `.claude_orchestrator/docs/task_history/過去TASK作業記録.md` の TASK-0141 / TASK-0142 エントリを参照。
2. `strategy_params` の共有化（Phase 1 で先行切り出し／**TASK-0123 で実装完了**）  
   * Phase 1 Step 2 の完了状態（`src/gui_common` 新設・strategy_params 移設・既存 7 箇所 import 書き換え・シム残置・Phase 2 冒頭シム削除予定）の正典記述は §5「共通 GUI 基盤の置き場所方針」を参照（2026-04-17 TASK-0126 で 3 箇所分散を §5 へ一本化）。採択方針（選択肢 C）と層破り解消の動機・選択肢比較の詳細は下記「Phase 1 Step 2 実装サブタスクへの引き渡し事項」を参照。
3. explore_gui に単発バックテスト実行導線を追加（小さく）  
   * 既存 `run_bollinger_exploration` が内部で単月実行を行うため、探索条件で「パラメータ1セット・1CSV」の単発実行ができる UI ボタンを追加する案。責務肥大化を避けるため必要性を director で再判断。
4. explore_gui に中央回帰分析サマリーの表示を追加（Phase 2 結果に対して）  
   * `analyze_all_months_mean_reversion` を Phase 2 結果にも適用。

#### Phase 1 Step 2 実装サブタスクへの引き渡し事項（TASK-0122 決定 / **TASK-0123 で実装完了**）

実装結果サマリー（TASK-0123, 2026-04-17）の正典記述は §5「共通 GUI 基盤の置き場所方針」を参照（2026-04-17 TASK-0126 で 3 箇所分散を §5 へ一本化）。本節は以降、TASK-0122 確定時点の選択肢比較および Phase 1 実装サブタスク起案時の固定事項を歴史的記録として残す。

選択肢比較:

| 選択肢 | 概要 | 評価 |
| --- | --- | --- |
| A: 現配置維持（`backtest_gui_app` を共有元のまま使い続ける） | import 書き換え不要、実装コスト0 | backend → GUI パッケージ依存の層破りを温存し、将来 backtest_gui_app を縮退・削除する際に逆に剥がしにくくなる。不採用。 |
| B: `src/gui_common/` を新設し widgets / styles / strategy_params をまとめて移設 | 最終形としては最もクリーン | Phase 1 の「既存挙動を変えない」原則下で書き換え箇所が広範になり、回帰リスクが高い。不採用。 |
| C: 部分移動（strategy_params のみ `src/gui_common/` へ先行移設、widgets / styles は現配置維持） | 層破りの深刻な箇所だけ先に解消し、段階的に Phase 2 で残りを評価 | import 書き換えは7箇所に限定でき、backend から GUI パッケージへの依存も解消できる。**採用**。 |

Phase 1 実装サブタスク起案時の固定事項:

* 新設パッケージ名は `src/gui_common/`、初期モジュールは `src/gui_common/strategy_params.py`（`StrategyParamSpec`, `get_param_specs`, `read_current_defaults`, `apply_strategy_overrides` をそのまま移設）。
* 対象 import 書き換え7箇所（上記リスト）。差分は import 文のみ・実装コード変更なし。
* `backtest_gui_app/services/strategy_params.py` の扱いは実装サブタスク内で「薄い再エクスポートシムで残す」を既定とし、シム削除は Phase 2 着手時に別サブタスクで行う。
* widgets / styles の gui_common 化は Phase 1 では対象外。Phase 2 の「中央回帰分析サマリー explore_gui 移設」「All Months 詳細 explore_gui 移設」実装タスク内で必要性を再判断する。
* 単発バックテスト導線追加（Phase 1 Step 3）は本決定のスコープ外で、別途 Phase 1 実装タスク分解時に再判断する。

### Phase 2 — explore_gui の主導線化と backtest_gui の責務縮退

目的: 日常操作を explore_gui 側で完結できる状態にする。backtest_gui は「詳細解析ビュー」に格下げする位置付けを確定。

1. explore_gui に「Compare A/B」相当のタブを追加  
   * 既存 `CompareABWorker` を流用（移動ではなく再利用）。
2. explore_gui に「All Months 詳細」タブ or パネルを追加  
   * 月別テーブル + 損益推移チャート + MR サマリーを Phase 2 結果に紐付け。
3. backtest_gui.py は「1戦術の詳細解析・チャート観察」用途として維持  
   * Standard ページ + Chart view タブは残置継続。
4. 両アプリが同時起動されることを前提とした操作導線整理（ランチャー的な README 更新）。

### Phase 3 — 実運用監視の統合と単一アプリ化の判断

目的: explore_gui を唯一の運用入口とし、app_watch_gui の責務を取り込む。  
ただしこのフェーズは `バックテスト・探索・実運用統合アプリ構想`（feature_inventory status=not_implemented）の下でのみ進める。

1. `BridgeService.read_current_state` を呼ぶ runtime 可視化パネルを explore_gui に追加（read-only）。
2. watch 起動/停止ボタンを explore_gui 側に追加し、WatchWorker 相当を再利用。
3. 実トレード送信（`command_writer`）に関わる導線は別タスクで安全制御方針を固めてから実装。本マップのスコープ外。

## 5. 実装前提として不足している部品・接続点

explore_gui 主導への寄せ作業を始める前に、director に確認してもらう必要がある箇所。

* 共通 GUI 基盤の置き場所方針（**TASK-0122 で確定済み / TASK-0123 で Phase 1 Step 2 実装完了** — Phase 1 Step 2 完了記述の正典はこのエントリ）  
  * 結論: 部分移動方針（Section 4 Phase 1 Step 2 の選択肢 C）を採用。`backtest_gui_app/services/strategy_params.py` のみ `src/gui_common/strategy_params.py` へ Phase 1 で移設し、`backtest_gui_app/widgets/`, `backtest_gui_app/styles/` は Phase 1 では現配置維持。選択肢比較（A/B/C）と採択理由の詳細は Section 4 Phase 1 Step 2 引き渡し事項を参照。
  * 実装状況: TASK-0123 で以下が完了（2026-04-17）。
    - `src/gui_common/` パッケージ新設（`src/gui_common/__init__.py`, `src/gui_common/strategy_params.py`）。
    - `StrategyParamSpec` / `STRATEGY_PARAM_MAP` / `get_param_specs` / `read_current_defaults` / `apply_strategy_overrides` を `gui_common.strategy_params` 配下へ物理移設。以降は `gui_common.strategy_params` が正式な import 元。
    - 実 grep で再確定した 7 ファイルの import を `gui_common.strategy_params` へ書き換え: `src/backtest/apply_params.py`, `src/backtest/exploration_loop.py`, `src/backtest/service.py`, `src/backtest_gui_app/views/input_panel.py`, `src/explore_gui_app/views/main_window.py`, `src/explore_gui_app/views/parameter_dialog.py`, `src/explore_gui_app/services/refinement.py`。
    - `src/backtest_gui_app/services/strategy_params.py` はシム削除完了（TASK-0127, 2026-04-17）。旧 import パス `backtest_gui_app.services.strategy_params` の残存ゼロを repo 全体 grep で確認済み（src/ 配下・tests/ 配下・scripts/ 配下いずれも該当なし、`bac/` 配下の過去バックアップは実行対象外）。
    - 売買ロジック・バックテスト数値・GUI 挙動への影響なし（import 文の移動のみ）。
  * 残課題: widgets / styles の gui_common 化は Phase 2 実装タスク内で再評価。
* explore_gui 側の「単発バックテスト」責務の要否  
  * 現状 Phase 1 は「探索ループ専用」で単発バックテストは backtest_gui 側にしかない。ユーザー要求が明確でないため実装順を director 判断とする。
* `apply_params.py` の GUI 連携有無  
  * CLI でしか使われていない。explore_gui から採択パラメータを戦術ファイルに書き戻す UI を作るかは構想段階。
* MT4 ブリッジ経由の runtime 表示方針  
  * `BridgeService.read_current_state` は read-only API として既に存在。書き込み系（`command_writer`）は GUI から叩かない前提を固めるかの合意が必要。
* backtest_gui の最終役割定義  
  * Phase 2 以降に backtest_gui を「詳細解析専用」として残すのか、最終的に explore_gui へ完全統合して削除するのかの方針確定。

## 6. このドキュメントが壊さない範囲

* `src/mt4_bridge/strategies/` 以下の売買ロジックは一切触らない。
* `src/backtest/simulator/` の評価計算・シミュレーターは触らない。
* `src/backtest/service.py`, `exploration_loop.py`, `mean_reversion_analysis.py` は GUI から呼ばれる API 契約を維持する。
* backtest_gui / app_watch_gui の現挙動は Phase 1 では変更しない。

## 7. このドキュメントを更新するタイミング

* Phase 1 のサブタスクが完了するたびに「実装済み / 未着手」のチェック状況を追記する。
* 共有基盤の配置方針が director により確定したら Section 5 の該当項目を確定版へ書き換える。
* Phase 3 に進む判断がされた時点で `統合運用GUI方針` エントリの status を partial → implemented/next として再整理する。

## 8. 4層モデル（バックテスト / 探索 / 分析 / 実運用）

TASK-0130 で確定。explore_gui を主導線にしたとき、扱う責務を「機能の塊」ではなく「層」として4分割する。  
各層は独立した起動点を保ったまま、explore_gui がオーケストレーションする構造とする。

| 層 | 主責務 | 現在の実体 | explore_gui 統合後の入口 | 隣接層との接続点 |
| --- | --- | --- | --- | --- |
| L1 バックテスト | 単発・全月一括バックテストの実行と結果可視化 | `backtest.service.run_backtest` / `run_all_months` / `compare_ab` + `backtest_gui_app` の Standard / All Months / Compare A/B / Chart view タブ | explore_gui に「Backtest」セクション（Phase 2 で導入） | L2: 探索結果の単一パラメータセットを L1 で再実行 / L3: L1 結果を L3 へ受け渡す |
| L2 探索 | パラメータ変動探索（Phase 1 + Phase 2）と上位候補の比較 | `backtest.exploration_loop.run_bollinger_exploration_loop` + `explore_gui_app` の `ExploreInputPanel` / `ExploreResultPanel` | 既に explore_gui に存在。主導線として維持 | L1: 候補 1 件を単発実行へ橋渡し / L3: 探索結果に対して MR 分析を適用 / L4: 採択候補を `apply_params.py` へ橋渡し |
| L3 分析 | 中央回帰成否分析・全月合算成績・MR サマリー・損益推移 | `backtest.mean_reversion_analysis.analyze_all_months_mean_reversion` + `BacktestResultPresenter` の MR セクション + `AllMonthsTab` の MR 列 | explore_gui の「Analysis」セクションとして Phase 2 で取り込む | L1: 単発結果に MR を貼る / L2: Phase 2 結果に対して全期間 MR を貼る / L4: 「採用予定パラメータがログ品質を満たしているか」をチェック |
| L4 実運用 | MT4 ブリッジ runtime 状態取得・watch ループ制御・コマンド送信（高リスク） | `mt4_bridge.services.bridge_service.BridgeService.read_current_state` / `app_watch.run_watch` / `app_watch_gui.WatchWorker` / `mt4_bridge.command_writer` / `mt4_bridge.command_guard` | Phase 3 で explore_gui に「Live」セクション（read-only からの段階導入） | L2/L3: 採択済みパラメータを `apply_params.py` 経由で戦術ファイルへ書き戻し、watch が再起動時に拾う / L4 内部: `command_guard` による send-side 安全制御 |

接続原則:

* 同一プロセス・同一ウィンドウから 4 層を扱えるようにするが、`L4 実運用` への書き込み導線（`command_writer`）は GUI から直接叩かない。L4 への書き込みは戦術ファイル更新（L2 → L4）と watch 再起動（L4 内部のみ）に限定する。
* `L1 バックテスト` の単発実行・チャート観察は backtest_gui に残置（Phase 2 完了時点でも併存可）。explore_gui からは「Backtest 単発」エントリだけを提供する形を初期形とする。
* `L3 分析` は L1 / L2 のいずれの結果に対しても同じ計算関数（`analyze_all_months_mean_reversion`）を流用し、UI 表示器だけを共有化する。

## 9. explore_gui 統合後の画面構成案

TASK-0130 で確定。Phase 完了状態に応じて explore_gui の画面構成を段階的に拡張する。  
最終形（Phase 3 完了時）の主要セクションを先に固定し、各 Phase でどこまで実装するかをマップする。

### 9-1. Phase 1 完了時点（共有基盤切り出し直後の現在地）

* 左ペイン: `ExploreInputPanel`（戦略 / CSV モード / ループ設定 / パラメータ範囲 / Run・Stop・Refine・「全期間で確認する」）
* 右ペイン: `ExploreResultPanel`（Iteration table / Exploration log / Monthly breakdown / Phase 2 results / Phase 2 summary）
* タブ構造なし（単一ページ + 右パネル内のセクション分割のみ）。

### 9-2. Phase 2 完了時点（explore_gui 主導線化）

トップレベルに 4 タブ構成を導入する。各タブは現在の `ExploreInputPanel` / `ExploreResultPanel` を再利用し、追加部分のみ新規実装する。

* タブ A「Explore」: 現在の `ExploreInputPanel` + `ExploreResultPanel`（既存実装そのまま）。主導線。
* タブ B「Backtest 単発」: `backtest.service.run_backtest` を 1 戦略 1 CSV で叩く軽量画面。Standard ページの再実装ではなく「探索結果の 1 候補を単発検証する」用途に絞る。詳細チャート観察は backtest_gui 側に残置案内を出す。
* タブ C「Analysis」: Phase 2 結果に対して `analyze_all_months_mean_reversion` を適用し、MR サマリー・全期間集約・月別ばらつきを大きく表示する読み取り専用ビュー。Compare A/B 相当もここに統合候補（実装は Phase 2 後半）。**[TASK-0137 実装済み / 2026-04-17]** 本タブは C1-a 採択により Phase 2 finished_ok 後の全月合算 MR サマリー 11 項目のみを対象として最小実装済み。全期間集約・月別ばらつきは本 TASK 時点で未対応で、§9-2 フル像との差分は §11-1 T-B 配下サブバレットで管理する。Phase 2 追補 task の起案要否は T-D（`gui_common/widgets/` 化判断）再評価時にまとめて判断する方針（本 TASK-0138 で決定）。注記追加にとどめた理由: 全期間集約・月別ばらつきは追加集計ロジックと UI 拡張を伴い影響範囲が広く、T-D の 2 系統並存解消判断と同じタイミングで評価したほうが docs / 実装双方の整合を取りやすいため。
* タブ D「Apply」: 採択候補パラメータを表示し、`apply_params.py` の dry-run / `--backup` 付き書き込みを GUI から呼び出す導線。実書き込み時は確認ダイアログ必須（戦術ファイルへの恒久反映だから）。**[TASK-0131 確定 / 2026-04-17]** 本タブは Phase 3 で着手する方針に変更（§11-3 T-G 参照）。Phase 2 完了時点のタブ構成は A/B/C の 3 タブで確定し、タブ D の空フレームも設置しない。

サイドバー / ステータスバー:

* ヘッダ右端に「Live status: stopped / running」インジケータ枠を Phase 2 で先行追加（中身は Phase 3 で実装）。
* ステータスバーに現在の Phase（Idle / Phase 1 / Phase 2）を表示（既存実装が `ExploreResultPanel.set_phase` で持っている情報を昇格表示）。

### 9-3. Phase 3 完了時点（実運用統合）

タブ D の右隣にタブ E「Live」を追加する。`app_watch_gui.MainWindow` 相当の責務を取り込む。

* タブ E「Live」:
  * 上段: Strategy / Config path / Status（read-only ラベル群、`load_app_config` 由来）
  * 中段: Start / Stop / Clear log ボタン群（既存 `app_watch_gui` の挙動を移植）
  * 下段: ログビュー（`QPlainTextEdit`、`MAX_LOG_BLOCKS = 1000` を維持）
  * 追加: `BridgeService.read_current_state` の runtime_state 表示パネル（読み取り専用、Phase 3 前半）
* タブ A「Explore」 ↔ タブ E「Live」の連携: タブ E は read-only から始め、「現在 watch が動いている戦術と、explore_gui が今表示している採択候補が一致しているか」を視覚的に比較できる枠を Phase 3 後半で追加する。

backtest_gui / app_watch_gui の扱い:

* Phase 3 完了時点でも両アプリは併存。「単独起動が必要な詳細解析・運用監視は別ウィンドウで継続」という方針を README で明文化する。
* explore_gui への完全統合と backtest_gui / app_watch_gui の廃止は本マップのスコープ外（Section 11 の保留項目）。

## 10. 実運用統合の安全制御方針

TASK-0130 で確定。L4 実運用層を explore_gui に取り込む際、絶対に外せない安全境界を明文化する。

### 10-1. 直接導線を作らない対象

* `mt4_bridge.command_writer` は GUI から直接呼ばない。explore_gui 側の「Apply」「Live」のいずれにも `command_writer` を import しない（仮の利便性関数も作らない）。
* `mt4_bridge.strategies/` 配下の戦術ファイル本体は GUI から書き換えない。書き換えは `backtest.apply_params.py` 経由で `--dry-run` → 確認ダイアログ → `--backup` 付き書き込みのフローに固定する。
* watch ループの `WATCH_INTERVAL_SECONDS = 1.0` を GUI から動的に変更しない（実トレード周期そのものを GUI で触らせない）。

### 10-2. 段階導入順（Phase 3 内サブステップ）

1. read-only runtime 表示の追加  
   * `BridgeService.read_current_state` を 1 秒ポーリング相当でタブ E に表示。書き込み APIは一切呼ばない。
2. watch start/stop の取り込み  
   * 既存 `WatchWorker` をそのまま移植。設定は `load_app_config` 由来で読み取り専用。explore_gui 内から戦術名・config 値を編集しない。
3. apply_params.py の GUI 導線追加（タブ D）  
   * `--dry-run` 結果を表示 → ユーザーが明示的に「Apply」押下 → `--backup` 付きで書き込み。書き込み完了後 watch を自動再起動しない（手動 stop → start を要求）。
4. （保留・本マップ範囲外）coordinated apply  
   * 「apply_params 書き込み → watch 自動再起動」連動は Phase 3 完了後に別マップで設計する。

### 10-3. 既存の安全機構を壊さないこと

以下は GUI 統合の有無にかかわらず維持する。GUI から bypass する API を作らない。

* `command_guard.should_emit_command`（同一バー内の重複 entry 抑止 / pending command の二重送信抑止）
* `runtime_state.RuntimeState` の lane 別 last_command_bar_time / last_command_action / active_command_status
* `position_consistency` のレーン別整合性チェック
* `stale_detector` によるデータ鮮度ブロック

### 10-4. GUI 上の視覚的安全策

* タブ D「Apply」と タブ E「Live」のヘッダ色を他タブと差別化（赤系アクセント）。誤操作を防ぐ。
* 実書き込み・watch start・watch stop は確認ダイアログ必須。Yes/No のデフォルトは No 側に置く。
* 戦術ファイル書き込み時は、書き込み前後の差分（旧値 → 新値の表）をダイアログ内で必ず提示する。

## 11. 次タスク分解と優先順位

TASK-0130 で確定。Phase 1 は完了、Phase 2 へ着手するための実装タスクを以下の粒度で切る。  
1 タスクの目安は「半日〜1 日で完了」「reviewer が単一マージ判断できる」サイズ。

### 11-1. 優先度 P0（Phase 2 の主導線確立に必要）

* T-A: explore_gui の トップレベル QTabWidget 化（タブ A のみ稼働、タブ B/C は placeholder、タブ D は未設置（Phase 3 帰属））  
  * 触る範囲: `explore_gui_app/views/main_window.py` のレイアウト再構成のみ。`ExploreInputPanel` / `ExploreResultPanel` は既存配置のまま タブ A に押し込める。
  * 完了条件: 既存挙動が壊れていないこと（探索 Run / Stop / Phase 2 / Refine が従来どおり動くこと）。
  * 売買ロジック・バックテスト数値変更なし。
  * **[TASK-0132 実装済み / 2026-04-17]** `src/explore_gui_app/views/main_window.py` でトップレベル QTabWidget 化を完了。タブ構成は A: Explore / B: Backtest 単発 / C: Analysis の 3 タブで、タブ B / C は placeholder（空 QWidget）として設置。タブ D は TASK-0131 確定方針（§11-3 T-G / §12-3 / §11-4）に従い未設置とし、空フレーム（空 QWidget）も配置しない（現 §11-1 T-A 見出し括弧書き『タブ A のみ稼働、タブ B/C は placeholder、タブ D は未設置（Phase 3 帰属）』と整合）。タブ A には既存 `ExploreInputPanel` / `ExploreResultPanel` を stretch=1 の `QHBoxLayout` で収容し既存 2 ペイン構成を保持。import / タブ構成 assert / offscreen 起動 exec ret=0 / タブ切替非クラッシュまで自動検証済み。実ユーザー操作による Run / Stop / Refine / Phase 2 全通しの手動確認はコミット前に user 側で履行予定。
* T-B: タブ C「Analysis」最小実装（Phase 2 結果に対して `analyze_all_months_mean_reversion` を表示）  
  * 触る範囲: 新規 `explore_gui_app/views/analysis_panel.py`。`backtest_gui_app/presenters/result_presenter.py` の MR 表示ロジックを参照に作る（コピー or 共通化は実装時判断）。
  * 完了条件: Phase 2 finished_ok 後にタブ C を選択すると、全月合算 MR サマリーが見える。
  * **[TASK-0137 実装済み / 2026-04-17]** 採択方針は C1-a（最小スコープ = 全月合算 MR サマリー 11 項目のみ）/ C2-a（タブ C 責務は Phase 2 結果専用の読み取り専用ビュー、backtest_gui_app 側 MR 表示は重複許容で残置）/ C3-a（参考ソース取り込みは `result_presenter._populate_mean_reversion` と `summary_panel` MR フィールド定義のコピー方式、`gui_common/widgets/` 化は T-D に先送り）。追加ファイルは新規 `src/explore_gui_app/views/analysis_panel.py`（`AnalysisPanel`: 11 MR フィールドを `QGridLayout` で配置 / `set_summary(None)` で全フィールド 'N/A' リセット、`backtest_gui_app` 側 `_populate_mean_reversion` の None 分岐と同挙動）と、`src/explore_gui_app/views/main_window.py` への `_MRAnalysisWorker`（`QThread`）非同期パス + `_on_phase2_finished_ok` 後の `_start_mr_analysis(best)` フック + `_on_run` リセット時の `set_summary(None)` 呼び出し + `_on_stop` での `requestInterruption` 分岐追加。`backtest_gui_app` / `backtest` / `gui_common` / `mt4_bridge` は参照のみで未改変。offscreen 自動検証（Phase 2 finished_ok 後の MR サマリー 11 項目数値表示 / Phase 2 未完了時は 11 フィールド全て 'N/A' / タブ A↔B↔C 切替非クラッシュ / offscreen 起動 `app.exec` ret=0）すべて通過。実ユーザー操作による Run/Stop/Refine/Phase 2 → MR analysis 非同期反映動作の手動確認は TASK-0132/0135/0136 carry_over として user 側履行予定。**申し送り:** C3-a コピー方式採用により MR 表示ロジックが `backtest_gui_app` 側（`result_presenter._populate_mean_reversion` / `summary_panel`）と `explore_gui_app` 側（`AnalysisPanel.set_summary`）の 2 系統で並存する。T-D（`gui_common/widgets/` 化判断）まで『片側変更時は他方同時メンテ必須』の運用ルールを維持する。
* T-C: タブ B「Backtest 単発」最小実装（戦略 1 + CSV 1 で `run_backtest` を叩いて結果を表示）  
  * 触る範囲: 新規 `explore_gui_app/views/backtest_panel.py`。Standard ページの完全再実装ではなく、KPI ストリップ + 結果テーブルの最小構成のみ。
  * 完了条件: 単発バックテストが動き、`SummaryPanel` 相当の主要 KPI が表示される。詳細チャート観察は backtest_gui 側に誘導するリンク文を出す。
  * **[TASK-0131 確定 / 2026-04-17]** 重複許容で進める。用途を「探索結果の 1 候補を単発検証」に限定し、KPI ストリップ + 結果テーブルのみ実装。詳細チャート観察・手動パラメータ調整は backtest_gui Standard ページに誘導。Standard ページは当面削除しない前提。根拠: L2 探索 → L1 単発検証の橋渡し（§8 接続原則）が explore_gui 主導線の中核価値。用途限定 + 誘導リンクで重複コストを最小化できる。
  * **[TASK-0139 実装済み / 2026-04-17]** TASK-0131 重複許容方針 + TASK-0136 タブ B 派生方針に従い、新規 `src/explore_gui_app/views/backtest_panel.py`（`BacktestPanel`: 探索結果 1 候補表示 / Single CSV ⇄ All months モード切替 / 6 KPI + 5 詳細 = 11 項目サマリー / Run・Stop ボタン / Status notes）と `src/explore_gui_app/views/main_window.py` への `_BacktestWorker`（`QThread`）非同期パス + `_on_finished_ok` / `_on_phase2_finished_ok` 後の `_push_candidate_to_backtest_panel` フック追加で T-C を最小実装。タブ B では Phase 1/Phase 2 で最後に採択された候補（adopted → 不在時は最高スコア）の `strategy_name` + `param_overrides` + 直近 CSV/CSV Dir をパネルに自動転送し、ユーザーは Run ボタンで `backtest.service.run_backtest`（単月）または `run_all_months`（全月）を非同期実行できる。Stop ボタンは T-C スコープ通り『実行中は Run を無効化 / ログに stop 要求を表示するだけ』の最小機能で、`run_backtest` / `run_all_months` 自体の中断は T-D で再評価。重複許容方針に従い `backtest_gui_app` 側 `InputPanel` / `SummaryPanel` のフィールド構成を参考にコピー方式で再実装し、`gui_common/widgets/` 化は T-D に先送り。`backtest_gui_app` / `backtest` / `gui_common` / `mt4_bridge` は参照のみで未改変。offscreen 自動検証（タブ A↔B↔C 切替非クラッシュ / `app.exec` ret=0 / 単月バックテスト実行 → 11 項目 summary 反映 = `total_pips=-18.80, trades=87, verdict=discard`）すべて通過。実ユーザー操作による Run/Stop/Refine/Phase 2 → タブ B 候補転送 → 単月/全月 backtest 実行の手動目視確認は TASK-0132/0135/0136/0137/0138 carry_over として user 側履行継続。

### 11-2. 優先度 P1（Phase 2 の品質強化）

* T-D: 共通ウィジェット（`CollapsibleSection` / `MatplotlibChart` / `TimeSeriesChartWidget`）の `gui_common` 化判断  
  * 触る範囲: `backtest_gui_app/widgets/` から `gui_common/widgets/` への物理移設 + 既存 import 書き換え。
  * 着手前に必要性を再判断する（タブ B / タブ C で実際に使い回しが発生してから）。
  * 完了条件: 既存 backtest_gui の挙動が壊れない。
  * **[TASK-0141/0142 実装済み / 2026-04-18]** 2 段移設で完遂。TASK-0141 で物理移設 + 再エクスポートシム残置、TASK-0142 でシム 3 点完全削除 + 旧 import 6 箇所 canonical 化。以降の canonical 経路は `gui_common.widgets.{collapsible_section,chart_widget,time_series_chart_widget}` のみで、`backtest_gui_app.widgets.*` 経路は repo 内に残存しない。作業経緯詳細は `.claude_orchestrator/docs/task_history/過去TASK作業記録.md` の TASK-0141 / TASK-0142 エントリを参照。
* T-E: ダークテーマの explore_gui 適用  
  * 触る範囲: `gui_common/styles/` 新設（または `backtest_gui_app/styles/dark_theme.py` の参照）。explore_gui 側 `MainWindow.__init__` に `apply_dark_theme(self)` を追加。
  * 完了条件: explore_gui の見た目が backtest_gui と統一される。
* T-F: タブ C へ Compare A/B 相当の統合判断  
  * `backtest_gui_app/views/compare_ab_tab.py` の責務を タブ C 配下に取り込むかどうかを実装前に director 判断。重複させない方針なら本タスクは「Compare A/B は backtest_gui 側に残置」で確定。
  * **[TASK-0131 確定 / 2026-04-17]** Phase 2 では Compare A/B は backtest_gui 側に残置で確定。タブ C（Analysis）のスコープは「Phase 2 結果に対する `analyze_all_months_mean_reversion` の MR 表示」に限定し、Compare A/B 機能を取り込まない。本 T-F は Phase 2 完了までは「残置確定」とし、実装タスクは起案しない。根拠: (a) §3-2 で `CompareABWorker` は独立性が高く残置が安全と既に整理済み、(b) タブ C に Compare A/B を取り込むと Phase 2 後半の実装コストが膨らみ、P0（T-A/T-B/T-C）主導線確立の遅延要因になる、(c) explore_gui からは backtest_gui への誘導で当面十分（3 アプリ併存運用方針と整合）。再評価トリガ: Phase 2 完了後、backtest_gui 縮退の方針確定タスクを起案する時点で T-F を再判断する。

### 11-3. 優先度 P2（Phase 2 完了 → Phase 3 着手の橋渡し）

* T-G: タブ D「Apply」最小実装（`apply_params.py` の `--list` / `--dry-run` 結果表示まで）  
  * 触る範囲: 新規 `explore_gui_app/views/apply_panel.py`。実書き込みボタンは disable で配置のみ。
  * 完了条件: 採択候補のパラメータ差分が GUI 上で確認できる。
  * **[TASK-0131 確定 / 2026-04-17]** タブ D は Phase 3 で着手する（Phase 2 では T-G を起案しない）。§9-2 画面構成案では Phase 2 完了時点でタブ D を掲載していたが、帰属 Phase は Phase 3 とする。Phase 2 完了時点ではタブ D は「空フレームを設置しない」扱いとし、タブ構成は A/B/C の 3 タブで確定させる。根拠: (a) §10-2 で apply_params.py の GUI 導線は Phase 3 サブステップ 3 として既に配置済み、(b) 戦術ファイル書き込みは §10-4 の差分表示・確認ダイアログ・`--backup` 必須など安全制御設計が重く Phase 2 の範囲を超える、(c) MVP では L2 採択頻度が低く（§12-3）Phase 3 寄せで実運用影響なし、(d) Phase 2 は T-A/T-B/T-C による主導線確立を優先する。再評価トリガ: Phase 2 完了後、L2 採択頻度が月次 1 回以上となり手動 CLI 実行の手間が顕在化した時点でタブ D 実装を再起案する。
* T-H: タブ E「Live」の枠だけ追加（read-only runtime 表示）  
  * 触る範囲: 新規 `explore_gui_app/views/live_panel.py`。`BridgeService.read_current_state` を 1 秒ポーリングで呼び、runtime_state 主要フィールドを表示。
  * 完了条件: watch 起動中・停止中ともに runtime 状態を正しく表示する。書き込み API には触らない。
* T-I: README 更新（3 アプリ併存運用の操作ガイド）  
  * 触る範囲: ルート README + `.claude_orchestrator/docs/feature_inventory.md` の `統合運用GUI方針` エントリ更新。
  * 完了条件: 「explore_gui を主導線として使い、詳細解析は backtest_gui、運用監視は app_watch_gui」という併存運用方針が明文化されている。

### 11-4. 着手順の推奨

**[TASK-0131 確定反映 / 2026-04-17]** T-F は backtest_gui 残置で確定・T-G は Phase 3 帰属で確定したため、Phase 2 着手順を以下に改訂。

1. T-A → T-C → T-B（タブ枠と最低限の機能 / タブ A 既存 + タブ B/C 実装 / タブ D は空フレームを設置しない）
2. T-E（見た目統一）※ T-D（共通ウィジェット化）は TASK-0141/0142 で完遂済み
3. T-H（タブ E「Live」の枠だけ read-only で先行追加）
4. T-I（ドキュメント締め）→ Phase 3 設計タスクへ移行
5. T-F は Phase 2 完了後、backtest_gui 縮退の方針確定タスクが起案された時点で再判断（Phase 2 では非対象）
6. T-G は Phase 3 で別起案（Phase 2 では非対象）

## 12. 非対象範囲・リスク明文化

TASK-0130 で確定。本マップが扱わない範囲を以下に固定する。

### 12-1. 本マップ・本 task 群の非対象

* 売買ロジックそのものの変更（`mt4_bridge/strategies/` 配下のシグナル判定ロジック、`backtest/simulator/engine.py` 等）。
* バックテスト結果の数値変更（評価式・指標定義の改変）。
* 実トレード送信導線（`command_writer`）の GUI 統合。
* watch ループの周期変更（`WATCH_INTERVAL_SECONDS`）。
* 3 レーン以上への拡張。
* backtest_gui / app_watch_gui の即時廃止。
* explore_gui への完全統合・単一アプリ化（Phase 3 完了後に別マップで判断）。
* `explore_gui_app/views/parameter_dialog.py` の責務再編。
* MT4 EA（`MT4/MQL4/Experts/`）側の変更。

### 12-2. 既知のリスク

* タブ B / C / D / E を性急に追加すると `ExploreInputPanel` の縦幅圧迫により既存探索 UI の操作性が落ちる。T-A 着手時に左ペイン幅・タブ高を実機確認する必要がある。
* `apply_params.py` の GUI 導線（タブ D）は戦術ファイルを書き換える破壊的操作。確認ダイアログ・差分表示・`--backup` 付き書き込みを T-G 実装時から外せない。
* `BridgeService.read_current_state` を 1 秒ポーリングで叩くと watch ループとファイル I/O が競合する可能性がある。T-H 着手時に I/O 排他・キャッシュ方針を実装サブタスク内で確認する。
* `gui_common/widgets/` 移設（T-D）は他に影響範囲が広いため、Phase 1 Step 2（`gui_common/strategy_params.py`）と同様に move + 再エクスポートシム残置 → 後続タスクでシム削除の 2 段で進めた（第1段 = TASK-0141 / 第2段 = TASK-0142 で完遂済み）。現時点でシムは残存せず、canonical 経路 `gui_common.widgets.*` のみが有効。
* タブ E「Live」と既存 `app_watch_gui.MainWindow` を同時起動するとブリッジ I/O が競合する。実装時は同時起動禁止か、ファイルロック方針を明示する。

### 12-3. 確定方針（TASK-0131 / 2026-04-17）

TASK-0130 で director 確認候補として挙げた 3 点を TASK-0131 で確定。詳細根拠と再評価トリガは §11 の各サブタスク記述に追記済み。

* **タブ B「Backtest 単発」の重複許容: 重複許容で進める（T-C 実施）。** 用途を「探索結果の 1 候補を単発検証」に限定し、詳細チャートは backtest_gui Standard ページに誘導。Standard ページは当面削除しない前提。詳細は §11-1 T-C を参照。
* **Compare A/B（T-F）の帰属先: backtest_gui 側に残置で確定。** Phase 2 ではタブ C は MR 表示に限定し、Compare A/B 機能は取り込まない。T-F の実装タスクは Phase 2 完了まで起案しない。詳細は §11-2 T-F を参照。
* **タブ D「Apply」の Phase 帰属: Phase 3 で着手。** Phase 2 完了時点のタブ構成は A/B/C の 3 タブ。§9-2 の画面構成案に空フレームを掲載していたタブ D は Phase 2 範囲外とする。詳細は §11-3 T-G を参照。

本確定に伴い、Phase 2 着手対象は P0（T-A/T-B/T-C）+ P1（T-D/T-E）+ P2（T-H/T-I）に絞られる。T-F / T-G は Phase 2 非対象。

### 12-4. 未解決の判断候補（Phase 3 着手前に確定必須）

* タブ E と `app_watch_gui` 同時起動による MT4 ブリッジ I/O 競合の方針（同時起動禁止 or ファイルロック）は §12-2 で方針提示のみ。Phase 3 着手タスク起案時に判断必須。
* ~~`gui_common/widgets/` 化（T-D）は影響範囲が広い 2 段移設想定のため、T-B / T-C 完了後の再評価フェーズで改めて必要性と段取りの確定が必要。~~ → **[解決済み / TASK-0141/0142]** 2 段移設で完遂済み。以降は canonical `gui_common.widgets.*` のみが有効。
* タブ D Phase 3 着手時の再評価トリガ: L2 採択頻度が月次 1 回以上となり手動 CLI 実行の手間が顕在化した時点で再起案。
