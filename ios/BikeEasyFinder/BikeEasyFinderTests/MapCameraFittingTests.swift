import CoreLocation
import XCTest
@testable import BikeEasyFinder

final class MapCameraFittingTests: XCTestCase {
    func testDestinationOnlyCentersOnSpot() {
        let destination = CLLocationCoordinate2D(latitude: 33.5902, longitude: 130.4017)

        let region = MapCameraFitting.region(destination: destination)

        XCTAssertEqual(region.center.latitude, destination.latitude, accuracy: 0.0001)
        XCTAssertEqual(region.center.longitude, destination.longitude, accuracy: 0.0001)
        XCTAssertEqual(region.span.latitudeDelta, 0.08, accuracy: 0.0001)
        XCTAssertEqual(region.span.longitudeDelta, 0.08, accuracy: 0.0001)
    }

    func testOriginAndDestinationFitBothPoints() {
        let destination = CLLocationCoordinate2D(latitude: 33.6407, longitude: 130.1962)
        let origin = CLLocationCoordinate2D(latitude: 33.5902, longitude: 130.4017)

        let region = MapCameraFitting.region(destination: destination, origin: origin)

        XCTAssertEqual(region.center.latitude, (destination.latitude + origin.latitude) / 2, accuracy: 0.0001)
        XCTAssertEqual(region.center.longitude, (destination.longitude + origin.longitude) / 2, accuracy: 0.0001)
        XCTAssertGreaterThanOrEqual(region.span.latitudeDelta, abs(destination.latitude - origin.latitude))
        XCTAssertGreaterThanOrEqual(region.span.longitudeDelta, abs(destination.longitude - origin.longitude))
    }
}
