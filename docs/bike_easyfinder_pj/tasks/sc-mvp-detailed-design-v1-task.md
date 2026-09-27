---
title: MVP詳細設計 v1 作成タスク
published: 2026-09-27
description: 承認済みMVP基本設計を実装可能なコンポーネント詳細へ分解する作業計画
tags: [mvp, detailed-design, task, sc]
category: tasks
draft: false
---

# MVP詳細設計 v1 作成タスク

## 前提

- 正本は承認済み `SystemDesign/mvp-basic-design-v1.md` とする。
- OpenAPI、DDL、実装、試験仕様は基本設計より下位とし、矛盾時は基本設計を優先する。
- O-01〜O-03は該当コンポーネントの実装着手前ゲート、O-04〜O-06は限定β開始前ゲートとする。

## 成果物とタスク

- [ ] DD-01 iOS状態・画面詳細: S01〜S08、状態遷移、ViewModel/UseCase/Repository境界、エラー・アクセシビリティ。
- [ ] DD-02 API詳細: OpenAPI v1.1.0、認証不要境界、validation、Problem Details、timeout/retry/idempotency。
- [ ] DD-03 データ詳細: ER図、PostGIS型、制約、索引、migration、削除台帳、fixture。
- [ ] DD-04 推薦詳細: 候補抽出、固定スコア式、多様性、`visited=-12`、決定論、warning code。
- [ ] DD-05 Apple Maps Provider詳細: token lifecycle、ETA batch、Directions、cache、quota、障害変換、POC結果。
- [ ] DD-06 WeatherKit・外部ナビ詳細: 注意判定、帰属、失敗表示、`MKMapItem`引き渡し。
- [ ] DD-07 Interaction/Privacy詳細: event queue、同意、重複排除、保持・削除、tombstone。
- [ ] DD-08 Worker/Review詳細: Source、canonical化、freshness、レビュー監査、taxonomy v1接続。
- [ ] DD-09 インフラ・運用詳細: ADR、環境差分、secret、CI/CD、監視、backup/restore、費用アラート。
- [ ] DD-10 テスト詳細: unit/contract/integration/UI/E2E/非機能、県別ケース、release gate。
- [ ] DD-11 横断レビュー: 要件・基本設計・OpenAPI・DDL・Privacyのトレーサビリティと不整合解消。

## 推奨順序

1. O-01、O-02と並行してDD-01、DD-03、DD-04の骨格を作る。
2. Provider POC確定後にDD-05を確定し、DD-02へエラー・警告契約を反映する。
3. DD-01〜DD-08確定後にDD-09、DD-10を固定する。
4. DD-11レビューを通過してからproduction向け実装を開始する。

## 完了条件

- 各DDに入力、出力、責務、正常系、異常系、永続化、監視、テスト観点がある。
- OpenAPIとDDLを機械検証でき、iOS/API/Worker間で型と状態が一致する。
- 各設計判断がBD-01〜BD-08およびRDへ追跡できる。
- 未確定事項に責任者、期限、実装を止めるゲートがある。
- SC、SD、QC、SO、DM、BUの該当責任者レビューを記録する。
