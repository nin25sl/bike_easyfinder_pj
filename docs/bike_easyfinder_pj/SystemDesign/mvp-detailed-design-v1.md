---
title: Bike EasyFinder MVP 詳細設計 v1
published: 2026-10-04
tags: [mvp, detailed-design, api, ios, data]
category: SystemDesign
draft: false
---

# Bike EasyFinder MVP 詳細設計 v1

## 1. 決定事項

- 限定βの公開範囲は九州7県（福岡、佐賀、長崎、熊本、大分、宮崎、鹿児島）。
- iOS 17以上、SwiftUI、既存MVPデザイン案のS01〜S08を採用する。
- 公開APIはOpenAPI 1.1の3本とし、`/v1/recommendations`、`/v1/interactions`、`/v1/installations/{id}/data` を提供する。
- 収集データと公開データを分離する。`spot_candidates` は証跡付き候補、`spots` は公開Canonicalである。
- localでは決定的な概算経路Providerを許可する。staging/productionでは起動時検証により禁止し、Apple Maps実Providerを必須とする。
- WeatherKitはSpot詳細の注意表示だけに使い、順位や候補除外には使わない。
- 匿名分析は明示同意後だけ有効にし、正確な現在地、走行軌跡、検索文字列をイベントへ含めない。

## 2. DD-01 API境界

契約は [mvp-openapi-v1.yaml](./mvp-openapi-v1.yaml) を正とする。全応答へ`X-Request-ID`を付与し、エラーは`application/problem+json`で返す。推薦は30回/10分/IP、イベントは60回/10分/IP、削除は5回/日/IPをアプリ内制限とし、stagingでは同じ制限をedgeにも設定する。

推薦は最大4秒、iOSは5秒で打ち切る。iOSの再試行対象はネットワーク障害、429、503、504だけで、1回に限定する。

## 3. DD-02 Canonicalデータ

Alembicがtaxonomy、Canonical、経路キャッシュ、分析、削除台帳を管理する。公開条件は`publication_status=published`、閉業でないこと、Spot基本情報が180日以内であること。`canonical_key`は収集元のstable identityで一意にし、重複行は削除せず`retired`で保持する。

昇格処理はlicenseがverifiedの最新・高信頼観測値を優先する。必須の名称または座標が欠ける場合は`data_review_tasks`へblocking taskを作る。

## 4. DD-03 推薦

処理順は次のとおり。

1. `min(250km, available_minutes × 1.5km)`でPostGIS近傍検索。
2. 公開状態、閉業、freshnessをhard filter。
3. 選択興味に一致する近傍上位10件へ経路照会。
4. `往路 + 滞在 + 復路 + 15分`が利用可能時間内の候補だけ残す。
5. 興味0〜40、時間適合0〜25、嗜好-30〜15、信頼度0〜10、編集人気0〜10で採点。
6. score降順、総時間昇順、Spot ID昇順。同一主カテゴリが連続し、5点以内の別カテゴリがあれば繰り上げる。
7. 最大5件を固定テンプレートの理由とともに返す。

全経路失敗は503、一部失敗は200と`PARTIAL_ROUTE_FAILURE`、候補0件は200と空配列。

## 5. DD-04 経路Provider

Provider境界は`RouteProvider`とし、local用`ApproximateRouteProvider`、実API用`AppleMapsRouteProvider`を実装する。Apple Mapsは`Automobile`、高速不可では`avoid=Highways`を使用し、復路は往路到着時刻と滞在時間を足した出発時刻で再計算する。

キャッシュキーは約1km origin mesh、Spot ID、往復、highway条件、滞在時間、15分bucket、Provider版から作る。TTLは15分で、正確な現在地をログやキー文字列へ保存しない。

実Provider採用には既存の140経路POCを全条件で通す必要がある。未実測のままstaging/productionへ進めない。

## 6. DD-05 iOS

`APIRecommendationService`がOpenAPI DTOを画面モデルへ変換する。API base URLは`BIKE_API_BASE_URL` build settingで環境ごとに切り替える。local HTTPはlocal networkingだけ許可し、β環境はHTTPSを必須とする。

Spot詳細はWeatherKitで目的地の次時間帯を取得する。降水確率50%以上、風速10m/s以上、5℃未満、35℃超で警告する。失敗時も推薦導線は継続する。

Apple Mapsには目的地名と座標だけを`MKMapItem`で渡す。OSが起動要求を受理したときだけ`route_started`を記録し、失敗時は座標コピーを提示する。

## 7. DD-06 匿名分析と削除

同意時に端末で128bit以上のinstallation IDと256bit削除トークンを生成し、Keychainへ保存する。初回イベントではトークンのSHA-256だけを登録し、生トークンは削除要求でのみ送る。

イベントbatchは最大50件、端末queueは最大7日。サーバーraw eventは90日、日次KPIは13か月。KPIはinstallation 5件以上の集約だけ保存する。削除APIは対象の存在やtoken一致を推測できないよう常に202を返し、maintenance jobが7日以内にイベントとinstallationを削除する。35日間のtombstoneでbackup復元後の再流入を抑止する。

## 8. DD-07 運用

`privacy-maintenance`を日次実行する。`audit-kyushu`を収集・昇格後とrelease前に実行し、7県のいずれかが閾値未満なら失敗終了する。API healthは`/healthz`、ログはrequest ID、path、status、durationだけを基本とし、座標やtokenを記録しない。

## 9. Release blocker

- Apple Maps 140経路POCの全gate合格。
- Mac/Xcodeでunit/UI test、WeatherKit entitlement、実機Apple Maps引き渡しを確認。
- staging/production事業者ADRの承認、HTTPS、secret manager、日次backup、月次restore、監視、費用alertの構築。
- 九州7県Canonical監査と目視レビュー。
- TestFlight限定βで0件、権限拒否、部分/全障害、削除要求をE2E確認。

