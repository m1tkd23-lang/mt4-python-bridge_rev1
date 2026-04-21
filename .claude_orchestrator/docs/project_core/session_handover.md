# セッション引継ぎ (session_handover)

最終更新日: 2026-04-21 (v4)

## この文書の役割

進行中の開発セッションを、別セッション／別の作業者が即座に引き継げるようにする。
「今どこまでやったか」「次に何をするか」「何が未解決か」を最小限の情報量で記録する。

---

## 今セッション v4 (2026-04-21) の追加到達点 — GUI 機能改善・Chart タブ追加・exe 化準備

### 大きな成果

- **explore_gui の Backtest 単発タブが Explore 未実行でも使えるように**: Strategy コンボ + CSV 手動指定 + 進捗バーで独立動作
- **連結 BT が GUI から選択可能**: `run_all_months(connected=True)` のチェックボックスを BT タブに追加
- **Chart タブ新設**: BT 結果の Trades + チャートをモードレスのポップアップで 1 画面表示、Table 選択 → 該当 trade にズーム & ハイライト(x/y 両方拡大)
- **Trades table を「コア 11 + 詳細 22」に再構成**: pips 色分け / 崩壊ハイライト / Lane・Position・Pips フィルタ
- **共通 widget 化**: `gui_common/widgets/linked_trade_chart_widget.py` と `trades_table_widget.py` で explore_gui / backtest_gui / 将来の ChartPopup が共有
- **本番環境クローン準備**: `.gitignore` に runtime/ analysis/out/ memo 追加、`requirements.txt` に pyinstaller 追加、`BUILD.txt` で `mt4-watch-gui.spec` ベースの exe 化手順を文書化
- **config/app.yaml の `risk:` セクション削除**: SL/TP は戦術ファイル側が正本(ライブ経路が `resolve_lane_risk_pips` 経由で決定)
- **デモ口座 broker time 確認済**: MT4 サーバー時刻 = UTC+3 (EEST, 夏時間中)、CSV データと一致、A `{5,7,13}` / B `{4,8,10}` はそのまま有効

### GUI 構造変更

1. **新規共通 widget (gui_common/widgets/)**
   - `linked_trade_chart_widget.py`: ローソク+累積 pips 連動、dark theme 配色、lane 別マーカー(range=青紫 / trend=緑橙)、描画間引き(可視本数 >= 2000 で close 折れ線に自動切替)、`reset_zoom()`、state 背景 ON/OFF 切替、`highlight_trade()` で x/y 両軸の自動フィット(padding 12%)
   - `trades_table_widget.py`: 33 列(コア 11 / 詳細 22)、詳細は default hidden、pips 色分け(正緑/負赤/崩壊-20 以下背景赤)、Lane / Position / Pips(Win/Loss/Crash) の 3 フィルタ、`trade_selected` シグナル

2. **新規 explore_gui ビュー**
   - `chart_popup_window.py` (QDialog モードレス): 全期間表示、Reset zoom / Clear highlight / State background トグル、close イベントで親タブに通知
   - `chart_tab.py`: Strategy / CSV / Trades 件数表示 + Open/Close ボタン + TradesTableWidget。**同時 1 枚ガード**(2度目 open は既存 raise、BT 再実行時は既存 close して新 artifacts で再生成)、テーブル選択で popup 自動 open & focus

3. **Backtest 単発タブの改修**
   - Strategy コンボを追加(`AVAILABLE_STRATEGIES` を `explore_gui_app/constants.py` に切り出して input_panel と共有)
   - 戦術定数 SL/TP の read-only ラベル表示(combo 戦術は lane 別に表示)
   - All months モード時に「Connect CSVs before backtest」チェックボックス
   - 進捗バー(Single/connected は indeterminate marquee、月独立は `i/12` 定量表示)
   - レイアウト改修: 上段 3 カラム横並び (candidate/source/market) + 下段 Splitter (details/notes)

4. **main_window 配線**
   - `_BacktestWorker` に `progress_signal` 追加、`run_all_months(progress_callback=...)` に接続
   - `_on_backtest_finished_single` / `_on_backtest_finished_all_months` で `self._chart_tab.set_artifacts(...)` を呼ぶ

### 最終 GUI タブ構成

```
ExploreMainWindow
├── Explore        (Phase 1/2 探索)
├── Backtest 単発  (候補検証 + 連結 BT + 進捗バー)
├── Chart          (新) Trades table + Open chart button
└── Analysis       (Phase 2 mean-reversion summary)
```

Chart window(モードレス、1 枚ガード)は別ウィンドウで開く。

### 検証

- pytest 15 passed(全フェーズで維持)
- smoke test: 各 widget 単体 import/instantiate OK、タブ構成 `['Explore', 'Backtest 単発', 'Chart', 'Analysis']` 確認
- デモ口座稼働: state.json の時刻から UTC+3 を確認、signal 評価は走行中(HOLD 期間)

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

## 戦略レビュー — 2026-04-21 v4 時点の率直な評価

**結論を先に**: 「崩壊月ゼロ / +1043 pips / 12ヶ月」は**限定された条件下での好結果**であり、本番運用の前提として頼れる数字ではない。

### 良い点

1. **退場しない設計は徹底されている**
   - 本筋 §2「破綻しないこと最優先」を実装レベルで満たしている
   - 月別崩壊ゼロが実測で 12ヶ月連続、worst 月でも -7.0 pips (2025-06)
   - SL=20 固定で最大損失がキャップされ、1 trade あたりの blow-up リスクは低い

2. **戦略の相補性が機能している**
   - A単独: +708.9, crash 1 (2025-08 -30.7)
   - B単独: +268.4, crash 0(時刻フィルタ採用後)
   - combo: +1043.0, crash 0 — **A と B が互いに崩壊月を救済する関係**
   - 特に 2026-02 は A +33.8 / B +27.9 = +61.7 で一方だけでは弱い月を補完

3. **コード構造は保守性が高い**
   - 3分離(params / indicators / rules + 本体)で戦略変更コストが低い
   - SL/TP を戦術ファイル側に持たせたことで `config/app.yaml` 依存が排除された
   - 連結 BT 実装で月跨ぎバイアスが定量化 (+60 pips 改善幅)

### 懸念点 (率直に)

1. **単一期間フィッティングの色が濃い**
   - 最適化に使ったデータは 2025-05〜2026-04 の 12ヶ月のみ
   - 手元に 2024 以前の CSV が無いため、**真の out-of-sample 検証が一度も行われていない**
   - 期間内分割(H1/H2、Q1-Q4)では崩壊ゼロ維持だが、これは「同じ 12ヶ月を切り分けただけ」で独立性は低い

2. **フィルタの多層化で過学習リスクが積み重なっている**
   - A 戦術: 対策①②③④、4 層
   - B 戦術: 修正 1+2+3、3 層
   - 合計 7 層のフィルタ、どれも「2025-2026 データで負けた事象を逆引き」で決めた閾値
   - 特に **B の時刻フィルタ `{4, 8, 10}` は 2026-02 の SL 4 件を観察して決定**。他年で同じ時刻が弱いとは限らない
   - A の H1 閾値 15 pips も "たまたま 15 が良かった" 可能性

3. **時刻フィルタで運用時間の 25% を放棄**
   - A `{5,7,13}` + B `{4,8,10}` = 6 時刻 / 24h = **運用時間の 25% 自主停止**
   - これは堅牢性の現れであると同時に、**特定時間帯の市場構造に依存している**ことも意味する
   - ブローカーや月によって weak hour が変わると、効果が逆転する可能性

4. **スプレッド込みの実戦績は不明**
   - BT は `close` 単価で発注・決済(bid=ask 仮定)
   - A 単独で年間 849 trade、スプレッド 0.3 pips/片側なら **往復 0.6 pips × 849 = -509 pips のバイアス**
   - 仮にこの劣化が丸々効いたら A 単独は +708.9 → +200、combo は +1043 → +534 に低下の可能性
   - B は 43 trade なので影響小(年 -26 pips 程度)
   - **この測定をせずに本番稼働するのは危険**、未解決課題の筆頭

5. **H1 フィルタは "5 分足の直近 60 本" の近似**
   - 真の H1 bar ではなく、5 分足 × 60 = 5 時間ウィンドウ
   - 本当の H1 足(時間足確定のタイミング)との微妙な乖離が BT/本番で差を生む可能性
   - `market_snapshot.bars` に複数時間足を載せる改修をすれば真の H1 に置換可能だが未着手

6. **統計的有意性の裏付けが弱い**
   - サンプル期間 12 ヶ月、サンプル trade 900 件は統計的には**まだ少ない**
   - PF や sharpe の数値は「この期間に対する記述統計」で、将来予測の信頼区間は出せていない
   - 「崩壊月ゼロ」は必要条件だが十分条件ではない

7. **signal_close 依存の decay リスク**
   - SL/TP 保険より signal_close 主体(91〜97%)という設計意図は良いが、これは「戦略の decision ロジックがずっと正しく市況を読めている」前提
   - 市況が未経験の相場(例: 2024 年の円急落、2022 年の極端レンジ)になった場合、signal_close が遅れる or 打たれないリスク

### 採点(個人的印象)

| 項目 | 点数 | 所見 |
|---|---:|---|
| 退場しない設計 | A | SL=20 固定、崩壊月ゼロ、フェイルセーフ実装済 |
| BT 結果 | B+ | 12ヶ月でクリーンだが out-of-sample 未検証 |
| コード品質 | A- | 3分離・戦術定数化で保守性高い |
| 再現性 | C | 本番・スプレッド・別年データ全部未検証 |
| 過学習耐性 | C+ | 7 層フィルタは最適化依存が高い、シンプル化余地あり |
| 統計的裏付け | C | サンプル不足、信頼区間未算出 |

**総合**: 現時点は「**有望な候補戦略**」であって「**本番稼働できる戦略**」ではない。少なくとも以下 3 つは片付けてから本番移行すべき:
- 2024 以前の OOS 検証(最優先)
- スプレッド 0.3〜0.5 pips を乗せた BT 再評価
- デモ口座で 1〜2 ヶ月の実稼働検証

逆に言えば、**崩壊月ゼロ基準を本当に崩さない堅さがあれば、小額ロットで走らせながら OOS を並行検証する**という運用は妥当。その場合も破綻回避が最優先なので、初期ロット = 0.01 から始めて 3 ヶ月ごとに増やす段階的運用を推奨。

### 優先的に詰めるべきこと (この順)

1. **2024 年以前の USDJPY 5 分足 CSV 取得** → 連結 BT で崩壊月ゼロ維持を検証(= 真の OOS)
2. **スプレッド影響測定** → 0.0/0.3/0.5 pips 条件で再評価、実績 pips の上振れ/下振れレンジを明確化
3. **デモ 1 ヶ月稼働** → BT 決定ログと本番コマンド発行ログを突合、multi-command / command_guard の実地検証
4. **冬時間移行後 (2026-10-25 頃) の再評価** → フィルタ hour そのままで崩壊月ゼロ維持されるか観察
5. フィルタの寄与分解 → どのフィルタを抜くと崩壊月が復活するかの感度分析、過学習リスクの高いフィルタ特定

---

## 本番再現性の所見 (2026-04-21 v2)

BT で得た数値を本番環境 (MT4 + Python ブリッジ) で再現できる前提と未解決リスクの整理。

### 整合している点

- **signal 評価ロジックは同一**: BT / 本番 とも `mt4_bridge.signal_engine.evaluate_signals` を呼び、A/B/combo_AB の決定ロジックは同じコードを通る。
- **SL/TP 経路**: Python 側で `sl_price` / `tp_price` を戦術定数から計算し、`command_writer` が command JSON の `sl` / `tp` フィールドに載せて EA に渡す。EA は `OrderSend` に反映。
- **magic_number 整合**: `bollinger_combo_AB.py::RANGE_MAGIC_NUMBER=44001` / `TREND_MAGIC_NUMBER=44002` と EA 側 `InpRangeMagicNumber=44001` / `InpTrendMagicNumber=44002` が一致。
- **lane 識別**: EA は command meta の `entry_lane` ("range" / "trend") を読み、対応する magic_number で発注。ポジション comment `lane:range|cmd:*` を埋めて Python 側 `_is_range_lane_position` / `_is_trend_lane_position` で認識。

### 確認済リスク

1. **broker time 整合 (2026-04-21 v3 確認済)**
   - デモ口座の state.json `last_seen_latest_bar_time=14:05:00` と JST 現在時刻 20:07 の差 → **JST - MT4 = +6h = UTC+3 (EEST, 夏時間)**
   - CSV データも MT4 出力なので同じタイムゾーン系、A `{5,7,13}` / B `{4,8,10}` はそのまま有効
   - BT データ(2025-05〜2026-04)は DST 跨ぎ(冬 EET / 夏 EEST)を内包しており、どちらの期間でも崩壊月ゼロ実績あり
   - 戦術フィルタは `latest_bar_time.hour` を MT4 ローカル時刻で判定、DST 切替後もそのまま動作

### 未解決リスク (本番稼働前に必ず確認)

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

- **Walk-Forward 検証 未実施** — 他期間でのパラメータロバストネス未検証(手元データは 2025-05 以降のみ、2024 以前の CSV 取得が前提)
- **スプレッド影響の測定** — BT は close 単価発注。本番は bid/ask 差で微劣化。複数スプレッド条件 (0.0 / 0.2 / 0.5 pips) での 1年 BT 再評価が必要
- **multi-command 同時発火** — combo_AB の range/trend 同時 signal 時の EA 順序処理/command_guard の振る舞いがデモで未検証
- **GUI の動作確認** — backtest_gui_app / explore_gui_app の既存 GUI が対策①〜④+combo_AB 追加後に正しく動作するか未検証
- **承認ゲート経由のパラメータ反映導線** 未実装(本筋 §3.3, 最終ゴール)
- **レジーム判定の A/B 共通分離モジュール** 未実装(本筋 §3.4) — 現状 A は v4_4 内部判定、B は独自判定で二重管理
- **月別崩壊ゼロ判定ロジック** 未実装(現状は手動集計)

### 期限付きタスク (calendar-driven)

- **2026-10-25 頃 (冬時間移行直前) — 時刻フィルタ DST 再確認**
  - ブローカーのサーバー時刻が EEST(UTC+3) → EET(UTC+2) に切り替わるタイミング
  - BT データ(2025-05〜2026-04)は DST 跨ぎを内包して崩壊月ゼロ実績ありなので、原則そのまま運用可
  - ただし念のため以下を実行:
    1. 冬時間のみ(2025-11〜2026-03)連結 BT → 崩壊月ゼロ維持確認
    2. 夏時間のみ(2025-05〜2025-10, 2026-04)連結 BT → 崩壊月ゼロ維持確認
    3. 稼働中の A `{5,7,13}` / B `{4,8,10}` 時刻フィルタが冬時間下でも期待通り機能するか、稼働ログで一週間程度観察
  - もし冬時間期間のみ崩壊月が出る場合は冬/夏別 hour セット `{winter_hours, summer_hours}` への分岐を検討

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
