# completion_definition

## 目的

本システムの「完成」を定義する。

---

## MVP 完成条件

以下がすべて成立した状態を MVP 完成とする。

---

## 1. バックテスト・ポジション管理機能

- `data\USDJPY-cd5_20250521_monthly` 配下の月別CSVを読み込み、単月実行と全月一括実行の両方でバックテストを実行できる
- 5分足データに対してA（レンジ系）・B（トレンド系）の2レーン戦術を適用し、トレード結果を再現できる
- 1レーンにつき常に1ポジションのみ保持可能とし、同一レーン内での複数ポジションを禁止する
- ポジション状態（未保有 / 保有中 / 決済待ち）を明確に管理できる

<!-- セクション1 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: 全4項目の対応エントリが feature_inventory 上で implemented であり、partial エントリなし（TASK-0053 判定状況確認で確認済み）
  feature_inventory 突合結果:
  - 月別CSVバックテスト実行: implemented
  - A/B 2レーン戦術適用: implemented
  - ポジション管理（1レーン1ポジション制約）: implemented
  - SL/TP処理（Intrabar fill）: implemented -->

> セクション判定: セクション3（MVP中心機能）

---

## 2. 評価・比較機能

- 各月の総pips、勝率、PF、最大DD、取引回数を算出できる
- 全月合算成績を算出できる
- 月別ばらつきや赤字月数を確認できる
- A単体、B単体、A+B合成成績を比較できる

<!-- セクション2 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: 全4項目の対応エントリが feature_inventory 上で implemented であり、partial エントリなし（TASK-0053 判定状況確認で確認済み）
  feature_inventory 突合結果:
  - 成績算出（総pips・勝率・PF・最大DD・取引回数）: implemented
  - 全月合算成績算出: implemented（月別ばらつき stddev・赤字月数は aggregate_stats.py で算出済み）
  - MFE/MAE ratio 補助品質指標: implemented
  - A単体・B単体・A+B合成成績比較: implemented -->

> セクション判定: セクション3（MVP中心機能）

---

## 3. GUI最適化支援機能

- `src\backtest_gui.py` を参考に新規GUIを作成する
  <!-- status: implemented — backtest_gui_app パッケージとして PySide6 ベースの新規 GUI を構築済み。feature_inventory「GUI バックテスト画面」エントリ（status: partial）が対応。partial の理由は GUI 探索ループ統合等の残課題があるため（本項目自体の充足には影響しない） -->
- GUI上から主要パラメータを変更できる
  <!-- status: implemented — input_panel.py で SL/TP/Balance + 戦術固有パラメータ（BOLLINGER_PERIOD, BOLLINGER_SIGMA 等8項目）を SpinBox/DoubleSpinBox で変更可能。feature_inventory「GUI パラメータ変更・即時再計算」エントリ（status: implemented）が対応 -->
- パラメータ変更後に再計算し、結果を即時反映できる
  <!-- status: implemented — Run backtest ボタン押下でパラメータ変更→再計算→結果反映が動作。apply_strategy_overrides によるランタイムオーバーライドで即時反映を実現。自動再計算（パラメータ変更検知トリガー）は MVP 必須ではなく将来 UX 改善として扱う（TASK-0049/0050 で方針確定）。feature_inventory「GUI パラメータ変更・即時再計算」エントリ（status: implemented）が対応 -->
- 月別成績表、全体成績、損益推移、必要な補助表示を確認できる
  <!-- status: implemented — 以下の GUI 表示で充足:
    - 月別成績表: All Months タブの月別テーブル（Total Pips, Win Rate, PF, Max DD, Trades, Avg MFE/MAE）
    - 全体成績: All Months タブの aggregate パネル（全月合算成績）、SummaryPanel（単月成績）
    - 損益推移: All Months タブの全月通算損益推移チャート（累積 pips 折れ線 + 月境界補助線）
    - 補助表示: Compare A/B タブ（A単体/B単体/A+B合成の3パターン全月合算成績比較）、Avg MFE/MAE 列（All Months・SummaryPanel）
    feature_inventory「GUI バックテスト画面」エントリ（status: partial）および「GUI パラメータ変更・即時再計算」エントリ（status: implemented）が対応 -->

<!-- セクション3「補助表示」充足基準の定義:
  completion_definition 本文の「必要な補助表示」は以下を充足基準とする:
  (a) Compare A/B タブによる A単体/B単体/A+B合成の3パターン比較表示（TASK-0028 実装済み）
  (b) Avg MFE/MAE の月別テーブル列・aggregate パネル・SummaryPanel への表示（TASK-0026/0027 実装済み）
  上記 (a)(b) により、採択判断に必要な比較情報と補助指標が GUI 上で確認可能であり、MVP における「必要な補助表示」を充足する。
  根拠: Compare A/B タブは CLI の --compare-ab 相当機能の GUI 化であり戦術比較の主要導線、MFE/MAE は ExecutedTrade に追加済みの補助指標の可視化 -->

<!-- セクション3 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: 上記4項目すべてが feature_inventory 上で実装確認済み（TASK-0050 MVP充足判定で全項目 implemented を確認）
  注意事項:
  - feature_inventory「GUI バックテスト画面」エントリの status は partial のまま（GUI 探索ループ統合等の残課題があるため）だが、completion_definition セクション3 が要求する4項目自体はすべて充足
  - 「即時反映」はボタン押下式（Run backtest）で MVP 充足と判定。自動再計算は将来の UX 改善
  - GUI 探索ループ統合のスコープ齟齬（completion_links vs completion_definition 本文）は未解決（本判定スコープ外、TASK-0049 carry_over） -->

<!-- TASK-0052 スコープ齟齬解決:
  GUI 探索ループ統合（exploration_loop.py の GUI 経由実行）は completion_definition セクション3 の本文4項目に含まれない。
  セクション3 は「新規GUI作成」「パラメータ変更」「再計算即時反映」「月別成績表・全体成績・損益推移・補助表示」の4項目を要求しており、
  「探索ループの GUI 統合」はこれらに該当しない。
  帰属先: セクション6（品質）— 探索ループは「月平均150〜200pips の構成を探索・確認できる」に対応する機能であり、CLI ベースで実装済み。
  GUI 統合は将来拡張（セクション9 相当）として扱う。
  これにより feature_inventory「GUI バックテスト画面」エントリの status を partial → implemented に昇格。
  TASK-0049/0050 carry_over の齟齬は本注釈をもって解決済みとする。

  [TASK-0065 方針確定] 探索ループの GUI 化は backtest_gui.py へのタブ追加ではなく、
  explore_gui.py を別エントリポイントとして新規作成する。内部パッケージも explore_gui_app として
  backtest_gui_app とは分離する。これにより既存 GUI の責務（単発バックテスト・全月集計・A/B比較）を壊さずに
  探索専用 UI を設計できる。初期スコープは bollinger_range_v4_4 を対象とした A単体探索に限定する。 -->

> セクション判定: セクション3（MVP中心機能）

---

## 4. ログ・追跡・最終統合機能

<!-- セクション4 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: TASK-0055 で構造化ログ出力（SKIP イベント reason_code 付き記録）と trade_id 必須化が完了し、全3項目の対応エントリが feature_inventory 上で implemented（TASK-0053 時点の partial 2件が解消済み）
  feature_inventory 突合結果:
  - 構造化ログ出力（trade_id / lane_id / reason_code）: implemented — TASK-0055 で SKIP イベント（見送り理由）の構造化記録を追加（reason_code: range_reentry_blocked / entry_event_not_allowed / no_entry_condition / hold_no_entry）
  - trade_id によるトレード追跡: implemented — TASK-0055 で trade_id を Optional→必須（str）に変更
  - 最終統合（採択結果の bollinger_combo_AB.py 反映）: implemented -->

- シミュレーターは「なぜエントリーしたか」「なぜ見送ったか」「なぜ決済したか」を追跡できるログを出力する
- 各トレードは一意な `trade_id` で追跡でき、各レーンは `lane_id`（A / B）で区別できる
- ログは人間が読めることに加え、構造化形式（JSON Lines または CSV）で機械集計可能に保存する
- 評価上位のA/B組み合わせを確定し、`src\mt4_bridge\strategies\bollinger_combo_AB.py` に反映でき、再実行時に採択時と同等の結果を再現できる

> セクション判定: セクション3（MVP中心機能）

---

## 5. 操作性

<!-- セクション5 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: TASK-0057 で GUI 応答速度の定量検証を実施し、全エントリが implemented に昇格
  「実用的な速度」基準定義: 単月バックテスト5秒以内、全月一括バックテスト60秒以内
  計測結果:
  - 単月バックテスト（bollinger_combo_AB, 12ヶ月個別計測）: 0.4〜2.8秒（平均約2.1秒） → 基準クリア
  - 全月一括バックテスト（12ヶ月一括）: 約26秒 → 基準クリア
  - GUI は QThread 非同期実行のため全月一括中も UI 応答を維持
  feature_inventory 突合結果:
  - GUI 応答速度（実用的な速度での再評価）: implemented（TASK-0057 定量検証済み）
  - Windows ローカル Python 実行: implemented
  - GUI バックテスト画面: implemented（採択判断の見える化として充足） -->

- GUI上でのパラメータ変更に対し、実用的な速度で再評価結果が表示される
- 複数月一括評価が現実的な時間で完了する
- GUIは分析・調整支援のための道具として、採択判断の見える化を担う
- Windowsローカル環境でのPython実行で完結する

> セクション判定: セクション5（技術方針）・セクション6（設計方針）

---

## 6. 品質

- 月平均で150〜200 pips程度の利益が出る構成を探索・確認できる
  <!-- status: implemented — evaluate_cross_month() / evaluate_integrated() で月平均 pips 基準の判定ロジックは実装済み（evaluator.py）。探索ループ（exploration_loop.py）との接続は TASK-0040 で完了済み -->
- 全月合算でプラスであり、赤字月が連続せず、月別成績のばらつきが極端でない
  <!-- status: implemented — evaluate_integrated() で total_pips>0・赤字月比率・連続赤字月・月別 stddev を統合判定（evaluator.py）。aggregate_stats.py で deficit_month_count / max_consecutive_deficit_months / monthly_pips_stddev を算出済み -->
- 単月だけ強い戦術は採択せず、全月合算成績と月別安定性の両方を採択条件に含める
  <!-- status: implemented — evaluate_integrated() が全月合算成績（総pips・PF・最大DD）と月別安定性（赤字月比率・連続赤字月・stddev）の両方を採択条件として ADOPT/IMPROVE/DISCARD を返す（evaluator.py） -->
- 戦術の複雑化よりも説明可能性を優先する
  <!-- status: 設計方針として維持。戦術は bollinger_range / bollinger_trend 系の説明可能な指標ベース構成 -->

<!-- セクション6 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: 全項目の対応エントリが feature_inventory 上で implemented であり、partial エントリなし（TASK-0053 判定状況確認で確認済み）
  feature_inventory 突合結果:
  - 月平均利益基準の探索・確認: implemented（TASK-0040 で探索ループ接続完了）
  - 全月安定性評価（赤字月非連続・ばらつき抑制）: implemented
  - 項目(3)(4) は設計方針として実装に反映済み -->

> セクション判定: セクション2（主目的）・セクション6（設計方針）

---

## 7. エラー処理・耐障害性

<!-- セクション7 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: TASK-0058 で残課題2件（ログ品質制約）を実装し、全項目の対応エントリが feature_inventory 上で implemented に昇格
  feature_inventory 突合結果:
  - エラー処理・耐障害性: implemented（TASK-0058 で partial → implemented に昇格）
  実装内容:
  - evaluator.py に check_log_quality() / evaluate_backtest_with_log_guard() を追加: BacktestResult の構造化ログ出力可能性を検証し、ログ不可ロジックを DISCARD 扱い
  - trade_logger.py に _validate_reason_code() を追加: SKIP/ENTRY/EXIT イベント記録時に reason_code フィールドの存在を検証し、欠落時に ValueError を送出 -->

- 失敗時は処理全体を壊さず、対象ファイル単位で安全に停止・記録する
- ログが取れないロジックは採択しない
- 自然文だけのログは禁止し、構造化項目（`reason_code` 等）を必須とする

> セクション判定: セクション5（技術方針）・セクション6（設計方針）

---

## 8. データ整合性

- シミュレーターと実運用（MT4）でエントリー条件判定・SL/TP処理・ポジション管理ロジックの挙動差が出ない設計とする
- シミュレーター専用の曖昧な簡略判定は避け、実戦側へ移植可能な設計にする
- 実戦側ログとシミュレーター側ログで `event_type` / `reason_code` / `lane_id` / `trade_id` の概念を一致させる

<!-- セクション8 完了判定: COMPLETE
  判定日: 2026-04-10
  判定根拠: TASK-0059 で残課題3件を解消し、データ整合性エントリが feature_inventory 上で implemented に昇格
  feature_inventory 突合結果:
  - データ整合性（シミュレーターと MT4 の挙動一致）: implemented
  実装内容:
  - log_concept_mapping.py を新設し、event_type / reason_code / lane_id / trade_id のシミュレーター⇔MT4 概念対応表を定義
  - trade_logger.py がマッピング定数（VALID_EVENT_TYPES / VALID_EXIT_REASON_CODES / VALID_LANE_IDS）を参照し、イベント出力時の概念一致を検証
  - engine.py の全 mixin（position_manager / intrabar / generic_runner / v7_runner）を精査し、シミュレーター専用の簡略判定がないことを確認:
    - SL/TP 計算: mt4_bridge.risk_manager.calculate_sl_tp() を共用（シミュレーター独自の簡略計算なし）
    - エントリー条件判定: 同一戦略関数（range_buy_confirmed 等）を使用（シミュレーター独自のショートカットなし）
    - ポジション管理: 1レーン1ポジション制約をシミュレーター・MT4 双方で同等に強制
    - Intrabar SL/TP: IntrabarFillPolicy による同一足 SL+TP 競合解決は設計上の制約であり簡略判定ではない -->

> セクション判定: セクション6（設計方針）

---

## 9. 将来拡張（MVP後）

以下は拡張対象とするが、MVP完成条件には含めない。

### リアルタイム・外部連携
- リアルタイム自動売買そのものの開発
- MT4実行中データを使ったオンライン最適化
- 外部APIやクラウド学習基盤の導入

### 探索ループ GUI 統合
- 探索専用GUI（explore_gui.py）の新規作成 — 既存 backtest_gui.py とは別エントリポイントとして設計
  <!-- [TASK-0065 方針確定]
    初期スコープ: bollinger_range_v4_4 を対象とした A単体探索（探索回数/improve回数/variation数/seed 入力、パラメータ範囲設定、実行ログ表示、結果一覧、上位候補確認）
    後続拡張: B単体探索、A/B組み合わせ探索、apply_params.py による採択結果反映導線 -->
  <!-- [TASK-0067 基本骨格完了]
    explore_gui.py エントリポイントと explore_gui_app パッケージ（main_window / input_panel / result_panel）を新規作成済み。
    BollingerLoopConfig 経由で run_bollinger_exploration_loop に接続する GUI フレームが構築済み。
    feature_inventory status: not_implemented → partial（TASK-0068 で更新）。
    残課題: GUI 実機起動確認未実施、BOLLINGER_PARAM_VARIATION_RANGES のモジュールレベル直接変更問題、Stop ボタン即時停止未対応 -->

### 構成・対象拡張
- 3レーン以上の戦術構成
- 全通貨対応の汎用最適化

---

## 優先順位

1. バックテスト・ポジション管理機能 + 評価・比較機能（主目的の達成に直結）
2. GUI最適化支援機能（パラメータ調整の高速試行錯誤に必要）
3. ログ・追跡・最終統合機能（品質保証と最終成果物の生成に必要）
4. 操作性・品質・エラー処理・データ整合性（全体の信頼性と実用性を支える）

---

## 対象外

- リアルタイム自動売買そのものの開発
- MT4実行中データを使ったオンライン最適化
- 3レーン以上の戦術構成
- 外部APIやクラウド学習基盤の導入
- 全通貨対応の汎用最適化
