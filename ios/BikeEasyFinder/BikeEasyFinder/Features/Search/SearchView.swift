import SwiftUI

private enum AppRoute: Hashable {
    case conditions(autoStart: Bool)
    case recommendations
    case detail(UUID)
    case interested
    case navigation(UUID)
    case settings
}

struct SearchView: View {
    @StateObject private var appState = AppState()
    @StateObject private var locationService = LocationService()
    @StateObject private var viewModel = SearchViewModel()
    @State private var path: [AppRoute] = []

    var body: some View {
        NavigationStack(path: $path) {
            Group {
                if appState.hasCompletedOnboarding {
                    HomeView(
                        appState: appState,
                        onStartWithPrevious: startWithPreviousCriteria,
                        onChangeConditions: {
                            viewModel.useReactions(appState.reactions)
                            path.append(.conditions(autoStart: false))
                        },
                        onShowInterested: { path.append(.interested) },
                        onShowSettings: { path.append(.settings) }
                    )
                } else {
                    OnboardingView {
                        appState.completeOnboarding()
                        viewModel.useCriteria(SearchCriteria())
                        viewModel.useReactions(appState.reactions)
                        path = [.conditions(autoStart: false)]
                    }
                }
            }
            .navigationDestination(for: AppRoute.self) { route in
                destination(for: route)
            }
        }
        .tint(AppTheme.brand)
    }

    @ViewBuilder
    private func destination(for route: AppRoute) -> some View {
        switch route {
        case .conditions(let autoStart):
            ConditionsView(
                viewModel: viewModel,
                locationService: locationService,
                autoStart: autoStart
            ) {
                appState.saveCriteria(viewModel.criteria)
                appState.recordShown(viewModel.spots)
                path.append(.recommendations)
            }
        case .recommendations:
            RecommendationCardView(
                viewModel: viewModel,
                appState: appState,
                onShowDetail: {
                    appState.recordSelected($0)
                    path.append(.detail($0.id))
                },
                onShowInterested: { path.append(.interested) },
                onChangeConditions: {
                    viewModel.useReactions(appState.reactions)
                    path.append(.conditions(autoStart: false))
                },
                onTryAgain: { path.append(.conditions(autoStart: true)) }
            )
        case .detail(let id):
            if let spot = spot(withID: id) {
                SpotDetailView(
                    spot: spot,
                    reaction: appState.reactions[id],
                    locationService: locationService,
                    onReact: { _ = appState.react(to: spot, as: $0) },
                    onNavigate: { path.append(.navigation(id)) }
                )
            } else {
                ContentUnavailableView("候補を表示できません", systemImage: "questionmark.folder")
            }
        case .interested:
            InterestedSpotsView(
                appState: appState,
                onSelect: { path.append(.detail($0.id)) },
                onFindSpots: { path.append(.conditions(autoStart: false)) }
            )
        case .navigation(let id):
            if let spot = spot(withID: id) {
                NavigationConfirmationView(
                    spot: spot,
                    onRouteStarted: { appState.recordRouteStarted(spot) }
                )
            } else {
                ContentUnavailableView("目的地を表示できません", systemImage: "map")
            }
        case .settings:
            SettingsView(appState: appState)
        }
    }

    private func startWithPreviousCriteria() {
        viewModel.useCriteria(appState.lastCriteria ?? SearchCriteria())
        viewModel.useReactions(appState.reactions)
        path.append(.conditions(autoStart: true))
    }

    private func spot(withID id: UUID) -> TouringSpot? {
        viewModel.spots.first(where: { $0.id == id })
            ?? appState.savedSpots.first(where: { $0.id == id })
            ?? Array<TouringSpot>.demoSpots.first(where: { $0.id == id })
    }
}

#Preview {
    SearchView()
}
