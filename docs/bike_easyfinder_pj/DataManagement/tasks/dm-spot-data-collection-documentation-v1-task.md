---
title: Spotデータ収集機構 実装・収集結果ドキュメント作成タスク
published: 2026-10-10
updated: 2026-10-10
description: 実装済みのSpotデータ収集機構と九州7県の収集結果を、現行コードおよびDB実績に基づいて文書化する作業記録
tags: [data-collection, documentation, task, DM]
category: tasks
draft: false
---

# Spotデータ収集機構 実装・収集結果ドキュメント作成タスク

## 目的

実装済みのSpotデータ収集機構について、構成、実装範囲、実行方法、データ件数、品質状態、運用上の注意を、現行コードとDocker上のDBを正として整理する。

## 影響と変更概要

- 対象はドキュメントとDBの読み取り確認のみとし、収集データ、Worker、Backend、DBスキーマは変更しない。
- 旧手順書に残る未実装時点の説明とは分離し、2026-10-10時点の実装結果を新しい変更履歴文書へ記録する。
- 件数は、収集処理件数、現在のSourceレコード件数、名寄せ後Entity件数、公開済みCanonical Spot件数を区別する。
- 外部公開の依頼ではないためProcedure APIへは投稿せず、リポジトリ内の`docs`だけを更新する。

## タスク

- [x] `.cursor/rules`、既存設計書、既存手順書を確認する。
- [x] Docker上のDBから現在の収集・名寄せ・公開件数を再集計する。
- [x] `ModifyHistory`に実装内容と収集結果の文書を作成する。
- [x] frontmatter、部門タグ、記載件数、参照先を検証する。

## 完了条件

- 現在実装されている収集、再開、名寄せ、Export、Backend promotion、Schedulerの責務が確認できる。
- 九州7県について、Source別・県別の件数と、重複を除いた公開Spot件数が明示されている。
- 実行・確認に必要なコマンドと、削除してはいけないDocker操作が明記されている。
- 文書内の件数が同日にDBから取得した集計結果と一致する。

## 実施結果

- `ModifyHistory/spot-data-collection-implementation-result-v1.md`を作成した。
- 九州一括バッチ29,000件、最新Sourceレコード29,004件、公開済みCanonical Spot 25,934件をDBから再確認した。
- 最新Sourceレコードの状態内訳、県別公開件数、Entity状態、レビュー理由別件数、provenance件数を文書へ反映した。
- frontmatter、`DM`タグ、相対リンク4件、DB集計値との一致を検証した。
- Procedure APIへの外部投稿は依頼範囲外のため実施していない。
