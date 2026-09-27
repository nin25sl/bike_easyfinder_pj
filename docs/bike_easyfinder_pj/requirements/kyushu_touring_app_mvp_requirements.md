# 九州ツーリング提案アプリ MVP 要件定義書

## 1. プロジェクト概要

### 1.1 背景
バイクユーザーが「今日、少し走りたい」「数時間だけツーリングしたい」と考えた際、行き先を自分で検索・比較・選定する必要がある。

既存サービスは検索型・地図型が中心であり、ユーザーの使える時間や気分、興味に応じて「今日行ける場所」を提案する体験は限定的である。

本プロジェクトでは、ユーザーの現在地・利用可能時間・やりたいこと・過去の反応をもとに、ツーリング先候補を提案するiOSアプリを開発する。

### 1.2 MVPの目的
MVPでは、高機能なツーリングナビゲーションを完成させることではなく、以下の仮説を検証する。

> 「行き先を検索する」のではなく、「今から行ける場所を提案される」ことにユーザー価値があるか。

### 1.3 開発方針
- 開発人数: 1名
- 実装主体: AI / Codex
- 対象地域: 九州
- 初期POC地域: 福岡県および周辺地域
- 対象OS: iOS
- UI実装: SwiftUI
- 地図表示: MapKit
- 位置情報取得: CoreLocation
- Backend: FastAPI
- DB: PostgreSQL + PostGIS
- Routing候補: Valhalla
- Spot Master: OSM + 公的データ + 自前データ
- 外部POI API: 必要時のEnrichment用途
- 推薦方式: MVPではルールベース

---

# 2. MVPスコープ

## 2.1 MVPで実現すること

ユーザーが以下を入力する。

- 現在地
- 使える時間
- やりたいこと
- 高速道路利用可否

入力内容をもとに、時間内に往復できるツーリングスポットを提案する。

ユーザーは提案されたSpotに対して以下の操作を行える。

- 興味あり
- 興味なし
- 行ったことがある
- ここに行く

## 2.2 MVPで実現しないこと

以下はMVP対象外とする。

- アプリ内ターンバイターンナビ
- リアルタイム事故情報統合
- リアルタイム渋滞最適化
- 高度なAI/LLM推薦
- 複数日ツーリング
- 宿泊予約
- キャンプ場予約
- SNS機能
- ユーザー投稿型口コミ
- Android対応
- iPad最適化
- 九州全域の高精度な道路快走度評価

---

# 3. ターゲットユーザー

## 3.1 想定ユーザー

- 九州在住または九州を訪れるバイクユーザー
- 日帰りツーリング中心
- 行き先を決めることに負担を感じる
- 「数時間だけ走りたい」という利用シーンがある
- iPhoneを利用している

## 3.2 初期ユースケース

### UC01: 仕事終わりに2時間走る
ユーザーが現在地から2時間以内で往復可能なスポットを探す。

### UC02: 休日午前に4時間走る
4時間以内で景色やワインディングを楽しめる候補を提案する。

### UC03: 特定の目的で走る
「海」「カフェ」「景色」などを指定し、条件に合う候補を提案する。

---

# 4. ユーザー入力

## 4.1 必須入力

### 現在地
- CoreLocationから取得
- ユーザーが任意の地点を指定する機能は将来対応

### 利用可能時間

候補:

- 1時間
- 2時間
- 3時間
- 4時間
- 半日
- 1日

内部では分単位に変換する。

例:

```text
1時間 = 60
2時間 = 120
3時間 = 180
4時間 = 240
半日 = 360
1日 = 600
```

### やりたいこと

MVP候補タグ:

```text
scenic
sea
mountain
winding
cafe
food
onsen
roadside_station
night_view
historic
tourism
```

### 高速道路

```text
allow_highway = true / false
```

---

# 5. 推薦結果

## 5.1 表示項目

各Spotについて以下を表示する。

- Spot名
- 画像
- カテゴリ
- タグ
- 片道時間
- 往復時間
- 滞在時間目安
- 合計所要時間
- 距離
- 簡易説明

表示例:

```text
糸島 二見ヶ浦

🏍 片道 46分
⏱ 滞在目安 30分
🏠 帰宅まで合計 2時間08分

#海
#景色
#カフェ

[興味なし]
[行った]
[ここに行く]
```

## 5.2 提案件数

初期値:

```text
5〜10件
```

---

# 6. 推薦ロジック

MVPでは機械学習・LLMを使用せず、ルールベースで実装する。

## 6.1 候補抽出

```text
現在地
+
利用可能時間
+
興味カテゴリ
+
訪問履歴
+
興味なし履歴
↓
Spot候補
```

## 6.2 時間条件

各Spotについて以下を計算する。

```text
往路時間
+
Spot滞在時間
+
復路時間
=
total_duration
```

以下を満たすSpotのみ候補とする。

```text
total_duration <= available_time
```

### 例

```text
available_time = 180分

往路 = 55分
滞在 = 30分
復路 = 60分

total = 145分

→ 候補
```

```text
往路 = 100分
滞在 = 60分
復路 = 100分

total = 260分

→ 除外
```

## 6.3 MVPスコア

初期案:

```text
score =
  0.30 * interest_match
+ 0.25 * distance_score
+ 0.20 * novelty
+ 0.15 * popularity
+ 0.10 * weather_score
```

ただし初期実装では、さらに単純化してもよい。

---

# 7. Spotデータモデル

## 7.1 spots

```text
id
name
latitude
longitude
category
prefecture
city
description
opening_hours
closed_days
parking_available
motorcycle_parking
recommended_duration_minutes
rating
created_at
updated_at
```

## 7.2 spot_sources

```text
id
spot_id
source_type
external_id
source_url
source_updated_at
retrieved_at
```

source_type候補:

```text
osm
google
manual
tourism_api
user
```

## 7.3 tags

```text
id
name
```

初期タグ:

```text
sea
mountain
scenic
winding
cafe
food
onsen
roadside_station
night_view
historic
tourism
```

## 7.4 spot_tags

```text
spot_id
tag_id
```

## 7.5 user_spot_actions

```text
id
user_id
spot_id
action
timestamp
```

action候補:

```text
shown
interested
not_interested
visited
selected
route_started
```

### 注意

`shown` は必ず保存する。

理由:

```text
ユーザーが嫌い
```

と

```text
そもそも表示していない
```

を区別するため。

---

# 8. Source / Freshness管理

Spotデータを単一APIのレスポンスとして扱わない。

```text
複数Source
↓
Canonical Spot
```

という構造にする。

## 8.1 管理項目

```text
source
last_verified_at
expires_at
confidence
```

## 8.2 更新頻度の目安

| データ | 更新頻度 |
|---|---|
| Spot位置 | 30〜90日 |
| 営業時間 | 7〜30日 |
| Rating | 必要時 |
| Weather | 数時間 |
| 道路規制 | 数分〜数時間 |
| OSM道路 | 月次程度 |

単純な `spots.updated_at` のみで管理しないこと。

---

# 9. データ取得方針

## 9.1 Spot Master

基本方針:

```text
OSM
+
公的データ
+
自前データ
↓
Spot Master
```

## 9.2 Google Places

用途:

- 必要時のEnrichment
- 補足情報取得
- 画面表示時の追加取得

Google Places取得情報を、そのまま恒久保存する設計にはしない。

保存可能範囲・キャッシュ条件・利用規約はDiscoveryで必ず確認する。

## 9.3 OSM

用途:

- Spot
- 道路ネットワーク
- Routing用データ

OSM DataとOSM Tileを分離して考える。

公開OSM Tile Serverを本番アプリの恒常利用前提にはしない。

## 9.4 Map

iOSではMapKitを使用する。

```text
表示: MapKit
Road Data: OSM
Routing: Valhalla
```

---

# 10. Routing

## 10.1 Routing POC

以下を検証する。

```text
現在地
↓
Spot
↓
現在地
```

取得項目:

```text
distance
duration
polyline
highway usage
```

## 10.2 Routing Engine候補

Valhallaを第一候補とする。

検証対象:

```text
Valhalla motorcycle
vs
Valhalla auto
```

福岡周辺の10〜20ルート程度で比較する。

確認事項:

- 所要時間
- 不自然な経路
- バイク走行不可道路
- 高速道路選択
- mountain / winding routeへの適性

---

# 11. 名寄せ

複数データソースから取得したSpotの重複を統合する。

例:

```text
桜井二見ヶ浦
桜井二見ヶ浦 夫婦岩
二見ヶ浦
糸島 二見ヶ浦
```

## 11.1 初期判定ルール

```text
distance < 100m
AND
name_similarity > 0.8
```

必要に応じてcategory similarityも使用する。

曖昧なもの:

```text
needs_review = true
```

とする。

MVP段階では高度なAI名寄せは不要。

---

# 12. Weather

MVPでは高度な天候推薦は実装しない。

利用用途:

```text
降水確率 > 60%
→ warning

強風
→ warning

山間部 + 低温
→ warning
```

Weather Scoreはランキング補助程度とする。

---

# 13. 道路情報

Discoveryでは以下の取得可否を確認する。

- 通行止め
- 工事
- 事故
- 渋滞
- 積雪
- 路面情報

ただしMVPでは全て実装しない。

優先候補:

```text
通行止め
```

取得が難しい場合、P1へ延期する。

---

# 14. iOSアプリ

## 14.1 技術

```text
Swift
SwiftUI
MapKit
CoreLocation
```

## 14.2 Location Permission

MVPでは以下のみを基本とする。

```text
When In Use
```

起動直後に許可を要求しない。

推奨フロー:

```text
ユーザーが
「現在地から探す」
を選択
↓
Permission Request
```

---

# 15. Backend Architecture

```text
                  ┌───────────────┐
                  │    iOS App    │
                  │ SwiftUI       │
                  │ MapKit        │
                  └───────┬───────┘
                          │
                        HTTPS
                          │
                  ┌───────▼───────┐
                  │    FastAPI    │
                  │ Recommendation│
                  └───────┬───────┘
                          │
                  ┌───────▼───────┐
                  │ PostgreSQL    │
                  │ PostGIS       │
                  └───────┬───────┘

      ┌──────────────┬────┴───────┬─────────────┐
      │              │            │             │
     OSM          Places       Weather       Road
      │
      ▼
   Valhalla
```

---

# 16. API候補

## GET /spots/recommendations

Request:

```json
{
  "latitude": 33.5902,
  "longitude": 130.4017,
  "available_minutes": 180,
  "interests": [
    "scenic",
    "cafe"
  ],
  "allow_highway": false
}
```

Response:

```json
{
  "spots": [
    {
      "id": "spot_001",
      "name": "Sample Spot",
      "latitude": 33.0,
      "longitude": 130.0,
      "category": "scenic",
      "tags": [
        "sea",
        "cafe"
      ],
      "outbound_minutes": 50,
      "return_minutes": 50,
      "stay_minutes": 30,
      "total_minutes": 130,
      "distance_km": 65
    }
  ]
}
```

---

# 17. App Store / Privacy

Discovery期間で以下を決定する。

- Privacy Policy
- Location利用目的
- 収集データ
- Analytics
- Account管理
- Account deletion
- 外部APIへ送信する情報
- ユーザー行動履歴の保存期間

---

# 18. Discovery / Data契約

## 18.1 実施内容

期間目安:

```text
2〜3週間
```

優先度:

```text
P0
```

### タスク

- ユーザー仮説整理
- 主要ユースケース定義
- UX試作
- Spot taxonomy決定
- OSM利用条件確認
- Google Places利用条件確認
- Weather Provider比較
- Road情報Provider比較
- Routing候補比較
- Map表示方式決定
- Spot Schema v1作成
- Source Schema作成
- Freshness設計
- Privacy方針決定
- API費用概算
- 九州データの取得可否確認

## 18.2 Definition of Done

以下をすべて満たすこと。

- 九州7県のSpot取得方式が決定
- OSM利用方法とライセンス整理完了
- Google Placesの保存条件整理完了
- Weather Provider決定
- Road情報Providerの採用/非採用決定
- Map Provider決定
- Routing候補決定
- Spot Schema v1完成
- Source/Freshness Schema完成
- 主要ユースケース3件確定
- UXモック完成
- Privacy方針確定
- APIコスト概算完成

---

# 19. Data Foundation

## 19.1 実施内容

期間目安:

```text
4〜6週間
```

優先度:

```text
P0
```

### タスク

- PostgreSQL構築
- PostGIS有効化
- Spot Schema実装
- Source Schema実装
- Freshness管理実装
- OSM ingest
- POI ingest
- 九州/福岡データ取得
- Spot名寄せ
- Canonical Spot生成
- Valhalla POC
- Recommendation API POC
- Location-based検索
- Available Time Filter
- iOS Map表示POC

## 19.2 Definition of Done

以下のE2Eが動作すること。

```text
アプリ起動

↓

現在地取得

↓

ユーザー入力
- 3時間
- 景色
- カフェ

↓

Recommendation API

↓

PostGISから候補検索

↓

Valhallaで所要時間計算

↓

利用可能時間内の候補のみFilter

↓

5件程度表示
```

---

# 20. P0実装ロードマップ

| Week | 内容 | 成果物 |
|---|---|---|
| 1 | ユーザー仮説・ユースケース整理 | PRD v1 |
| 1 | UX | Wireframe / Mock |
| 1〜2 | OSM / Places / Weather / Road調査 | Data Contract |
| 2 | Spot taxonomy | Spot Schema v1 |
| 2 | Architecture | System Design |
| 3 | PostgreSQL + PostGIS | DB |
| 3 | OSM ingest | 福岡データ |
| 4 | POI ingest | Spot DB |
| 4 | 名寄せ | Canonical Spot |
| 5 | Valhalla | Routing API |
| 5 | Available Time Filter | Candidate API |
| 6 | iOS POC | Spot一覧 + Map |
| 6 | E2E | 現在地 → 候補 → Route |

---

# 21. P0終了時の完成イメージ

ユーザー操作:

```text
アプリ起動

↓

現在地から探す

↓

時間
3時間

↓

やりたいこと
景色
カフェ

↓

高速道路
使わない

↓

検索
```

Backend:

```text
現在地
↓
PostGIS Spatial Search
↓
Tag Filter
↓
Visited / Disliked Filter
↓
Valhalla Routing
↓
Available Time Filter
↓
Ranking
```

App:

```text
5〜10件のSpot表示
↓
ユーザー操作
- Interested
- Not Interested
- Visited
- Selected
```

---

# 22. MVP成功指標

候補KPI:

```text
recommendation_view_count
spot_interested_rate
spot_not_interested_rate
spot_selected_rate
route_started_rate
repeat_user_rate
```

特に重要なKPI:

```text
推薦表示
↓
「ここに行く」
```

の転換率。

MVPではRecommendation精度よりも、

```text
提案型UXそのものに需要があるか
```

を確認する。

---

# 23. 開発上の重要原則

## 23.1 Spot DB完成を待たない

九州全域のSpot DBを完成させてからApp開発を開始しない。

初期は福岡周辺100〜300Spot程度でもよい。

まず以下のUXを動かす。

```text
現在地
↓
時間入力
↓
目的入力
↓
提案
↓
反応
↓
目的地決定
```

## 23.2 DiscoveryとiOS開発を並行する

Discovery完了後に実装開始するWaterfallにしない。

Week 1終了時点から以下を並行する。

```text
Data調査
Backend POC
iOS UI POC
```

## 23.3 高度なAIは後回し

MVPでは以下を優先する。

```text
ルールベース推薦
↓
ユーザー行動データ収集
↓
推薦改善
↓
必要になった段階でML / AI
```

---

# 24. Codex実装ルール

Codexは以下の優先順位で実装する。

```text
P0
↓
P1
↓
P2
```

要求されていない機能を先回りして実装しない。

特に以下を勝手に追加しない。

- SNS
- Chat
- LLM Recommendation
- Real-time Navigation
- User Generated Content
- Android Support

## 24.1 実装単位

可能な限り以下の単位に分割する。

```text
1 Issue
=
1 Responsibility
```

例:

```text
#001 Create PostgreSQL environment

#002 Enable PostGIS

#003 Create spots schema

#004 Create tags schema

#005 Create user_spot_actions schema

#006 Create OSM ingest script

#007 Implement duplicate detection

#008 Setup Valhalla POC

#009 Implement recommendation API

#010 Create SwiftUI home screen
```

---

# 25. 最優先タスク

最初に実施すること。

```text
1. PRD確定

2. Spot taxonomy確定

3. Data Contract作成

4. Spot Schema作成

5. 福岡県のSpotを100〜300件取得

6. PostGISへ保存

7. Valhalla Routing POC

8. Recommendation API POC

9. SwiftUI画面作成

10. E2E検証
```

---

# 26. MVPの最終判断基準

以下が動作すればMVPとして成立する。

```text
ユーザーがiPhoneを開く
↓
現在地取得
↓
使える時間を入力
↓
目的を選択
↓
数秒以内に候補Spot表示
↓
行きたいSpotを選択
↓
ルートを確認
```

この段階では、

```text
最高のルートを作る
```

ことではなく、

```text
行き先を決める時間を短縮する
```

ことを最重要価値とする。
