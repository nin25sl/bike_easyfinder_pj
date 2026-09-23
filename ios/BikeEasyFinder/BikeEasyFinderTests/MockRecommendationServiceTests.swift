import CoreLocation
import XCTest
@testable import BikeEasyFinder

final class MockRecommendationServiceTests: XCTestCase {
    private let origin = CLLocationCoordinate2D(latitude: 33.5902, longitude: 130.4017)

    func testRecommendationsNeverExceedFiveItems() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 600, interests: [.any], allowsHighway: true)

        let results = try await service.recommendations(origin: origin, criteria: criteria)

        XCTAssertLessThanOrEqual(results.count, 5)
    }

    func testRecommendationsRespectAvailableTime() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 120, interests: [.any], allowsHighway: false)

        let results = try await service.recommendations(origin: origin, criteria: criteria)

        XCTAssertFalse(results.isEmpty)
        XCTAssertTrue(results.allSatisfy { $0.totalMinutes <= 120 })
    }

    func testRecommendationsRespectSelectedInterest() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 600, interests: [.cafe], allowsHighway: false)

        let results = try await service.recommendations(origin: origin, criteria: criteria)

        XCTAssertFalse(results.isEmpty)
        XCTAssertTrue(results.allSatisfy { $0.tags.contains(.cafe) })
    }

    func testNoMatchingConditionsReturnEmptyList() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 60, interests: [.onsen], allowsHighway: false)

        let results = try await service.recommendations(origin: origin, criteria: criteria)

        XCTAssertTrue(results.isEmpty)
    }
}

