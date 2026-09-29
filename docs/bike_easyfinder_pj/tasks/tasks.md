---
title: 公開までのタスク
published: 2026-09-27
updated: 2026-09-28
description: MVP限定β公開までの完了事項と残タスクを、依存順およびPIC別に管理する
tags: [mvp, SC]
category: tasks
draft: false
---

# 公開までのタスク

## PICの定義

- `[PIC: 人]`: 外部アカウントの契約・資格情報の発行、方針決定、承認、実機での官能確認、ストア提出を担当する。
- `[PIC: AI]`: 調査、設計、文書化、実装、自動テスト、試験結果の集計を担当する。
- 人からAIへ資格情報を渡す場合も、値をリポジトリ、タスク文書、試験証跡へ記録しない。
- 各タスクは、依存先が完了し、成果物または証跡が残った時点で完了とする。

## 完了済み

- [x] `[PIC: AI]` 承認結果を要件定義書、基本設計書、承認記録へ反映する。
- [x] `[PIC: AI]` MVP基本設計書を作成し、プロダクトオーナーの承認を反映する。
- [x] `[PIC: AI]` 詳細設計タスク `sc-mvp-detailed-design-v1-task.md` を作成する。
- [x] `[PIC: AI]` テスト計画書 `Test/mvp-test-plan-v1.md` の初版を作成する。承認は残タスク H-05で管理する。
- [x] `[PIC: AI]` 固定データによるiOS S01〜S08、端末内保存、主要エラー表示、単体テストを実装する。
- [x] `[PIC: AI]` Spotデータ収集Workerの基盤、初期DDL、収集アダプター、単体テストを実装する。
- [x] `[PIC: AI]` Apple Maps Server API POCの実行基盤、140件の入力雛形、自動判定を実装する。実API測定は残タスク H-01〜H-03、A-01で管理する。

## 残タスク

### 1. 人の決定・外部手続き・入力待ち

- [ ] **H-01** `[PIC: 人]` Apple Developer Programへ登録し、アプリのTeam・Bundle IDを確定する。
  - ブロック解除: Apple Maps Server API、WeatherKit、実機署名、TestFlight/App Store Connect。
- [ ] **H-02** `[PIC: 人]` Maps ID、Apple Maps Server API用秘密鍵・JWT発行手順を用意し、資格情報を安全な経路で実行環境へ設定する。
  - 完了条件: リポジトリへ秘密情報を保存せず、短期access tokenを発行できる。
- [ ] **H-03** `[PIC: 人]` POCの140件を実在する都市部・山間部・海沿い・高速可否の経路へ置換し、同一出発時刻にApple Mapsアプリの比較所要時間を記録する。
  - 依存: H-01、H-02。
- [ ] **H-04** `[PIC: 人]` UIデザイン案の画面構造、ブランド、写真運用、興味taxonomyなど事前決定6項目を承認または変更する。
  - 成果物: `SystemDesign/mvp-ui-design-proposal-v1.md` の承認記録。
- [ ] **H-05** `[PIC: 人]` MVPテスト計画書をレビューし、限定βのリリースゲートとして承認または修正指示する。
  - 成果物: `Test/mvp-test-plan-v1.md` の承認記録。
- [ ] **H-06** `[PIC: 人]` 限定βか一般公開か、テスト人数、期間、対象地域、実機試験協力者を決定する。
- [ ] **H-07** `[PIC: 人]` 採用するデータSourceの利用条件・ライセンスを承認し、AIのみでは確定できないSpot候補とtaxonomyをレビューする。
- [ ] **H-08** `[PIC: 人]` 運営者名、問い合わせ先、採用Provider・監視事業者を確定し、Privacy PolicyとApp Store申告に必要な事業者情報を提供する。

### 2. POCと詳細設計

- [ ] **A-01** `[PIC: AI]` Apple Maps Server APIを140経路で実測し、成功率、表示時間との誤差、p95、料金・Privacy・利用規約を集計して採用可否を記録する。
  - 依存: H-02、H-03。
  - 不合格時: 代替Provider比較をADRとして起票し、人へ選択を依頼する。
- [ ] **A-02** `[PIC: AI]` iOS状態・画面、API、データ、推薦、Provider、WeatherKit、Privacy、Workerの詳細設計（DD-01〜DD-08）を作成する。
  - 依存: H-04。Provider詳細はA-01にも依存する。
- [ ] **A-03** `[PIC: AI]` インフラ・運用、テスト、横断レビューの詳細設計（DD-09〜DD-11）を作成し、要件・基本設計・OpenAPI・DDL・Privacyの不整合を解消する。
  - 依存: A-01、A-02、H-05、H-06。
- [ ] **A-04** `[PIC: AI]` OpenAPIをv1.1.0へ更新し、validation、Problem Details、timeout、retry、冪等性、rate limit、warning codeを確定する。
- [ ] **A-05** `[PIC: AI]` DB物理設計を確定し、PostGIS型、制約、索引、migration、削除台帳、fixture、バックアップ対象を設計へ反映する。
- [ ] **A-06** `[PIC: AI]` ホスティング、DB、監視、バックアップの月額1万円以内の構成案と費用見積を作成する。
- [ ] **H-09** `[PIC: 人]` A-02〜A-06の詳細設計、インフラ構成、費用見積をレビューし、実装開始を承認する。

### 3. 本番機能の実装

- [ ] **A-07** `[PIC: AI]` 推薦API、候補抽出、固定スコア、多様性、決定性、Provider障害時の部分成功を実装する。
- [ ] **A-08** `[PIC: AI]` interaction API、同意前送信禁止、event queue、冪等処理、同意撤回、匿名データ削除とtombstoneを実装する。
- [ ] **A-09** `[PIC: AI]` Apple Maps ETA/Directions、cache、quota、token lifecycleとWeatherKit注意表示を実装する。
  - 依存: A-01、H-01、H-02。
- [ ] **A-10** `[PIC: AI]` iOSの固定推薦サービスを本番APIクライアントへ置換し、ルートポリライン、本番ETA、イベント送信、削除APIを接続する。
- [ ] **A-11** `[PIC: AI]` データ収集WorkerをPostGISへ結合し、canonical化、重複排除、Freshness、Source削除伝播、レビュー監査を実装する。
- [ ] **A-12** `[PIC: AI]` 承認済みSourceから九州7県の候補を収集し、レビュー待ち一覧と品質集計を作成する。
  - 依存: H-07、A-11。
- [ ] **H-10** `[PIC: 人]` レビュー待ちSpotのblocking項目を承認・却下し、限定β用の九州7県Ver0.1データを確定する。
- [ ] **A-13** `[PIC: AI]` local / staging / production、secret管理、CI/CD、監視、費用アラート、日次バックアップを構築する。
  - 依存: H-09。

### 4. 品質確認とリリース

- [ ] **A-14** `[PIC: AI]` Python 3.12でデータ収集テストを再実行し、公開APIのunit / contract / integration試験と固定7回帰ケースを追加する。
- [ ] **H-11** `[PIC: 人]` macOS、Xcode 15以降、XcodeGen、iOS 17系Simulator、署名Teamを利用可能にする。
- [ ] **A-15** `[PIC: AI]` macOS環境でiOS単体・UI・E2E試験を実行し、`.xcresult` と不具合一覧を保存する。
  - 依存: H-04、H-11、A-10。
- [ ] **H-12** `[PIC: 人]` 小型・標準・大型iPhone、VoiceOver、最大Dynamic Type、片手操作、Reduce Motionを実機またはSimulatorで確認する。
- [ ] **H-13** `[PIC: 人]` 九州7県で最低1ケースずつ、Apple Mapsへの引き渡し、往復経路、安全表示を実機確認する。
  - 依存: H-10、A-09、A-10。
- [ ] **A-16** `[PIC: AI]` 推薦APIのp95、成功率、可用性、rate limit、費用上限、障害フォールバック、バックアップ復元を検証する。
- [ ] **A-17** `[PIC: AI]` 実装と採用事業者を再棚卸しし、Privacy Policy、Privacy Manifest、App Store Connect回答案、リリースチェックリストを更新する。
  - 依存: H-08、A-08、A-09、A-13。
- [ ] **H-14** `[PIC: 人]` Privacy Policy、Privacy Manifest、App Store申告、スクリーンショット、説明文、年齢区分を最終確認する。
- [ ] **A-18** `[PIC: AI]` 全試験証跡を集計し、PASS / FAIL / BLOCKED、Severity 1・2件数、残存リスクを記載したQC判定資料を作成する。
- [ ] **H-15** `[PIC: 人]` QC判定資料を承認し、Severity 1・2が0件かつBLOCKEDがないことを確認して限定β公開可否を決定する。
- [ ] **H-16** `[PIC: 人]` App Store Connect / TestFlightへ提出し、審査対応と公開操作を行う。

## MVP公開をブロックしない後続タスク

- [ ] **A-19** `[PIC: AI]` `osm_pbf` の全国規模抽出処理を実装する。MVPの九州7県収集では必須にしない。
- [ ] **A-20** `[PIC: AI]` 限定βの提案件数、保存件数、再訪、継続率を集計し、サブスクリプション仮説の評価資料を作成する。
- [ ] **H-17** `[PIC: 人]` β成功後にFree上限、Plus初期機能、価格、課金実験の実施可否を承認する。
- [ ] **A-21** `[PIC: AI]` 課金承認後にStoreKit 2、App Store Server Notifications、entitlement、復元、ペイウォール、課金テストを設計・実装する。

## 推奨着手順

1. 人: H-01、H-02、H-04、H-05、H-06を並行して進める。
2. AI: 入力が揃ったものからA-01〜A-06を実施し、H-09の設計承認へ渡す。
3. AI: A-07〜A-13を実装し、人: H-07、H-10でデータ承認を行う。
4. AI: A-14〜A-18、人: H-11〜H-15で品質ゲートを完了する。
5. 人: H-16で限定βを公開し、公開後はA-20、H-17、A-21を別計画として扱う。
