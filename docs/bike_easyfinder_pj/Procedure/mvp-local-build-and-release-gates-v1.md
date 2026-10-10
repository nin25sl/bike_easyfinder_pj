---
title: MVP ローカル構築・Release Gate手順 v1
published: 2026-10-04
tags: [mvp, runbook, local, release]
category: Procedure
draft: false
---

# MVP ローカル構築・Release Gate手順 v1

## ローカル起動

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose run --rm migrate
docker compose run --rm api-migrate
docker compose up -d api
Invoke-RestMethod http://localhost:8000/healthz
```

## 収集済み候補を公開Canonicalへ昇格

```powershell
docker compose run --rm api-migrate `
  bike-api promote --prefecture-codes 40 41 42 43 44 45 46

docker compose run --rm api-migrate `
  bike-api audit-kyushu --minimum-spots-per-prefecture 1
```

`release_ready=false`が1県でもあれば公開を止める。限定β前には`1`を品質担当が承認した県別最低件数へ変更する。

## API疎通

```powershell
$body = @{
  origin = @{ latitude = 33.5902; longitude = 130.4017 }
  available_minutes = 120
  interests = @("scenic")
  allow_highway = $false
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/v1/recommendations `
  -ContentType application/json `
  -Body $body
```

## 自動テスト

```powershell
docker compose --profile test build api-test
docker compose --profile test run --rm api-test

.\.venv\Scripts\python.exe -m pytest data_collection\tests -q `
  --basetemp .pytest-tmp\manual-run
```

## 日次privacy maintenance

```powershell
docker compose run --rm api-migrate bike-api privacy-maintenance --dry-run
docker compose run --rm api-migrate bike-api privacy-maintenance
```

本番ではschedulerから1日1回実行し、`deletions_completed`、`events_expired`、`kpis_aggregated`を監視する。

## Apple Maps実Provider gate

短期access tokenをPowerShellプロセスにだけ設定する。`.env`やGitへtokenを保存しない。

```powershell
$env:APPLE_MAPS_ACCESS_TOKEN = "<short-lived access token>"
cd data_collection
python scripts/apple_maps_poc.py --cases config/apple_maps_poc_routes.csv
```

140件すべての基準と手動確認が合格するまで、`APP_ENV=staging`または`production`へ進めない。API起動値は次のとおり。

```text
APP_ENV=staging
ROUTE_PROVIDER=apple
APPLE_MAPS_ACCESS_TOKEN=<secret managerから注入>
BIKE_API_BASE_URL=https://<staging API host>
```

## iOS

Macで`ios/BikeEasyFinder`へ移動し、`xcodegen generate`後にXcodeで開く。Simulatorでは`BIKE_API_BASE_URL=http://127.0.0.1:8000`、実機ではMacのLAN URL、TestFlightではHTTPS staging URLを設定する。WeatherKit capabilityとTeamを選択してから実機試験する。
