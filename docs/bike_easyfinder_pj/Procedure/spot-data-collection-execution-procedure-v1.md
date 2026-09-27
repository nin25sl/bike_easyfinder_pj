---
title: Spotデータ収集機構 実行手順書 v1
published: 2026-09-23
updated: 2026-09-26
description: Spotデータ収集機構をローカル環境で起動し、地域同期、収集、再開、出力を行う手順
tags: [Procedure, data-collection, docker, postgis, openai]
category: Procedure
draft: false
---

# Spotデータ収集機構 実行手順書 v1

## 目次

- [1. 目的と対象](#1-目的と対象)
- [2. ユーザーが準備するもの](#2-ユーザーが準備するもの)
  - [2.1 必須の実行環境](#21-必須の実行環境)
  - [2.2 実行前に決める項目](#22-実行前に決める項目)
  - [2.3 ローカル環境変数ファイル](#23-ローカル環境変数ファイル)
  - [2.4 Sourceごとの準備](#24-sourceごとの準備)
    - [2.4.1 共通設定](#241-共通設定)
    - [2.4.2 N03行政区域](#242-n03行政区域)
    - [2.4.3 OSM Overpass](#243-osm-overpass)
    - [2.4.4 公的オープンデータ](#244-公的オープンデータ)
    - [2.4.5 Manual Seed](#245-manual-seed)
    - [2.4.6 OpenAI候補発見・属性抽出](#246-openai候補発見属性抽出)
    - [2.4.7 OSM PBF](#247-osm-pbf)
    - [2.4.8 設定反映と検証](#248-設定反映と検証)
  - [2.5 ネットワークと利用条件](#25-ネットワークと利用条件)
  - [2.6 CodexでSpot候補を収集する](#26-codexでspot候補を収集する)
- [3. OpenAI APIキー（任意）](#3-openai-apiキー任意)
- [4. 初回セットアップ](#4-初回セットアップ)
  - [4.1 buildとDB起動](#41-buildとdb起動)
  - [4.2 migrationとSource台帳同期](#42-migrationとsource台帳同期)
  - [4.3 N03行政区域同期](#43-n03行政区域同期)
  - [4.4 初回実行前チェック](#44-初回実行前チェック)
- [5. 福岡市の初回収集](#5-福岡市の初回収集)
  - [5.1 dry-run](#51-dry-run)
  - [5.2 最小構成で実収集する](#52-最小構成で実収集する)
  - [5.3 OpenAIを含む実収集](#53-openaiを含む実収集)
- [6. 別地域と都道府県の収集](#6-別地域と都道府県の収集)
- [7. Source設定とManual Seed](#7-source設定とmanual-seed)
- [8. 月次更新と再開](#8-月次更新と再開)
- [9. 結果出力](#9-結果出力)
- [10. レビュー](#10-レビュー)
- [11. 停止](#11-停止)
- [12. トラブルシューティング](#12-トラブルシューティング)
  - [12.1 5432番ポート競合](#121-5432番ポート競合)
  - [12.2 OpenAI認証・利用上限](#122-openai認証利用上限)
  - [12.3 Overpassの429・timeout](#123-overpassの429timeout)
  - [12.4 Runが再開できない](#124-runが再開できない)
- [13. 実装時の検証記録](#13-実装時の検証記録)

## 1. 目的と対象

ローカルPC上でPostgreSQL/PostGISと収集Workerを起動し、全国の都道府県・市区町村・政令指定都市・行政区を指定してSpot候補を収集する手順を示す。収集結果の再開、確認、JSONL/CSV出力も対象とする。

実装は次にある。

- `compose.yaml`
- `data_collection/`
- [Spotデータ収集機構 基本設計書 v1](../SystemDesign/spot-data-collection-basic-design-v1.md)

現版の `osm_pbf` は全国規模収集用の交換境界までで、PBF抽出本体は未実装である。公開Overpassは市区町村単位の小規模検証だけに使用する。

## 2. ユーザーが準備するもの

### 2.1 必須の実行環境

- Windows 11、PowerShell、Git
- 起動済みのDocker DesktopとDocker Compose v2以降
- インターネット接続
- Codexで候補を調査する場合はCodex CLIとChatGPTログイン
- OpenAI候補発見・属性抽出を使う場合のみOpenAI APIキー

ホストOSへPythonやPostgreSQLを直接インストールする必要はない。

Docker Desktopには、コンテナイメージ、PostGISデータ、N03行政区域、Rawデータを保存できる空き容量を確保する。必要量は収集地域とRaw保存量で変わるため、実行中はDockerのディスク使用量を確認する。

### 2.2 実行前に決める項目

ユーザーは収集開始前に次を決める。

- 対象地域の行政区域コード。都道府県は2桁、市区町村・行政区・政令指定都市は5桁を使う。
- 初回に使うSource。まずは `osm_overpass` と承認済みManual Seedによる少量実行を推奨する。
- 候補発見にCodexを使うか、Worker内蔵のOpenAI API連携を使うか。Codexを使う場合、Worker実行時の `openai_web_discovery` は不要である。
- 取得本文を保存できるか、出典表示は何か、商用利用可能かなど、各Sourceの利用条件。
- 出力をCanonical工程へ渡すか、人手レビューするか。前者はJSONL、後者はCSVを使う。

行政区域コードは総務省の全国地方公共団体コードまたはN03の `N03_007` と照合する。政令指定都市全体の親コードはN03の行政区からWorkerが生成するため、最初にdry-runで地域名を確認する。

### 2.3 ローカル環境変数ファイル

リポジトリルートへ移動する。

```powershell
Set-Location 'C:\Users\nakam\iCloudDrive\software_creation\bike_PJ\bike_easyfinder_pj'
```

Dockerを確認する。

```powershell
docker --version
docker compose version
docker info
```

環境変数サンプルを `.env` へコピーする。`.env` はGit管理対象外である。

```powershell
Copy-Item .env.example .env
notepad .env
```

共有PC、LAN公開、クラウド環境では、`.env` の `POSTGRES_PASSWORD` を初期値から十分に強い値へ変更する。ローカルPCだけで利用する場合も、DBを外部へ公開しない。

別のPostgreSQLが5432番を使用している場合は、Git管理対象外の `.env` に次を設定する。

```dotenv
POSTGRES_PORT=55432
```

`OPENAI_API_KEY` は原則として `.env` へ保存せず、3章の方法で現在のPowerShellセッションだけに設定する。

### 2.4 Sourceごとの準備

編集対象はリポジトリルートから見た `data_collection/config/sources.yaml` である。YAMLはインデントに意味があるため、タブではなく半角スペースを使用する。編集前後は `git diff -- data_collection/config/sources.yaml` で意図しない変更がないことを確認する。

#### 2.4.1 共通設定

各Sourceは `sources:` の直下にSourceキーを持つ。収集時の `--sources` にはこのキーを指定する。たとえば `osm_overpass` を実行する場合は `--sources osm_overpass` とする。

主な共通項目は次の意味である。

- `source_type`: 使用するアダプター。実装済みの値を変更せず、新しいSourceキーを追加するときも目的に合う型を指定する。
- `approval_status`: `approved` のSourceだけが自動収集できる。利用条件の確認前は `pending_review` とし、確認後に人が `approved` へ変更する。
- `license_status`: `verified`、`restricted`、`unknown`、`prohibited` のいずれか。`unknown` や `restricted` の観測値を含む候補はレビュー対象になる。
- `license_name`: ライセンスまたは利用規約の名称。
- `terms_url`: ライセンス・利用規約を確認できるURL。
- `attribution_text`: 出力データへ継承する出典表示。提供元指定の文言を記載する。
- `raw_storage_policy`: `full_allowed` はRaw本文を圧縮保存する。`facts_only` と `metadata_only` は本文を保存せず、構造化した事実やメタデータだけを保持する。`prohibited` は保存禁止Sourceに使用する。
- `rate_limit_per_minute`: 1分当たりの許容リクエスト数。配布元の条件より大きくしない。
- `request_timeout_seconds`: 1リクエストのタイムアウト秒数。
- `max_pages_per_run`: 1 Runで処理するページまたはデータセット数の上限。
- `refresh_interval_days`: 再確認周期。現版では運用判断用の設定であり、CLIの自動スケジュールは行わない。

利用条件が異なるデータを同じSourceキーへ混在させない。たとえば福岡市と別自治体でライセンスが異なる場合は、`fukuoka_open_data`、`other_city_open_data` のように別キーで定義する。

#### 2.4.2 N03行政区域

`sources.n03` の次の3項目を、実際に利用する国土数値情報N03の版へ揃える。

```yaml
sources:
  n03:
    base_url: "https://nlftp.mlit.go.jp/.../N03-YYYYMMDD_GML.zip"
    config:
      dataset_version: N03-YYYYMMDD
      valid_from: YYYY-MM-DD
```

編集手順:

1. 国土数値情報の行政区域データ配布ページで使用する版とURLを確認する。
2. `base_url` をZIPの直接取得URLへ変更する。
3. `dataset_version` を他の版と区別できる値へ変更する。推奨形式は `N03-YYYYMMDD` である。
4. `valid_from` をその行政区域が有効な基準日へ変更する。
5. `license_name`、`terms_url`、`attribution_text` が配布元の現在の条件と一致することを確認する。

`python -m collection_worker regions sync --dataset-version latest` の `latest` は、Web上の最新版を検索する意味ではない。`sources.yaml` に記載した `dataset_version` を使う。手元のZIPを `--input` で指定する場合も、`--dataset-version` へ実際の版を明示する。

#### 2.4.3 OSM Overpass

`sources.osm_overpass.config.user_agent` のプレースホルダーを、運用担当者へ連絡できる値に変更する。

変更前:

```yaml
config:
  user_agent: BikeEasyFinder/0.1 (data collection; contact required before production)
```

変更例:

```yaml
config:
  user_agent: "BikeEasyFinder/0.1 (spot collection; contact: mailto:data-owner@example.jp)"
  cache_ttl_seconds: 86400
```

`data-owner@example.jp` は実際に受信できる管理者アドレスへ置換する。メールアドレスを公開したくない場合は、連絡フォームのURLを記載する。

公開Overpassでは次を守る。

- `rate_limit_per_minute` を既定値の1より安易に増やさない。
- `cache_ttl_seconds: 86400` は同じクエリ結果を24時間再利用する設定である。緊急性がない限り短くしない。
- 市区町村単位の小規模収集に限定し、都道府県全体や全国の反復収集に使用しない。
- エンドポイントを変更するときは、運営者の利用条件と容量方針を確認する。

#### 2.4.4 公的オープンデータ

既定の `sources.public_open_data.config.datasets` は空なので、そのまま実行しても0件である。利用するCSV、JSON、GeoJSONを追加する。

まず配布データの次を確認する。

1. ファイルへ直接アクセスできるURL
2. 形式が `csv`、`json`、`geojson` のいずれか
3. 1レコードを一意に識別する安定したID列
4. 名称、住所、緯度、経度、地域コードなどの列名
5. ライセンス、利用規約、必要な出典表示、本文保存可否

ここでいう「直接アクセスできるURL」とは、ブラウザやWorkerがURLを開いたときに、データカタログの説明画面ではなくCSV・JSON・GeoJSON本体が返るURLである。ユーザー自身がCSVを新たにインターネット公開する必要はない。自治体や公的機関が提供するダウンロードURLまたはAPI URLをそのまま利用できる。

現在の `public_open_data` で利用できるURLの条件:

- `http://` または `https://` で、Dockerコンテナから認証なしに取得できる。
- インターネット上で名前解決できる公開ホストである。`localhost`、PC内のパス、LAN内IPは安全対策により拒否される。
- ログイン、Cookie、ブラウザ上のボタン操作、JavaScript実行を必要としない。
- 別ドメインへリダイレクトされる場合は拒否されるため、可能ならリダイレクト後の正式な直接URLを設定する。
- 取得サイズが `collection.max_response_bytes` 以下である。既定値は10 MiBである。
- CSVはUTF-8またはUTF-8 BOM付きである。Shift_JISの場合はUTF-8へ変換してからローカルファイル経路を使う。

準備は次の順序で行う。

1. 自治体などのオープンデータカタログで、目的に合うデータセットを探す。
2. 「CSV」「JSON」「GeoJSON」「API」などのダウンロードリンクを1回手動取得し、ファイル本体であることを確認する。
3. ファイルをExcelではなくテキストエディタでも開き、ヘッダー行またはJSONキーを確認する。
4. ID、名称、住所、緯度、経度、自治体コードに対応する列名をメモする。
5. 利用規約ページのURL、ライセンス名、指定された出典文をメモする。
6. データ本体の直接URLが継続利用できるなら `public_open_data`、手動ダウンロードしかできないなら後述のローカルファイル経路を選ぶ。

直接URLをPowerShellで確認する例:

```powershell
$downloadUrl = 'https://data.example.jp/spots.csv'
$testFile = Join-Path $env:TEMP 'spots-source-test.csv'
Invoke-WebRequest -Uri $downloadUrl -OutFile $testFile
Get-Item $testFile | Select-Object FullName, Length
Get-Content -Encoding UTF8 $testFile -TotalCount 3
```

先頭にHTMLの `<!DOCTYPE html>` やログイン画面が表示される場合、そのURLはデータ本体ではない。カタログ画面内のダウンロードリンク、リソースURL、API URLを探す。

直接URLがない場合は、次のどちらかを選ぶ。

- 配布元が提供するAPIや固定ダウンロードURLを探す。これが推奨経路である。
- ファイルを手動でダウンロードし、Worker用の列名へ整形して `manual_seed` として読み込む。

ローカルCSVは `data_collection/seeds/` 配下へ保存する。元ファイルの列名をそのまま変換する機能はManual Seedにはないため、次のようなWorker用列名へ事前変換する。

```csv
source_record_id,source_url,region_code,name,address,latitude,longitude,source_categories,features
facility-001,https://www.example.jp/spots/001,40130,地点名,福岡県福岡市...,33.5900,130.4000,official-tourism,駐車場
```

たとえば `data_collection/seeds/fukuoka_downloaded_spots.csv` として保存し、`sources.yaml` に次のSourceを追加する。

```yaml
sources:
  fukuoka_downloaded_spots:
    source_type: manual_seed
    approval_status: approved
    license_status: verified
    license_name: "実際のライセンス名"
    terms_url: "https://data.example.jp/terms"
    attribution_text: "配布元が指定した出典表示"
    raw_storage_policy: facts_only
    base_url: null
    rate_limit_per_minute: 1
    request_timeout_seconds: 60
    max_pages_per_run: 10
    refresh_interval_days: 30
    config:
      paths:
        - /app/seeds/fukuoka_downloaded_spots.csv
      ai_extract: false
```

この場合は次のように実行する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources fukuoka_downloaded_spots `
  --mode initial `
  --limit 10 `
  --dry-run
```

注意点として、ローカルファイルへコピーしただけでは利用条件は変わらない。元データのライセンス、出典表示、再配布可否、加工時の表示条件を確認し、Source設定へ記録する。

CSVの設定例:

```yaml
sources:
  fukuoka_city_open_data:
    source_type: public_open_data
    approval_status: approved
    license_status: verified
    license_name: "実際のライセンス名"
    terms_url: "https://data.example.jp/terms"
    attribution_text: "福岡市○○データを加工して作成"
    raw_storage_policy: facts_only
    base_url: null
    rate_limit_per_minute: 6
    request_timeout_seconds: 60
    max_pages_per_run: 10
    refresh_interval_days: 30
    config:
      ai_extract: false
      datasets:
        - url: "https://data.example.jp/spots.csv"
          format: csv
          id_field: facility_id
          user_agent: "BikeEasyFinder/0.1 (contact: mailto:data-owner@example.jp)"
          mapping:
            name: facility_name
            address: full_address
            latitude: lat
            longitude: lon
            region_code: local_government_code
            official_url: detail_url
            opening_hours_text: opening_hours
```

`mapping` は左側がWorker側の固定フィールド名、右側が配布データ側の列名である。逆に書かない。

`id_field` には施設コードなど、再ダウンロードしても同じ地点で変わらない列を指定する。ID列がない場合、WorkerはURL・行位置・レコード内容から代替IDを生成するが、配布元で行順や内容が変わると別レコードになる可能性がある。可能なら前処理で安定した `source_record_id` 列を追加する。

使用できる主なWorker側フィールド名:

- `source_record_id`: 原典側の永続ID。通常は `id_field` を使えばよい。
- `source_url`: レコード固有の詳細ページURL。なければデータセットURLが使用される。
- `region_code`: レコードの行政区域コード。指定すると収集対象コードとの完全一致で絞り込まれる。
- `name`、`address`、`latitude`、`longitude`
- `source_categories`、`features`
- `opening_hours_text`、`business_status`
- `parking`、`motorcycle_access`、`road_access`
- `suggested_stay_minutes`、`official_url`

値の規約:

- `business_status`: `open`、`temporarily_closed`、`permanently_closed`、`unknown`
- `parking`: `available`、`unavailable`、`unknown`
- `motorcycle_access`: `allowed`、`not_allowed`、`unknown`
- `road_access`: `accessible`、`restricted`、`unknown`
- `latitude` と `longitude`: WGS84の10進度
- `source_categories` と `features`: CSVではカンマ区切り文字列、JSONでは文字列配列を使用できる

JSONはトップレベルの配列、または `results`、`items`、`data` 配下の配列に対応する。GeoJSONは `FeatureCollection` に対応し、Point geometryの経度・緯度は自動取得される。

利用条件の確認が終わるまでは、次のように自動収集を止める。

```yaml
approval_status: pending_review
license_status: unknown
```

確認後に `approval_status: approved` とし、正しい `license_status`、`license_name`、`terms_url`、`attribution_text` を設定する。

#### 2.4.5 Manual Seed

編集対象は `data_collection/seeds/manual_spots.jsonl` である。1行に1件のJSONを記載し、ファイル全体をJSON配列にはしない。

既存のサンプル行:

```json
{"source_record_id":"sample-fukuoka-001","source_url":"https://example.invalid/replace-with-approved-source","region_code":"40130","name":"サンプル候補（承認済みSourceへ置換）","address":"福岡県福岡市","latitude":null,"longitude":null,"source_categories":["manual-seed"],"features":[]}
```

この行は動作説明用であり、`example.invalid` のまま収集に使わない。行を削除するか、実在する承認済み公式Sourceへ置き換える。

入力例:

```json
{"source_record_id":"fukuoka-official-001","source_url":"https://www.example.jp/spots/001","region_code":"40130","name":"地点名","address":"福岡県福岡市...","latitude":33.5900,"longitude":130.4000,"source_categories":["official-tourism"],"features":["駐車場"],"official_url":"https://www.example.jp/spots/001"}
```

必須項目:

- `source_record_id`: 同じ原典内で変わらない一意ID
- `source_url`: 事実を確認できる原典URL

強く推奨する項目:

- `region_code`: 対象地域の2桁または5桁コード。省略すると別地域の収集にも同じ行が投入されるため、原則として必ず指定する。
- `name`
- `address`、または `latitude` と `longitude`

Manual Seedのライセンス状態はJSONL各行の `license_status` ではなく、`sources.yaml` のSource定義から継承される。公式データと利用条件不明データを同じ `manual_seed` に混在させない。公式Source用に分ける場合の例:

```yaml
sources:
  fukuoka_official_seed:
    source_type: manual_seed
    approval_status: approved
    license_status: verified
    license_name: "福岡市Webサイト利用規約"
    terms_url: "https://www.example.jp/terms"
    attribution_text: "福岡市公式情報を基に作成"
    raw_storage_policy: facts_only
    base_url: null
    rate_limit_per_minute: 6
    request_timeout_seconds: 60
    max_pages_per_run: 100
    refresh_interval_days: 30
    config:
      paths:
        - /app/seeds/fukuoka_official_spots.jsonl
      ai_extract: false
```

この場合は `data_collection/seeds/fukuoka_official_spots.jsonl` を作成し、実行時に `--sources fukuoka_official_seed` と指定する。`/app/seeds/` はコンテナ内パスであり、ホスト側の `data_collection/seeds/` に対応する。

#### 2.4.6 OpenAI候補発見・属性抽出

モデルと予算表示値は、同じファイル上部の `openai:` を編集する。

```yaml
openai:
  discovery_model: gpt-6-astra
  extraction_model: gpt-6-luna
  store: false
  request_timeout_seconds: 120
  max_retries: 3
  run_budget_jpy: 500
  monthly_budget_jpy: 3000
  prompt_version: spot-collection-v1
```

- `discovery_model`: Web検索による候補URL発見に使うモデル。
- `extraction_model`: Structured Outputsによる属性抽出に使うモデル。
- `store`: 必ず `false` のままにする。`true` は設定検証で拒否される。
- `run_budget_jpy`、`monthly_budget_jpy`: dry-runで表示する運用判断用の値。現版のWorkerはこの金額でAPI通信を強制停止しないため、OpenAI Project側にもHard spend limitを設定する。
- `prompt_version`: プロンプトを変更したときに版を更新する。

候補の観点は `sources.openai_web_discovery.config.search_themes` で増減できる。

```yaml
config:
  search_themes:
    - 景勝地
    - 海岸
    - 温泉
    - 道の駅
    - 二輪駐車場
```

`openai_web_discovery` は引用URLとタイトルを候補として保存するが、発見先ページを自動的に信頼済みSourceへ昇格しない。新規ドメインは `pending_review` となる。利用条件を人が確認した後、別Sourceとして登録してから本文取得・公開可否を判断する。

公的データSourceの `config.ai_extract` を `true` にすると、取得レコードをOpenAI属性抽出へ送る。公開情報であっても、利用規約上の外部API送信が許可されていることを確認してから有効化する。通常のCSV・JSON mappingで十分な場合は `false` のままにする。

APIキーはYAMLへ書かず、3章のとおり `OPENAI_API_KEY` 環境変数へ設定する。公式推奨に従い、コードや公開リポジトリへ保存せず、Projectキーの期限とローテーションも設定する。

#### 2.4.7 OSM PBF

`sources.osm_pbf` は将来の全国規模収集用インターフェースである。現版の `extract_path` は未実装なので、値を設定しても収集できない。`--sources osm_pbf` は指定しない。

#### 2.4.8 設定反映と検証

編集後、まずYAMLと設定Schemaを検証する。

```powershell
docker compose run --rm worker `
  python -c "from collection_worker.config import load_settings; load_settings(); print('settings: OK')"
```

`settings: OK` が表示されたら、migrationコマンドでSource台帳へ反映する。

```powershell
docker compose run --rm migrate
```

最後に対象地域と編集したSourceキーでdry-runする。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources fukuoka_city_open_data,fukuoka_official_seed `
  --mode initial `
  --limit 10 `
  --dry-run
```

`sources` に編集したキーが表示され、ライセンス状態と保存方針が意図どおりであることを確認する。Source設定を変更した後は、変更前のRunをresumeせず、新しいRunを開始する。

### 2.5 ネットワークと利用条件

組織ネットワークやプロキシを利用している場合は、少なくともN03配布元、選択した公的データ配布元、OverpassへのHTTPS接続を許可する。Codex方式ではCodexの認証・検索先、Worker内蔵AI方式ではOpenAI APIへの接続も必要である。アクセス制限を回避するためのIP分散や、利用条件で禁止された本文保存は行わない。

実行前準備の完了条件は次のとおりである。

- Docker Engineが起動し、`docker info` が成功する。
- `.env` のDB名、ユーザー、パスワード、ホスト側ポートを確認した。
- N03の版とURL、対象地域コードを確認した。
- 選択する全Sourceの承認状態、ライセンス、帰属表示、本文保存方針を確認した。
- Overpassを使う場合は連絡先付きUser-Agentへ変更した。
- Codexを使う場合はChatGPTログインと利用枠、Worker内蔵AIを使う場合はAPIキー、モデル権限、Project予算を確認した。
- Manual Seedのプレースホルダーを置換または削除した。

### 2.6 CodexでSpot候補を収集する

OpenAI PlatformのAPIキーを用意せず、ChatGPTアカウントで認証したCodex CLIをSpot候補の収集に利用できる。この方式ではCodexが対象地域に実在するSpotをライブWeb検索で探し、Spot名、所在地、分類などをレビュー待ちJSONLへ出力する。各Spotの `source_url` は、そのSpotの存在や属性を確認した原典ページであり、探す対象そのものがSource一覧という意味ではない。Codexの出力は原典でも利用許諾でもないため、URLと利用条件を人が確認した後にだけWorkerへ投入する。

この方式で代替できるのは、主に `openai_web_discovery` の候補URL発見である。Worker内で各レコードをStructured Outputsへ送る属性抽出を、そのままCodexへ置き換えるものではない。CSV・JSON・GeoJSONは可能な限り `mapping` で正規化する。

#### 2.6.1 Codexの準備

PowerShellで次を実行する。このPCではPowerShellの実行ポリシーにより `codex.ps1` が拒否される場合があるため、明示的に `codex.cmd` を使う。

```powershell
codex.cmd --version
codex.cmd login
codex.cmd login status
```

ブラウザでChatGPTへログインでき、`codex.cmd login status` が成功すれば、OpenAI Platformの `OPENAI_API_KEY` は不要である。Codexの利用枠はChatGPT契約と組織設定に従う。認証ファイルをDockerコンテナへコピーしたり、Gitへ追加したりしない。

公式リファレンス: [Codex認証](https://learn.chatgpt.com/docs/auth)、[Codex CLI](https://learn.chatgpt.com/docs/codex/cli)、[非対話実行](https://learn.chatgpt.com/docs/non-interactive-mode)

#### 2.6.2 用意済みプロンプト

プロンプトは `data_collection/prompts/codex-spot-discovery-v1.md` にある。実行スクリプトが次の値を置換する。

- `{{REGION_NAME}}`: 人が読める地域名
- `{{REGION_CODE}}`: 2桁または5桁の行政区域コード
- `{{LIMIT}}`: 最大候補数
- `{{THEMES}}`: 景勝地、温泉、道の駅などの調査観点

プロンプトは、公式ページ優先、原典ページの確認、URLのない結果の破棄、推測値の禁止、重複除外をCodexへ指示する。候補段階では `license_status: unknown`、`review_status: pending` を固定し、Codexに利用許諾の承認をさせない。

#### 2.6.3 福岡市で実行する

リポジトリルートで次を実行する。

```powershell
.\data_collection\scripts\run_codex_spot_discovery.cmd `
  -RegionCode 40130 `
  -RegionName "福岡県福岡市" `
  -Limit 30
```

調査観点を指定する例:

```powershell
.\data_collection\scripts\run_codex_spot_discovery.cmd `
  -RegionCode 40130 `
  -RegionName "福岡県福岡市" `
  -Limit 30 `
  -Themes "景勝地","海岸","温泉","道の駅","二輪駐車場"
```

スクリプトは内部で次に相当する処理を行う。

```powershell
$prompt | codex.cmd --search exec `
  --sandbox read-only `
  --cd <リポジトリルート> `
  --output-last-message <出力JSONL> `
  -
```

- `--search`: ライブWeb検索を有効にする。
- `--sandbox read-only`: 調査中のCodexによるリポジトリ変更を禁止する。
- `--output-last-message`: Codexの最終回答だけをJSONLファイルへ保存する。
- `-`: 標準入力からプロンプトを渡す。

実行結果は `data_collection/seeds/codex_pending/<地域コード>-<日時>.jsonl` に作成される。このディレクトリ内の生成ファイルはGit管理対象外である。スクリプトは、各行がJSONであること、必須項目、HTTP(S) URL、地域コード、未レビュー状態を検査する。ただし、URL先の事実やライセンスの正しさを保証する検査ではない。

`.cmd` ランチャーとPowerShellスクリプトは、Codexへ渡す標準入力とコンソール出力をUTF-8に設定する。Codexの画面で地域名や日本語の指示が `????` と表示された場合、その実行結果は使用せず、最新版の `.cmd` ランチャーで再実行する。

CodexでSpot候補を収集するだけなら、`sources.yaml` の `n03.base_url`、`osm_overpass.base_url`、`public_open_data.config.datasets` を変更する必要はない。Codexが見つけたSpotごとの原典URLは、設定ファイルではなく生成JSONLの `source_url` に保存される。人手レビュー後は、承認済み行を既存の `manual_spots.jsonl` へ追加して `manual_seed` を使えるため、この場合もURL設定の変更は不要である。異なる利用条件のSpotを分離管理したい場合だけ、2.4.5の手順で専用のManual Seed Sourceを追加する。

Codex CLIを対話的に使用する場合は、同じプロンプトの地域・件数・観点を置換して、次のように開始してもよい。

```powershell
codex.cmd --search
```

対話画面から得た結果も、承認前は `codex_pending` に置き、直接 `manual_spots.jsonl` へ追加しない。

#### 2.6.4 人手レビューとWorkerへの投入

生成されたJSONLを開き、全行について次を確認する。

1. `source_url` をブラウザで開き、Spot名と所在地が原典ページで確認できる。
2. 対象の行政区域内であり、閉業・廃止・期間終了ではない。
3. 住所や座標が原典と一致し、Codexによる推測値ではない。
4. 利用規約、ライセンス、商用利用、加工、再配布、出典表示、本文保存の条件を確認できる。
5. 同じ利用条件を適用できる候補だけを同じSeedファイルへまとめる。

承認した行だけを、たとえば `data_collection/seeds/fukuoka_official_spots.jsonl` へコピーする。その後、2.4.5の例に従い、同ファイルを読む専用Sourceを `sources.yaml` に追加する。`license_name`、`terms_url`、`attribution_text`、`raw_storage_policy` は人が確認した内容を設定する。

2026-09-26の福岡市初回収集では、レビュー承認した40件を `data_collection/seeds/fukuoka_codex_reviewed_spots.jsonl` へ固定し、Sourceキー `fukuoka_codex_reviewed` で読み込む。Spot内容は承認済みだが、複数ドメインの利用条件を一括で検証済みとは扱わないため、Source台帳の `license_status` は `unknown`、本文保存方針は `facts_only` とする。

```yaml
sources:
  fukuoka_codex_reviewed:
    source_type: manual_seed
    approval_status: approved
    license_status: unknown
    license_name: Source-specific public web pages
    terms_url: null
    attribution_text: null
    raw_storage_policy: facts_only
    base_url: null
    rate_limit_per_minute: 1
    request_timeout_seconds: 60
    max_pages_per_run: 100
    refresh_interval_days: 30
    config:
      paths:
        - /app/seeds/fukuoka_codex_reviewed_spots.jsonl
      ai_extract: false
```

設定検証と台帳同期後、Codex用の `openai_web_discovery` を含めずに実行する。

```powershell
docker compose run --rm worker `
  python -c "from collection_worker.config import load_settings; load_settings(); print('settings: OK')"
docker compose run --rm migrate
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources osm_overpass,fukuoka_codex_reviewed `
  --mode initial `
  --limit 100
```

別の市区町村・行政区では `RegionCode`、`RegionName` とWorkerの `--region-code` を変更する。都道府県単位のCodex調査も2桁コードで実行できるが、一度に広域を調査すると取りこぼしや重複が増えるため、市区町村単位へ分割する。

## 3. OpenAI APIキー（任意）

Codex方式を使うだけなら本章は不要である。Worker内蔵の `openai_web_discovery` またはAI属性抽出を使う場合だけ、現在のPowerShellセッションへ設定する。

```powershell
$env:OPENAI_API_KEY = Read-Host 'OpenAI API key' -AsSecureString | ConvertFrom-SecureString -AsPlainText
```

値を表示せず、設定有無だけを確認する。

```powershell
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    throw 'OPENAI_API_KEY is not set.'
}
```

キーをソース、YAML、Markdown、ログ、Git管理対象へ記録しない。WorkerはOpenAI Responses APIを `store=false` で呼び出す。

OpenAI Platformでは、この収集処理専用ProjectのAPIキーを使用する。可能ならキーに有効期限を設定し、定期的にローテーションする。失効前に新しいキーへ切り替えて動作確認し、その後に古いキーを無効化する。利用状況はOpenAI PlatformのUsage画面で確認する。

月額費用を強制的に止める必要がある場合は、ProjectのLimitsでMonthly spend limitを設定し、`Enforce a hard limit` を有効にする。通知だけが必要ならSpend alertも設定する。Worker設定の `run_budget_jpy` と `monthly_budget_jpy` はdry-run表示と運用判断用であり、現版のWorker単体ではAPI通信を強制停止しない。

- [OpenAI APIキーのProduction best practices](https://developers.openai.com/api/docs/guides/production-best-practices#api-keys)
- [OpenAI Spend limits](https://developers.openai.com/api/docs/guides/spend-limits)

## 4. 初回セットアップ

### 4.1 buildとDB起動

```powershell
docker compose build
docker compose up -d db
docker compose ps
```

`db` が `healthy` になることを確認する。失敗時は次を確認する。

```powershell
docker compose logs db --tail 100
```

### 4.2 migrationとSource台帳同期

```powershell
docker compose run --rm migrate
```

成功時は次が表示される。

```json
{"status":"completed"}
```

同じmigrationは何度実行しても再適用されない。

### 4.3 N03行政区域同期

設定済みURLから国土数値情報N03を取得する。

```powershell
docker compose run --rm worker `
  python -m collection_worker regions sync --dataset-version latest
```

手元のN03 ZIPを使う場合はread-onlyでmountする。

```powershell
docker compose run --rm `
  -v "C:\path\to\n03:/input:ro" `
  worker python -m collection_worker regions sync `
  --dataset-version N03-YYYYMMDD `
  --input /input/N03-YYYYMMDD_GML.zip
```

出力された `region_count` が0より大きいことを確認する。

`--dataset-version latest` は `sources.yaml` の `n03.config.dataset_version` を使用する。国土数値情報サイトの最新版を自動探索する指定ではない。配布URLや版を変更した場合は、`base_url`、`dataset_version`、`valid_from` を同時に更新してから同期する。

### 4.4 初回実行前チェック

Compose設定とCLI起動を確認する。

```powershell
docker compose config --services
docker compose run --rm worker python -m collection_worker --help
docker compose run --rm worker python -m collection_worker collect --help
```

`docker compose config --services` に `db`、`migrate`、`worker` が表示されることを確認する。Source設定を変更した場合は、収集前にSource台帳を再同期する。秘密情報を含む可能性があるため、APIキー設定後の `docker compose config` 全文をログやチャットへ貼り付けない。

```powershell
docker compose run --rm migrate
```

初回は次の順序で進める。

1. dry-runで地域と設定を確認する。
2. OpenAIを使わず、1 Source・`--limit 10` 程度で実収集する。
3. Run状態とCSVを確認する。
4. 問題がなければSourceと上限を増やす。
5. 最後にOpenAI候補発見を追加する。

## 5. 福岡市の初回収集

### 5.1 dry-run

福岡市全体の行政区域コードは `40130` である。dry-runは外部Source取得と収集Run作成を行わない。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources osm_overpass,public_open_data,openai_web_discovery,manual_seed `
  --mode initial `
  --limit 100 `
  --dry-run
```

次を確認する。

- `region_name` が福岡市、`region_kind` が `designated_city` である。
- 行政区域版とSource一覧が意図どおりである。
- `openai_budget` のRun・月次上限が意図どおりである。
- Sourceのライセンス状態と本文保存方針が意図どおりである。

dry-runは地域・設定検査であり、各外部サービスへ実際に接続できることまでは確認しない。また、`--limit` は全Source合計ではなく、各Sourceが返す最大件数として渡される。複数Sourceを指定すると、Run全体では指定値を超える場合がある。

### 5.2 最小構成で実収集する

最初はOpenAI APIキーを使わず、Overpass 1 Sourceで10件まで収集する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources osm_overpass `
  --mode initial `
  --limit 10
```

終了後、表示された `run_id` を使って9章のCSVを出力し、名称、座標、地域、Source URL、ライセンス、レビュー理由を確認する。

### 5.3 OpenAIを含む実収集

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources osm_overpass,public_open_data,openai_web_discovery,manual_seed `
  --mode initial `
  --limit 100
```

出力されたUUID形式の `run_id` を控える。状態は `completed`、一部Source失敗時は `partial`、全Source失敗時は `failed` になる。

`public_open_data.config.datasets` が空なら公的データは0件となる。Manual Seedの全行が対象地域外ならManual Seedも0件となる。OpenAI候補発見は引用URLを候補として保存する段階であり、新規ドメインは `pending_review` となるため、そのまま信頼済みSourceや公開可能Spotにはならない。

終了コードは次のとおりである。

- `0`: 完了
- `2`: Sourceの一部または全部が失敗。保存済み成果は再開可能
- `3`: 引数、設定、地域コードが不正
- `4`: Source承認状態などのPolicy違反
- `5`: その他の実行エラー

## 6. 別地域と都道府県の収集

市区町村または行政区は5桁コードを指定する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code <5桁コード> `
  --sources osm_overpass,public_open_data `
  --mode initial `
  --dry-run
```

都道府県は2桁コードを指定する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --prefecture-code <2桁コード> `
  --sources public_open_data,openai_web_discovery `
  --mode initial `
  --dry-run
```

政令指定都市全体は親コード、区単体は各区コードを使用する。必ず先にdry-runし、地域名と境界版を確認する。都道府県全体に公開Overpassを使用しない。

## 7. Source設定とManual Seed

Source設定は `data_collection/config/sources.yaml` にある。変更後はmigrationを再実行して `source_registry` と同期する。

設定ファイルを変更したら、収集中のRunをresumeせず、新しいRunを開始する。resumeは開始時の設定ファイルSHA-256と現在の設定が一致する場合だけ許可される。

公的データは `public_open_data.config.datasets` にURL、形式、フィールドmappingを追加する。自動取得対象は `approval_status: approved` のSourceだけである。

手入力候補は `data_collection/seeds/manual_spots.jsonl` へ1行1JSONで追加する。最低限 `source_record_id`、`source_url`、`region_code` を指定し、可能なら名称、住所、緯度、経度を付ける。サンプル行の `example.invalid` は実データでは承認済み公式URLへ置換する。

Manual Seedの例:

```json
{"source_record_id":"official-spot-001","source_url":"https://city.example.jp/spots/001","region_code":"40130","name":"地点名","address":"福岡県福岡市...","latitude":33.59,"longitude":130.40,"source_categories":["official-tourism"],"features":["駐車場"]}
```

`source_record_id` は同じSource内で永続的に変わらないIDを使う。URLや名称をID代わりに頻繁に変更すると、別候補として扱われる可能性がある。

## 8. 月次更新と再開

月次更新は `refresh` を指定する。現版はSource全件を冪等upsertし、候補レコードを増殖させず取得履歴を更新する。

```powershell
docker compose run --rm worker `
  python -m collection_worker collect `
  --region-code 40130 `
  --sources osm_overpass,public_open_data,openai_web_discovery,manual_seed `
  --mode refresh
```

`partial`、`failed`、`cancelled` のRunは同じ `run_id` で再開する。

```powershell
docker compose run --rm worker `
  python -m collection_worker runs resume <run_id>
```

設定ファイルの内容が開始時から変わったRunは再開を拒否する。その場合は新しいRunを開始する。Run状態の確認には次を使う。

```powershell
docker compose run --rm worker `
  python -m collection_worker runs show <run_id>
```

## 9. 結果出力

Canonical工程へ渡すJSONLを出力する。

```powershell
docker compose run --rm worker `
  python -m collection_worker export `
  --run-id <run_id> `
  --format jsonl `
  --status ready,review_required
```

人手レビュー用CSVを出力する。

```powershell
docker compose run --rm worker `
  python -m collection_worker export `
  --run-id <run_id> `
  --format csv `
  --status ready,review_required
```

`data_collection/output/<run_id>/` に次を生成する。

- `candidates.jsonl`（JSONL指定時）
- `candidates.csv`
- `observations.csv`
- `attributions.csv`
- `reviews.csv`

JSONLは `SpotCandidate v1` JSON Schemaで検証してから出力される。本文保存不可SourceのRaw本文、APIキー、Cookieは出力しない。

出力後に最低限次を確認する。

- `candidates` の件数が想定範囲にある。
- 各候補に地域情報があり、座標または住所が存在する。
- `observations` にSource URL、原典ID、取得日時、ライセンス状態、抽出方法がある。
- `attributions` に利用するSourceのライセンス名、利用条件URL、帰属表示がある。
- `reviews` のblocking理由を解消するまで、該当候補を公開データとして扱わない。
- APIキー、Cookie、保存不可本文が出力されていない。

同じ `run_id`・形式で再出力すると、同名ファイルを置き換える。必要な成果物は別の安全な保管先へコピーする。

## 10. レビュー

初期版は管理画面を持たない。`reviews.csv` と `observations.csv` を確認する。代表的な理由コードは次のとおりである。

- `LICENSE_UNKNOWN`: 利用条件が確認できない
- `LOCATION_MISSING`: 座標と住所がない
- `OUTSIDE_REGION` / `OUTSIDE_REGION_REJECTED`: 指定境界外
- `SOURCE_CONFLICT`: 同一属性の観測値が矛盾
- `DUPLICATE_SUSPECTED`: 名称と距離から重複の疑い
- `AI_ONLY_EVIDENCE`: AI抽出以外の根拠がない
- `CLOSED_OR_UNAVAILABLE`: 閉業・一時休業情報がある

OpenAI候補発見で得た新規ドメインは `pending_review` でSource台帳へ追加され、自動で承認済みにはならない。

## 11. 停止

DBデータを残して停止する。

```powershell
docker compose down
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
```

`docker compose down --volumes` は収集DBを削除するため、通常運用では実行しない。

## 12. トラブルシューティング

### 12.1 5432番ポート競合

`.env` の `POSTGRES_PORT` を未使用ポートへ変更し、`docker compose up -d db` を再実行する。

### 12.2 OpenAI認証・利用上限

APIキーの設定有無、キーが属するProject、モデル利用権限、請求設定、ProjectのSpend limitを確認する。キー自体は表示しない。Worker側の予算値はdry-runに表示される運用上限であり、強制停止にはOpenAI Project側でHard spend limitを有効にする。上限到達時は `429` と `project_spend_limit_exceeded` または `organization_spend_limit_exceeded` が返る場合がある。

### 12.3 Overpassの429・timeout

Workerは直列呼び出し、24時間キャッシュ、`Retry-After`、指数バックオフを使用する。繰り返し失敗する場合は時間を空ける。都道府県規模・定期大量取得を公開Overpassへ送らない。

### 12.4 Runが再開できない

`runs show` で状態を確認する。完了済みRun、または開始時からSource設定・モデル・プロンプト版が変わったRunはresumeせず、新しいRunを開始する。

## 13. 実装時の検証記録

2026-09-23に次を確認済みである。

- Python単体試験11件が成功する。
- Dockerイメージがbuildできる。
- PostGIS migrationとSource台帳6件の同期が成功する。
- ミニN03 fixtureから福岡市、行政区、都道府県を含む7地域を同期できる。
- 福岡市dry-run、Manual Seed収集、部分失敗Runのresumeが成功する。
- Source付きJSONLと `candidates` / `observations` / `attributions` / `reviews` CSVを出力できる。

実N03ダウンロード、公開Overpass、実OpenAI APIは外部サービス・課金を伴うため、利用者の初回実行時に確認する。
