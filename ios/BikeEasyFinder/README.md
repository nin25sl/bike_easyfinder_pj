# BikeEasyFinder iOS MVP

iOS 17以上のSwiftUIアプリです。既存MVPデザイン案のS01〜S08を実装し、固定データではなく`/v1/recommendations`へ接続します。

実装済み:

- 初回説明、ホーム、条件入力、最大5件のカード、詳細、保存一覧、安全確認、設定。
- When In Use位置取得。検索終了後に位置情報を破棄。
- API timeout 5秒。ネットワーク、429、503、504だけ1回再試行。
- WeatherKitによる目的地天候の注意表示。取得失敗時も推薦を継続。
- Apple Mapsへの目的地引き渡しと座標copy fallback。
- SwiftDataによるリアクション保存。
- 明示同意後だけ匿名イベントを送信。installation IDと削除tokenはKeychain保存、queueは7日、batchは50件。
- 匿名データ削除API連携。

Macでの起動:

1. Xcode 15以降とXcodeGenを用意する。
2. このディレクトリで`xcodegen generate`を実行する。
3. `BikeEasyFinder.xcodeproj`を開き、Signing TeamとWeatherKit capabilityを確認する。
4. local APIを起動し、Simulatorなら`BIKE_API_BASE_URL=http://127.0.0.1:8000`を使用する。
5. 実機では`127.0.0.1`をMacのLAN IPへ変更する。限定βではHTTPS staging URLを使用する。

Apple Maps 140経路POC、WeatherKit実機、TestFlight E2Eはrelease gateであり、Mac、署名、短期access token、staging環境で実施します。
