---
title: Spotデータ収集機構 実装ドキュメント作成タスク
published: 2026-10-10
description: 実装済みのSpotデータ収集・名寄せ・Canonical公開処理と収集実績を文書化するSC作業記録
tags: [sc, task, data-collection, documentation]
category: tasks
draft: false
---

# Spotデータ収集機構 実装ドキュメント作成タスク

## 影響と変更概要

- システム開発部（SC）の成果物として、実装済みコードを基準に構成、処理フロー、CLI、DB、運用上の制約を整理する。
- 既存の計画書・基本設計書・他部門の運用文書は変更しない。
- PostgreSQL/PostGISを読み取り専用で照会し、取得件数とCanonical公開件数を再確認する。
- プログラムや収集データは変更せず、文書だけを追加する。

## タスク

- [x] `.cursor/rules` とシステム設計テンプレートを確認する。
- [x] 実装済みCLI、Adapter、収集Pipeline、Entity Resolution、Export、Backend Promotionを確認する。
- [x] Docker上のDBから最新成功Run、候補、Entity、公開Spot、レビュー残件を集計する。
- [x] 実装仕様書を `SystemDesign` に作成する。
- [x] 既知の制約、未承認Source、未登録スケジューラーを明記する。

## 完了条件

- [x] 実装の責務、入力、出力、依存関係、正常系、異常系を追跡できる。
- [x] 一括収集29,000件、最新Source別取得29,005件、公開Spot 25,934件の違いを説明できる。
- [x] 収集件数を県別・Source別に確認できる。
- [x] 文書のfrontmatterに部門コード `sc` が含まれる。

