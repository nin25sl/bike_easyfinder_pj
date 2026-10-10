import SwiftUI

struct ConditionsView: View {
    @ObservedObject var viewModel: SearchViewModel
    @ObservedObject var locationService: LocationService
    let autoStart: Bool
    let onRecommendationsReady: () -> Void

    @State private var pendingSearch = false
    @State private var didAutoStart = false

    private let columns = [GridItem(.adaptive(minimum: 96), spacing: 10)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                locationSection
                durationSection
                interestSection
                highwaySection

                if case .empty = viewModel.resultState {
                    StatusNotice(
                        kind: .info,
                        title: "条件に合う候補がありません",
                        message: "指定時間±60分まで探しました。使える時間、興味、高速道路の条件を変更してください。"
                    )
                }

                if case .failed(let message) = viewModel.resultState {
                    StatusNotice(kind: .error, title: "候補を取得できません", message: message)
                }
            }
            .padding()
        }
        .navigationTitle("提案条件")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            PrimaryBottomAction(
                title: buttonTitle,
                systemImage: "sparkles",
                isLoading: viewModel.resultState == .loading || pendingSearch,
                action: beginSearch
            )
        }
        .onAppear {
            viewModel.resetResults()
            guard autoStart, !didAutoStart else { return }
            didAutoStart = true
            beginSearch()
        }
        .onChange(of: locationService.state) { _, state in
            guard pendingSearch else { return }
            switch state {
            case .available:
                runSearchIfPossible()
            case .denied, .failed:
                pendingSearch = false
            default:
                break
            }
        }
    }

    private var buttonTitle: String {
        if pendingSearch { return "現在地を確認しています…" }
        if viewModel.resultState == .loading { return "候補を探しています…" }
        return "この条件で提案を受ける"
    }

    private var locationSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("現在地", icon: "location")
            switch locationService.state {
            case .idle:
                Text("提案を始めるときだけ現在地を取得します。")
                    .foregroundStyle(.secondary)
            case .requestingPermission, .locating:
                Label("現在地を取得しています…", systemImage: "location.circle")
                    .foregroundStyle(.secondary)
            case .available:
                Label("現在地を取得しました", systemImage: "checkmark.circle.fill")
                    .foregroundStyle(.green)
            case .denied:
                PermissionDeniedView(onRetry: { locationService.requestCurrentLocation() })
            case .failed(let message):
                StatusNotice(kind: .error, title: "現在地を取得できません", message: message)
                Button("再試行") { locationService.requestCurrentLocation() }
                    .buttonStyle(.bordered)
            }
        }
    }

    private var durationSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("使える時間", icon: "clock")
            LazyVGrid(columns: columns, spacing: 10) {
                ForEach(DurationOption.mvpOptions) { option in
                    ChoiceChip(
                        title: option.label,
                        isSelected: viewModel.criteria.availableMinutes == option.minutes
                    ) {
                        viewModel.criteria.availableMinutes = option.minutes
                    }
                }
            }
        }
    }

    private var interestSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("興味", icon: "sparkles")
            Text("複数選べます。「おまかせ」は他の選択を解除します。")
                .font(.footnote)
                .foregroundStyle(.secondary)
            LazyVGrid(columns: columns, spacing: 10) {
                ForEach(SpotInterest.allCases) { interest in
                    ChoiceChip(
                        title: interest.displayName,
                        isSelected: viewModel.criteria.interests.contains(interest)
                    ) {
                        viewModel.toggleInterest(interest)
                    }
                }
            }
        }
    }

    private var highwaySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("高速道路", icon: "road.lanes")
            LazyVGrid(columns: columns, spacing: 10) {
                ChoiceChip(title: "使わない", isSelected: !viewModel.criteria.allowsHighway) {
                    viewModel.criteria.allowsHighway = false
                }
                ChoiceChip(title: "使ってよい", isSelected: viewModel.criteria.allowsHighway) {
                    viewModel.criteria.allowsHighway = true
                }
            }
        }
    }

    private func sectionTitle(_ title: String, icon: String) -> some View {
        Label(title, systemImage: icon)
            .font(.title3.bold())
    }

    private func beginSearch() {
        guard viewModel.resultState != .loading, !pendingSearch else { return }
        pendingSearch = true
        locationService.discardCurrentLocation()
        locationService.requestCurrentLocation()
    }

    private func runSearchIfPossible() {
        guard let location = locationService.currentLocation else { return }
        pendingSearch = false
        Task {
            await viewModel.search(from: location)
            locationService.discardCurrentLocation()
            if viewModel.resultState == .loaded {
                onRecommendationsReady()
            }
        }
    }
}
