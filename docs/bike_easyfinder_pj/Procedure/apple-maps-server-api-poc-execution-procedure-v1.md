---
title: Apple Maps Server API POC 実行手順書 v1
published: 2026-09-27
description: Apple Maps Server APIを移動時間Providerとして評価するための準備、実行、結果確認手順
tags: [mvp, apple-maps, poc, procedure]
category: Procedure
draft: false
---

# Apple Maps Server API POC 実行手順書 v1

## 1. 目的

`data_collection/scripts/apple_maps_poc.py` を使用し、Apple Maps Server APIの成功率、所要時間誤差、応答時間、高速道路回避を評価する。本手順だけで自動合格とはせず、経路の目視確認と規約・Privacyレビューを合わせて最終判定する。

## 2. 前提条件

- Apple Developer Programを利用できること。
- Apple Developer AccountでMaps ID、Maps対応秘密鍵、Key ID、Team IDを用意していること。
- Maps認証JWTをES256で署名し、scopeに `server_api` を指定していること。
- Python仮想環境 `.venv` の依存関係を導入済みであること。
- PowerShellでリポジトリルートを開いていること。

秘密鍵、認証JWT、access tokenはGit管理対象へ保存しない。コマンド履歴、画面共有、CIログにも出力しない。

## 3. Apple Maps access tokenの準備

Apple公式手順に従い、Maps IDと秘密鍵からMaps認証JWTを作成する。その認証JWTをApple Maps Server APIの `/v1/token` に渡し、短期access tokenを取得する。

- [Maps Server APIのトークン作成](https://developer.apple.com/documentation/applemapsserverapi/creating-and-using-tokens-with-maps-server-api)
- [Generate a Maps token](https://developer.apple.com/documentation/applemapsserverapi/-v1-token)

取得したレスポンスの `accessToken` を、現在のPowerShellセッションだけに設定する。

```powershell
$env:APPLE_MAPS_ACCESS_TOKEN = "<取得したaccessToken>"
```

値を画面やログへ出さないため、`echo` や `Write-Output` でトークンを確認しない。

## 4. POC入力データの準備

入力ファイルは次を使用する。

```text
data_collection/config/apple_maps_poc_routes.csv
```

初期ファイルは7県各20件、合計140件の構造確認用雛形であり、正式評価前に実在経路へ置き換える。各県について都市部、山間部、海沿い、高速利用可、高速利用不可、往路・復路を含める。

| 列 | 内容 |
|---|---|
| `route_id` | 一意な試験ID |
| `prefecture` | `fukuoka`、`saga`、`nagasaki`、`kumamoto`、`oita`、`miyazaki`、`kagoshima` |
| `scenario` | `urban`、`mountain`、`coastal`、`highway_allowed`、`highway_avoided` |
| `origin_lat` / `origin_lng` | 出発地点の緯度・経度 |
| `destination_lat` / `destination_lng` | 目的地点の緯度・経度 |
| `highway_allowed` | 高速利用可は `true`、不可は `false` |
| `apple_maps_seconds` | 同条件・同出発時刻でApple Mapsアプリに表示された所要時間（秒） |

`apple_maps_seconds` が空欄の場合、API成功率と応答時間は測定できるが、所要時間の誤差判定は完了しない。

## 5. 入力ファイルの検証

リポジトリルートで次を実行する。

```powershell
cd C:\Users\nakam\iCloudDrive\software_creation\bike_PJ\bike_easyfinder_pj

.\.venv\Scripts\python.exe `
  data_collection\scripts\apple_maps_poc.py `
  --cases data_collection\config\apple_maps_poc_routes.csv `
  --dry-run
```

正常時は次のように表示される。

```json
{"case_count": 140, "valid": true}
```

## 6. 実APIによるPOC実行

```powershell
.\.venv\Scripts\python.exe `
  data_collection\scripts\apple_maps_poc.py `
  --cases data_collection\config\apple_maps_poc_routes.csv `
  --output data_collection\output\apple_maps_poc_results.jsonl `
  --summary data_collection\output\apple_maps_poc_summary.json
```

出力は次の2ファイルである。

- `data_collection/output/apple_maps_poc_results.jsonl`: 経路ごとのstatus、時間、距離、latency、比較誤差。
- `data_collection/output/apple_maps_poc_summary.json`: 県別件数、成功率、誤差、p95 latency、自動ゲート結果。

`data_collection/output/` は `.gitignore` の対象であり、測定結果を通常のGit管理へ含めない。

## 7. 終了コード

| 終了コード | 意味 | 対応 |
|---:|---|---|
| `0` | 全自動・手動ゲートがPASS | 判定記録へ証跡を追記する |
| `1` | POCが保留または不合格 | summaryのfalse項目と個別結果を確認する |
| `2` | access token未設定 | `APPLE_MAPS_ACCESS_TOKEN` を設定して再実行する |

現在は目視・規約レビュー用ゲートを意図的に自動PASSにしないため、API呼び出しが成功しても終了コード1となる。CIの単純な失敗とは区別して扱う。

## 8. 合格基準と結果確認

- 九州7県各20件以上、合計140件以上。
- API成功率99%以上。
- Apple Mapsアプリ表示時間との誤差が中央値15%以内、p95 30%以内。
- 高速不可ケースで有料高速利用0件。
- 往路・復路の非対称性を取得できる。
- 最大5候補のAPI処理全体がp95で4秒以内。
- Privacy、利用規約、帰属、1チーム1日25,000 service callsの枠と整合する。

`hasTolls=false` は高速道路不使用の証明にはならない。高速不可ケースはApple Mapsアプリの経路表示と照合し、実際に高速道路を通っていないことを目視確認する。

最終結果と証跡は次へ追記する。

```text
docs/bike_easyfinder_pj/Handover/apple-maps-server-api-poc-v1.md
```

## 9. 終了処理

実行後はPowerShellセッションからaccess tokenを削除する。

```powershell
Remove-Item Env:APPLE_MAPS_ACCESS_TOKEN
```

次も確認する。

- `.env`、CSV、JSONL、summary、ログへtokenや秘密鍵を記録していない。
- 個別失敗を候補0件として扱わず、HTTP statusとerror種別を確認した。
- Apple Mapsアプリとの比較日時、端末、出発条件を判定記録へ残した。

## 10. 参考資料

- [Apple Maps Server API](https://developer.apple.com/documentation/applemapsserverapi)
- [ETA endpoint](https://developer.apple.com/documentation/applemapsserverapi/-v1-etas)
- [Directions endpoint](https://developer.apple.com/documentation/applemapsserverapi/-v1-directions)
- [POC判定記録](../Handover/apple-maps-server-api-poc-v1.md)
- [MVP基本設計書](../SystemDesign/mvp-basic-design-v1.md)
