---
title: MVP テスト実行 QC引継ぎ v1
published: 2026-09-27
description: QCが現行実装の自動テストと手動確認を実行し結果を記録するための引継ぎ
tags: [mvp, test, qc, handover]
category: Handover
draft: false
---

# MVP テスト実行 QC引継ぎ v1

## 引継ぎの目的

本書は、QC担当者が現行実装に対して実行可能な試験を再現し、証跡と判定を残すための作業指示である。全体方針と将来の試験範囲は `../Test/mvp-test-plan-v1.md` を正本とし、本書では今回の実行対象、準備、コマンド、期待結果、記録方法を具体化する。

## 現在の引継ぎ状態

- 引継ぎ日: 2026-09-27
- 開発側事前確認: Pythonテスト17件成功
- QC判定: 未実施
- リリース判定: 対象外。現行実装は固定データ版であり、限定βの全リリースゲートを満たしていない
- QC実行対象: Python自動テスト、iOS単体テスト、現行iOS画面のスモーク確認
- QC実行対象外: 未実装の公開API、S01〜S08完成フロー、永続化、分析・削除、WeatherKit、Provider結合、負荷、バックアップ・復元

## 対象成果物

### テスト計画と設計根拠

- `docs/bike_easyfinder_pj/Test/mvp-test-plan-v1.md`
- `docs/bike_easyfinder_pj/SystemDesign/mvp-basic-design-v1.md`
- `docs/bike_easyfinder_pj/SystemDesign/mvp-ui-design-proposal-v1.md`
- `docs/bike_easyfinder_pj/SystemDesign/mvp-requirements-v1.md`

### 今回追加・更新したテスト

- `data_collection/tests/test_pipeline.py`
- `ios/BikeEasyFinder/BikeEasyFinderTests/MockRecommendationServiceTests.swift`
- `ios/BikeEasyFinder/BikeEasyFinderTests/SearchViewModelTests.swift`
- `ios/BikeEasyFinder/BikeEasyFinderTests/TouringSpotTests.swift`
- `ios/BikeEasyFinder/BikeEasyFinder/Services/RecommendationService.swift`

既存の `data_collection/tests/test_apple_maps_poc.py` もPythonテスト一式に含まれる。ただしApple Maps実APIの140経路実測ではなく、入力雛形と判定ロジックの単体テストである。

## QC開始前の確認

1. 実行対象のコミットIDまたは受領時点のブランチ名を記録する。
2. `git status --short` を保存し、試験対象外のローカル変更が混在していないことを確認する。
3. `.env`、APIキー、Apple Maps tokenなどの秘密情報を証跡へ添付しない。
4. Pythonは3.12系、iOSはXcode 15以降とiOS 17系Simulatorを使用する。
5. iOSプロジェクト生成にはXcodeGenが必要である。
6. 実行日時、OS、Python、Xcode、Simulator、端末モデルを試験結果へ記録する。

## QC 01 Python自動テスト

### 目的

データ収集Workerの設定、正規化、URL安全性、OpenAI引用、Apple Maps POC補助ロジック、Sourceポリシーを確認する。

### Windows PowerShellでの実行

リポジトリルートで実行する。

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest data_collection/tests --basetemp .pytest-tmp -ra
```

仮想環境が未作成の場合は、Python 3.12の仮想環境へ `data_collection` のtest依存関係を導入してから実行する。依存関係の追加や更新はQC判断で行わず、導入に失敗した場合は環境不備として開発へ返却する。

### 期待結果

- 17件がすべてPASSする。
- ERROR、FAILED、XPASS、XFAILがない。
- 実行中に外部APIへ接続しない。
- APIキーやURLクエリ内の秘密値がログへ出ない。

### 主な確認内容

- 未知または未承認のSourceを拒否する。
- OpenAI discoveryはAPIキーなしで開始しない。
- dry-run結果にAPIキーを含めず、予算と `store: false` を示す。
- URLの危険なscheme、資格情報、追跡queryを拒否または除去する。
- OpenAI生成候補は引用URLがない場合に採用しない。
- Apple Maps POC雛形が7県140件と高速不可28件を含む。

## QC 02 iOS単体テスト

### 目的

固定データ版の推薦絞り込み、最大件数、決定性、時間表示、興味選択、ViewModel状態遷移を確認する。

### macOSでの実行

```bash
cd ios/BikeEasyFinder
xcodegen generate
xcodebuild test \
  -scheme BikeEasyFinder \
  -destination 'platform=iOS Simulator,name=iPhone 15,OS=17.5' \
  -resultBundlePath TestResults/BikeEasyFinderTests.xcresult
```

指定Simulatorが存在しない場合は、利用可能なiOS 17系iPhoneへ変更し、変更後の名前とOS版を結果へ記録する。`TestResults` が既に存在する場合は、既存証跡を上書きせず別名を指定する。

### 期待結果

- `MockRecommendationServiceTests` がすべてPASSする。
- `SearchViewModelTests` がすべてPASSする。
- `TouringSpotTests` がすべてPASSする。
- build error、test failure、クラッシュがない。
- 同一入力を2回実行した候補ID順が一致する。
- 検索失敗時に以前の候補を新しい結果として表示しない。

### 補足

Windows環境ではXcodeを実行できないため、開発側ではiOSテストを未実行である。コンパイルエラーを含め、QC実行結果を初回の正式結果とする。

## QC 03 現行iOSスモーク確認

### 前提

現行画面はUIデザイン案の最終形ではない。S01、S02、S04単一カード、S06、S07確認画面、S08は未実装である。このスモーク確認は現行の固定データ版が破綻なく動作することだけを対象とし、UIデザイン案への適合判定には使用しない。

### 手順と期待結果

1. アプリを新規インストール状態で起動する。
   - 「行き先を見つける」画面が表示され、起動直後に位置権限ダイアログを出さない。
2. 「現在地から探す」を押す。
   - 初めて位置権限が要求される。
3. 位置情報を許可する。
   - 現在地取得中を経て「現在地を取得しました」と表示する。
4. 時間、興味、高速道路利用可否を変更する。
   - 「おまかせ」と個別興味が同時選択にならない。
5. 「この条件で候補を探す」を押す。
   - 処理中はボタンが無効になり、最大5件の候補または0件状態を表示する。
6. 1時間、興味を温泉に設定して検索する。
   - 「条件に合う候補がありません」と表示し、条件が自動で緩和されない。
7. 候補の詳細を開く。
   - 地図、概要、合計時間、往路、滞在、復路、距離、推薦理由を表示する。
8. 「ここに行く（Apple Maps）」を押す。
   - Apple Mapsへ目的地を渡す。Simulatorで失敗した場合は座標コピーを含むエラー導線を確認する。
9. アプリの位置権限を拒否して再度検索を開始する。
   - 必要理由と設定アプリへの導線を表示する。

### 追加する手動確認

- iPhone SE相当、標準サイズ、大型iPhoneの各Simulatorで主要文言が欠けない。
- Dynamic Type最大で主要ボタンへ到達できる。
- VoiceOverでボタン、選択値、地図のラベルを識別できる。
- ライト・ダーク両モードで文字と状態を判別できる。

現行UIでデザイン案との差分を検出した場合は既知未実装として記録し、クラッシュ、操作不能、誤った状態遷移、アクセシビリティ上の重大問題は不具合として起票する。

## 未実装のため保留する試験

次の項目はQC未実施ではなく、実装待ちの `BLOCKED` として記録する。

- TP-001: S01からS07までの初回E2E。
- TP-002: S02から前回条件を使う再訪E2E。
- TP-003: S06興味あり一覧と再計算。
- TP-005: 公開APIの200空配列Contract。
- TP-006、TP-007: Provider部分障害、全障害、503・504。
- TP-008: 完成版S07のApple Maps失敗処理。
- TP-010: 分析同意、撤回、匿名データ削除。
- 固定回帰7ケースの正式API fixture。
- PostGIS結合、イベント冪等、削除Worker、WeatherKit。
- 推薦API p95、成功率、可用性、rate limit、費用。
- バックアップ・復元、監視通知、九州7県実機確認。

BLOCKED項目は合格扱いにせず、機能実装後にテスト計画と本引継ぎを更新してQCへ再依頼する。

## 証跡として保存するもの

- 対象コミットIDまたはブランチ名。
- 実行環境と実行日時。
- Pythonのpytestコンソール出力。
- iOSの `.xcresult`。
- スモーク確認の画面キャプチャ。位置座標、通知、個人情報、tokenはマスクする。
- FAIL時の再現手順、期待結果、実結果、ログ、スクリーンショットまたは動画。
- PASS、FAIL、BLOCKED、NOT RUNの件数と総合判定。

証跡はリポジトリへ直接コミットせず、チームで定めたQC保管先へ置く。保管先が未決定の場合は、秘密情報を除いた結果サマリーだけを本書末尾へ追記し、添付先の決定を依頼する。

## 不具合起票ルール

不具合には次を含める。

- タイトル。
- Severity 1〜4。
- 対象コミット、端末、OS、環境。
- 前提条件と最小再現手順。
- 期待結果と実結果。
- 再現率。
- 関連するテストIDまたはテストクラス名。
- ログ、画像、動画などの証跡。
- 秘密情報を除去したことの確認。

Severity 1は安全、秘密情報漏えい、データ復元不能、全面停止、Severity 2は主要ユースケース不能、誤った時間内判定、Privacy違反、回避困難なクラッシュとする。Severity 1・2が1件でもあれば不合格である。

## QC結果記入欄

### 実行情報

- 実行者:
- 実行日:
- 対象コミット:
- ブランチ:
- Python／OS:
- Xcode／macOS:
- Simulator／iOS:
- 実機:
- 証跡保管先:

### 結果集計

| 試験群 | PASS | FAIL | BLOCKED | NOT RUN | 証跡 |
|---|---:|---:|---:|---:|---|
| QC 01 Python自動テスト |  |  |  |  |  |
| QC 02 iOS単体テスト |  |  |  |  |  |
| QC 03 現行iOSスモーク確認 |  |  |  |  |  |
| 未実装項目 |  |  |  |  |  |

### 不具合一覧

| ID | Severity | 概要 | 状態 | 関連試験 |
|---|---|---|---|---|
|  |  |  |  |  |

### QC総合判定

- 判定: PASS / CONDITIONAL PASS / FAIL / BLOCKED
- Severity 1・2件数:
- 条件または阻害要因:
- 再試験要否:
- QC責任者:
- 判定日:

## 開発への返却条件

次のいずれかに該当する場合は、QC側で回避修正せず開発へ返却する。

- 自動テストが再現可能な手順で失敗する。
- テスト依存関係やXcodeプロジェクトを生成できない。
- 手順と実装の期待結果が矛盾する。
- 秘密情報がログまたは成果物へ出力される。
- Severity 1・2を検出する。
- BLOCKED項目の実装完了判断に必要な情報が不足する。

## 参照資料

- `../Test/mvp-test-plan-v1.md`
- `../SystemDesign/mvp-requirements-v1.md`
- `../SystemDesign/mvp-basic-design-v1.md`
- `../SystemDesign/mvp-ui-design-proposal-v1.md`
- `apple-maps-server-api-poc-v1.md`
- `../Procedure/apple-maps-server-api-poc-execution-procedure-v1.md`

---

## QC実行結果 2026-09-27

### 実行情報

- 実行者: Codex QC
- 実行日時: 2026-09-27 22:11:13 +09:00
- 対象: `main` / `d337da8903397f3f29e1742d1eabdd38069852af` と受領時点の未コミット変更
- OS: Windows NT 10.0.26200.0
- PowerShell: 5.1.26100.9444
- Python: 3.13.6（指定の3.12系は端末に存在せず、環境差分あり）
- Xcode／XcodeGen／Swift: 利用不可
- Simulator／iOS／実機: 利用不可
- 証跡: 本節および実行セッションのコンソール出力。`.xcresult` と画面キャプチャは未生成

### 結果集計

| 試験群 | PASS | FAIL | BLOCKED | NOT RUN | 証跡・備考 |
|---|---:|---:|---:|---:|---|
| QC 01 Python自動テスト | 17 | 0 | 0 | 0 | 指定コマンドで `17 passed in 3.93s`。ソケット接続を強制遮断した補助実行でも `17 passed in 1.26s` |
| QC 02 iOS単体テスト | 0 | 0 | 20 | 0 | Windows環境にXcode、XcodeGen、iOS Simulatorがないため実行不可。指定3クラス16件に加え、同一ターゲットの `AppStateTests` 4件も対象 |
| QC 03 現行iOSスモーク確認 | 0 | 0 | 13 | 0 | 基本9項目と追加4項目はiOS実行環境がないため確認不可 |
| 未実装項目 | 0 | 0 | 10 | 0 | 引継ぎ書に列挙された10グループを実装待ちとして継続BLOCKED |

### 確認事項

- PythonはERROR、FAILED、SKIP、XPASS、XFAILなし。
- 外部ソケット通信を禁止した補助実行でも全件成功したため、Pythonテスト中の外部API接続は検出されなかった。
- pytestコンソール出力にAPIキー、token、資格情報、URLクエリの秘密値は表示されなかった。
- Pythonの正式基準は3.12系のため、今回の3.13.6での成功は互換性確認として扱い、3.12系で再試験する。
- 受領時点の作業ツリーには多数の未コミット変更と未追跡ファイルがあり、コミットIDだけでは今回の試験対象を再現できない。

### 不具合一覧

実行できたPython試験では不具合を検出しなかった。iOS未実行とPythonバージョン差分は環境阻害要因であり、製品不具合としては起票していない。

### QC総合判定

- 判定: **BLOCKED**
- 検出済みSeverity 1・2: 0件（未実行範囲を除く）
- 阻害要因: macOS、Xcode 15以降、XcodeGen、iOS 17系Simulatorがなく、QC 02とQC 03を実行できない。Python 3.12系もない。
- 再試験要否: 必要。Python 3.12系で17件、macOS環境でiOS単体20件、iOS 17系Simulatorでスモーク13項目を実施する。
- 判定日: 2026-09-27
