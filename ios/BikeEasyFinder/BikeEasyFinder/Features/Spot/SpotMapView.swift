import MapKit
import SwiftUI

struct SpotMapView: View {
    let spot: TouringSpot
    let origin: CLLocationCoordinate2D?
    @State private var cameraPosition: MapCameraPosition

    init(spot: TouringSpot, origin: CLLocationCoordinate2D? = nil) {
        self.spot = spot
        self.origin = origin
        _cameraPosition = State(
            initialValue: .region(Self.region(spot: spot.coordinate, origin: origin))
        )
    }

    var body: some View {
        Map(position: $cameraPosition) {
            if let origin {
                Marker("現在地", systemImage: "location.fill", coordinate: origin)
                    .tint(.blue)
            }
            Marker(spot.name, coordinate: spot.coordinate)
        }
        .mapStyle(.standard)
        .accessibilityLabel(
            origin == nil
                ? "\(spot.name)の目的地地図"
                : "現在地と\(spot.name)の位置を示す地図"
        )
        .onChange(of: origin?.latitude) { _, _ in updateCamera() }
        .onChange(of: origin?.longitude) { _, _ in updateCamera() }
    }

    private func updateCamera() {
        cameraPosition = .region(Self.region(spot: spot.coordinate, origin: origin))
    }

    private static func region(
        spot: CLLocationCoordinate2D,
        origin: CLLocationCoordinate2D?
    ) -> MKCoordinateRegion {
        guard let origin else {
            return MKCoordinateRegion(
                center: spot,
                span: MKCoordinateSpan(latitudeDelta: 0.08, longitudeDelta: 0.08)
            )
        }
        let latitudeDelta = max(abs(spot.latitude - origin.latitude) * 1.5, 0.05)
        let longitudeDelta = max(abs(spot.longitude - origin.longitude) * 1.5, 0.05)
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(
                latitude: (spot.latitude + origin.latitude) / 2,
                longitude: (spot.longitude + origin.longitude) / 2
            ),
            span: MKCoordinateSpan(
                latitudeDelta: min(latitudeDelta, 180),
                longitudeDelta: min(longitudeDelta, 360)
            )
        )
    }
}

