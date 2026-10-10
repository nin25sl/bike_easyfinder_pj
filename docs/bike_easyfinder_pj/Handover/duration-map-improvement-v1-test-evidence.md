---
title: 指定時間推薦・地図改善 v1 テストエビデンス
published: 2026-10-10
description: 指定時間推薦とiOS地図改善の自動テスト結果および実機確認待ち項目
tags: [mvp, recommendation, map, test-evidence, handover, SC]
category: Handover
draft: false
---

# 指定時間推薦・地図改善 v1 テストエビデンス

## 対象

- Backendの希望所要時間事前選別、±15分判定、段階拡張、警告、決定的順位
- iOSの警告デコード・表示、Mock時間窓、提案画面の目的地地図
- iOS詳細画面の現在地再取得、現在地・目的地表示、取得失敗時フォールバック

## 自動テスト結果

### Backend

- 実施日: 2026-10-10
- 環境: Windows、Python仮想環境
- コマンド: `.\.venv\Scripts\python.exe -m pytest backend\tests --basetemp .pytest-tmp-backend-3`
- 結果: **16 passed、1 skipped**
- 補足: skipはPostGIS結合試験。Starlette非推奨警告とiCloud配下のpytest cache書込警告があるが、試験結果には影響しない。

### Lint

- コマンド: `.\.venv\Scripts\python.exe -m ruff check backend\src\bike_easyfinder_api\recommendation.py backend\tests\test_recommendation.py backend\tests\test_api.py`
- 結果: **変更対象の違反0件**
- IDE診断: 変更対象のエラー0件

### iOS

- `SearchViewModelTests` に警告保持、`MockRecommendationServiceTests` に±15分と段階拡張のケースを追加した。
- Swift 5.9／iOS 17 APIとの整合、protocol実装・呼出箇所、テスト型を静的レビューし、コンパイルブロッカーは検出されなかった。
- 現在の実行環境がWindowsのため、Xcodeによるビルド・単体テストは未実施。

## 実機確認待ち

- 4時間指定で原則3時間45分〜4時間15分の候補だけが表示される。
- ±15分に0件の場合、最初に候補が得られた拡張範囲が表示される。
- 提案画面で目的地ピンが見える。
- 詳細画面で再取得した現在地と目的地が同じ地図範囲に入る。
- 位置権限拒否・取得失敗時に目的地だけを表示し、説明が出る。
- VoiceOverと最大Dynamic Typeで地図周辺の説明と操作を確認できる。

## 判定

- Backend自動試験: **合格**
- iOSビルド・単体試験: **未判定（macOS/Xcodeが必要）**
- iPhone実機試験: **未判定（実機が必要）**
- 総合判定: **条件付き。iOS試験完了前にリリースしない**
