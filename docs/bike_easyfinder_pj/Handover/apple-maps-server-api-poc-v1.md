---
title: Apple Maps Server API POC v1
published: 2026-09-27
description: Apple Mapsを移動時間Providerとして採用するための実行可能なPOCと判定記録
tags: [mvp, apple-maps, poc, provider]
category: Handover
draft: false
---

# Apple Maps Server API POC v1

## 現在の判定

**保留（実行基盤完成、実API実測待ち）**。2026-09-27時点でリポジトリとローカル環境にApple Maps資格情報がないため、140経路の実測合否は確定していない。未実測のまま採用合格とは扱わない。

## 実装したPOC

- `data_collection/scripts/apple_maps_poc.py`: 九州7県各20件、合計140件の入力検証、API呼出、匿名化した測定結果、合否集計。
- `data_collection/config/apple_maps_poc_routes.csv`: 140件の入力雛形。座標は試験生成値なので、実走行候補とApple Mapsアプリの表示時間へ置換・入力してから正式評価する。
- 高速利用可はETA、不可はDirectionsの `avoid=Highways` を使用する。ETA endpoint単体にはavoid指定がないため、実装でも両endpointを使い分ける。
- tokenや生レスポンスは保存しない。出力はroute ID、時間、距離、latency、status、誤差だけとする。

## 実行方法

詳細な準備、入力編集、実行、結果確認、終了処理は [Apple Maps Server API POC 実行手順書 v1](../Procedure/apple-maps-server-api-poc-execution-procedure-v1.md) を参照する。

Apple Developer AccountでMaps ID・秘密鍵を用意し、`server_api` scopeの認証JWTから `/v1/token` で短期access tokenを取得する。短期tokenを環境変数へ設定して次を実行する。

```powershell
cd data_collection
$env:APPLE_MAPS_ACCESS_TOKEN = "<short-lived access token>"
python scripts/apple_maps_poc.py --cases config/apple_maps_poc_routes.csv
```

入力だけの検証は資格情報なしで実行できる。

```powershell
python scripts/apple_maps_poc.py --cases config/apple_maps_poc_routes.csv --dry-run
```

## 合格判定

- 7県各20件以上、合計140件以上。
- API成功率99%以上。
- Apple Mapsアプリ表示時間との誤差が中央値15%以内、p95 30%以内。
- 高速不可ケースで有料高速利用0件。`hasTolls=false`だけでは高速不使用を証明できないため、経路形状を目視照合する。
- 往路・復路の非対称性を組にしたケースで確認する。
- 推薦相当の最大5候補について、API処理全体のp95が4秒以内。
- Privacy、利用規約、帰属、25,000 calls/day/teamの枠をレビューする。

自動集計のmanual 2項目は意図的にfalseのまま出力する。目視・規約レビュー後に本記録へ証跡を追記して最終判定する。

## 残作業

1. 入力雛形を都市部・山間部・海沿い・高速可否の実在経路へ置換する。
2. Apple Mapsアプリの同一出発時刻の表示秒数を入力する。
3. 実APIを実行し、失敗、誤差、latencyを集計する。
4. 高速不可28件と往復組を目視確認する。
5. 規約・Privacyレビューを記録し、PASSまたはFAILを確定する。

## 仕様根拠

- Apple Maps Server APIはJWT認証を使い、Server API用scopeは `server_api`。
- ETAは1回につき最大10目的地、交通手段はMVPで `Automobile`。
- Directionsは `avoid` を受け付ける。
- Apple Maps Server APIとMapKit JSの合算枠は1チーム1日25,000 service calls。

参照: [Apple Maps Server API](https://developer.apple.com/documentation/applemapsserverapi)、[ETA endpoint](https://developer.apple.com/documentation/applemapsserverapi/-v1-etas)、[Directions endpoint](https://developer.apple.com/documentation/applemapsserverapi/-v1-directions)、[token生成](https://developer.apple.com/documentation/applemapsserverapi/-v1-token)
