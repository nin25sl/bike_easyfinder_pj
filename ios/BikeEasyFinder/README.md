# BikeEasyFinder iOS MVP

RD-01〜RD-04で承認された範囲を、固定データで確認するSwiftUIアプリ骨格です。

## 実装済み

- iOS 17以上、iPhone、SwiftUI
- 「現在地から探す」操作後の `When In Use` 権限要求
- 利用可能時間、興味、高速道路利用可否の入力
- 固定データによる候補最大5件の表示
- 候補詳細とMapKit上の候補ピン
- Apple Mapsへの目的地引き渡し
- 位置情報拒否、位置取得失敗、候補0件、候補取得失敗の状態表示
- 候補生成モックのユニットテスト

固定候補はUI検証用であり、正式なSpotデータや営業・道路情報として利用しないでください。

## 未実装

- RD-05で確定する最終画面フローとデザイン
- RD-06で確定する推薦API、時間計算、エラー契約
- サーバ通信、行動イベント送信、永続化
- ルートポリラインと本番ETA
- 天気・道路規制

## Macでの起動

1. Xcode 15以降とXcodeGenを用意する。
2. このディレクトリで `xcodegen generate` を実行する。
3. `BikeEasyFinder.xcodeproj` をXcodeで開く。
4. SigningのTeamを選択する。
5. iOS 17以上のSimulatorまたは実機で実行する。

位置情報をSimulatorで確認する場合は、XcodeのLocationメニューから任意の位置を設定してください。
