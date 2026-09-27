---
title: MVP基本設計書 v1 承認記録
published: 2026-09-27
description: バイク目的地提案アプリMVP基本設計書v1の承認結果と実装前ゲート
tags: [mvp, design, approval, handover]
category: Handover
draft: false
---

# MVP基本設計書 v1 承認記録

## 承認結果

- 結果: **承認済み**
- 承認日: 2026-09-27
- 承認者: プロダクトオーナー（本チャットのユーザー）
- 承認方法: チャットでの明示承認
- 承認対象版: v1
- 承認範囲: 本書の「承認依頼事項」6項目
- 条件: 「承認後の必須ゲート」は継続し、各ゲート未通過のままproductionへ進めない。

この承認は基本設計から詳細設計へ進む判断であり、具体インフラ契約、月額10,000円超過、Apple Maps Providerの本番採用を単独で承認するものではない。

## 承認対象

- `docs/bike_easyfinder_pj/SystemDesign/mvp-basic-design-v1.md`

## 概要

承認済みのMVP要件定義書v1を、iOS、FastAPI、PostgreSQL/PostGIS、データ収集、Apple Maps、WeatherKit、監視・バックアップへ実装できる基本設計に具体化した。

## 主な設計判断

1. 推薦用所要時間はApple Maps Server APIを第一候補とし、九州7県140経路以上のPOC合格を採用条件とする。
2. 二輪専用経路は保証せず、MVPは`Automobile` ETAとApple Mapsへのナビ委譲を使用する。
3. `visited`は同一Spotを-12点とし、永久除外しない。
4. 端末嗜好は集約して推薦APIへ渡し、サーバに永続化しない。OpenAPI v1.1.0への更新を実装前タスクとする。
5. WeatherKitは詳細画面の注意表示だけに使い、推薦順位・候補除外に使わない。
6. productionはPostGIS対応マネージドDBを採用し、具体ベンダーは月額10,000円以内の見積を伴うADRで確定する。

## 承認事項

- システム構成、コンポーネント責務、主要シーケンス。
- Apple Maps Provider方針とPOC合格基準。
- 推薦スコア、多様性、端末嗜好の受け渡し方式。
- WeatherKit注意閾値。
- 環境、監視、バックアップ、費用、リリース阻止条件。

## 承認後の必須ゲート

- OpenAPI v1.1.0更新。
- Provider POC合格。
- インフラADRと契約時見積の承認。
- taxonomy v1、県別リリースケース、Privacy最終文書の承認。

## 留意事項

- 基本設計の承認は、具体インフラ契約や月額上限超過を承認するものではない。
- Provider POC不合格時は、代替ProviderのADRを作成し、再承認する。
