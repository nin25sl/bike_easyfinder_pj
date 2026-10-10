import CoreLocation
import XCTest
@testable import BikeEasyFinder

@MainActor
final class SearchViewModelTests: XCTestCase {
    private let location = CLLocation(latitude: 33.5902, longitude: 130.4017)

    func testSelectingAnyClearsOtherInterests() {
        let viewModel = SearchViewModel()

        viewModel.toggleInterest(.cafe)
        viewModel.toggleInterest(.sea)
        viewModel.toggleInterest(.any)

        XCTAssertEqual(viewModel.criteria.interests, [.any])
    }

    func testRemovingLastSpecificInterestRestoresAny() {
        let viewModel = SearchViewModel()

        viewModel.toggleInterest(.cafe)
        viewModel.toggleInterest(.cafe)

        XCTAssertEqual(viewModel.criteria.interests, [.any])
    }

    func testSuccessfulSearchTransitionsToLoaded() async {
        let expected = Array<TouringSpot>.demoSpots[0]
        let viewModel = SearchViewModel(
            recommendationService: RecommendationServiceStub(
                result: .success(RecommendationResult(spots: [expected], warnings: ["範囲を拡張"]))
            )
        )

        await viewModel.search(from: location)

        XCTAssertEqual(viewModel.resultState, .loaded)
        XCTAssertEqual(viewModel.spots, [expected])
        XCTAssertEqual(viewModel.recommendationWarnings, ["範囲を拡張"])
    }

    func testEmptySearchTransitionsToEmptyAndClearsPreviousResults() async {
        let viewModel = SearchViewModel(
            recommendationService: RecommendationServiceStub(
                result: .success(RecommendationResult(spots: [], warnings: []))
            )
        )

        await viewModel.search(from: location)

        XCTAssertEqual(viewModel.resultState, .empty)
        XCTAssertTrue(viewModel.spots.isEmpty)
    }

    func testFailedSearchTransitionsToFailedAndDoesNotExposeStaleResults() async {
        let viewModel = SearchViewModel(
            recommendationService: RecommendationServiceStub(result: .failure(TestError.unavailable))
        )

        await viewModel.search(from: location)

        XCTAssertEqual(viewModel.resultState, .failed("テスト用の障害です。"))
        XCTAssertTrue(viewModel.spots.isEmpty)
    }
}

private struct RecommendationServiceStub: RecommendationProviding {
    let result: Result<RecommendationResult, Error>

    func recommendations(
        origin: CLLocationCoordinate2D,
        criteria: SearchCriteria,
        reactions: [UUID: SpotReaction]
    ) async throws -> RecommendationResult {
        try result.get()
    }
}

private enum TestError: LocalizedError {
    case unavailable

    var errorDescription: String? { "テスト用の障害です。" }
}
