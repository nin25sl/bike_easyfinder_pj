import SwiftUI

struct RecommendationCardView: View {
    private struct LastAction {
        let spot: TouringSpot
        let previous: SpotReaction?
        let index: Int
        let reaction: SpotReaction
    }

    @ObservedObject var viewModel: SearchViewModel
    @ObservedObject var appState: AppState
    let onShowDetail: (TouringSpot) -> Void
    let onShowInterested: () -> Void
    let onChangeConditions: () -> Void
    let onTryAgain: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var currentIndex = 0
    @State private var lastAction: LastAction?
    @State private var undoTask: Task<Void, Never>?

    private var currentSpot: TouringSpot? {
        guard viewModel.spots.indices.contains(currentIndex) else { return nil }
        return viewModel.spots[currentIndex]
    }

    var body: some View {
        Group {
            if let spot = currentSpot {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        Text("\(currentIndex + 1) / 最大\(viewModel.spots.count)件")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.secondary)
                            .accessibilityLabel("\(viewModel.spots.count)件中\(currentIndex + 1)件目")

                        SpotHero(spot: spot)
                        TimeSummary(spot: spot)
                        SpotMapView(spot: spot)
                            .frame(height: 180)
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                        ReasonBlock(reason: spot.recommendationReason)

                        ForEach(viewModel.recommendationWarnings, id: \.self) { warning in
                            StatusNotice(
                                kind: .info,
                                title: "検索範囲を広げました",
                                message: warning
                            )
                        }

                        StatusNotice(
                            kind: .info,
                            title: "最近確認された情報です",
                            message: "最終確認 \(spot.verifiedAt.formatted(date: .abbreviated, time: .omitted))。出発前に営業・道路状況を確認してください。"
                        )

                        Button("詳しく見る", systemImage: "info.circle") {
                            onShowDetail(spot)
                        }
                        .buttonStyle(.bordered)
                        .frame(maxWidth: .infinity)
                    }
                    .padding()
                }
                .safeAreaInset(edge: .bottom) {
                    reactionArea(for: spot)
                }
            } else {
                completionView
            }
        }
        .navigationTitle("あなたへの提案")
        .navigationBarTitleDisplayMode(.inline)
        .overlay(alignment: .bottom) {
            if let lastAction {
                UndoBanner(message: "「\(lastAction.reaction.label)」を記録しました") {
                    undo()
                }
                .padding(.bottom, dynamicTypeSize.isAccessibilitySize ? 190 : 96)
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .onDisappear { undoTask?.cancel() }
    }

    @ViewBuilder
    private func reactionArea(for spot: TouringSpot) -> some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(spacing: 8) {
                    reactionButtons(for: spot)
                }
            } else {
                HStack(spacing: 8) {
                    reactionButtons(for: spot)
                }
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(.bar)
    }

    @ViewBuilder
    private func reactionButtons(for spot: TouringSpot) -> some View {
        ForEach(SpotReaction.allCases) { reaction in
            Button {
                select(reaction, for: spot)
            } label: {
                Label(reaction.label, systemImage: reaction.systemImage)
                    .font(.caption.weight(.semibold))
                    .frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.bordered)
            .tint(reaction == .interested ? AppTheme.brand : .secondary)
            .accessibilityHint("記録して次の候補へ進みます")
        }
    }

    private var completionView: some View {
        ContentUnavailableView {
            Label("候補をすべて確認しました", systemImage: "checkmark.circle")
        } description: {
            Text("保存した場所を見直すか、条件を変えてもう一度提案を受けられます。")
        } actions: {
            Button("興味ありを見る", action: onShowInterested)
                .buttonStyle(.borderedProminent)
                .tint(AppTheme.brand)
            Button("条件を変更", action: onChangeConditions)
            Button("同じ条件で再提案", action: onTryAgain)
        }
    }

    private func select(_ reaction: SpotReaction, for spot: TouringSpot) {
        undoTask?.cancel()
        let action = LastAction(
            spot: spot,
            previous: appState.react(to: spot, as: reaction),
            index: currentIndex,
            reaction: reaction
        )
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.25)) {
            currentIndex += 1
            lastAction = action
        }
        undoTask = Task {
            try? await Task.sleep(for: .seconds(5))
            guard !Task.isCancelled else { return }
            await MainActor.run {
                withAnimation { lastAction = nil }
            }
        }
    }

    private func undo() {
        guard let action = lastAction else { return }
        undoTask?.cancel()
        appState.restoreReaction(for: action.spot, to: action.previous)
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.25)) {
            currentIndex = action.index
            lastAction = nil
        }
    }
}
