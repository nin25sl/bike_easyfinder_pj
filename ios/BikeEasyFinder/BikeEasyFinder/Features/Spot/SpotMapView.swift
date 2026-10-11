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
            initialValue: .region(MapCameraFitting.region(destination: spot.coordinate, origin: origin))
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
        cameraPosition = .region(MapCameraFitting.region(destination: spot.coordinate, origin: origin))
    }
}

