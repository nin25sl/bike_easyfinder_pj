import SwiftUI

struct HomeView: View {
    @ObservedObject var appState: AppState
    let onStartWithPrevious: () -> Void
    let onChangeConditions: () -> Void
    let onShowInterested: () -> Void
    let onShowSettings: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("今日はどれくらい走る？")
                        .font(.largeTitle.bold())
                    Text("現在地は提案を始めるときに取得します。前回の位置は保存しません。")
                        .foregroundStyle(.secondary)
                }

                if let criteria = appState.lastCriteria {
                    previousCriteriaCard(criteria)
                } else {
                    StatusNotice(
                        kind: .info,
                        title: "最初の条件を決めましょう",
                        message: "使える時間、興味、高速道路の利用可否を選びます。"
                    )
                }

                Button(action: onShowInterested) {
                    HStack(spacing: 14) {
                        Image(systemName: "heart.fill")
                            .font(.title2)
                            .foregroundStyle(AppTheme.brand)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("興味ありを見る")
                                .font(.headline)
                                .foregroundStyle(.primary)
                            Text("保存中 \(appState.savedSpots.count)件")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                            .foregroundStyle(.secondary)
                    }
                    .padding()
                    .background(AppTheme.cardBackground, in: RoundedRectangle(cornerRadius: 14))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("興味ありを見る。保存中\(appState.savedSpots.count)件")
            }
            .padding()
        }
        .navigationTitle("Bike EasyFinder")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("設定", systemImage: "gearshape", action: onShowSettings)
            }
        }
        .safeAreaInset(edge: .bottom) {
            VStack(spacing: 8) {
                PrimaryBottomAction(
                    title: appState.lastCriteria == nil ? "条件を決める" : "前回の条件で提案を受ける",
                    systemImage: "location.fill",
                    action: appState.lastCriteria == nil ? onChangeConditions : onStartWithPrevious
                )
                if appState.lastCriteria != nil {
                    Button("条件を変更", action: onChangeConditions)
                        .fontWeight(.semibold)
                        .frame(minHeight: 44)
                }
            }
            .background(.bar)
        }
    }

    private func previousCriteriaCard(_ criteria: SearchCriteria) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("前回の条件")
                .font(.headline)
            Label(criteria.durationLabel, systemImage: "clock")
            Label(criteria.interestsLabel, systemImage: "sparkles")
            Label("高速道路：\(criteria.highwayLabel)", systemImage: "road.lanes")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(AppTheme.brandSoft.opacity(0.55), in: RoundedRectangle(cornerRadius: 16))
        .accessibilityElement(children: .combine)
    }
}
