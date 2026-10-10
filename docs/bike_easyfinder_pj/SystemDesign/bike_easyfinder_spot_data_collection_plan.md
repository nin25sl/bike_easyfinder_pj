# Bike EasyFinder Spotデータ収集 実装状況・不足機能・推奨データソース整理

更新日: 2026-10-05

## 1. 目的

Bike EasyFinder の Spot データ収集機構について、現行 GitHub 実装と基本設計をもとに、以下を整理する。

- 現在何が実装済みか
- 今後何を実装すべきか
- 人手を極力介さず、人は判断だけを行う構成にするための改善点
- 九州 MVP で利用候補となるデータソース
- 各データソースを個別にも一括でも収集できる実行方式

対象リポジトリ:

https://github.com/nin25sl/bike_easyfinder_pj

基本設計書:

https://github.com/nin25sl/bike_easyfinder_pj/blob/main/docs/bike_easyfinder_pj/SystemDesign/spot-data-collection-basic-design-v1.md

---

## 2. 現在の実装状況

### 2.1 実装済み

| 項目 | 状況 | 評価 |
|---|---|---|
| Docker + PostgreSQL/PostGIS | 実装済み | ◎ |
| N03行政区域同期 | 実装済み | ◎ |
| 都道府県・市区町村単位で収集 | 実装済み | ◎ |
| Source台帳 | 実装済み | ◎ |
| Sourceを個別指定して実行 | 実装済み | ◎ |
| 複数Sourceを一括実行 | 実装済み | ◎ |
| OSM Overpass収集 | 実装済み | ○ |
| OpenData汎用CSV/JSON/GeoJSON Adapter | 実装済み | ○ |
| OpenAI Web Searchによる候補発見 | 実装済み | ○ |
| Rawデータ管理 | 実装済み | ◎ |
| Observation管理 | 実装済み | ◎ |
| 品質チェック | 実装済み | ○ |
| 重複候補検出 | 実装済み | ○ |
| Review Task生成 | 実装済み | ○ |
| JSONL/CSV Export | 実装済み | ◎ |
| retry | 一部実装 | ○ |
| resume | 実装済み | ○ |

現在の構成は、Source Adapter を共通 Pipeline から呼び出す形になっており、Sourceを個別実行・複数同時実行できる土台は既にある。

例:

```bash
python -m collection_worker collect \
  --region-code 40130 \
  --sources osm_overpass,public_open_data,openai_web_discovery \
  --mode initial
```

この設計方針は維持する。

---

## 3. 未実装または不足している箇所

| 項目 | 状況 | 優先度 |
|---|---|---|
| OSM PBF大量取得 | Stubのみ | P0 |
| 実際の自治体OpenData登録 | 未実装 | P0 |
| Source横断 Entity Resolution / 名寄せ | 不十分 | P0 |
| 同一Spotへの自動統合 | 未実装 | P0 |
| All Sources Runner | 未実装 | P0 |
| Source単位実行wrapper | 実質CLIで可能だが明示scriptなし | P0 |
| 公式観光サイトAdapter | 未実装 | P1 |
| OpenAI Discovery後のURL Fetch | 未実装 | P1 |
| Web本文からAI属性抽出の自動連携 | 部品のみ | P1 |
| Source別License管理強化 | 一部実装 | P1 |
| Source別差分更新 | 不十分 | P1 |
| Field単位Canonical採用 | 未実装 | P1 |
| Webike/HondaGO等のDiscovery Adapter | 未実装 | P2 |
| Touring relevance score | 未実装 | P2 |
| Scheduler / 定期実行 | 未実装 | P2 |

---

## 4. 最重要の改善点

現状は概ね以下まで実装されている。

```text
Source
  ↓
Candidate
  ↓
Observation
  ↓
Quality Check
```

今後は以下へ拡張する。

```text
大量収集
  ↓
Candidate
  ↓
複数Source横断名寄せ
  ↓
同一Spot統合
  ↓
属性ごとのSource比較
  ↓
自動採用
  ↓
判断が必要なものだけReview Task
  ↓
人間は承認 / 却下のみ
```

特に重要なのは、Sourceごとに別Candidateとして保持されたデータを、同じSpotへ統合する Entity Resolution である。

例:

```text
OSM: 草千里ヶ浜
熊本県公式観光: 草千里ヶ浜
HondaGO: 草千里ヶ浜
Webike: 草千里ヶ浜
```

これらを別Spotとして残すのではなく、

```text
Canonical Spot: 草千里ヶ浜
```

へ統合し、属性ごとに最適Sourceを採用する。

---

## 5. 推奨データソース

以下は九州MVPで優先的に検討するデータソース候補。

### 5.1 OpenStreetMap

URL:

https://www.openstreetmap.org/

ライセンス:

https://www.openstreetmap.org/copyright

用途:

- Spot候補の大量発見
- 緯度経度
- POI種別
- 駐車場
- カフェ
- レストラン
- 温泉
- 景勝地
- 公園
- 海岸
- 山
- 史跡など

推奨用途:

**Canonical Base Source**

注意:

- ODbLの帰属表示が必要。
- 標準Tileサーバを大量収集用途に使わない。
- データそのものを利用する。

---

### 5.2 Geofabrik Kyushu OSM Extract

URL:

https://download.geofabrik.de/asia/japan/kyushu.html

用途:

- 九州全域のOSM PBF一括取得
- Overpassより大量取得向き
- 九州MVPの初期候補母集団生成

取得例:

```text
kyushu-latest.osm.pbf
```

推奨用途:

**Canonical Base Source / Bulk Collection**

現在の `OSMPBFAdapter` は Stub のため、P0で実装する。

---

### 5.3 クロスロードふくおか

URL:

https://www.crossroadfukuoka.jp/spot

対象:

福岡県

用途:

- 観光スポット
- 自然
- 山
- 海岸
- 景勝地
- 展望スポット
- 歴史施設
- 道の駅等

推奨用途:

**Official Verification / Candidate Discovery**

注意:

公開Webであることと、DBへの再配布・保存可否は別である。
各ページの利用規約・著作権条件を確認する。

---

### 5.4 あそぼーさが

URL:

https://www.asobo-saga.jp/spots/

対象:

佐賀県

用途:

- 景勝地
- 温泉
- キャンプ場
- 道の駅
- 自然
- 観光施設
- 駐車場情報

推奨用途:

**Official Verification / Candidate Discovery**

---

### 5.5 ながさき旅ネット

URL:

https://www.nagasaki-tabinet.com/guide

対象:

長崎県

用途:

- 景勝地
- 展望スポット
- 島
- 温泉
- 観光施設
- 歴史
- 道の駅候補

推奨用途:

**Official Verification / Candidate Discovery**

---

### 5.6 もっと、もーっと！くまもっと。

URL:

https://kumamoto.guide/spots

対象:

熊本県

用途:

- 阿蘇
- 景勝地
- 自然
- 温泉
- 展望所
- 歴史
- レジャー
- 道の駅等

推奨用途:

**Official Verification / Candidate Discovery**

Bike EasyFinderとの相性は非常に高い。
阿蘇・ミルクロード・大観峰周辺等のツーリング候補検証に有効。

---

### 5.7 ツーリズムおおいた

URL:

https://www.visit-oita.jp/spots/lists

対象:

大分県

用途:

- 自然景観
- 温泉
- 道の駅
- グルメ
- レジャー
- 歴史施設

推奨用途:

**Official Verification / Candidate Discovery**

---

### 5.8 みやざき観光ナビ

URL:

https://www.kanko-miyazaki.jp/spot

対象:

宮崎県

用途:

- 高千穂
- 都井岬
- えびの高原
- 日南エリア
- 海岸
- 山
- 景勝地

推奨用途:

**Official Verification / Candidate Discovery**

---

### 5.9 かごしまの旅

URL:

https://www.kagoshima-kankou.com/guide

対象:

鹿児島県

用途:

- 桜島
- 霧島
- 佐多岬
- 屋久島
- 景勝地
- 温泉
- 道の駅
- 公園
- 歴史施設

推奨用途:

**Official Verification / Candidate Discovery**

---

### 5.10 HondaGO BIKE LAB 九州・沖縄

URL:

https://hondago-bikerental.jp/bike-lab/area/kyushu-okinawa

用途:

- バイク向けツーリングスポット発見
- ツーリングロード発見
- ライダー向け人気エリア判定
- Touring relevance算出

推奨用途:

**Discovery Source**

Canonicalデータの正本ではなく、

```text
motorcycle_media_mentions
```

等のシグナルとして使う。

例:

```json
{
  "touring_relevance": 0.85,
  "reasons": [
    "motorcycle_media_mentions",
    "scenic_road_nearby"
  ]
}
```

注意:

記事本文や画像をそのままDBへ転載しない。
利用規約を確認し、URL・Spot名・事実情報・派生特徴の利用に留める。

---

### 5.11 Webike Plus

URL:

https://news.webike.net/

九州ツーリング例:

https://news.webike.net/?p=254857

用途:

- 九州ツーリングロード
- ライダー視点のおすすめSpot
- 絶景ロード
- 季節情報
- バイク向け立寄り先

推奨用途:

**Discovery Source**

HondaGOと同様に、

```text
「観光地として存在するか」
```

ではなく、

```text
「バイクで行きたい場所か」
```

を評価するSourceとして利用する。

---

## 6. Sourceの役割分担

### Base Source

大量候補の母集団を作る。

```text
OpenStreetMap
Geofabrik PBF
自治体OpenData
```

主な属性:

- name
- latitude
- longitude
- category
- address
- POI種別

---

### Official Verification Source

現在状態や正確な属性確認に使う。

```text
福岡県公式観光
佐賀県公式観光
長崎県公式観光
熊本県公式観光
大分県公式観光
宮崎県公式観光
鹿児島県公式観光
施設公式サイト
自治体公式サイト
```

主な属性:

- official_name
- opening_hours
- business_status
- parking
- access
- official_url

---

### Touring Discovery Source

Bike EasyFinder独自価値の算出に使う。

```text
HondaGO
Webike Plus
その他バイク専門メディア
```

主な派生属性:

- touring_relevance
- scenic
- winding
- biker_popular
- scenic_road_nearby
- cafe_stop
- sunset
- mountain
- sea
- historic
- onsen

---

## 7. 実装するSource Adapter構成

推奨:

```text
data_collection/
└─ src/
   └─ collection_worker/
      └─ adapters/
         ├─ osm_overpass.py
         ├─ osm_pbf.py
         ├─ open_data.py
         ├─ official_web.py
         ├─ touring_media.py
         ├─ openai_discovery.py
         └─ manual.py
```

Sourceごとに完全に別ロジックを複製するのではなく、Adapterを共通化する。

例:

```text
kumamoto_tourism
  ↓
official_web adapter

fukuoka_tourism
  ↓
official_web adapter

miyazaki_tourism
  ↓
official_web adapter
```

---

## 8. Source単位の個別実行

Sourceごとの薄いwrapperを用意する。

```text
scripts/
└─ sources/
   ├─ collect_osm_pbf.py
   ├─ collect_osm_overpass.py
   ├─ collect_fukuoka_tourism.py
   ├─ collect_saga_tourism.py
   ├─ collect_nagasaki_tourism.py
   ├─ collect_kumamoto_tourism.py
   ├─ collect_oita_tourism.py
   ├─ collect_miyazaki_tourism.py
   ├─ collect_kagoshima_tourism.py
   ├─ collect_hondago.py
   ├─ collect_webike.py
   └─ collect_openai_discovery.py
```

例:

```bash
python scripts/sources/collect_kumamoto_tourism.py
```

---

## 9. 一括実行

別途、

```text
collect_all.py
```

を用意する。

例:

```bash
python collect_all.py --region kyushu
```

処理:

```text
1. OSM PBF
2. OpenData
3. 7県公式観光サイト
4. HondaGO
5. Webike
6. OpenAI Discovery
7. Normalize
8. Entity Resolution
9. Field Source Selection
10. Quality Check
11. Review Task生成
12. Export
```

---

## 10. Entity Resolution

最優先で強化する。

現在:

```text
source_key + source_record_id
```

をベースにCandidateが分離される。

今後:

```text
name_similarity
distance
address
official_url
phone
source_category
```

等を使って同一Spot判定する。

例:

```text
distance <= 100m
AND
name_similarity >= 0.8
```

だけでなく、複数指標によるスコアリングを行う。

例:

```text
+40 name exact/near match
+30 distance < 50m
+15 address一致
+10 official_url一致
+5 category一致
```

一定以上なら自動merge。

中間スコアならReview Task。

---

## 11. Field単位Canonical採用

同一Spotへ統合後、属性単位でSourceを選択する。

例:

```text
name
→ 公式観光

coordinate
→ OSM

opening_hours
→ 施設公式

parking
→ 施設公式 / OpenData

touring_relevance
→ HondaGO / Webike / internal score
```

Source全体に固定順位を付けるのではなく、Fieldごとに評価する。

---

## 12. 人間が行う作業

目標は、人間が調査・入力をしないこと。

人間の作業は以下だけとする。

```text
承認
却下
保留
Source利用可否判断
重大なSource競合の判断
```

例:

```text
SOURCE_CONFLICT

Spot:
草千里ヶ浜

営業時間候補:
公式観光: 09:00-17:00
施設公式: 09:00-16:30

推奨:
施設公式を採用

[承認]
[却下]
[保留]
```

---

## 13. 優先実装順

### P0

1. OSMPBFAdapter実装
2. 九州7県のOpenData Source登録
3. Entity Resolution
4. Source個別実行wrapper
5. collect_all.py

### P1

6. official_web Adapter
7. OpenAI Discovery → URL Fetch
8. Web本文 → Structured Output
9. Field単位Canonical Source採用
10. 差分更新
11. License/robots/terms管理強化

### P2

12. HondaGO Adapter
13. Webike Adapter
14. Touring relevance score
15. Scheduler
16. 差分通知/Review Task自動生成

---

## 14. 推奨最終構成

```text
                  ┌─ OSM PBF
                  ├─ OpenData
                  ├─ 福岡観光
                  ├─ 佐賀観光
                  ├─ 長崎観光
Collect All ──────┼─ 熊本観光
                  ├─ 大分観光
                  ├─ 宮崎観光
                  ├─ 鹿児島観光
                  ├─ HondaGO
                  ├─ Webike
                  └─ OpenAI Discovery
                          │
                          ▼
                    Observation
                          │
                          ▼
                  Entity Resolution
                          │
                          ▼
                   Canonical Spot
                          │
                          ▼
                 Field Source Select
                          │
                 ┌────────┴────────┐
                 ▼                 ▼
             Auto Accept       Review Task
                                    │
                                    ▼
                              Human Decision
```

---

## 15. 結論

現在の `data_collection` は、データ収集基盤としては既に十分良い構造を持っている。

特に、

- Source Adapter方式
- Observation分離
- Provenance保持
- Review Task
- PostgreSQL/PostGIS
- Source個別指定
- 複数Source同時実行

は、そのまま維持してよい。

今後重要なのは、収集Sourceを増やすだけではなく、

```text
大量収集
→ 自動名寄せ
→ 自動統合
→ Field単位Source選択
→ 人間は判断のみ
```

へ進化させることである。

MVPの次の実装対象としては、以下4点を最優先とする。

```text
1. OSM PBF
2. 九州OpenData Source分離
3. Entity Resolution
4. collect_all
```

この4点が完成すると、九州7県を対象とした大量収集を自動化し、人手作業を大幅に減らせる。
