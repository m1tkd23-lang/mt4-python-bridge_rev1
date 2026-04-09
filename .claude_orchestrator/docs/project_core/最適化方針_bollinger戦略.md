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
3. **A+B 統合評価**: combo_AB で A/B を組み合わせた全月横断評価
4. **採択判定**: evaluate_integrated() による ADOPT/IMPROVE/DISCARD 判定

各ステップで全月横断評価（evaluate_cross_month / evaluate_integrated）を使用する。

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

## 現状の課題と次の実装ステップ

### 課題

1. `exploration_loop.py` は `strategy_generator.py` の `generate_strategy_file()` に依存しており、bollinger 系戦術を直接最適化対象にできない
2. bollinger 系戦術は既存の `.py` ファイルとして存在し、テンプレート生成ではなくパラメータオーバーライド方式（`strategy_params.py` の `apply_strategy_overrides`）で調整する設計
3. exploration_loop と bollinger 系戦術のパラメータオーバーライド方式を接続する実装が必要

### 次のステップ（実装タスク候補）

* exploration_loop が bollinger 系既存戦術を直接バックテスト対象にできるようにする
  * `generate_strategy_file()` を経由せず、既存戦術名 + パラメータオーバーライドで探索サイクルを回す方式
* bollinger 系パラメータの変動範囲定義（PARAM_VARIATION_RANGES 相当）を追加する
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
