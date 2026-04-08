<!-- CLAUDE.md -->

# CLAUDE.md

このリポジトリは `claude_orchestrator` によりタスク駆動で更新される。

## 絶対守ること

* `task.json` と `state.json` を唯一の実行根拠とする
* 指定された `context_files` のみを参照する
* 推測で不足情報を補わない
* `role` の責務を越えない
* 無関係なファイル変更を行わない
* 既存コードを破壊する変更を行わない
* 出力は必ず指定 schema の JSON のみとする

## 参照可能な判断基準

* `.claude_orchestrator/docs/completion_definition.md`
* `.claude_orchestrator/docs/feature_inventory.md`

## 編集禁止

以下は編集しないこと。

* `.claude_orchestrator/templates`
* `.claude_orchestrator/tasks`
* `.claude_orchestrator/skills`
* `.claude_orchestrator/schemas`
* `.claude_orchestrator/roles`
* `.claude_orchestrator/requirements`

## 実装方針

* MVP最小構成を優先する
* 小さく確実に完了する実装を行う
* 後から変更できる構造を維持する
* Python 仮想環境（`.venv`）前提で動作する構成を優先する
