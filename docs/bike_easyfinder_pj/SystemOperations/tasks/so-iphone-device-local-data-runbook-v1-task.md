---
title: iPhone実機・ローカル収集データ接続手順書 作成タスク
published: 2026-10-10
updated: 2026-10-10
description: Windows上の収集済みPostGISデータをBackend経由でMac・iPhone実機から利用する手順を整備する作業記録
tags: [ios, device, local-api, procedure, task, SO]
category: tasks
draft: false
---

# iPhone実機・ローカル収集データ接続手順書 作成タスク

## 目的

WindowsのDocker/PostGISに保存された九州7県のCanonical Spotを、同一LAN上のMacでビルドしたBike EasyFinderからiPhone実機で確認できるようにする。

## 影響と変更概要

- 対象は実機起動手順の文書化とし、iOSアプリ、Backend、DBデータは変更しない。
- WindowsをDB/APIホスト、MacをXcodeビルド端末、iPhoneを実行端末とする最短構成を正とする。
- LAN用HTTPはローカル開発だけに限定し、TestFlightや外部ネットワークではHTTPS staging APIを必須とする。
- Appleの署名、Developer Mode、ローカルネットワーク権限は公式資料を基準にする。

## タスク

- [x] 現行iOS、Backend、Docker、既存手順書の接続条件を確認する。
- [x] Apple公式資料で実機署名、Developer Mode、ローカルネットワーク用途説明を確認する。
- [x] `Procedure`にWindows、Mac、iPhoneの実施順を記載する。
- [x] コマンド、設定キー、参照ファイル、内部リンクを検証する。

## 完了条件

- iPhoneから収集済みデータを使った推薦結果を表示できるまでの手順が、端末別に明確である。
- 事前条件、疎通確認、Xcode署名、権限許可、成功判定、トラブルシューティングが揃っている。
- ローカルHTTPと本番HTTPSの用途を混同しない。
- 現行実装上の不足または注意点を隠さず明記する。

## 実施結果

- `Procedure/iphone-device-local-canonical-data-runbook-v1.md`を作成した。
- WindowsをDB/APIホスト、MacをXcodeビルド端末、iPhoneを実行端末とする構成を記載した。
- Backend起動、LAN疎通、推薦API確認、XcodeGen、署名、Developer Mode、実機実行、九州外のlocation simulation、停止までを手順化した。
- 現行`Info.plist`に`NSLocalNetworkUsageDescription`がない点を実機実行前の必須確認事項として明記した。
- frontmatter、`SO`タグ、設定キー、内部リンク3件の存在を検証した。
- Procedure APIへの外部投稿は依頼範囲外のため実施していない。
