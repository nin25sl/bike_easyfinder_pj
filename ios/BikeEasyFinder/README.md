# BikeEasyFinder iOS MVP

基本設計書とMVP UIデザイン案のS01〜S08を、固定データで操作確認するSwiftUIアプリです。

## 実装済み

- iOS 17以上、iPhone、SwiftUI
- S01 初回説明、S02 再訪ホーム、S03 提案条件
- S04 最大5件の単一カード型提案、3種のリアクション、5秒間のUndo
- S05 候補詳細、時間内訳、MapKit上の候補ピン、根拠・鮮度表示
- S06 興味あり一覧、S07 Apple Maps引き渡し前の安全確認
- S08 分析同意、前回条件・リアクション履歴・匿名データの管理
- 提案開始時だけの `When In Use` 位置取得と、利用後のメモリ破棄
- オンボーディングと前回条件のUserDefaults保存
- リアクションと興味ありSpotスナップショットのSwiftData保存
- Dynamic Typeでのリアクション縦配置、VoiceOver用ラベル、44pt以上の操作領域
- 位置情報拒否、位置取得失敗、候補0件、推薦失敗、Apple Maps起動失敗の状態表示
- 推薦モック、ViewModel、時間計算、端末保存のユニットテスト

固定候補はUI検証用であり、正式なSpotデータや営業・道路情報として利用しないでください。

## 未実装

- RD-06で確定する推薦API、時間計算、エラー契約
- サーバ通信、行動イベント送信、匿名データ削除API
- ルートポリラインと本番ETA
- 天気・道路規制

固定Spotの所要時間・出典・鮮度はUI検証用です。興味あり一覧から開く詳細でも固定値を表示するため、本番API接続時に現在地と出発時刻から再計算します。

## Macでの起動

1. Xcode 15以降とXcodeGenを用意する。
2. このディレクトリで `xcodegen generate` を実行する。
3. `BikeEasyFinder.xcodeproj` をXcodeで開く。
4. SigningのTeamを選択する。
5. iOS 17以上のSimulatorまたは実機で実行する。

位置情報をSimulatorで確認する場合は、XcodeのLocationメニューから任意の位置を設定してください。
