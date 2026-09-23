import SwiftUI
import UIKit

struct SpotDetailView: View {
    private enum Feedback: String {
        case interested
        case notInterested
        case visited

        var label: String {
            switch self {
            case .interested: "興味あり"
            case .notInterested: "今回は違う"
            case .visited: "訪問済み"
            }
        }
    }

    let spot: TouringSpot

    @State private var isOpeningMaps = false
    @State private var showNavigationFailure = false
    @State private var feedback: Feedback?
    private let navigationService = ExternalNavigationService()

    var body: some View {
        List {
            Section {
                SpotMapView(spot: spot)
                    .frame(height: 260)
                    .listRowInsets(EdgeInsets())
            }

            Section("概要") {
                Text(spot.summary)
                LabeledContent("合計所要時間", value: spot.formattedDuration)
                LabeledContent("往路", value: "\(spot.outboundMinutes)分")
                LabeledContent("滞在目安", value: "\(spot.stayMinutes)分")
                LabeledContent("復路", value: "\(spot.returnMinutes)分")
                LabeledContent("概算距離", value: "\(spot.distanceKilometers, specifier: "%.0f")km")
            }

            Section("推薦理由") {
                Text(spot.recommendationReason)
                Text(spot.tags.map(\.displayName).sorted().map { "#\($0)" }.joined(separator: "  "))
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section("この候補について") {
                ForEach([Feedback.interested, .notInterested, .visited], id: \.rawValue) { option in
                    Button {
                        feedback = option
                    } label: {
                        HStack {
                            Text(option.label)
                                .foregroundStyle(.primary)
                            Spacer()
                            if feedback == option {
                                Image(systemName: "checkmark")
                                    .foregroundStyle(.tint)
                            }
                        }
                    }
                }

                if feedback != nil {
                    Text("β版の計測仕様が確定するまで、この選択は画面を閉じると破棄されます。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }

            Section {
                Button {
                    isOpeningMaps = true
                    let success = navigationService.openInAppleMaps(spot)
                    isOpeningMaps = false
                    showNavigationFailure = !success
                } label: {
                    if isOpeningMaps {
                        HStack {
                            ProgressView()
                            Text("Apple Mapsを開いています…")
                        }
                        .frame(maxWidth: .infinity)
                    } else {
                        Text("ここに行く（Apple Maps）")
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isOpeningMaps)
            } footer: {
                Text("ルートと所要時間は変わる場合があります。現地の標識とApple Mapsの最新情報を確認してください。")
            }
        }
        .navigationTitle(spot.name)
        .navigationBarTitleDisplayMode(.inline)
        .alert("Apple Mapsを開けませんでした", isPresented: $showNavigationFailure) {
            Button("座標をコピー") {
                UIPasteboard.general.string = "\(spot.latitude),\(spot.longitude)"
            }
            Button("閉じる", role: .cancel) {}
        } message: {
            Text("目的地の座標をコピーして、ナビアプリで検索できます。")
        }
    }
}
