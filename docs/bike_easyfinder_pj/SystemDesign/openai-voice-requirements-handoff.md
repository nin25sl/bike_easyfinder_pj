---
title: OpenAI音声会話用 MVP要件引き継ぎ
published: 2026-09-23
description: ChatGPT iOSの音声会話でBike EasyFinderの要件と実装方針をレビューし、承認結果を記録するための引き継ぎ文書
tags: [mvp, requirements, handoff, openai, voice]
category: SystemDesign
draft: false
---

# OpenAI音声会話用 MVP要件引き継ぎ

> **目的とゴールの違い**
>
> - **目的** = Why（なぜ音声会話へ引き継ぐか）
> - **ゴール** = Done 条件（どの判断がテキストとして残れば完了か）

## 目次

<inline-toc preview="3"></inline-toc>

## 目的

ChatGPT iOSの音声会話で、Bike EasyFinderのMVP要件、承認待ち事項、先行実装との差分を順番に確認し、プロダクトオーナーの判断を構造化されたテキストとして残す。

## 背景

RD-01〜RD-04は承認済みで、RD-05〜RD-12は統合要件定義書に決定案を記載している。要件確定後に基本設計を作成するため、先行実装をそのまま正とせず、承認済み要件と基本設計を基準に改修範囲を決める必要がある。

音声会話の文字起こしは逐語記録にならない場合がある。そのため、音声だけで承認を完了せず、会話終了時に決定事項をテキストで復唱し、プロダクトオーナーが最終確認する。

## ゴール

- RD-05〜RD-12を順番に説明し、承認・修正・保留を記録する。
- A-01〜A-04を一件ずつ確認する。
- 要件、基本設計、実装の境界を混同しない。
- 音声会話終了時に、Codexへ渡せる決定記録を生成する。

## ファイル名

- 本書: `docs/bike_easyfinder_pj/SystemDesign/openai-voice-requirements-handoff.md`
- 要件定義書: `docs/bike_easyfinder_pj/SystemDesign/mvp-requirements-v1.md`
- API契約: `docs/bike_easyfinder_pj/SystemDesign/mvp-openapi-v1.yaml`
- 決定バックログ: `docs/bike_easyfinder_pj/SystemDesign/mvp-requirements-decision-backlog.md`

## 役割

GitHub接続済みChatGPTが、音声会話を始める前に読む自己完結型の案内兼レビュー進行台本。

## 本文

### 1. ChatGPTへの最初の指示

以下を音声会話開始前のテキストメッセージとして使用する。

```text
GitHubの nin25sl/bike_easyfinder_pj リポジトリを参照してください。

最初に次の順番でファイルを読んでください。
1. docs/bike_easyfinder_pj/SystemDesign/openai-voice-requirements-handoff.md
2. docs/bike_easyfinder_pj/SystemDesign/mvp-requirements-v1.md
3. docs/bike_easyfinder_pj/SystemDesign/mvp-openapi-v1.yaml
4. docs/bike_easyfinder_pj/SystemDesign/mvp-requirements-decision-backlog.md

読了後、まだレビューを開始せず、参照できたファイル名と現在の承認状態だけを簡潔に回答してください。
その後、同じチャットで音声会話を開始します。
```

### 2. プロジェクト概要

- プロダクト: 利用可能時間と興味から、時間内に往復できるバイクツーリング先を提案するiPhoneアプリ。
- 初期地域: 福岡市および周辺の日帰り圏。
- MVPの検証対象: 検索ではなく提案される体験が、目的地決定と走行開始につながるか。
- 対象外: 内蔵ターンバイターンナビ、Android、オフライン地図、UGC、SNS、ML・LLM推薦。
- 走行開始後: Apple Mapsへ引き渡す。

### 3. 承認済み事項

RD-01〜RD-04は2026-09-23にプロダクトオーナー承認済み。音声会話では、明示的な変更依頼がない限り再承認を求めない。

#### RD-01 検証仮説・KPI・リリース

- TestFlight限定β。
- 30人、4週間、有効推薦セッション100件。
- 主要KPIは `route_started / recommendation_view`。
- 20%以上で成功、10%以上20%未満で再検証、10%未満で中止候補。

#### RD-02 ユースケース

- 仕事終わり2時間、休日午前4時間、目的指定の3ケース。
- 必須入力は現在地、利用可能時間、興味、高速利用可否。
- 現在地へ戻る日帰り往復に限定する。

#### RD-03 MVP境界

- 候補最大5件、詳細、地図、フィードバック、Apple Maps連携。
- アカウントなし、匿名端末ID。
- アプリの責任は目的地の引き渡しまで。

#### RD-04 モバイル・地図・ナビ

- iPhone、iOS 17以上、SwiftUI、MapKit、CoreLocation。
- 位置権限は `When In Use` のみ。
- 外部ナビはApple Mapsのみ。

### 4. RD-05〜RD-12の決定案

詳細は要件定義書を正とする。以下は音声レビュー用の要約。

#### RD-05 UX

- 初回説明 → 現在地 → 時間 → 興味 → 高速可否 → 候補一覧 → 詳細 → 安全確認 → Apple Maps。
- 位置拒否、候補0件、部分障害、全障害を別状態として扱う。
- スワイプを必須にせず、VoiceOverとDynamic Typeへ対応する。

#### RD-06 推薦・API

- 合計時間は往路、滞在、復路、帰着余裕の合計。
- 帰着余裕は15分と走行時間の10%の大きい方を5分単位で切り上げる。
- 興味、時間適合、未訪問、データ信頼度、編集人気度、天気警告で決定論的に順位付けする。
- APIの正本は `mvp-openapi-v1.yaml`。

#### RD-07 Spotデータ

- 20件でData Contractを検証後、100〜300件へ拡大する。
- OSM、公共データ、手動確認からCanonical Spotを作る。
- Google PlacesはMVP不採用。

#### RD-08 スキーマ

- PostgreSQL + PostGIS、UUID、`GEOGRAPHY(Point, 4326)`。
- Canonical SpotとSourceを分離し、属性単位で出典を追跡する。
- 重複候補は100m以内かつ名称類似度0.8以上とし、手動承認する。

#### RD-09 Routing

- Valhallaを条件付き採用する。
- motorcycle profileを15ルートでPOCする。
- 不合格時はauto profile、次に商用APIを再評価する。

#### RD-10 天気・道路情報

- WeatherKitを警告用途で採用する。
- リアルタイム道路規制のアプリ内統合はMVP対象外。
- 現地標識、Apple Maps、外部の道路情報を優先する。

#### RD-11 プライバシー

- アカウントなし、生GPS軌跡なし、広告・トラッキングなし。
- 分析は明示同意したβユーザーだけ有効にする。
- 正確な現在地は推薦処理中だけ利用し、保存しない。

#### RD-12 基本設計・運用

- SwiftUI → HTTPS → FastAPI → PostgreSQL + PostGIS。
- データ取込はWorker、RoutingはPOC合格後のValhalla。
- local、staging、productionを分離する。
- 推薦API p95 5秒、β可用性99.0%、日次バックアップを要件とする。

### 5. 必ず確認する4件

以下を一件ずつ説明し、プロダクトオーナーが回答するまで次へ進まない。

#### A-01 データ保持期間

- 推奨: 生の行動イベント90日、端末と結び付けられない匿名集計13か月。
- 選択肢: 承認、期間を変更、保留。

#### A-02 月額上限

- 推奨: 限定βの外部API・インフラ合計を月額10,000円以内。
- Apple Developer Program、開発端末、ドメインは別管理。
- 選択肢: 承認、上限を変更、保留。

#### A-03 天気・道路情報

- 推奨: WeatherKit採用、リアルタイム道路規制はMVP対象外。
- 選択肢: 承認、変更、保留。

#### A-04 Routing

- 推奨: Valhallaを条件付き採用。motorcycle POC不合格時はauto、次に商用APIを再評価。
- 選択肢: 承認、変更、保留。

### 6. 音声レビューの進め方

音声会話を開始したら、ChatGPTは次の順序を守る。

1. 日本語で話す。
2. 最初に30秒程度でプロジェクトと承認状態を要約する。
3. RD-05からRD-12を一件ずつ説明する。
4. 各RDについて「承認」「修正」「保留」の回答を求める。
5. 一度に複数の判断を質問しない。
6. ユーザーの回答が曖昧な場合は、承認と推測せず確認する。
7. A-01〜A-04を必ず個別に確認する。
8. 実装方法の細部は、要件判断に必要な場合だけ説明する。
9. 先行実装を理由に要件を固定しない。
10. 会話終了前に決定結果をテキストで復唱する。

### 7. 音声での開始文

ChatGPTは次の内容から開始する。

```text
Bike EasyFinderの要件レビューを始めます。
RD-01からRD-04は承認済みです。
今回はRD-05からRD-12と、データ保持期間、月額上限、天気と道路情報、ルーティング方式の4件を確認します。
一度に一つずつ説明し、承認、修正、保留のいずれかを確認します。
まずRD-05の画面フローから始めてもよいですか。
```

### 8. 会話終了時の出力形式

音声会話終了前に、ChatGPTは以下のMarkdownをテキストで出力する。

```markdown
# Bike EasyFinder 要件レビュー決定記録

- 実施日: YYYY-MM-DD
- 参照コミット: <Git commit SHA。不明なら不明と記載>

## 承認

- RD-05: ...

## 修正

- RD-xx
  - 変更前: ...
  - 変更後: ...
  - 理由: ...

## 保留

- 項目: ...
- 必要情報: ...
- 決定期限: ...

## A-01〜A-04

- A-01: 承認／修正／保留
- A-02: 承認／修正／保留
- A-03: 承認／修正／保留
- A-04: 承認／修正／保留

## 基本設計への引き継ぎ

- ...

## 先行実装への影響

- 継続: ...
- 改修: ...
- 削除: ...
```

### 9. Codexへの戻し方

音声会話で生成した決定記録を、同じGitHubリポジトリのIssue、またはCodexのチャットへ貼り付ける。Codexには次のように依頼する。

```text
以下の要件レビュー決定記録を正として、
mvp-requirements-v1.md、mvp-openapi-v1.yaml、
mvp-requirements-decision-backlog.mdを更新してください。
変更後に要件間の矛盾を検査し、基本設計へ進める状態か報告してください。
```

### 10. 禁止事項

- 音声会話だけを最終承認記録にしない。
- ユーザーが明示していない判断を承認扱いにしない。
- `.env`、APIキー、削除トークン、正確な現在地を会話やGitHubへ貼らない。
- garbage内の旧文書を現行要件として扱わない。
- 先行iOSコードを承認済み基本設計として扱わない。

## 依存関係

- GitHub上の `nin25sl/bike_easyfinder_pj` リポジトリ。
- GitHubアプリを接続したChatGPTの対応チャット。
- ChatGPT iOSの音声会話。
- 決定結果を文書へ反映するCodex。

## 注意点

- GitHub接続の利用可否はChatGPTのプラン、ワークスペース、画面によって異なる。
- 音声会話でGitHubを直接参照できない場合は、先にテキスト会話で本書と要件定義書を読み込ませ、同じチャットで音声会話を開始する。
- 音声会話の文字起こしと、実際の発言が完全に一致しない可能性があるため、最終テキストを必ず確認する。

