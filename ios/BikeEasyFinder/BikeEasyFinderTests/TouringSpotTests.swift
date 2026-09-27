import XCTest
@testable import BikeEasyFinder

final class TouringSpotTests: XCTestCase {
    func testTotalMinutesIncludesOutboundStayAndReturn() {
        let spot = makeSpot(outbound: 40, stay: 25, returning: 45)

        XCTAssertEqual(spot.totalMinutes, 110)
    }

    func testFormattedDurationForMinutesOnly() {
        XCTAssertEqual(makeSpot(outbound: 20, stay: 15, returning: 20).formattedDuration, "55分")
    }

    func testFormattedDurationForWholeHours() {
        XCTAssertEqual(makeSpot(outbound: 45, stay: 30, returning: 45).formattedDuration, "2時間")
    }

    func testFormattedDurationForHoursAndMinutes() {
        XCTAssertEqual(makeSpot(outbound: 45, stay: 25, returning: 45).formattedDuration, "1時間55分")
    }

    func testEstimatedTotalIncludesSafetyBuffer() {
        let spot = makeSpot(outbound: 40, stay: 25, returning: 40)

        XCTAssertEqual(spot.estimatedTotalMinutes, 120)
        XCTAssertEqual(spot.formattedEstimatedDuration, "2時間")
    }

    private func makeSpot(outbound: Int, stay: Int, returning: Int) -> TouringSpot {
        TouringSpot(
            id: UUID(),
            name: "テスト地点",
            summary: "テスト用",
            latitude: 33.5,
            longitude: 130.4,
            tags: [.scenic],
            outboundMinutes: outbound,
            returnMinutes: returning,
            stayMinutes: stay,
            distanceKilometers: 10,
            recommendationReason: "テスト用"
        )
    }
}
