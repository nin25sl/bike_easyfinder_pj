import SwiftUI

struct SearchView: View {
    @StateObject private var locationService = LocationService()
    @StateObject private var viewModel = SearchViewModel()

    var body: some View {
        NavigationStack {
            List {
                introductionSection
                locationSection

                if locationService.currentLocation != nil {
                    durationSection
                    interestSection
                    highwaySection
                    searchSection
                    resultSection
                }
            }
            .navigationTitle("行き先を見つける")
            .navigationDestination(for: UUID.self) { spotID in
                if let spot = viewModel.spots.first(where: { $0.id == spotID }) {
                    SpotDetailView(spot: spot)
                }
            }
        }
    }

    private var introductionSection: some View {
        Section {
            Text("今から使える時間と興味から、現在地へ戻れるツーリング候補を提案します。")
            Text("所要時間は予測です。走行時は現地の標識と外部ナビの最新情報を優先してください。")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private var locationSection: some View {
        Section("現在地") {
            switch locationService.state {
            case .idle:
                Button("現在地から探す", systemImage: "location.fill") {
                    locationService.requestCurrentLocation()
                }
            case .requestingPermission, .locating:
                HStack {
                    ProgressView()
                    Text("現在地を取得しています…")
                }
            case .available:
                Label("現在地を取得しました", systemImage: "checkmark.circle.fill")
                    .foregroundStyle(.green)
                Button("現在地を更新") {
                    locationService.requestCurrentLocation()
                }
            case .denied:
                PermissionDeniedView()
            case .failed(let message):
                ContentUnavailableView {
                    Label("現在地を取得できません", systemImage: "location.slash")
                } description: {
                    Text(message)
                } actions: {
                    Button("再試行") {
                        locationService.requestCurrentLocation()
                    }
                }
            }
        }
    }

    private var durationSection: some View {
        Section("使える時間") {
            Picker("使える時間", selection: $viewModel.criteria.availableMinutes) {
                ForEach(DurationOption.mvpOptions) { option in
                    Text(option.label).tag(option.minutes)
                }
            }
            .pickerStyle(.segmented)
        }
    }

    private var interestSection: some View {
        Section("興味") {
            ForEach(SpotInterest.allCases) { interest in
                Button {
                    viewModel.toggleInterest(interest)
                } label: {
                    HStack {
                        Text(interest.displayName)
                            .foregroundStyle(.primary)
                        Spacer()
                        if viewModel.criteria.interests.contains(interest) {
                            Image(systemName: "checkmark")
                                .foregroundStyle(.tint)
                        }
                    }
                }
            }
        }
    }

    private var highwaySection: some View {
        Section {
            Toggle("高速道路を利用してよい", isOn: $viewModel.criteria.allowsHighway)
        }
    }

    private var searchSection: some View {
        Section {
            Button {
                guard let location = locationService.currentLocation else { return }
                Task { await viewModel.search(from: location) }
            } label: {
                if viewModel.resultState == .loading {
                    HStack {
                        ProgressView()
                        Text("候補を探しています…")
                    }
                    .frame(maxWidth: .infinity)
                } else {
                    Text("この条件で候補を探す")
                        .frame(maxWidth: .infinity)
                }
            }
            .disabled(viewModel.resultState == .loading)
            .buttonStyle(.borderedProminent)
        }
    }

    @ViewBuilder
    private var resultSection: some View {
        switch viewModel.resultState {
        case .idle, .loading:
            EmptyView()
        case .loaded:
            Section("候補") {
                ForEach(viewModel.spots) { spot in
                    NavigationLink(value: spot.id) {
                        SpotRow(spot: spot)
                    }
                }
            }
        case .empty:
            Section {
                ContentUnavailableView {
                    Label("条件に合う候補がありません", systemImage: "magnifyingglass")
                } description: {
                    Text("使える時間、興味、高速道路の条件を変更してください。条件は自動では緩和しません。")
                }
            }
        case .failed(let message):
            Section {
                ContentUnavailableView {
                    Label("候補を取得できません", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(message)
                }
            }
        }
    }
}

private struct SpotRow: View {
    let spot: TouringSpot

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(spot.name)
                .font(.headline)
            Text("往復・滞在込み \(spot.formattedDuration)")
                .font(.subheadline)
            Text(spot.recommendationReason)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    SearchView()
}
