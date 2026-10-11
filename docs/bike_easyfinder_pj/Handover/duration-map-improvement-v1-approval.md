---
title: 指定時間推薦・地図改善 v1 承認記録
published: 2026-10-10
description: 指定時間推薦、地図、現在地表示、画像後続設計の承認結果
tags: [mvp, recommendation, map, approval, handover, SC, approved]
category: Handover
draft: false
---

# 指定時間推薦・地図改善 v1 承認記録

## 承認結果

- 結果: **承認済み**
- 承認日: 2026-10-10
- 承認者: プロダクトオーナー（本チャットのユーザー）
- 承認方法: 添付計画に対するチャットでの明示的な実装指示
- 承認対象版: v1

## 承認対象

- 希望所要時間±15分を原則とする推薦
- 0件時だけ±60分まで15分刻みで行う段階拡張
- 提案画面の目的地地図
- 詳細画面の現在地再取得と目的地との2点表示
- 画像収集を後続設計とし、今回のコード実装から除外する判断

## 変更対象

- `../SystemDesign/mvp-basic-design-v1.md`
- `../Test/mvp-test-plan-v1.md`
- `../SystemDesign/spot-data-collection-basic-design-v1.md`
- `../tasks/sc-duration-map-improvement-v1-task.md`

## 留意事項

- 現在地は詳細画面で一度だけ再取得し、永続化せず画面終了時に破棄する。
- 経路線の描画と画像収集・表示は今回の受入条件に含めない。
- Procedure API同期は2026-10-10に実施した。保存先は `src/content/posts/management/bike_easyfinder_pj/` 配下。
- 同期SHA: 基本設計 `ecda2cc45dad`、収集設計 `20dfe88dc513`、テスト計画 `df62657600cd`、実装タスク `ecf70896f8d1`、公開タスク `8b5289771f20`、承認記録 `401793c99991`、テストエビデンス `68aa723a0cb2`。
