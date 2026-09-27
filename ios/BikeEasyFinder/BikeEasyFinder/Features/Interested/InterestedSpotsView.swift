import SwiftUI

struct InterestedSpotsView: View {
    @ObservedObject var appState: AppState
    let onSelect: (TouringSpot) -> Void
    let onFindSpots: () -> Void

    var body: some View {
        Group {
            if appState.savedSpots.isEmpty {
                ContentUnavailableView {
                    Label("まだ保存した場所はありません", systemImage: "heart")
                } description: {
                    Text("提案カードで「興味あり」を選ぶと、ここから後で見直せます。")
                } actions: {
                    Button("条件を決めて提案を受ける", action: onFindSpots)
                        .buttonStyle(.borderedProminent)
                        .tint(AppTheme.brand)
                }
            } else {
                List {
                    Section {
                        ForEach(appState.savedSpots) { spot in
                            Button {
                                onSelect(spot)
                            } label: {
                                HStack(spacing: 14) {
                                    Image(systemName: "mountain.2.fill")
                                        .foregroundStyle(AppTheme.brand)
                                        .frame(width: 52, height: 52)
                                        .background(AppTheme.brandSoft, in: RoundedRectangle(cornerRadius: 10))
                                        .accessibilityHidden(true)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(spot.name)
                                            .font(.headline)
                                            .foregroundStyle(.primary)
                                        Text(spot.summary)
                                            .font(.subheadline)
                                            .foregroundStyle(.secondary)
                                            .lineLimit(2)
                                        Text(spot.tags.map(\.displayName).sorted().joined(separator: "・"))
                                            .font(.caption)
                                            .foregroundStyle(AppTheme.brand)
                                    }
                                    Spacer()
                                    Image(systemName: "chevron.right")
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .buttonStyle(.plain)
                            .swipeActions {
                                Button("解除", role: .destructive) {
                                    appState.removeSavedSpot(spot)
                                }
                            }
                            .contextMenu {
                                Button("興味ありから解除", role: .destructive) {
                                    appState.removeSavedSpot(spot)
                                }
                            }
                        }
                    } footer: {
                        Text("所要時間は現在地と出発時刻で変わるため、ここでは表示しません。")
                    }
                }
            }
        }
        .navigationTitle("興味あり")
    }
}
