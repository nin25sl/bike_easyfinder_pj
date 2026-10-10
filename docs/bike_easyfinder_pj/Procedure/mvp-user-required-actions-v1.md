---
title: MVP限定β公開に向けたユーザー実施事項 v1
published: 2026-10-04
description: 九州7県を対象とするBike EasyFinder MVPの限定β公開前に、ユーザー本人の操作、判断または承認が必要な事項を実施順にまとめた手順書
tags: [mvp, procedure, release, user-action, sc]
category: Procedure
draft: false
---

# MVP限定β公開に向けたユーザー実施事項 v1

## 結論

現時点では、すぐにTestFlight限定βを開始できる状態ではない。ユーザー本人が実施する必要があるのは、次の7項目である。**最初に行うことは、Apple Developer環境の準備と、インフラ事業者を選定するための承認条件の提示である。**

1. Apple Developer Program、Mac、iPhoneを準備する。
2. Apple Maps Server APIの140経路POCを実測し、採用可否を承認する。
3. staging／productionのインフラ事業者、予算、ドメインを決定する。
4. 九州7県の公開Spot品質基準を決定し、目視レビュー結果を承認する。
5. Privacy Policyに必要な運営者情報を提示し、最終内容を承認する。
6. Mac、Simulator、実機でiOSビルドとリリースゲートを確認する。
7. TestFlightテスターを集め、限定β開始のGo／No-Goを承認する。

コード修正、DB migration、API構築、`PrivacyInfo.xcprivacy`作成、CI/CD、監視設定などは開発作業であり、ユーザー本人が実装する必要はない。必要な判断を本書の「回答テンプレート」で返した後、Codexへ実装・検証を依頼する。

## 1. 対象と確定済み事項

本書の対象は、TestFlightによる招待制限定βの開始までである。App Store一般公開は、限定βの結果を確認した後の別承認とする。

次の方針は確定済みのため、再選択しない。

- 公開対象: 福岡、佐賀、長崎、熊本、大分、宮崎、鹿児島の九州7県全域。
- UI: 既存のMVPデザイン案S01〜S08。
- 対象OS: iOS 17以上。
- 限定β: 30人、4週間、有効推薦セッション100件を最小判定母数とする。
- 月額上限: 外部APIとインフラの合計10,000円。超過時は再承認する。

現在、API、Canonical Spot、iOSの主要画面、WeatherKit連携、匿名分析・削除の実装骨格は存在する。一方、Apple Maps実測、Mac／実機試験、staging環境、Privacy公開文書、TestFlight運用は人のアカウントまたは判断が必要なため未完了である。

## 2. 実施順序と完了判定

| ID | ユーザーが行うこと | 完了条件 | 次工程 |
|---|---|---|---|
| U-01 | Apple開発環境を準備 | Program、Mac、実機、必要な権限を確認済み | U-02、U-06 |
| U-02 | Apple Maps POCを実測・承認 | 140経路の自動・手動ゲートがPASS | U-03、U-06 |
| U-03 | インフラとドメインを決定 | ADR-003の選定値を承認 | staging構築 |
| U-04 | Spot品質基準を決定・承認 | 7県すべてが承認済み閾値を満たす | staging投入 |
| U-05 | Privacy情報を提示・承認 | Policy、Manifest、申告案、実装が一致 | TestFlight申請 |
| U-06 | Mac／実機試験を実施 | 必須試験PASS、Severity 1・2が0件 | Go／No-Go |
| U-07 | TestFlight開始を承認 | 体制、期間、証跡、全ゲートが揃う | 限定β開始 |

U-01とU-03の準備は並行してよい。U-02、U-04、U-05、U-06を完了する前にU-07を承認しない。

## 3. U-01 Apple開発環境を準備する

### ユーザーが実施すること

- Apple Developer Programの有効なTeamを用意する。
- Xcode 15以降とXcodeGenを利用できるMacを用意する。
- iOS 17以上のiPhoneを少なくとも1台用意する。
- Apple Developer AccountでMaps ID、Maps対応秘密鍵、Key ID、Team IDを用意する。
- App IDに必要なCapabilityを設定できる権限と、App Store Connectでアプリを作成・配布できる権限を確認する。

### 秘密情報の扱い

秘密鍵、認証JWT、access token、App Store Connect API keyは、チャット、Git、Markdown、CSV、`.env.example`へ記載しない。Codexへ伝えるのは「準備済み／未準備」と、秘密値を除くエラー内容だけにする。

### 完了条件と証跡

- Apple Developer ProgramのTeam名とTeam IDを、非公開の管理場所で確認できる。
- MacでXcodeを起動し、対象Teamを選択できる。
- 実機をMacへ接続し、Developer Modeを有効にできる。
- 証跡には秘密値を含めず、Xcode版、macOS版、iPhone機種、iOS版だけを残す。

## 4. U-02 Apple Maps Server API POCを実測・承認する

### ユーザーが実施すること

1. `data_collection/config/apple_maps_poc_routes.csv`の140件を、九州7県各20件の実在経路へ置き換える。
2. 同じ出発条件でApple Mapsアプリに表示された時間を`apple_maps_seconds`へ入力する。
3. 短期access tokenを現在のPowerShellプロセスだけに設定する。
4. POCを実行する。
5. 高速不可ケースと往復ケースをApple Mapsアプリ上で目視確認する。
6. 利用規約、Privacy、帰属、1日利用枠を確認し、採用可否を承認する。

```powershell
$env:APPLE_MAPS_ACCESS_TOKEN = "<short-lived access token>"

.\.venv\Scripts\python.exe `
  data_collection\scripts\apple_maps_poc.py `
  --cases data_collection\config\apple_maps_poc_routes.csv `
  --dry-run

.\.venv\Scripts\python.exe `
  data_collection\scripts\apple_maps_poc.py `
  --cases data_collection\config\apple_maps_poc_routes.csv `
  --output data_collection\output\apple_maps_poc_results.jsonl `
  --summary data_collection\output\apple_maps_poc_summary.json

Remove-Item Env:APPLE_MAPS_ACCESS_TOKEN
```

### 完了条件

- 九州7県各20件以上、合計140件以上。
- API成功率99%以上。
- Apple Mapsアプリ表示時間との誤差が中央値15%以内、p95 30%以内。
- 高速不可ケースで有料高速利用0件。
- 最大5候補相当の処理時間がp95で4秒以内。
- 手動の経路目視と利用条件レビューが完了している。

スクリプトが終了コード`1`でも、必ずしも通信失敗ではない。手動ゲートが未承認の場合も`1`になるため、summaryの各項目で判断する。詳細は[Apple Maps Server API POC実行手順](./apple-maps-server-api-poc-execution-procedure-v1.md)を参照する。

### 残す証跡

- 実行日時、対象端末、出発条件。
- tokenを除いたsummary。
- 高速不可ケースと往復ケースの確認結果。
- PASS／FAILと判断理由。

実測結果ファイルは通常のGit管理へ含めない。判定結果だけを[Apple Maps Server API POC判定記録](../Handover/apple-maps-server-api-poc-v1.md)へ反映するようCodexへ依頼する。

## 5. U-03 インフラ事業者、予算、ドメインを決定する

### ユーザーが実施すること

- 月額税込見積、リージョン、PostGIS、バックアップ、ログ保持、通信費、停止時料金、サポートを比較する。
- 月額10,000円以内で利用する事業者とプランを承認する。
- stagingとproductionで使用するドメインまたはサブドメインを決める。
- 契約、支払情報の登録、アカウント所有者の設定を行う。
- Codexがデプロイ設定を作るために必要な権限の渡し方を決める。秘密値そのものはチャットへ貼らない。

必須条件は[ADR-003 Infrastructure Provider](../ADR/ADR-003-infrastructure-provider-pending.md)を参照する。事業者選定前にproduction相当の有料構成を作成しない。

### ユーザーが承認する値

- 事業者名とプラン:
- 日本向けリージョン:
- 月額見積:
- staging API URL:
- production API URL:
- DB／backupのRPO・RTO:
- ログ保持期間:
- 費用アラート通知先:
- アカウント責任者:

### 完了条件

- ADR-003の比較値と選定理由をユーザーが承認している。
- stagingとproductionのDB、ドメイン、シークレットが分離される計画になっている。
- 日次backup、月次restore試験、監視、費用アラートを設定できる。
- 承認後、Codexへstaging構築、CI/CD、監視設定を依頼できる。

## 6. U-04 九州7県のSpot品質を決定・承認する

`--minimum-spots-per-prefecture 1`は疎通確認用であり、限定βの品質基準ではない。ユーザーまたは品質責任者が、県別最低公開件数とカバレッジ条件を決定する必要がある。

### ユーザーが決定すること

- 県別最低公開Spot件数。
- 都市部、山間部、海沿い、温泉、景勝地など、最低限含めるカテゴリと地域条件。
- `review_required`候補の担当者、確認期限、承認・却下基準。
- 閉業、二輪駐車不可、通行不可、ライセンス不明を発見した場合の非公開判断。
- OSM等の帰属表示、Source削除要求、月次再収集の運用責任者。

### 承認値で監査する

```powershell
[int]$minimumSpotsPerPrefecture = Read-Host "承認済みの県別最低公開Spot件数"

docker compose run --rm api-migrate `
  bike-api audit-kyushu `
  --minimum-spots-per-prefecture $minimumSpotsPerPrefecture
```

### 完了条件と証跡

- 7県すべてが承認済みの最低件数を満たす。
- 各県で複数のカテゴリと地域条件を目視確認する。
- blockingのレビュー項目が0件である。
- 県別公開件数、サンプル確認結果、除外理由、確認者、確認日を残す。

不足や誤りが見つかった場合、ユーザーがSQLや収集コードを修正する必要はない。対象県、Spot名、期待値、根拠URLをCodexへ渡して再収集・補正を依頼する。

## 7. U-05 Privacy情報を提示し、最終内容を承認する

### ユーザーが提示する情報

- アプリ運営者の正式名称。
- Privacy問い合わせ先。
- Privacy Policyを公開するHTTPS URL。
- 利用するインフラ、ログ、Appleサービス等の委託先一覧。
- 対応する国・地域と、必要に応じた法務確認担当者。
- TestFlight開始日と、Policyの発効日。

### ユーザーが承認するもの

- Privacy Policy本文。
- アプリ内の分析同意、撤回、匿名データ削除の説明。
- `PrivacyInfo.xcprivacy`の内容。
- App Store ConnectのApp Privacy回答。
- 位置情報、匿名識別子、製品操作、診断情報の取扱いが実装と一致すること。

### 完了条件

- Privacy Policy URLがTestFlight外部テストから閲覧できる。
- Policy、アプリ内表示、Privacy Manifest、App Store Connect回答、実際の通信先が一致する。
- 同意前に分析イベントが送信されないこと、撤回と削除が動作することを確認済みである。
- 一般公開前の専門家レビュー要否と担当者を記録している。

ユーザーが`PrivacyInfo.xcprivacy`を手書きする必要はない。上記情報と承認を受領後、Codexへファイル作成と実装照合を依頼する。

## 8. U-06 Mac、Simulator、実機でリリースゲートを確認する

### プロジェクト生成と単体試験

Macで次を実行する。

```bash
cd ios/BikeEasyFinder
xcodegen generate
xcodebuild test \
  -scheme BikeEasyFinder \
  -destination 'platform=iOS Simulator,name=iPhone 15,OS=17.5' \
  -resultBundlePath TestResults/BikeEasyFinderTests.xcresult
```

利用可能なSimulator名やOSが異なる場合は値を変更し、実行環境を記録する。既存の`.xcresult`を上書きしない。

### Xcodeで確認すること

- Signing TeamとBundle IDを設定する。
- WeatherKit capabilityとentitlementを確認する。
- Simulatorでは`BIKE_API_BASE_URL=http://127.0.0.1:8000`を使用する。
- 実機ではMacのLAN URL、TestFlightではHTTPS staging URLを設定する。
- 位置情報の許可、拒否、制限、タイムアウトを確認する。
- 候補0件、Apple Maps起動失敗、API部分障害・全障害を確認する。
- VoiceOver、最大Dynamic Type、片手操作、Reduce Motion、ライト／ダークを確認する。
- WeatherKitの実データ、帰属、取得失敗時の継続動作を確認する。
- 匿名分析の同意前未送信、撤回、削除要求を確認する。

### 九州7県の確認

各県で最低1ケースを実施し、全体で都市部、山間部、海沿い、高速利用可、高速利用不可を含める。現地のテスターへ分担してよい。実機Apple Mapsへ正しい名称と座標が渡り、往復時間内の候補として不自然でないことを確認する。

### 完了条件と証跡

- iOS単体、UI、必須E2EがすべてPASS。
- 九州7県の実機確認が完了。
- Severity 1・2の既知不具合が0件。
- `.xcresult`、端末・OS、実行日時、PASS／FAIL／BLOCKED件数、秘密情報を除いた画面証跡を保管している。

不具合を見つけた場合、再現手順、期待結果、実結果、端末、OS、頻度をCodexへ渡す。ユーザーがSwiftコードを直接修正する必要はない。

## 9. U-07 TestFlight限定βを開始する

### ユーザーが実施すること

- App Store Connectでアプリ情報、TestFlight情報、Privacy Policy URLを登録する。
- 内部テスト後、必要に応じて外部テストのBeta App Reviewへ提出する。
- 九州7県を確認できる30人のテスターと連絡手段を確保する。
- 検証期間4週間と、最大2週間の延長条件を共有する。
- 問い合わせ、障害、Spot誤情報、削除要求の受付担当者を決める。
- リリースゲート結果を確認し、限定β開始のGo／No-Goを明示的に承認する。

### 開始前の最終チェック

- [ ] Apple Maps 140経路POCがPASS。
- [ ] stagingがHTTPS、実Provider、実WeatherKitで稼働。
- [ ] 九州7県のSpot品質監査と実機確認がPASS。
- [ ] Privacy Policy、Manifest、App Store申告、実装が一致。
- [ ] 必須自動試験、UI、E2E、復元試験がPASS。
- [ ] Severity 1・2が0件。
- [ ] 監視、費用アラート、日次backup、月次restore手順が有効。
- [ ] 30人、4週間、有効100セッションの運用計画がある。
- [ ] 問い合わせと緊急停止の責任者が決まっている。

承認事項は`docs/bike_easyfinder_pj/Handover/`へ記録し、`.cursor`の規定に従ってGitHubへPushする。外部公開や有料契約を伴う操作は、都度ユーザー承認後に行う。

## 10. ユーザーが実装しなくてよい事項

次は開発・運用担当へ依頼する事項であり、ユーザー本人がコードを書く必要はない。

- Privacy Manifestの作成とXcode targetへの追加。
- staging／productionのデプロイ、migration、secret manager設定。
- CI/CD、監視、rate limit、backup／restoreジョブ。
- 収集対象地域の同期、OSM収集、Canonical昇格、品質レポート生成。
- API、iOS、Workerの不具合修正と自動テスト追加。
- App Store Connectへ入力するPrivacy回答案の作成。
- リリースゲート報告書とHandover承認記録の作成。

## 11. Codexへ返す回答テンプレート

秘密鍵、token、パスワードを含めず、次を回答する。

```text
【Apple環境】
Apple Developer Program: 準備済み
Mac・Xcode: 準備済み
iPhone・iOS: Iphone17 
Maps ID等: 準備済み 

【インフラ】
選定事業者・プラン: AWS/Local
月額見積: 3000
リージョン: ap-northeast-1
stagingドメイン: 検討中
productionドメイン: 検討中

【Spot品質】
県別最低公開件数: 検討中。九州一円をカバーしたい。
必須カテゴリ・地域条件: なし。AIと決めたい。
レビュー責任者: わて

【Privacy】
運営者名: 中村友哉
問い合わせ先: easyfinderpj@gmail.com
Privacy Policy URL: 未取得
法務確認: 必要

【限定β】
開始希望日: 10/15
テスター30人:  募集中
問い合わせ担当: 中村友哉
最終承認者: 中村友哉
```

回答を受領後、開発側は不足実装、staging構築、Privacy成果物、試験手順、Handover承認記録を更新する。

## 12. 関連資料

- [MVPローカル構築・Release Gate手順](./mvp-local-build-and-release-gates-v1.md)
- [Apple Maps Server API POC実行手順](./apple-maps-server-api-poc-execution-procedure-v1.md)
- [MVP詳細設計](../SystemDesign/mvp-detailed-design-v1.md)
- [MVP要件定義](../SystemDesign/mvp-requirements-v1.md)
- [MVPテスト計画](../Test/mvp-test-plan-v1.md)
- [ADR-003 Infrastructure Provider](../ADR/ADR-003-infrastructure-provider-pending.md)
