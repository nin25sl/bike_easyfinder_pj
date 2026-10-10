---
title: バイク目的地提案アプリ MVP 基本設計書 v1
published: 2026-09-27
updated: 2026-10-10
description: MVP要件定義書v1に基づくiOS、API、データ、外部連携、運用の基本設計
tags:
  - mvp
  - design
  - ios
  - api
  - data
  - operations
  - SC
  - approved
category: SystemDesign
draft: false
Approval flag: Approved
approved: 2026-09-27
---

# バイク目的地提案アプリ MVP 基本設計書 v1

> **承認記録:** 2026-09-27承認。詳細設計への移行を承認する。O-01〜O-06の必須ゲートおよび再承認条件は継続する。記録は `../Handover/mvp-basic-design-v1-approval.md` を参照。

> **目的とゴールの違い**
>
> - **目的** = Why（なぜこの設計を行うか）
> - **ゴール** = Done 条件（何を満たせば基本設計完了とするか）

## 目次

<inline-toc preview="3"></inline-toc>

## 目的

承認済みの `mvp-requirements-v1.md` を、iOSアプリ、公開API、データ基盤、外部サービス連携、運用監視へ一貫して実装できる構造に具体化する。本書は詳細設計、実装、テスト計画の上位設計とし、要件を変更せずに各コンポーネントの責務と境界を定める。

## ゴール

- BD-01〜BD-08に対応する構成、API、データ、推薦、iOS、外部連携、運用、試験の設計がある。
- local / staging / productionの差分、バックアップ対象、復旧優先度、監視閾値、費用統制が実装可能な粒度で定義されている。
- 要件、OpenAPI、データ収集設計との不整合または追加変更が明示されている。
- 未確定のProvider・インフラは、採用候補と合否判定を定め、未検証のままproductionへ進まない。
- ユーザー承認後、詳細設計と実装へ移行できる。

## 1. 文書の位置付け

### 1.1 正本と優先順位

設計・実装上の優先順位は次のとおりとする。

1. `mvp-requirements-v1.md`（業務・製品要件）
2. 本書（基本設計）
3. `mvp-openapi-v1.yaml`（公開APIの機械可読契約）
4. `spot-data-collection-basic-design-v1.md`（収集Workerの詳細設計）
5. 詳細設計、DDL、実装、テスト仕様

矛盾時は上位文書を優先する。ただしOpenAPIと実装は常に一致させ、本書承認後に本書で指摘したOpenAPI差分を反映する。

### 1.2 対象範囲

- iOS 17以上のSwiftUIアプリ。
- FastAPIによる公開APIと管理Worker。
- PostgreSQL 16 + PostGISによるCanonical Spot、Source、分析・削除管理。
- Apple Maps Server API、MapKit、CoreLocation、WeatherKit、Apple Maps連携。
- 九州7県のデータ収集・更新・レビュー運用。
- CI/CD、監視、ログ、バックアップ、セキュリティ、費用管理。

### 1.3 対象外

Android、アカウント、複数端末同期、内蔵ナビ、走行追跡、オフライン地図、独自ルーティング、Valhalla、UGC、SNS、通知、課金、ML / LLM推薦は対象外とする。

## 2. 設計原則

1. 検索一覧ではなく、最大5候補を1件ずつ提案する。
2. 時間条件、安全、利用条件、プライバシーをランキングより優先する。
3. iOSは表示と端末状態、APIは推薦とCanonical参照、Workerは収集と更新を担当する。
4. 機能データと分析データを分離し、分析拒否で主要機能を制限しない。
5. 外部サービス障害を候補0件と混同しない。
6. 同一入力・同一データ版・同一ルール版では同一順位を返す。
7. stagingとproductionは同一構成とし、規模と値だけを変える。
8. 月額10,000円を超える変更は事前承認を必須とする。

## 3. システム構成

### 3.1 コンテキスト図

```text
[利用者]
   │ 条件入力・リアクション
   ▼
[iOS App]
   ├── CoreLocation ───────────── 現在地（都度取得）
   ├── MapKit / Apple Maps ───── 地図表示・外部ナビ
   ├── WeatherKit ────────────── Spot地点の天気注意
   └── HTTPS
         ▼
   [FastAPI Public API]
      ├── Recommendation ── [Apple Maps Server API]
      ├── Interaction
      ├── Privacy
      └── Spot Query
         │
         ▼
   [PostgreSQL + PostGIS]
         ▲
         │ Canonical更新
   [Data Worker / Review CLI]
      └── OSM・公共・公式・公開Web情報
```

### 3.2 デプロイ構成

```text
Internet
  │ TLS / rate limit
  ▼
[Managed Edge / Container Host]
  └─ FastAPI container
       ├─ API process
       └─ Worker process（別コマンド・同一イメージ）
             │ private TLS
             ▼
       [Managed PostgreSQL + PostGIS]
             ├─ primary database
             └─ daily backup / PITR相当

[CI/CD]
  ├─ lint / test / OpenAPI validation / migration dry-run
  ├─ staging deploy
  └─ approval gate → production deploy
```

ベンダーは基本設計承認後のADRで確定する。採用条件は、東京または日本から低遅延なリージョン、PostGIS、保存時暗号化、日次バックアップ、staging / production分離、月額上限内、メトリクス取得、データ削除可能性である。条件を満たすマネージド構成を第一候補とし、単一VPSへのDB同居はproductionで採用しない。

### 3.3 コンポーネント責務

| コンポーネント | 責務 | 保持しないもの |
|---|---|---|
| iOS Presentation | S01〜S08、アクセシビリティ、ローディング・エラー表示 | サーバ秘密鍵、走行軌跡 |
| iOS Domain | 条件検証、カード進行、リアクション状態、ナビ前確認 | Canonical更新ロジック |
| iOS Persistence | 前回条件、オンボーディング済み、Spotスナップショット、嗜好、同意、送信キュー | 正確な現在地の履歴 |
| Recommendation API | 入力検証、候補抽出、ETA取得、フィルタ、スコア、多様性、理由生成 | 端末の生嗜好履歴の永続化 |
| Interaction API | 同意確認、イベント冪等受理、期限削除 | 同意前イベント |
| Privacy API | 削除トークン照合、削除受付、削除台帳、再流入防止 | 平文削除トークン |
| Data Worker | 収集、正規化、名寄せ候補、Freshness、Canonical反映候補 | 公開API機能 |
| Review CLI | 人間レビュー、採用・却下・非公開、監査記録 | 一般ユーザー操作 |
| PostgreSQL / PostGIS | 正本データ、空間検索、分析、削除管理 | WeatherKitの応答キャッシュ |

## 4. iOSアプリ設計

### 4.1 アーキテクチャ

SwiftUI + MVVMを基本とし、Feature単位に `View / ViewModel / UseCase / Repository` を分ける。依存はProtocol経由で注入し、固定JSONとモック外部サービスへ置換可能にする。

```text
App
├─ Features
│  ├─ Onboarding
│  ├─ Home
│  ├─ Conditions
│  ├─ Recommendation
│  ├─ SpotDetail
│  ├─ InterestedSpots
│  ├─ NavigationHandoff
│  └─ PrivacySettings
├─ Domain
├─ Data
│  ├─ APIClient
│  ├─ LocalStore
│  └─ EventQueue
└─ Platform
   ├─ LocationClient
   ├─ WeatherClient
   ├─ MapClient
   └─ KeychainClient
```

### 4.2 画面遷移と状態

| 状態 | 遷移先 | 条件 |
|---|---|---|
| firstLaunch | S01 | 初回説明未完了 |
| ready | S02 | 初回説明完了 |
| editingConditions | S03 | 条件変更または初回開始 |
| locating | S03内 | 提案開始時だけ現在地取得 |
| loadingRecommendations | S03内 | リクエスト中。二重送信禁止 |
| presenting(index) | S04 | 候補1件以上 |
| showingDetail(index) | S05 | 詳細選択 |
| showingInterested | S06 | 保存済みSpotを表示 |
| confirmingNavigation | S07 | 目的地確定 |
| privacySettings | S08 | 設定選択 |
| empty | S04空状態 | 200かつ候補0件 |
| failed(kind) | 現画面 | 権限、通信、外部依存を区別 |

### 4.3 端末保存

| データ                              | 保存先                 | 保持・削除                     |
| -------------------------------- | ------------------- | ------------------------- |
| 初回説明済み、前回条件                      | UserDefaults相当      | 設定から消去、アプリ削除まで            |
| リアクション、興味ありSpotスナップショット          | SwiftData           | 設定から消去、アプリ削除まで            |
| analytics installation ID、削除トークン | Keychain            | 撤回・削除時に消去。再インストール復元は保証しない |
| 未送信イベント                          | 暗号化ファイルまたはSwiftData | 最大7日、撤回時即時削除              |
| 現在地                              | メモリのみ               | 推薦完了または画面終了時に破棄           |

Spotスナップショットは `spot_id / name / summary / coordinate / tags / verified_at / saved_at` に限定する。次回同じSpotを推薦された時だけ表示情報を更新し、専用同期APIは設けない。

### 4.4 位置権限

- S01では権限ダイアログを出さず、S03の提案開始操作時に `When In Use` を要求する。
- `authorizedWhenInUse` 以外は理由と次操作を表示する。
- reduced accuracyで推薦精度を満たせない場合は精度不足として再試行を案内する。
- 前回位置、バックグラウンド位置、走行軌跡は保存・利用しない。

### 4.5 分析イベント送信

- 同意後だけIDと削除トークンを生成する。
- 端末内の機能リアクション保存を先に確定し、その後イベントをキューへ追加する。
- 50件またはアプリの安全なバックグラウンド移行時にバッチ送信する。
- 503、通信断だけ指数バックオフし、最大7日で破棄する。
- 分析送信失敗で推薦・リアクション・ナビを止めない。

## 5. 公開API設計

### 5.1 共通仕様

- ベースパスは `/v1`、HTTPS、UTF-8 JSON。
- クライアントは全要求へランダムUUIDの `X-Request-ID` を付与する。
- エラーは `application/problem+json`。内部例外やDBキーを返さない。
- APIのサーバ処理期限4秒、iOSタイムアウト5秒。
- 429の `Retry-After`、503、504、通信断だけ再試行対象とする。
- CORSはWebクライアントを提供しない間は無効とする。
- 公開APIはIPベースと全体の二層レート制限を行い、installation IDを認証に使わない。

### 5.2 エンドポイント

| Endpoint                             | 成功  | 冪等性            | レート制限（初期値） |
| ------------------------------------ | --- | -------------- | ---------- |
| `POST /v1/recommendations`           | 200 | 読取。同一データ版で決定論的 | 30回/10分/IP |
| `POST /v1/interactions`              | 202 | `event_id` 一意  | 60回/10分/IP |
| `DELETE /v1/installations/{id}/data` | 202 | 同一対象を常に受理表示    | 5回/日/IP    |

閾値はstaging負荷試験後に設定ファイルで変更できるようにし、コードへ散在させない。

### 5.3 OpenAPI差分

現行 `mvp-openapi-v1.yaml` の `RecommendationRequest` には、要件が求める過去リアクション入力がない。実装開始前に次を追加し、契約バージョンを `1.1.0` とする。

```yaml
preference_profile:
  type: object
  required: [spot_reactions, category_weights, tag_weights]
  properties:
    spot_reactions:
      type: array
      maxItems: 200
    category_weights:
      type: object
      additionalProperties: { type: integer, minimum: -30, maximum: 15 }
    tag_weights:
      type: object
      additionalProperties: { type: integer, minimum: -30, maximum: 15 }
```

送信する個別Spot反応は直近または影響対象の最大200件とし、それ以前は端末でカテゴリ・タグ重みに集約する。分析同意とは独立した機能入力で、API処理後に保存しない。

また、Apple Maps Server APIのETAは二輪専用プロファイルを提供しないため、`route.profile` はMVPでは `auto` を返す。現行OpenAPIの `motorcycle` は将来予約値として残し、MVP応答で使用しない。

## 6. 推薦設計

### 6.1 処理パイプライン

```text
入力検証
 → PostGIS粗検索（片道180分相当の距離上限）
 → 公開・Freshness・利用条件検査
 → 希望所要時間との差による概算事前選別（最大10地点）
 → ETA一括取得（最大10地点/要求）
 → 往復ETA取得
 → 希望所要時間窓・営業・経路のハードフィルタ
 → スコア計算
 → 多様性調整
 → 上位5件の概要ルート取得
 → レスポンス生成
```

粗検索は直線距離250kmを初期上限とし、時間条件に応じて `min(250km, available_minutes × 1.5km)` を探索半径の初期値とする。これはDB候補削減だけに使う。取得した最大100件は、直線距離、滞在時間、安全余裕15分から概算総時間を算出し、希望所要時間との差が小さい最大10件をETA評価対象とする。最終的な時間窓判定には必ずETAを使う。

### 6.2 時間計算

```text
estimated_total_minutes
  = ceil(outbound_seconds / 60)
  + stay_minutes
  + ceil(return_seconds / 60)
  + 15
```

- 往路は現在時刻、復路は現在時刻 + 往路 + 滞在時間を出発日時として個別に照会する。
- `available_minutes` は希望所要時間として扱い、まず `abs(estimated_total_minutes - available_minutes) <= 15` の候補だけ残す。
- ±15分の候補が0件の場合に限り、許容差を±30分、±45分、±60分へ段階的に広げる。候補が1件以上見つかった最初の範囲を採用し、±60分でも0件なら空配列を返す。
- 許容差を拡張した場合は `TIME_WINDOW_EXPANDED` warningで採用範囲を返し、iOSで条件緩和を明示する。
- ETAキャッシュキーは、丸めた出発メッシュ、spot ID、方向、高速可否、15分時間帯、Provider版とする。
- キャッシュTTLは15分。正確な緯度経度はキャッシュキー・ログへ保存せず、約1kmメッシュへ丸める。
- `allow_highway=false` をProviderで保証できない場合、そのProviderは不採用とする。POC完了までは当該条件を満たしたと見なさない。

### 6.3 スコア

| 要素 | 配点 | 基本式 |
|---|---:|---|
| 興味一致 | 0〜40 | 選択興味に対応するタグ一致率。`any` は20 |
| 時間適合 | 0〜25 | 希望所要時間との差が0分なら25、採用時間窓の端で0となる線形減点 |
| リアクション嗜好 | -30〜15 | Spot、カテゴリ、タグ重みの合計を範囲内へ丸める |
| データ信頼度 | 0〜10 | 必須属性confidence平均 × 10 |
| 編集人気度 | 0〜10 | 根拠・期限付きの運用値 |

- `interested`: 同一Spot +15、カテゴリ/タグは端末集約で各+2（上限+10）。
- `not_interested`: 同一Spot -30、カテゴリ/タグは各-3（下限-20）。ハード除外しない。
- `visited`: 同一Spot -12、カテゴリ/タグは変更しない。未訪問を優先するが永久除外しない。
- 順位は `希望所要時間との差 asc → score desc → spot_id asc` とし、時間条件をランキングより優先する。
- ルール版を `recommendation_rule_version` として応答・内部メトリクスに残す。

### 6.4 多様性

スコア順に候補を走査し、同一のカテゴリ集合先頭値が連続する場合は、5点以内の別カテゴリ候補を先に採用する。最大5件を満たせない場合は重複カテゴリを許容する。多様性調整後もハード条件と決定論を維持する。

### 6.5 推薦理由

自由生成は行わず、寄与要素からテンプレートで最大3件を返す。

- `選んだ「海」に合っています`
- `2時間以内で往復できる見込みです`
- `保存した傾向に近いスポットです`
- `最近確認された情報です`

信頼度や編集人気度を、事実の人気・安全保証として表現しない。

### 6.6 障害時

| 状況 | API | iOS表示 |
|---|---|---|
| 条件該当なし | 200、空配列 | 条件変更 |
| ±15分に候補なし、拡張範囲に候補あり | 200、候補 + `TIME_WINDOW_EXPANDED` | 採用した許容差を明示 |
| 一部ETA失敗 | 200、成功候補 + warning | 一部取得不能の警告 |
| 全ETA失敗 | 503 | 外部サービス障害・再試行 |
| 4秒超過 | 504 | タイムアウト・再試行 |
| ETAクォータ超過 | 503、専用code | 混雑表示。候補0件にしない |
| キャッシュのみ利用可能 | 200、警告 | 推定時刻を表示。15分超のキャッシュは使わない |

## 7. 外部サービス設計

### 7.1 移動時間Provider

第一候補はApple Maps Server APIとする。ETA endpointは1回で最大10目的地の時間・距離を取得できるため候補の一括評価に使用する。概要ポリラインはDirections endpointを上位候補へ使用する。認証トークンはサーバで生成・保管し、iOSへ配布しない。

制約として交通手段は `Automobile` を使用し、二輪専用経路を保証しない。小型二輪の道路制約、通行規制、現地標識を置き換えないことをS01、S05、S07に表示する。

### 7.2 Provider POC合格基準

各県で都市部、山間部、海沿い、高速可/不可を含む最低20経路、合計140経路以上を検証する。

- API成功率99%以上。
- Apple Mapsアプリ表示時間との差の中央値15%以内、p95 30%以内。
- 高速不可条件で有料高速を利用する経路が0件。
- 往路・復路の非対称性を取得できる。
- 4秒のAPI処理期限内で、最大5候補のp95が収まる。
- 規約、クォータ、データ送信、帰属がPrivacy Policyと整合する。

1項目でも不合格ならproduction採用を保留し、代替Provider比較を新しいADRで行う。推定値を直線距離だけで代替してβ公開しない。

### 7.3 WeatherKit

- S05表示時に天候依存属性を持つSpotだけ問い合わせる。
- Spot座標だけを送り、現在地、installation ID、リアクションを結合しない。
- 降水確率50%以上、風速10m/s以上、気温5℃未満または35℃以上で注意を表示する。
- 属性 `weather_sensitivity = rain | wind | temperature | visibility` と一致する注意だけを強調する。
- 取得失敗時は「天気情報を取得できません。出発前に最新情報を確認してください」と表示する。
- 天気は推薦順位・除外に使わない。Apple Weatherの帰属と法的リンクを表示する。

### 7.4 Apple Mapsへの引き渡し

S07でSpot名、座標、安全注意を確認後、`MKMapItem.openInMaps` に目的地だけを渡す。OS受理で `route_started` とする。失敗時は緯度経度の文字列をクリップボードへコピーできるようにし、二重タップを抑止する。

## 8. データ設計

### 8.1 ER概要

```text
spots ──< spot_categories >── categories
  │  └──< spot_tags >──────── tags
  ├──< spot_hours
  ├──< spot_field_sources >── spot_sources
  └──< data_review_tasks

installations ──< interaction_events
       └────────< data_deletion_requests

taxonomy_versions ──< interest_taxonomy_mappings
```

収集前段の `spot_candidates` 等は `spot-data-collection-basic-design-v1.md` を正本とし、公開APIはCanonicalへ昇格した `spots` 系だけを参照する。

### 8.2 主要テーブル

| テーブル | 主キー・主要列 | 主要制約・索引 |
|---|---|---|
| `spots` | id UUID、name、summary、location geography、status、stay_minutes、confidence、verified_at、data_version | GIST(location)、status+verified_at |
| `spot_sources` | id、source_type、source_record_id、url、license_status、retrieved_at、verified_at | unique(source_type, source_record_id) |
| `spot_field_sources` | spot_id、field_name、source_id、adopted_at、rule_version | unique(spot_id, field_name) |
| `categories` / `tags` | id、code、label、taxonomy_version | unique(code, taxonomy_version) |
| 中間表 | spot_id、category_id/tag_id | 複合PK、逆引きindex |
| `spot_hours` | spot_id、day/date、open、close、state | spot_id+day/date |
| `installations` | id、consent_version、token_hash、last_event_at、deletion_state | token_hash unique |
| `interaction_events` | event_id、installation_id、session_id、spot_id、type、occurred_at、payload_min | event_id unique、occurred_at、installation_id |
| `data_deletion_requests` | id、installation_hash、status、requested_at、completed_at | status+requested_at |
| `daily_kpis` | date、dimension、counts | 5件未満の単位を生成しない |

### 8.3 マイグレーション

- Alembicを使用し、DDLの手編集を禁止する。
- CIで空DBへのupgrade、直前版からのupgrade、主要制約の検査を行う。
- production適用前にバックアップを取得し、破壊的変更はexpand → migrate → contractの順に分割する。
- taxonomy、推薦ルール、データ版を独立してバージョン管理する。

### 8.4 Freshness

| 属性        |     期限 | 期限超過時            |
| --------- | -----: | ---------------- |
| 名称・座標・説明  |   180日 | stale警告、月次レビュー継続 |
| 営業・閉業     |    30日 | 不明扱い。重大疑義は非公開    |
| 営業時間      |    30日 | `unknown` として警告  |
| 駐車場・二輪・通行 |    30日 | 安全影響時は非公開        |
| 経路・天気     | リアルタイム | 永続Sourceに保存しない   |

## 9. 主要シーケンス

### 9.1 推薦

```text
User → iOS: 条件確定
iOS → CoreLocation: 現在地取得
iOS → API: POST /recommendations + 嗜好集約
API → DB: 空間・公開・Freshness候補検索
API → Apple Maps: 往路/復路ETA
API → API: filter → score → diversity
API → Apple Maps: 上位候補の概要ルート
API → iOS: 最大5件 + warnings
iOS → User: 先頭1件を表示
```

### 9.2 リアクション

```text
User → iOS: 興味あり/なし/訪問済み
iOS → LocalStore: 状態を先に保存
iOS → User: 保存結果と取消を表示、次カードへ
[同意済み] iOS → EventQueue → Interaction API
[未同意] サーバ送信なし
```

### 9.3 分析撤回・削除

```text
User → iOS: 同意撤回または削除
iOS: 新規イベント停止 + 未送信削除
iOS → Privacy API: ID + deletion token
API: token hash照合 → 202（存在有無を同じ応答）
Worker: 稼働系を7日以内に削除 → tombstone記録
Backup: 復元時にtombstone適用、35日以内に世代消去
iOS: ID/token消去
```

## 10. セキュリティ・プライバシー

- TLS 1.2以上、DB・バックアップの保存時暗号化。
- 外部サービス鍵、DB資格情報、署名鍵は環境別Secret Storeで管理する。
- CIは短期資格情報を使用し、production Secretの読取を開発端末へ許可しない。
- 管理Worker / Review CLIはVPNまたはIDプロキシ配下とし、公開ルートを設けない。
- DBユーザーはAPI読取+必要なイベント書込、Worker更新、migration管理者に分ける。
- ログへ緯度経度、本文、installation ID、event ID、削除トークン、外部APIトークンを出力しない。
- 依存関係とコンテナの脆弱性をCIで検査し、重大度Critical/Highはproduction反映を止める。
- Privacy Policy、App Store Connect回答、`PrivacyInfo.xcprivacy`、実コードの送信先をリリースごとに照合する。

## 11. 環境・CI/CD

### 11.1 環境差分一覧

| 項目 | local | staging | production |
|---|---|---|---|
| iOS配布 | Simulator / 開発署名 | TestFlight内部 | TestFlight外部β |
| API | localhost、固定JSON可 | 実コンテナ | 実コンテナ |
| DB | Docker PostgreSQL/PostGIS | 専用DB | 専用DB |
| Spotデータ | fixture | 匿名化/公開データ | 承認済みCanonical |
| Apple Maps API | mock可 | 実API・別キー | 実API・別キー |
| WeatherKit | mock可 | 実サービス | 実サービス |
| ログ保持 | 任意、個人データ禁止 | 14日 | 30日 |
| バックアップ | 不要 | 日次7世代 | 日次7世代以上 |
| レート制限 | 無効可 | production相当 | 有効 |
| Secret | `.env`非追跡 | Secret Store | 別Secret Store |

### 11.2 パイプライン

1. pull requestでiOS/API lint、単体、OpenAPI検証、migration dry-run、Secret scanを行う。
2. main統合後に同一コミットSHAのコンテナを作成し、stagingへ自動反映する。
3. 契約、固定回帰、E2E、migration、監視疎通を実行する。
4. 承認ゲート後、同一イメージをproductionへ昇格する。
5. migration失敗または主要ヘルスチェック失敗時はアプリを切り戻し、DBは前方修正する。

## 12. 監視・障害対応

### 12.1 SLIと初期閾値

| 対象 | Warning | Critical | 一次対応 |
|---|---:|---:|---|
| Recommendation p95 | 4秒超/10分 | 5秒超/10分 | ETA、DB、候補数を切分け |
| 5xx率 | 2%超/5分 | 5%超/5分 | β停止判断、直近変更確認 |
| 候補表示成功率 | 95%未満/1時間 | 90%未満/1時間 | 0件と障害を分離分析 |
| CPU | 70%超/15分 | 85%超/10分 | 遅延・Worker競合確認 |
| memory | 75%超/15分 | 90%超/5分 | leak/OOM確認 |
| DB接続 | 70%超 | 90%超 | pool、遅いSQL確認 |
| backup | 24時間未成功 | 36時間未成功 | 手動取得、原因調査 |
| deletion SLA | 5日未完了 | 7日到達 | Worker再実行、責任者通知 |
| 月額費用 | 70%予測 | 90%予測 | 非必須Worker抑制 |

通知先は運用責任者の単一オンコール先とする。Severity 1（漏えい、安全上重大、全停止）とSeverity 2（主要機能継続不能）はβを停止し、原因・影響・再開条件を記録する。

### 12.2 構造化ログ

`timestamp / level / environment / service / request_id / route / status / duration_ms / candidate_count / warning_codes / error_code / rule_version / data_version` を記録する。座標や利用者識別子は含めない。

## 13. バックアップ・復旧

| 優先度 | 対象 | 分類 | 復旧方針 |
|---|---|---|---|
| P0 | 削除台帳、同意状態 | 必ず復旧 | DB backup + 復元直後に削除台帳再適用 |
| P0 | Canonical Spot、手動補正 | 必ず復旧 | 日次backup、監査履歴 |
| P1 | taxonomy、推薦・運用設定 | 必ず復旧 | DB + Git管理設定から復元 |
| P1 | Source台帳、採用関係 | 必ず復旧 | DB backup |
| P2 | 原文・取得物 | 再収集可能 | Source URL・版から再取得 |
| P2 | 生イベント | 可能な範囲 | 期限内backup。削除台帳を優先 |
| 対象外 | 端末リアクション | サーバに存在しない | 消失可能性を仕様に明記 |

- RPO 24時間、RTO 8時間。
- 日次バックアップを7世代以上保持し、個人関連データを含む世代は35日以内に失効させる。
- 月1回stagingへ復元し、件数、主要制約、PostGIS検索、削除台帳適用、API疎通を確認する。

## 14. 費用設計

| 区分 | 月額目標 | 制御 |
|---|---:|---|
| API container（staging + production） | 3,000円以内 | 最小インスタンス、staging休止可 |
| Managed PostgreSQL/PostGIS | 4,000円以内 | 小容量、保持期間制限 |
| 監視・ログ | 1,000円以内 | 無料枠、30日上限、本文非記録 |
| Apple Maps / WeatherKit | 既定枠内 | 呼出数監視、追加課金を自動契約しない |
| 予備 | 2,000円 | 為替、転送、バックアップ |

契約時の税込価格と為替で再見積し、合計10,000円を超える場合は契約しない。70%で通知、90%で収集Workerと非必須処理を抑制し、100%見込みで拡大を停止する。

## 15. 試験方針

### 15.1 レベル別

| レベル | 主対象 |
|---|---|
| 単体 | スコア境界、時間計算、状態遷移、同意、削除トークン |
| Contract | OpenAPI request/response、Problem、互換性 |
| 結合 | PostGIS検索、ETA往復、WeatherKit、イベント冪等、削除Worker |
| 回帰 | 要件8.4の固定7ケース、同一入力の決定論 |
| UI | S01〜S08、VoiceOver、Dynamic Type、44pt、色非依存 |
| E2E | 初回、再訪、0件、権限拒否、部分/全障害、Apple Maps失敗 |
| 非機能 | p95、成功率、レート制限、費用、バックアップ/復元 |
| データ | 7県、重複、Freshness、Source削除、レビュー滞留 |

### 15.2 リリース阻止条件

- 固定回帰ケース失敗。
- Severity 1・2の未解決不具合。
- Apple Maps Provider POC不合格。
- 九州7県のいずれかで候補取得・ナビ引き渡し未確認。
- Privacy文書、Manifest、App Store申告と実装の不一致。
- バックアップ復元未成功、削除SLA未検証、監視未通知。
- 月額見積10,000円超過。

## 16. 要件トレーサビリティ

| 基本設計タスク | 本書 | 主な要件 |
|---|---|---|
| BD-01 構成・シーケンス | 3、9 | RD-03、RD-12 |
| BD-02 API | 5 | RD-06、RD-11 |
| BD-03 ER・索引・migration | 8 | RD-08 |
| BD-04 取込・Canonical・Freshness | 8、関連設計書 | RD-07、RD-08 |
| BD-05 推薦 | 6 | RD-06 |
| BD-06 iOS | 4、7 | RD-04、RD-05、RD-10 |
| BD-07 構成・運用 | 10〜14 | RD-11、RD-12 |
| BD-08 試験 | 15 | RD-01〜RD-12 |

## 17. 設計判断と未決事項

### 17.1 本書で採用する判断

- `visited` は同一Spotを-12点とし、永久除外しない。
- 移動時間の第一候補をApple Maps Server APIとし、`Automobile` ETAを用いる。
- WeatherKit注意閾値を降水確率50%、風速10m/s、5℃未満、35℃以上とする。
- 端末嗜好をリクエストへ集約して渡し、APIは処理後に保存しない。
- production DBはアプリと同居させず、PostGIS対応のマネージドDBを採用する。

### 17.2 実装前に必要な作業

| ID | 作業 | 完了条件 | 責任 |
|---|---|---|---|
| O-01 | OpenAPIへ嗜好集約を追加 | v1.1.0契約試験成功 | SC |
| O-02 | Apple Maps Provider POC | 7.2の全条件合格 | SC / QC |
| O-03 | インフラADR | ベンダー、リージョン、税込見積、削除/backup条件承認 | SC / SO |
| O-04 | taxonomy v1 | 実データ分析と興味対応表承認 | DM / BU |
| O-05 | 県別リリースケース | 各県の最低ケースとカバレッジ指標承認 | BU / QC |
| O-06 | Privacy最終化 | 事業者、送信先、Manifest、申告の一致 | BU / SC |

O-01〜O-03は該当機能実装前、O-04〜O-06は外部β開始前の必須ゲートとする。

## 18. 実装順序

1. S01〜S08を固定JSONとモックClientで実装する。
2. OpenAPI v1.1.0、FastAPIスタブ、iOS APIClientを実装する。
3. Canonical公開スキーマ、migration、fixtureを実装する。
4. Data Workerとレビュー導線を既存収集設計に従って実装する。
5. 推薦ルール、決定論、固定回帰を実装する。
6. Apple Maps Provider POCを完了し、ETA・概要ルートを接続する。
7. WeatherKit注意表示と外部Map引き渡しを実装する。
8. 同意、Interaction、Privacy削除を実装する。
9. 監視、バックアップ、復旧、費用アラートを有効化する。
10. 九州7県E2Eとリリースゲートを実施する。

## 19. 承認事項

本書は基本設計書のため、次を一括してユーザー承認対象とする。

1. システム構成と責務分離。
2. Apple Maps Server APIを第一候補とするProvider方針とPOC基準。
3. `visited` の-12点、嗜好集約のAPI追加、多様性規則。
4. WeatherKit注意閾値と、推薦に使用しない方針。
5. マネージドPostGISを含むインフラ選定条件と費用配分。
6. 監視閾値、バックアップ優先度、リリース阻止条件。

承認後もO-03の具体ベンダー契約と、月額上限を超える変更は別途承認を必要とする。

## 20. 参照資料

- [MVP要件定義書 v1](mvp-requirements-v1.md)
- [MVP OpenAPI v1](mvp-openapi-v1.yaml)
- [Spotデータ収集 基本設計書 v1](spot-data-collection-basic-design-v1.md)
- [Privacy Policy草案 v1](privacy-policy-draft-v1.md)
- [Apple Maps Server API: ETA](https://developer.apple.com/documentation/applemapsserverapi/-v1-etas)
- [Apple Maps](https://developer.apple.com/maps/)
- [WeatherKit](https://developer.apple.com/jp/weatherkit/)

## 21. 変更管理

- 要件と異なる変更は、理由、対象RD、API・DB・Privacy・費用・試験への影響を変更記録へ残し、要件変更承認後に反映する。
- OpenAPIの破壊的変更は `/v2` またはβ利用者を含む承認済み移行計画を必要とする。
- 推薦ルール、taxonomy、Freshness、警告閾値は版を持ち、過去の評価結果を再現できるようにする。
- 安全、法令、データ利用条件に関する変更を通常の改善より優先する。
