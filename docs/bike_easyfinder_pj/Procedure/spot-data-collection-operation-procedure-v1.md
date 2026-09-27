---
title: Spotデータ収集 運用実行手順書 v1
published: 2026-09-26
updated: 2026-09-26
description: 初期設定完了後に、Spotデータの収集・再開・出力を行うための運用手順
tags: [Procedure, data-collection, operation]
category: Procedure
draft: false
---

# Spotデータ収集 運用実行手順書 v1

## 目次

- [1. この手順書の対象](#1-この手順書の対象)
- [2. 実行前チェック](#2-実行前チェック)
- [3. データ収集](#3-データ収集)
  - [3.1 作業フォルダへ移動](#31-作業フォルダへ移動)
  - [3.2 データベースを起動](#32-データベースを起動)
  - [3.3 初回収集](#33-初回収集)
  - [3.4 2回目以降の収集](#34-2回目以降の収集)
  - [3.5 別の地域を収集](#35-別の地域を収集)
- [4. 実行結果の確認](#4-実行結果の確認)
- [5. 失敗・中断した処理の再開](#5-失敗中断した処理の再開)
- [6. 収集結果の出力](#6-収集結果の出力)
- [7. 終了](#7-終了)
- [8. 成功の判断](#8-成功の判断)

## 1. この手順書の対象

この手順書は、初期設定が完了した環境で、運用担当者がSpotデータを収集するための手順だけを記載する。

現在の標準運用では、次の2つを使用する。

- `osm_overpass`: OpenStreetMapからSpot候補を取得する。
- `openai_web_discovery`: OpenAIでWeb上のSpot候補ページを探し、参照URLを保存する。

設定が未完了のため、標準コマンドには次のSourceを含めない。

- `public_open_data`: データセットがまだ登録されていない。
- `manual_seed`: 現在のファイルはサンプルデータである。
- `osm_pbf`: 収集処理が未実装である。

## 2. 実行前チェック

次を確認する。

- Docker Desktopが起動している。
- インターネットへ接続できる。
- `.env` にOpenAI APIキーが設定されている。
- `data_collection/config/sources.yaml` のOSM連絡先が設定されている。
- 初回セットアップでDBマイグレーションと行政区域データ同期が完了している。

## 3. データ収集

### 3.1 作業フォルダへ移動

PowerShellを開き、次を実行する。

```powershell
Set-Location 'C:\Users\nakam\iCloudDrive\software_creation\bike_PJ\bike_easyfinder_pj'
```

### 3.2 データベースを起動

```powershell
docker compose up -d db
docker compose ps
```

`db` の状態が `Up` または `running` になっていることを確認する。

### 3.3 初回収集

福岡市を初めて収集する場合は、次を実行する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources osm_overpass,openai_web_discovery `
  --mode initial `
  --limit 100
```

処理終了時に表示される `run_id` を控える。

### 3.4 2回目以降の収集

同じ地域の情報を更新する場合は、`refresh` を指定する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources osm_overpass,openai_web_discovery `
  --mode refresh `
  --limit 100
```

### 3.5 別の地域を収集

市区町村を変更する場合は、`40130` を対象の5桁行政区域コードへ置き換える。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code <5桁行政区域コード> `
  --sources osm_overpass,openai_web_discovery `
  --mode initial `
  --limit 100
```

都道府県単位で実行する場合は、2桁の都道府県コードを指定する。ただし、公開Overpassへの大規模な収集は避け、OpenAIによる候補発見だけを実行する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --prefecture-code <2桁都道府県コード> `
  --sources openai_web_discovery `
  --mode initial `
  --limit 100
```

## 4. 実行結果の確認

収集時に表示された `run_id` を指定する。

```powershell
docker compose run --rm worker `
  python -m collection_worker runs show <run_id>
```

主な状態は次のとおり。

- `completed`: 完了。結果を出力できる。
- `partial`: 一部失敗。成功分は保存されており、再開できる。
- `failed`: 失敗。原因を確認して再開する。
- `running`: 実行中。

## 5. 失敗・中断した処理の再開

`partial`、`failed`、`cancelled` の処理は、同じ `run_id` で再開する。

```powershell
docker compose run --rm worker `
  python -m collection_worker runs resume <run_id>
```

再開後、4章のコマンドで状態をもう一度確認する。

## 6. 収集結果の出力

確認しやすいCSV形式で出力する。

```powershell
docker compose run --rm worker `
  python -m collection_worker export `
  --run-id <run_id> `
  --format csv `
  --status ready,review_required
```

出力先は次のフォルダである。

```text
data_collection/output/<run_id>/
```

主に次のファイルを確認する。

- `candidates.csv`: 収集したSpot候補。
- `observations.csv`: 候補の属性と参照元。
- `attributions.csv`: ライセンスと出典表示。
- `reviews.csv`: 人による確認が必要な項目。

## 7. 終了

収集と出力が終わったら、DBを停止する。

```powershell
docker compose down
```

通常運用では `docker compose down --volumes` を実行しない。`--volumes` を付けると、収集済みDBが削除される。

## 8. 成功の判断

次をすべて満たせば完了とする。

- Runの状態が `completed` または、失敗内容を把握したうえでの `partial` である。
- `data_collection/output/<run_id>/` にCSVファイルが生成されている。
- `candidates.csv` にSpot候補が含まれている。
- `observations.csv` に参照元URLが含まれている。
- `reviews.csv` の内容を確認できる。
