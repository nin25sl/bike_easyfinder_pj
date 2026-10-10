import CoreLocation
import XCTest
@testable import BikeEasyFinder

final class MockRecommendationServiceTests: XCTestCase {
    private let origin = CLLocationCoordinate2D(latitude: 33.5902, longitude: 130.4017)

    func testRecommendationsNeverExceedFiveItems() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 240, interests: [.any], allowsHighway: true)

        let results = try await service.recommendations(origin: origin, criteria: criteria, reactions: [:])

        XCTAssertLessThanOrEqual(results.spots.count, 5)
    }

    func testRecommendationsRespectTargetTimeWindow() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 120, interests: [.any], allowsHighway: false)

        let results = try await service.recommendations(origin: origin, criteria: criteria, reactions: [:])

        XCTAssertFalse(results.spots.isEmpty)
        XCTAssertTrue(results.spots.allSatisfy { abs($0.estimatedTotalMinutes - 120) <= 15 })
        XCTAssertTrue(results.warnings.isEmpty)
    }

    func testRecommendationsRespectSelectedInterest() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 120, interests: [.cafe], allowsHighway: false)

        let results = try await service.recommendations(origin: origin, criteria: criteria, reactions: [:])

        XCTAssertFalse(results.spots.isEmpty)
        XCTAssertTrue(results.spots.allSatisfy { $0.tags.contains(.cafe) })
    }

    func testNoMatchingConditionsReturnEmptyList() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 60, interests: [.onsen], allowsHighway: false)

        let results = try await service.recommendations(origin: origin, criteria: criteria, reactions: [:])

        XCTAssertTrue(results.spots.isEmpty)
    }

    func testInvalidOriginIsRejected() async {
        let service = MockRecommendationService()
        let invalidOrigin = CLLocationCoordinate2D(latitude: 100, longitude: 130)

        do {
            _ = try await service.recommendations(origin: invalidOrigin, criteria: SearchCriteria(), reactions: [:])
            XCTFail("invalid origin must fail")
        } catch {
            XCTAssertEqual(error as? RecommendationError, .invalidOrigin)
        }
    }

    func testSameInputProducesSameOrder() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 240, interests: [.any], allowsHighway: true)

        let first = try await service.recommendations(origin: origin, criteria: criteria, reactions: [:])
        let second = try await service.recommendations(origin: origin, criteria: criteria, reactions: [:])

        XCTAssertEqual(first.spots.map(\.id), second.spots.map(\.id))
    }

    func testTimeWindowExpansionIsReported() async throws {
        let service = MockRecommendationService()
        let criteria = SearchCriteria(availableMinutes: 240, interests: [.any], allowsHighway: true)

        let result = try await service.recommendations(origin: origin, criteria: criteria, reactions: [:])

        XCTAssertFalse(result.spots.isEmpty)
        XCTAssertEqual(result.warnings.count, 1)
        XCTAssertTrue(result.warnings[0].contains("±45分"))
    }
}
