import CoreLocation
import Foundation

@MainActor
final class SearchViewModel: ObservableObject {
    enum ResultState: Equatable {
        case idle
        case loading
        case loaded
        case empty
        case failed(String)
    }

    @Published var criteria = SearchCriteria()
    @Published private(set) var resultState: ResultState = .idle
    @Published private(set) var spots: [TouringSpot] = []
    @Published private(set) var recommendationWarnings: [String] = []
    private var reactions: [UUID: SpotReaction] = [:]

    private let recommendationService: RecommendationProviding

    init(recommendationService: RecommendationProviding = APIRecommendationService.live) {
        self.recommendationService = recommendationService
    }

    var currentSpot: TouringSpot? {
        spots.first
    }

    func useCriteria(_ criteria: SearchCriteria) {
        self.criteria = criteria
    }

    func useReactions(_ reactions: [UUID: SpotReaction]) {
        self.reactions = reactions
    }

    func resetResults() {
        resultState = .idle
        spots = []
        recommendationWarnings = []
    }

    func toggleInterest(_ interest: SpotInterest) {
        if interest == .any {
            criteria.interests = [.any]
            return
        }

        criteria.interests.remove(.any)
        if criteria.interests.contains(interest) {
            criteria.interests.remove(interest)
        } else {
            criteria.interests.insert(interest)
        }

        if criteria.interests.isEmpty {
            criteria.interests = [.any]
        }
    }

    func search(from location: CLLocation) async {
        resultState = .loading
        do {
            let result = try await recommendationService.recommendations(
                origin: location.coordinate,
                criteria: criteria,
                reactions: reactions
            )
            spots = result.spots
            recommendationWarnings = result.warnings
            resultState = result.spots.isEmpty ? .empty : .loaded
        } catch {
            spots = []
            recommendationWarnings = []
            resultState = .failed(
                (error as? LocalizedError)?.errorDescription
                    ?? "候補を取得できませんでした。もう一度お試しください。"
            )
        }
    }
}
