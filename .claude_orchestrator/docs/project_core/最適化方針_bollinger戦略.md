# 最適化方針: ボリンジャー戦略を主対象とする

## 目的

exploration_loop の最適化対象を明確化し、
汎用テンプレート戦略ではなく既存のボリンジャーバンド戦略を主対象として位置づける。

---

## 対象戦略

### A レーン（レンジ系）

* 主対象: `bollinger_range_v4_4.py`（およびその派生）
* 役割: レンジ相場でのバンド反発エントリー
* パラメータ例: BOLLINGER_PERIOD, BOLLINGER_SIGMA, BOLLINGER_EXTREME_SIGMA, RANGE_SLOPE_THRESHOLD, RANGE_BAND_WIDTH_THRESHOLD, RANGE_MIDDLE_DISTANCE_THRESHOLD

### B レーン（トレンド系）

* 主対象: `bollinger_trend_B.py`（およびその派生: B2, B3, B3_weak_start 等）
* 役割: トレンド相場でのトレンドフォローエントリー
* パラメータ例: TREND_SLOPE_THRESHOLD, STRONG_TREND_SLOPE_THRESHOLD

### A+B 統合

* `bollinger_combo_AB.py` / `bollinger_combo_AB_v1.py` による A/B 統合評価
* 最終採択は A+B 合成成績と月別安定性の両面で判断する

---

## 最適化順序

1. **A レーン単体の最適化**: bollinger_range 系のパラメータ調整を先行
2. **B レーン単体の最適化**: bollinger_trend 系のパラメータ調整
3. **A/B 組み合わせ評価**: A 最適パラメータ + B 最適パラメータで combo_AB 全月横断評価
4. **combo_AB 反映**: 採択パラメータを bollinger_combo_AB.py に反映（apply_params.py）

各ステップで全月横断評価（evaluate_cross_month / evaluate_integrated）を使用する。

---

## ボリンジャー専用 exploration_loop 方針

### 基本方針

ボリンジャー戦略の最適化には、既存の exploration_loop を汎用的にそのまま使うのではなく、
bollinger_range / bollinger_trend / bollinger_combo_AB を対象とした **専用の探索フロー** を用いる。

### 探索方式

* **既存戦略ファイルをそのまま使う**: bollinger_range_v4_4.py / bollinger_trend_B.py 等の既存 `.py` ファイルを探索対象とする
* **`generate_strategy_file()` は使わない**: strategy_generator.py によるテンプレート生成は bollinger 系戦術の構造に対応しておらず、探索フローで使用しない
* **`apply_strategy_overrides()` によるランタイム一時上書きで評価する**: strategy_params.py のコンテキストマネージャでモジュール定数を一時的にオーバーライドし、バックテスト完了後に復元する方式を採用する。戦略ファイル自体は変更しない

### 探索フロー（4段階）

1. **A 単体探索**: bollinger_range 系戦術のパラメータバリエーション（BOLLINGER_PARAM_VARIATION_RANGES）を生成し、全月横断バックテスト→ evaluate_integrated() で各パラメータセットを評価。最良パラメータセットを特定する
2. **B 単体探索**: bollinger_trend 系戦術に対して同様にパラメータバリエーション探索を実施し、最良パラメータセットを特定する
3. **A/B 組み合わせ探索**: A 最良パラメータ + B 最良パラメータの組み合わせで combo_AB を全月横断評価し、A+B 合成成績と月別安定性を確認する
4. **combo_AB 反映**: 採択判定（ADOPT）を得たパラメータセットを apply_params.py で bollinger_combo_AB.py に恒久的に書き込む

### 実装上の対応

* `exploration_loop.py` の `run_bollinger_exploration()` / `run_bollinger_exploration_loop()` が上記フローを担う（TASK-0042 実装済み）
* `generate_bollinger_param_variations()` が BOLLINGER_PARAM_VARIATION_RANGES に基づきパラメータバリエーションを自動生成する
* csv_dir 指定時に全月バックテスト→ aggregate_monthly_stats → evaluate_cross_month / evaluate_integrated を実行する（TASK-0040 実装済み）
* 2レーン構成（A/B）を維持し、3レーン以上には拡張しない

---

## 対象外

以下は現時点での最適化対象に含めない。

* `close_compare` テンプレート戦略（strategy_generator.py のテンプレート）
* `ma_cross` テンプレート戦略（同上）
* `strategy_generator.py` による自動生成戦術ファイル（bac/ 配下）
* 3レーン以上の構成
* 全通貨対応

### 理由

* `close_compare` / `ma_cross` は探索ループの動作検証用テンプレートであり、本来の主対象ではない
* 開発の目的本筋（セクション1）が明示する主対象は「ボリンジャーバンド系のA/B 2レーン戦術」である
* strategy_generator.py の自動生成は bollinger 系戦術の構造に対応していないため、そのまま利用できない

---

## 採択方針

### 利益基準（開発の目的本筋 セクション2 準拠）

* 月平均 150〜200 pips 程度の利益
* 全月合算でプラス
* 特定月のみで利益を出している構成は不採択

### 安定性基準（同セクション2 準拠）

* 赤字月が連続しないこと
* 月別成績のばらつきが極端でないこと
* 最大ドローダウンが破綻レベルに達していないこと

### 判定ロジック

* `evaluator.py` の `evaluate_integrated()` が最終判定を担う
* ADOPT / IMPROVE / DISCARD の3段階判定
* 閾値はパラメータ化済みであり、運用時に調整可能

---

## 実装状況と残課題

### 解決済み

1. ~~`exploration_loop.py` は `strategy_generator.py` の `generate_strategy_file()` に依存しており、bollinger 系戦術を直接最適化対象にできない~~ → TASK-0042 で `run_bollinger_exploration()` / `run_bollinger_exploration_loop()` を実装し、既存戦術 + パラメータオーバーライド方式での探索が可能になった
2. ~~bollinger 系パラメータの変動範囲定義が未整備~~ → TASK-0042 で `BOLLINGER_PARAM_VARIATION_RANGES` / `generate_bollinger_param_variations()` を実装済み
3. ~~exploration_loop と全月横断評価の接続が未実装~~ → TASK-0040 で csv_dir 指定時の全月バックテスト→ evaluate_cross_month / evaluate_integrated 接続を実装済み
4. ~~実データ CSV を用いた結合テスト（TASK-0042 実装後の動作検証）は未実施~~ → TASK-0062 で A単体結合テスト6項目全PASSにより解消済み（2026-04-10）

### 残課題

* GUI 経由の探索統合（将来スコープ）

---

## 整合性

* **開発の目的本筋**: セクション1「ボリンジャーバンド系のA/B 2レーン戦術」、セクション6「初期段階では既存戦術のパラメータ調整を優先」と整合
* **completion_definition**: セクション6「月平均で150〜200 pips程度の利益が出る構成を探索・確認できる」と整合
* **feature_inventory**: 「月平均利益基準の探索・確認」「戦術パラメータ探索ループ」エントリの方向性と整合

---

## この文書の役割

* planner が探索対象を提案する際の基準
* implementer が exploration_loop 改修時の設計方針
* reviewer が「主対象外の戦術に逸れていないか」を検証する際の基準
