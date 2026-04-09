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

<!-- TASK-0053 セクション1 判定状況確認: COMPLETE 判定可能
  判定日: 2026-04-10
  feature_inventory 突合結果:
  - 月別CSVバックテスト実行: implemented
  - A/B 2レーン戦術適用: implemented
  - ポジション管理（1レーン1ポジション制約）: implemented
  - SL/TP処理（Intrabar fill）: implemented
  全4項目の対応エントリが implemented であり、partial エントリなし。COMPLETE 判定可能。 -->

> セクション判定: セクション3（MVP中心機能）

---

## 2. 評価・比較機能

- 各月の総pips、勝率、PF、最大DD、取引回数を算出できる
- 全月合算成績を算出できる
- 月別ばらつきや赤字月数を確認できる
- A単体、B単体、A+B合成成績を比較できる

<!-- TASK-0053 セクション2 判定状況確認: COMPLETE 判定可能
  判定日: 2026-04-10
  feature_inventory 突合結果:
  - 成績算出（総pips・勝率・PF・最大DD・取引回数）: implemented
  - 全月合算成績算出: implemented（月別ばらつき stddev・赤字月数は aggregate_stats.py で算出済み）
  - MFE/MAE ratio 補助品質指標: implemented
  - A単体・B単体・A+B合成成績比較: implemented
  全4項目の対応エントリが implemented であり、partial エントリなし。COMPLETE 判定可能。 -->

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
  TASK-0049/0050 carry_over の齟齬は本注釈をもって解決済みとする。 -->

> セクション判定: セクション3（MVP中心機能）

---

## 4. ログ・追跡・最終統合機能

<!-- TASK-0053 セクション4 判定状況確認: COMPLETE 判定不可（partial エントリあり）
  判定日: 2026-04-10
  feature_inventory 突合結果:
  - 構造化ログ出力（trade_id / lane_id / reason_code）: partial — JSONL 形式のトレードライフサイクルログは実装済みだが、「なぜ見送ったか」の構造化記録等が未完了
  - trade_id によるトレード追跡: partial — trade_id フィールドは実装済みだが Optional（デフォルト None）のまま
  - 最終統合（採択結果の bollinger_combo_AB.py 反映）: implemented
  残課題: 構造化ログ出力・trade_id 追跡が partial。COMPLETE 判定には見送り理由の構造化記録、trade_id 必須化等の対応が必要。 -->

- シミュレーターは「なぜエントリーしたか」「なぜ見送ったか」「なぜ決済したか」を追跡できるログを出力する
- 各トレードは一意な `trade_id` で追跡でき、各レーンは `lane_id`（A / B）で区別できる
- ログは人間が読めることに加え、構造化形式（JSON Lines または CSV）で機械集計可能に保存する
- 評価上位のA/B組み合わせを確定し、`src\mt4_bridge\strategies\bollinger_combo_AB.py` に反映でき、再実行時に採択時と同等の結果を再現できる

> セクション判定: セクション3（MVP中心機能）

---

## 5. 操作性

<!-- TASK-0053 セクション5 判定状況確認: COMPLETE 判定不可（partial エントリあり）
  判定日: 2026-04-10
  feature_inventory 突合結果:
  - GUI 応答速度（実用的な速度での再評価）: partial — 応答速度の定量検証が未実施
  - Windows ローカル Python 実行: implemented
  - GUI バックテスト画面: implemented（採択判断の見える化として充足）
  残課題: GUI 応答速度の検証未実施（単月・全月一括の実行時間計測と「実用的な速度」の基準判定が必要）。 -->

- GUI上でのパラメータ変更に対し、実用的な速度で再評価結果が表示される
- 複数月一括評価が現実的な時間で完了する
- GUIは分析・調整支援のための道具として、採択判断の見える化を担う
- Windowsローカル環境でのPython実行で完結する

> セクション判定: セクション5（技術方針）・セクション6（設計方針）

---

## 6. 品質

- 月平均で150〜200 pips程度の利益が出る構成を探索・確認できる
  <!-- status: partial — evaluate_cross_month() / evaluate_integrated() で月平均 pips 基準の判定ロジックは実装済み（evaluator.py）。ただし探索ループ（exploration_loop.py）との接続は未実装 -->
- 全月合算でプラスであり、赤字月が連続せず、月別成績のばらつきが極端でない
  <!-- status: implemented — evaluate_integrated() で total_pips>0・赤字月比率・連続赤字月・月別 stddev を統合判定（evaluator.py）。aggregate_stats.py で deficit_month_count / max_consecutive_deficit_months / monthly_pips_stddev を算出済み -->
- 単月だけ強い戦術は採択せず、全月合算成績と月別安定性の両方を採択条件に含める
  <!-- status: implemented — evaluate_integrated() が全月合算成績（総pips・PF・最大DD）と月別安定性（赤字月比率・連続赤字月・stddev）の両方を採択条件として ADOPT/IMPROVE/DISCARD を返す（evaluator.py） -->
- 戦術の複雑化よりも説明可能性を優先する
  <!-- status: 設計方針として維持。戦術は bollinger_range / bollinger_trend 系の説明可能な指標ベース構成 -->

<!-- TASK-0053 セクション6 判定状況確認: COMPLETE 判定可能
  判定日: 2026-04-10
  feature_inventory 突合結果:
  - 月平均利益基準の探索・確認: implemented（TASK-0040 で探索ループ接続完了）
  - 全月安定性評価（赤字月非連続・ばらつき抑制）: implemented
  注意: 本セクション内の項目(1)既存注釈に「status: partial — 探索ループとの接続は未実装」とあるが、
  feature_inventory では TASK-0040 で接続完了し implemented に更新済み。既存注釈は陳腐化している。
  項目(3)(4) は設計方針として実装に反映済み。
  全項目の対応エントリが implemented であり、COMPLETE 判定可能。 -->

> セクション判定: セクション2（主目的）・セクション6（設計方針）

---

## 7. エラー処理・耐障害性

<!-- TASK-0053 セクション7 判定状況確認: COMPLETE 判定不可（partial エントリあり）
  判定日: 2026-04-10
  feature_inventory 突合結果:
  - エラー処理・耐障害性: partial
  残課題:
  - 「ログが取れないロジックは採択しない」の仕組みが未実装
  - 「構造化項目 reason_code 必須」の強制が未実装
  - リアルタイム側エラー処理は充実しているが、ログ品質制約の実装は不足 -->

- 失敗時は処理全体を壊さず、対象ファイル単位で安全に停止・記録する
- ログが取れないロジックは採択しない
- 自然文だけのログは禁止し、構造化項目（`reason_code` 等）を必須とする

> セクション判定: セクション5（技術方針）・セクション6（設計方針）

---

## 8. データ整合性

- シミュレーターと実運用（MT4）でエントリー条件判定・SL/TP処理・ポジション管理ロジックの挙動差が出ない設計とする
- シミュレーター専用の曖昧な簡略判定は避け、実戦側へ移植可能な設計にする
- 実戦側ログとシミュレーター側ログで `event_type` / `reason_code` / `lane_id` / `trade_id` の概念を一致させる

<!-- TASK-0053 セクション8 判定状況確認: COMPLETE 判定不可（partial エントリあり）
  判定日: 2026-04-10
  feature_inventory 突合結果:
  - データ整合性（シミュレーターと MT4 の挙動一致）: partial
  残課題:
  - event_type / reason_code / lane_id / trade_id のログ概念一致が未実装
  - 「シミュレーター専用の曖昧な簡略判定を避ける」の乖離有無は精査未実施
  - MT4 側（MQL4）と Python 側の構造的対応は取れているが、ログ意味体系の一致は未達 -->

> セクション判定: セクション6（設計方針）

---

## 9. 将来拡張（MVP後）

以下は拡張対象とするが、MVP完成条件には含めない。

### リアルタイム・外部連携
- リアルタイム自動売買そのものの開発
- MT4実行中データを使ったオンライン最適化
- 外部APIやクラウド学習基盤の導入

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
