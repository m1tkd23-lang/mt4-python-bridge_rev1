# セッション引継ぎ (session_handover)

最終更新日: 2026-04-21 (v3)

## この文書の役割

進行中の開発セッションを、別セッション／別の作業者が即座に引き継げるようにする。
「今どこまでやったか」「次に何をするか」「何が未解決か」を最小限の情報量で記録する。

---

## 今セッション v3 (2026-04-21) の追加到達点 — 連結 BT 対応

### 課題: 月独立 BT の月跨ぎバイアス

従来の `run_all_months` は CSV を 1 ファイルずつ読み込み、月ごとに独立 BT していた。
これにより以下のバイアスが発生していた:
- **月末強制決済**: `close_open_position_at_end=True` で月跨ぎのオープンポジションを `forced_end_of_data` 決済
- **月初ウォームアップ不連続**: H1 フィルタ (`A_H1_LOOKBACK_BARS=60`, `B_H1_LOOKBACK_BARS=60`) が月初 5 時間発動しない
- **A 戦術の range_reentry_blocks が月初でリセット**(連続 SL 履歴切断)

### 実装

**`src/backtest/csv_loader.py::load_historical_bars_csv_multi(paths: list[Path])`** を新規追加。
複数 CSV を時刻順に結合し、重複時刻は後勝ち、`digits`/`point` は最大値で統一した `HistoricalBarDataset` を返す。

### 連結 BT 結果 (12 ヶ月 65,051 bar, 2025-05-21 〜 2026-04-07)

| 戦略 | 月独立 | **連結** | Δ | trades差 |
|---|---:|---:|---:|---:|
| A 単独 | +708.9 | **+749.3** | +40.4 | +2 |
| B 単独 | +268.4 | +268.4 | ±0 | 0 |
| **combo_AB** | +983.2 | **+1043.0** | +59.8 | +5 |

- 差分の主因は **月初 H1 フィルタ不発動による見逃しエントリーの回復** (月末強制決済は全期間で 1 件のみ)
- B はトレード頻度低いため差分ゼロ
- **連結 BT の数値が本番相当の見積もり**、月独立 BT は過小評価

### combo_AB 連結 BT 月別

| 月 | 独立 | 連結 | Δ |
|---|---:|---:|---:|
| 2025-05 | +30.6 | **+44.8** | +14.2 |
| 2025-06 | -18.4 | **-7.0** | +11.4 |
| 2025-07 | +192.8 | +202.8 | +10.0 |
| 2025-08 | +28.8 | +28.8 | ±0 |
| 2025-09 | +160.6 | +169.6 | +9.0 |
| 2025-10 | +69.1 | +77.1 | +8.0 |
| 2025-11 | +17.4 | +17.4 | ±0 |
| 2025-12 | +58.4 | +58.4 | ±0 |
| 2026-01 | +61.4 | +54.8 | -6.6 |
| 2026-02 | +61.7 | +61.7 | ±0 |
| 2026-03 | +286.9 | +286.9 | ±0 |
| 2026-04 | +33.9 | +47.7 | +13.8 |

**連結 BT 総合: +1043.0 / 崩壊月ゼロ / worst 2025-06 (-7.0)**

### 連結 BT のサンプルコマンド

```python
# 方法 1: 直接 simulator (詳細制御・探索用)
from pathlib import Path
from backtest.csv_loader import load_historical_bars_csv_multi
from backtest.simulator import BacktestSimulator, IntrabarFillPolicy

months = ['2025-05','2025-06','2025-07','2025-08','2025-09','2025-10',
          '2025-11','2025-12','2026-01','2026-02','2026-03','2026-04']
paths = [Path(f'data/USDJPY-cd5_20250521_monthly/USDJPY-cd5_20250521_{m}.csv') for m in months]
ds = load_historical_bars_csv_multi(paths)
sim = BacktestSimulator(strategy_name='bollinger_combo_AB', symbol='USDJPY', timeframe='M5',
    pip_size=0.01, sl_pips=999.0, tp_pips=999.0,  # 戦術定数優先
    intrabar_fill_policy=IntrabarFillPolicy.CONSERVATIVE)
res = sim.run(ds, close_open_position_at_end=True)

# 方法 2: run_all_months の連結モード (service 経由の標準経路)
from backtest.service import run_all_months
r = run_all_months(
    csv_dir=Path('data/USDJPY-cd5_20250521_monthly'),
    strategy_name='bollinger_combo_AB',
    symbol='USDJPY', timeframe='M5',
    pip_size=0.01, sl_pips=999.0, tp_pips=999.0,
    intrabar_fill_policy=IntrabarFillPolicy.CONSERVATIVE,
    connected=True,  # ← 連結 BT
)
# r.aggregate.total_pips, r.aggregate.total_trades
# r.monthly_artifacts = [("connected", BacktestRunArtifacts)]  (単一)
```

### 期間ロバストネス検証 (2026-04-21 v3)

連結 BT で同一 12 ヶ月を 6ヶ月 / 3ヶ月に分割し、各ウィンドウで崩壊月ゼロが維持されるかチェック。

| ウィンドウ | 期間 | total pips | trades | crash | worst 月 |
|---|---|---:|---:|---:|---|
| 12M 全期間 | 2025-05-21〜2026-04-07 | +1043.0 | 903 | 0 | 2025-06 (-7.0) |
| H1 前半6M | 2025-05-21〜2025-10-31 | +516.1 | 451 | 0 | 2025-06 (-7.0) |
| H2 後半6M | 2025-11-03〜2026-04-07 | +526.9 | 452 | 0 | 2025-11 (+17.4) |
| Q1 2025-05..07 | | +240.6 | 170 | 0 | 2025-06 (-7.0) |
| Q2 2025-08..10 | | +275.5 | 281 | 0 | 2025-08 (+28.8) |
| Q3 2025-11..2026-01 | | +130.6 | 266 | 0 | 2025-11 (+17.4) |
| Q4 2026-02..04 | | +396.3 | 186 | 0 | 2026-04 (+47.7) |

- H1 +516 ≒ H2 +527 で期間バイアスほぼ無し
- 全ウィンドウで崩壊月ゼロ、worst は全期間共通で 2025-06 (-7.0)
- これは**同一期間の分割ロバストネス検証**であって、**真の out-of-sample Walk-Forward ではない**点に注意:
  - 手元データは 2025-05-21 以降のみ(`data/USDJPY-cd5.csv` 等は 2026-03〜 の重複データ)
  - 真の OOS 検証には **2024 年以前の USDJPY 5 分足 CSV** が必要 → 別途データ取得タスク

---

## 今セッション v2 (2026-04-21) の追加到達点

### 大きな成果

- **bollinger_combo_AB で BT が成立、1年 12ヶ月すべて崩壊月ゼロ、合計 +983.2 pips** を達成。
- **SL/TP の正本を戦術ファイル側に移管**: `config/app.yaml` の `risk:` セクションを削除し、各戦術ファイル (`bollinger_range_A.py`, `bollinger_trend_B_params.py`) の `SL_PIPS` / `TP_PIPS` 定数を正本とする。combo 戦術は lane 経由で子戦術値を解決。
- **B戦術の 2026-02 崩壊月を解消**: 時刻フィルタ `B_ENTRY_BANNED_HOURS={4, 8, 10}` 導入で B 単独 +229.6 → +268.4、崩壊月 1 → 0。

### 構造変更

1. **BT シミュレータの lane 別 SL/TP 対応**
   - `BacktestSimulator.__init__` に `lane_sl_pips` / `lane_tp_pips` 追加(明示指定用)
   - `_create_position_from_decision` で優先順位 `明示引数 > 戦術定数 > simulator fallback`
2. **戦術ファイルが SL/TP を保持**
   - `bollinger_range_A.py`: `SL_PIPS=20.0`, `TP_PIPS=20.0` 追加
   - `bollinger_trend_B_params.py`: `SL_PIPS=20.0`, `TP_PIPS=40.0` 追加、本体で re-export
   - `bollinger_combo_AB.py`: `LANE_STRATEGY_MAP = {"range": "bollinger_range_A", "trend": "bollinger_trend_B"}` 追加
3. **共通解決ヘルパー**
   - 新規 `src/mt4_bridge/strategies/risk_config.py`
     - `resolve_strategy_risk_pips(strategy_name)` / `resolve_lane_risk_pips(strategy_name, entry_lane)`
4. **ライブ経路の戦術定数必須化**
   - `config/app.yaml` から `risk:` セクション削除(コメントで戦術ファイル側が正本である旨を明記)
   - `app_config.py`: `RiskConfig` 削除、`AppConfig.risk` 削除、yaml パース/環境変数読取削除
   - `app_cli._build_decision_with_risk`: `sl_pips`/`tp_pips` 引数削除、戦術定数が None なら `SignalEngineError`
5. **GUI の戦略選択肢に combo_AB / range_A を追加**
   - `explore_gui_app/views/input_panel.py::_AVAILABLE_STRATEGIES` に追加
   - `backtest/exploration_loop.BOLLINGER_PARAM_VARIATION_RANGES` に `bollinger_range_A` エントリ追加
6. **B戦術の時刻フィルタ本番化**
   - `B_TIME_FILTER_ENABLED = True`
   - `B_ENTRY_BANNED_HOURS = {4, 8, 10}` (2026-02 の SL 集中時刻)
   - 単独時刻寄与: {4}=+0.8, {8}=+20.0, {10}=+18.0 pips(独立加算)

### 最終 BT 結果 (1年, 戦術ファイル SL/TP 経由)

| 戦略 | total | 崩壊月 | worst |
|---|---:|---:|---|
| A 単独 | +708.9 | 1 | 2025-08 (-30.7) |
| B 単独 | **+268.4** | **0** | 2025-09 (-5.7) |
| **combo_AB** | **+983.2** | **0** | 2025-06 (-18.4) |

combo_AB 月別: 2025-06 (-18.4) 以外全月プラス、最強 2026-03 (+286.9)。2026-02 は +61.7(以前 +3.7 → +58 改善)。

### 検証
- pytest 15 passed (戦術定数経由・app.yaml risk 削除・B 時刻フィルタ適用後)
- combo_AB BT は `sl_pips=999/tp_pips=999` のデタラメ fallback 値を渡しても戦術定数経由で +983.2 を再現

---

## 本番再現性の所見 (2026-04-21 v2)

BT で得た数値を本番環境 (MT4 + Python ブリッジ) で再現できる前提と未解決リスクの整理。

### 整合している点

- **signal 評価ロジックは同一**: BT / 本番 とも `mt4_bridge.signal_engine.evaluate_signals` を呼び、A/B/combo_AB の決定ロジックは同じコードを通る。
- **SL/TP 経路**: Python 側で `sl_price` / `tp_price` を戦術定数から計算し、`command_writer` が command JSON の `sl` / `tp` フィールドに載せて EA に渡す。EA は `OrderSend` に反映。
- **magic_number 整合**: `bollinger_combo_AB.py::RANGE_MAGIC_NUMBER=44001` / `TREND_MAGIC_NUMBER=44002` と EA 側 `InpRangeMagicNumber=44001` / `InpTrendMagicNumber=44002` が一致。
- **lane 識別**: EA は command meta の `entry_lane` ("range" / "trend") を読み、対応する magic_number で発注。ポジション comment `lane:range|cmd:*` を埋めて Python 側 `_is_range_lane_position` / `_is_trend_lane_position` で認識。

### 未解決リスク (本番稼働前に必ず確認)

1. **broker time 整合**
   - CSV データ `USDJPY-cd5_20250521_monthly/*.csv` の time 列は broker server time (EET, GMT+2/+3 想定)。
   - A の時刻フィルタ `{5, 7, 13}` と B の時刻フィルタ `{4, 8, 10}` は **この broker hour を前提**。
   - 実ブローカー MT4 のサーバータイムゾーンが CSV データ出所と一致するか、デモ口座で `TimeCurrent()` と JST の差を突き合わせる必要あり。
   - 一致しない場合は時刻フィルタの hours をサーバー時刻にマッピング修正。

2. **スプレッド・スリッページ**
   - BT は `close` 単価で発注し `close` 単価で決済 (bid==ask 仮定、pip=0.01)。
   - 本番は bid/ask 差があるため、エントリー/エグジット双方で微劣化 (典型的に 0.2〜0.5 pips/取引)。
   - A 戦術年間 849 取引で仮に 0.3 pips 劣化なら年 -254 pips 程度のバイアス。SL/TP 計算は point-based で整合だが、合計 pips には影響。
   - 対策: デモ実測でスプレッド影響を測定し、BT を複数スプレッド条件 (0.0 / 0.2 / 0.5 pips) で再評価する(開発の目的本筋 §7 参照)。

3. **バー確定タイミング**
   - BT は CSV 行 = 確定済バーを逐次渡す。
   - 本番は `BridgeSnapshotWriter.mqh` が `last_tick_time` と `TimeCurrent()` で snapshot 生成。未確定バーを含むかは EA の実装に依存。
   - 対策: `snapshot_reader` / `stale_detector` のログで、5分足確定直後のスナップショットが取れているか実稼働で確認。

4. **multi-command dispatch**
   - combo_AB は同一バーで range/trend 双方の signal を返すことがある (`evaluate_bollinger_combo_AB_signals` は list を返す)。
   - `app_cli` はループで各 decision に対し `write_command` を呼ぶ → 同一バーで最大 2 command を出す。
   - EA 側の `BridgeCommandProcessor` が順序通り2 command を処理できるか、また `BridgeCountOpenPositionsForLane` で lane ごとの重複発注をブロックしているかは実装済みだが、実環境での挙動未検証。

5. **command guard との協調**
   - `command_guard.should_emit_command` が `skip_if_pending_command=True` (app.yaml 設定) の場合、まだ EA が未消化の command がある間は次の command を発行しない。
   - combo_AB の range + trend 同時発火時、一方が pending 中だともう一方も skip される可能性あり → lane 別 pending 管理か、順序保証かを詰める必要。

### 本番再現性確認の推奨手順

1. デモ口座で `BridgeWriterEA` を走らせ、`TimeCurrent()` の値を 1 時間単位でログし、CSV データの time と timezone を照合。
2. スプレッド 0.2/0.5 pips 条件で 1年 BT を再実行し、A/B/combo_AB の崩壊月ゼロが維持されるか確認。
3. デモ口座で `bollinger_combo_AB` を 1-2 週間稼働させ、BT 決定ログと実際のコマンド発行ログを突合。

---

## 今セッション (2026-04-21) の到達点

### 大きな成果

**A戦術 + B戦術 合算で、1年 12ヶ月 全てにおいて「崩壊月ゼロ」を達成**。
合計 +938.5 pips、月別すべて -30 pips 以上で、本筋 §6「崩壊月ゼロを採用基準」を満たす状態。

### 設計・ポリシー確定
- 開発目的本筋を改定: A/B 両戦術の磨き込み対象化、評価期間「1ヶ月/3ヶ月/半年/1年」統一、「崩壊月ゼロ」採用基準の新設、ライブは後段
- 戦術構造の統一: A戦略 / B戦略 ともに `*_params / *_indicators / *_rules + 本体` の 3分離構造
- v7 関連コードを全削除(`v7_runner.py` / 旧 `linked_trade_chart_widget.py` / `engine.py` の V7Mixin)

### A戦術のゲーティング確定 (対策①〜④)

各フィルタは個別 ON/OFF 可能(`bollinger_range_A.py` 先頭の ENABLED フラグ)。

| 対策 | 内容 | パラメータ |
|---|---|---|
| **①** `A_SKIP_TREND_STATE_ENABLED=True` | trend_up/trend_down state ではエントリーしない(B の領域) | 固定 |
| **②** `A_UNSUITABLE_FLAG_FILTER_ENABLED=True` | bandwidth_expansion=True ならエントリー見送り | `A_REJECT_ON_BANDWIDTH_EXPANSION=True`, `A_REJECT_ON_SLOPE_ACCELERATION=False` |
| **③** `A_TIME_FILTER_ENABLED=True` | 弱い時刻帯(broker hour 5, 7, 13)を除外 | `A_ENTRY_BANNED_HOURS={5,7,13}` |
| **④** `A_H1_TREND_FILTER_ENABLED=True` | H1 逆張り禁止(直近5時間 close 変化が逆方向なら HOLD) | `A_H1_LOOKBACK_BARS=60`, `A_H1_TREND_THRESHOLD_PIPS=15.0` |

加えて A 戦術の内部設定:
- `ENABLE_RANGE_EXTREME_TOUCH_ENTRY=False`(3σ即時エントリー廃止、2σ再突入のみ)
- `ENABLE_RANGE_FAILURE_EXIT=True`, `RANGE_FAILURE_ADVERSE_MOVE_RATIO=0.28`(現状維持、閾値調整は効果薄と確認)
- SL=20 / TP=20 pips(BT 側で設定、戦略内部は SL/TP 依存しない設計)

### B戦術のゲーティング確定

| 修正 | 内容 | パラメータ |
|---|---|---|
| **修正1** | trend_slope 閾値を 15 倍厳格化(0.00002 → 0.0003) | `TREND_SLOPE_THRESHOLD=0.0003`, `STRONG_TREND_SLOPE_THRESHOLD=0.0008` |
| **修正2** | H1 コンテキストフィルタ(H1 順張り必須、逆張り禁止) | `B_H1_TREND_FILTER_ENABLED=True`, `B_H1_LOOKBACK_BARS=60`, `B_H1_TREND_THRESHOLD_PIPS=15.0` |
| **修正3** | 時刻フィルタ(暫定 OFF) | `B_TIME_FILTER_ENABLED=False`, `B_ENTRY_BANNED_HOURS={5,7,13}` |

B の BT 設定: SL=20 / TP=40 pips(トレンド追従なので TP 幅広め)

### BT 基盤の分析機能強化
- `SignalDecision.exit_subtype` フィールド追加
- A戦術の 4 分岐で `exit_subtype` を設定: `middle_touch_exit` / `range_failure_exit` / `opposite_state_exit` / `opposite_signal_exit`
- B戦術の 3 分岐で `exit_subtype` を設定: `tp_upper_2sigma` / `tp_lower_2sigma` / `opposite_trend_exit`
- `ExecutedTrade` に `exit_subtype` / `entry_bar_index` / `exit_bar_index` / `unsuitable_bars_*` 追加
- `SimulatedPosition` に `entry_absolute_bar_index` / `unsuitable_bars_*` カウンタ追加
- `generic_runner` を `enumerate` 化、保有期間中の `range_unsuitable_flag_*` を蓄積
- 新規 `src/backtest/export.py`: trades / decision_logs / bar-level CSV 出力
- A戦術ラッパーで `debug_metrics` を decision に伝搬(observation を BT log まで届くように)

### 検証
- pytest 15 passed(v7 削除後・3分離統合後・exit_subtype 追加後・A ゲーティング後のすべて)
- 1年 BT 結果(USDJPY 5分足, 2025-05 〜 2026-04):

| 段階 | 総pips | 崩壊月(<-30) | 備考 |
|---|---:|---:|---|
| v4_4 hybrid (初期) | +601.9 | 1 (2026-02 -215) | 3σ即時あり、A が trend も入る |
| 対策①(A pure range) | +706.9 | 1 (2026-02 -178) | B領域非干渉 |
| 対策①+②(bw_exp only) | +726.2 | 1 (2025-08 -131) | |
| 対策①+②+③(time) | +1,021.3 | 2 (2025-05, 2025-08) | 総 pips 最大 |
| 対策①+②+③+④(H1,th=15) | +708.9 | 1 (2025-08 -30.7) | 崩壊月ほぼ解消 |
| **A + B (修正1+2)** | **+938.5** | **0** | **本筋 §6 基準達成** |

### 解明された負けの根本原因
- 2025-05/2025-08 の崩壊の主犯: **「H1 下降中の BB 下限 buy 逆張り」**(downtrend_buy_counter)
- 時刻的には broker hour 13 時(JST 20時、ロンドン午後→NY オープン前)に損失集中
- エントリー時点の単独観測指標(slope / nbw / flags)では勝敗差が出ない
- 5分足 BB だけでは不足で、**上位時間足(H1)コンテキストが判断材料として不可欠**

---

## 次にやること

### 推奨順序
1. **別年データ取得 + 真の Walk-Forward**: 2024年以前の USDJPY 5 分足 CSV を取得し、連結 BT で崩壊月ゼロが維持されるか確認。現状同一 12 ヶ月の分割ロバストネスは確認済みだが out-of-sample 未検証。
2. **本番再現性確認(スプレッド/broker time/multi-command)**: 「本番再現性の所見」§未解決リスク 1〜5 をデモ口座等で詰める。
3. **(δ) GUI 反映**(最終ゴール): パラメータ承認ゲート経由で本番反映するフローを構築、GUI の連結モードチェックボックス追加も含む。
4. **MVP 完成条件 §3.2「月別崩壊ゼロ判定」の BT ロジック実装**: robustness_evaluator.py 等を新規作成、連結 BT の月別結果を消費する。
5. **(α) B単月の微調整**: 更なる改善(軽微、優先度低)

### 崩壊月ゼロ達成後の論点は「再現性」
現在の **連結 BT +1043.0 pips / 崩壊月ゼロ**(combo_AB)は **2025-05 〜 2026-04 の特定 12 ヶ月** に対する結果。
同一期間の 6ヶ月/3ヶ月分割ではすべて崩壊月ゼロを維持しており、期間内ロバストネスは確認済。
残る検証ポイントは **真の out-of-sample(別年データ)** と **本番環境(MT4 + スプレッド込み)** での一致性。

---

## 未解決課題

- **Walk-Forward 検証 未実施** — 他期間でのパラメータロバストネス未検証
- **実ブローカー時刻の確認** — A 時刻フィルタ {5,7,13} / B 時刻フィルタ {4,8,10} は CSV の broker time (GMT+2/+3 想定) が前提。ライブ稼働前に実ブローカーの MT4 サーバー時刻と突き合わせ要
- **スプレッド影響の測定** — BT は close 単価発注。本番は bid/ask 差で微劣化。複数スプレッド条件 (0.0 / 0.2 / 0.5 pips) での 1年 BT 再評価が必要
- **multi-command 同時発火** — combo_AB の range/trend 同時 signal 時の EA 順序処理/command_guard の振る舞いがデモで未検証
- **GUI の動作確認** — backtest_gui_app / explore_gui_app の既存 GUI が対策①〜④+combo_AB 追加後に正しく動作するか未検証
- **承認ゲート経由のパラメータ反映導線** 未実装(本筋 §3.3, 最終ゴール)
- **レジーム判定の A/B 共通分離モジュール** 未実装(本筋 §3.4) — 現状 A は v4_4 内部判定、B は独自判定で二重管理
- **月別崩壊ゼロ判定ロジック** 未実装(現状は手動集計)

---

## 重要な参照

- 正本: `.claude_orchestrator/docs/project_core/開発の目的本筋.md`(2026-04-21 更新)
- 機能棚卸し: `.claude_orchestrator/docs/feature_inventory.md`(2026-04-21 更新)
- 完成定義: `.claude_orchestrator/docs/completion_definition.md`(2026-04-21 更新)

### 出発点モジュール
- A戦略: `src/mt4_bridge/strategies/bollinger_range_A.py`(ラッパー、対策①〜④、`SL_PIPS=20.0`/`TP_PIPS=20.0`) + `bollinger_range_v4_4*.py`(3分離)
- B戦略: `src/mt4_bridge/strategies/bollinger_trend_B.py`(修正1+2+3適用) + `bollinger_trend_B_*.py`(3分離、`SL_PIPS=20.0`/`TP_PIPS=40.0`, `B_ENTRY_BANNED_HOURS={4,8,10}`)
- combo: `src/mt4_bridge/strategies/bollinger_combo_AB.py`(lane 分離、`LANE_STRATEGY_MAP`)
- SL/TP 解決: `src/mt4_bridge/strategies/risk_config.py`(戦術定数の動的解決、lane→子戦術マッピング)
- BT 分析: `src/backtest/export.py`(trades / decision_logs / bar-level をCSVへ)

### 直近 BT の基本コマンド

A戦略 1年 BT:
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "
from pathlib import Path
from backtest.csv_loader import load_historical_bars_csv
from backtest.simulator import BacktestSimulator, IntrabarFillPolicy
months = ['2025-05','2025-06','2025-07','2025-08','2025-09','2025-10','2025-11','2025-12','2026-01','2026-02','2026-03','2026-04']
total = 0.0
for m in months:
    ds = load_historical_bars_csv(Path(f'data/USDJPY-cd5_20250521_monthly/USDJPY-cd5_20250521_{m}.csv'))
    sim = BacktestSimulator(strategy_name='bollinger_range_A', symbol='USDJPY', timeframe='M5',
        pip_size=0.01, sl_pips=20.0, tp_pips=20.0, intrabar_fill_policy=IntrabarFillPolicy.CONSERVATIVE)
    res = sim.run(ds, close_open_position_at_end=True)
    print(m, res.stats.total_pips)
    total += res.stats.total_pips
print('TOTAL', total)
"
```

B戦略は `strategy_name='bollinger_trend_B'`, `tp_pips=40.0`

---

## 環境メモ

- Python 3.12 venv: `.venv/Scripts/python.exe`
- PYTHONPATH: `src` を通す
- データ: `data/USDJPY-cd5_20250521_monthly/USDJPY-cd5_20250521_{YYYY-MM}.csv`(2025-05 〜 2026-04 の 12 ヶ月分)
- pytest: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests`(所要 約 3 分)
- git: main branch 作業中(2026-04-21 時点)、未コミット変更多数
