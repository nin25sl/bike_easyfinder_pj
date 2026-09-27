import SwiftUI

struct SpotDetailView: View {
    let spot: TouringSpot
    let reaction: SpotReaction?
    let onReact: (SpotReaction) -> Void
    let onNavigate: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                SpotHero(spot: spot)

                Text(spot.summary)
                    .font(.body)

                TimeSummary(spot: spot)

                SpotMapView(spot: spot)
                    .frame(height: 240)
                    .clipShape(RoundedRectangle(cornerRadius: 14))

                VStack(alignment: .leading, spacing: 12) {
                    Text("現地情報")
                        .font(.title3.bold())
                    Label(spot.motorcycleParkingNote, systemImage: "parkingsign.circle")
                    Label("概算距離 \(spot.distanceKilometers, specifier: "%.0f")km", systemImage: "point.topleft.down.to.point.bottomright.curvepath")
                }

                StatusNotice(
                    kind: .warning,
                    title: "天気情報を確認できません",
                    message: "固定データ版ではWeatherKit未接続です。出発前に目的地の最新の天気を確認してください。"
                )

                ReasonBlock(reason: spot.recommendationReason)

                VStack(alignment: .leading, spacing: 8) {
                    Text("情報の根拠")
                        .font(.headline)
                    LabeledContent("出典", value: spot.sourceLabel)
                    LabeledContent(
                        "最終確認",
                        value: spot.verifiedAt.formatted(date: .abbreviated, time: .omitted)
                    )
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text("この候補について")
                        .font(.headline)
                    ForEach(SpotReaction.allCases) { option in
                        Button {
                            onReact(option)
                        } label: {
                            HStack {
                                Label(option.label, systemImage: option.systemImage)
                                    .foregroundStyle(.primary)
                                Spacer()
                                if reaction == option {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(AppTheme.brand)
                                }
                            }
                            .frame(minHeight: 44)
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(reaction == option ? .isSelected : [])
                    }
                }
                .padding()
                .background(AppTheme.cardBackground, in: RoundedRectangle(cornerRadius: 14))
            }
            .padding()
        }
        .navigationTitle(spot.name)
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            PrimaryBottomAction(title: "ここに行く", systemImage: "arrow.triangle.turn.up.right.diamond", action: onNavigate)
        }
    }
}

#Preview {
    NavigationStack {
        SpotDetailView(
            spot: Array<TouringSpot>.demoSpots[0],
            reaction: nil,
            onReact: { _ in },
            onNavigate: {}
        )
    }
}
