import SwiftUI
import UIKit

struct NavigationConfirmationView: View {
    let spot: TouringSpot

    @Environment(\.dismiss) private var dismiss
    @State private var isOpeningMaps = false
    @State private var showNavigationFailure = false
    private let navigationService = ExternalNavigationService()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Apple Mapsへ移ります")
                        .font(.largeTitle.bold())
                    Text(spot.name)
                        .font(.title3.weight(.semibold))
                    Text("\(spot.latitude, specifier: "%.5f"), \(spot.longitude, specifier: "%.5f")")
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                }

                VStack(alignment: .leading, spacing: 16) {
                    safetyRow("停車中に操作してください", icon: "hand.raised.fill")
                    safetyRow("現地の標識・通行規制を優先してください", icon: "signpost.right.fill")
                    safetyRow("Apple Mapsの最新案内を確認してください", icon: "map.fill")
                }

                StatusNotice(
                    kind: .warning,
                    title: "二輪専用ルートではありません",
                    message: "自動車向け経路を開きます。二輪車の通行条件と現地の案内を必ず確認してください。"
                )

                Button("キャンセル") { dismiss() }
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .padding()
        }
        .navigationTitle("ナビを開く前に")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            PrimaryBottomAction(
                title: isOpeningMaps ? "Apple Mapsを開いています…" : "Apple Mapsでルートを開く",
                systemImage: "map",
                isLoading: isOpeningMaps,
                action: openMaps
            )
        }
        .alert("Apple Mapsを開けませんでした", isPresented: $showNavigationFailure) {
            Button("座標をコピー") {
                UIPasteboard.general.string = "\(spot.latitude),\(spot.longitude)"
            }
            Button("閉じる", role: .cancel) {}
        } message: {
            Text("目的地の座標をコピーして、ナビアプリで検索できます。")
        }
    }

    private func safetyRow(_ title: String, icon: String) -> some View {
        Label(title, systemImage: icon)
            .font(.headline)
            .accessibilityElement(children: .combine)
    }

    private func openMaps() {
        guard !isOpeningMaps else { return }
        isOpeningMaps = true
        let success = navigationService.openInAppleMaps(spot)
        isOpeningMaps = false
        showNavigationFailure = !success
    }
}
